import hashlib
import json
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Body, Depends, FastAPI, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response

from app.config import settings
from app.database import get_db, async_session, wait_for_db
from app.models import Document, ExtractionJob, JobStatus, SavedSchema
from app.processing import process_job
from app.storage import save_file
from app.ws import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.skip_db_wait:
        await wait_for_db()
    yield


app = FastAPI(title="Struct My Data", lifespan=lifespan)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload(file: UploadFile, db: AsyncSession = Depends(get_db)):
    content = await file.read()
    if len(content) > settings.max_upload_size:
        raise HTTPException(status_code=413, detail="File exceeds maximum upload size")

    content_hash = hashlib.sha256(content).hexdigest()

    stmt = select(Document).where(Document.content_hash == content_hash)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        return {
            "id": str(existing.id),
            "filename": existing.filename,
            "content_type": existing.content_type,
            "file_size": existing.file_size,
            "storage_path": existing.storage_path,
            "created_at": existing.created_at.isoformat(),
            "updated_at": existing.updated_at.isoformat(),
        }

    storage_path = save_file(file.filename or "unnamed", content)

    doc = Document(
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        storage_path=storage_path,
        content_hash=content_hash,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "content_type": doc.content_type,
        "file_size": doc.file_size,
        "storage_path": doc.storage_path,
        "created_at": doc.created_at.isoformat(),
        "updated_at": doc.updated_at.isoformat(),
    }


@app.post("/extract")
async def create_extraction(
    background_tasks: BackgroundTasks,
    document_id: uuid.UUID = Body(...),
    pydantic_schema: str = Body(..., max_length=10000),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        compile(pydantic_schema, "<schema>", "exec")
    except SyntaxError as e:
        raise HTTPException(status_code=422, detail=f"Invalid Pydantic schema: {e}")

    job = ExtractionJob(document_id=document_id, pydantic_schema=pydantic_schema, upload_duration_ms=0)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    if background_tasks:
        background_tasks.add_task(process_job, job.id)

    return {
        "id": str(job.id),
        "status": job.status,
    }


@app.get("/jobs/{job_id}")
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    job = await db.get(ExtractionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "id": str(job.id),
        "document_id": str(job.document_id),
        "status": job.status,
        "output_data": job.output_data,
        "error_message": job.error_message,
        "input_tokens": job.input_tokens,
        "output_tokens": job.output_tokens,
        "upload_duration_ms": job.upload_duration_ms,
        "parsing_duration_ms": job.parsing_duration_ms,
        "llm_duration_ms": job.llm_duration_ms,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@app.get("/")
async def index():
    return FileResponse("app/templates/index.html")


@app.post("/ui/extract")
async def ui_extract(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    pydantic_schema: str = Form(..., max_length=10000),
    db: AsyncSession = Depends(get_db),
):
    t0 = time.monotonic_ns()
    content = await file.read()
    if len(content) > settings.max_upload_size:
        return HTMLResponse('<div style="color:red">File exceeds maximum upload size</div>')

    content_hash = hashlib.sha256(content).hexdigest()

    stmt = select(Document).where(Document.content_hash == content_hash)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if not doc:
        storage_path = save_file(file.filename or "unnamed", content)
        doc = Document(
            filename=file.filename or "unnamed",
            content_type=file.content_type or "application/octet-stream",
            file_size=len(content),
            storage_path=storage_path,
            content_hash=content_hash,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

    upload_duration_ms = (time.monotonic_ns() - t0) // 1_000_000

    try:
        compile(pydantic_schema, "<schema>", "exec")
    except SyntaxError as e:
        return HTMLResponse(f'<div style="color:red">Invalid Pydantic schema: {e}</div>')

    job = ExtractionJob(document_id=doc.id, pydantic_schema=pydantic_schema, upload_duration_ms=upload_duration_ms)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    if background_tasks:
        background_tasks.add_task(process_job, job.id)

    return HTMLResponse(f'<div hx-get="/ui/jobs/{job.id}" hx-trigger="every 2s">⏳ Processing...</div>')


def _render_output(data):
    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        keys = sorted({k for d in data for k in d})
        rows = "".join(
            "<tr>" + "".join(f"<td>{_cell(d.get(k))}</td>" for k in keys) + "</tr>"
            for d in data
        )
        headers = "".join(f"<th>{k}</th>" for k in keys)
        return f"<table><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>"
    if isinstance(data, dict):
        rows = "".join(f"<tr><td>{k}</td><td>{_cell(v)}</td></tr>" for k, v in data.items())
        return f"<table><tbody>{rows}</tbody></table>"
    return f"<pre>{json.dumps(data, indent=2)}</pre>"


def _cell(value):
    if isinstance(value, (dict, list)):
        return f"<pre>{json.dumps(value, indent=2)}</pre>"
    return str(value)


def _job_stats_html(job) -> str:
    parts = []

    if job.input_tokens is not None:
        parts.append(f"Tokens: {job.input_tokens} in / {job.output_tokens} out")

    timing_parts = []
    if job.upload_duration_ms is not None:
        timing_parts.append(f"upload {_fmt_ms(job.upload_duration_ms)}")
    if job.parsing_duration_ms is not None:
        timing_parts.append(f"parse {_fmt_ms(job.parsing_duration_ms)}")
    if job.llm_duration_ms is not None:
        timing_parts.append(f"llm {_fmt_ms(job.llm_duration_ms)}")
    if timing_parts:
        parts.append(" | ".join(timing_parts))

    if not parts:
        return ""

    return f'<div style="font-size:0.85rem;color:#666;margin-bottom:0.5rem">{" | ".join(parts)}</div>'


def _fmt_ms(ms: int) -> str:
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms / 1000:.1f}s"


@app.get("/ui/jobs/{job_id}")
async def ui_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    job = await db.get(ExtractionJob, job_id)
    if not job:
        return HTMLResponse("<div>Job not found</div>")

    stats = _job_stats_html(job)
    if job.status in (JobStatus.pending, JobStatus.running):
        return HTMLResponse(f'<div hx-get="/ui/jobs/{job.id}" hx-trigger="every 2s">⏳ Processing...</div>')
    elif job.status == JobStatus.completed:
        return HTMLResponse(stats + _render_output(job.output_data))
    else:
        return HTMLResponse(stats + f'<div style="color:red">Error: {job.error_message}</div>')


@app.post("/ui/jobs/{job_id}/retry")
async def ui_job_retry(
    job_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(ExtractionJob, job_id)
    if not job:
        return HTMLResponse("<div>Job not found</div>")

    st = job.status
    if hasattr(st, "value"):
        st = st.value
    if st not in ("pending", "failed"):
        return HTMLResponse("<div>Can only retry failed or pending jobs</div>")

    job.status = JobStatus.pending
    job.error_message = None
    job.completed_at = None
    await db.commit()

    background_tasks.add_task(process_job, job.id)
    return HTMLResponse(f'<div hx-get="/ui/jobs/{job.id}" hx-trigger="every 2s">⏳ Retrying...</div>')


@app.get("/ui/jobs")
async def ui_jobs(
    offset: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    total_q = select(func.count()).select_from(ExtractionJob)
    total = (await db.execute(total_q)).scalar()

    q = (
        select(ExtractionJob, Document.filename)
        .join(Document, ExtractionJob.document_id == Document.id)
        .order_by(ExtractionJob.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(q)).all()

    def _status_badge(status) -> str:
        if status in (JobStatus.pending, JobStatus.running):
            return "⏳"
        if status == JobStatus.completed:
            return "✅"
        return "❌"

    table_rows = ""
    for job, filename in rows:
        st = job.status
        if hasattr(st, "value"):
            st = st.value
        badge = _status_badge(st)
        fn = (filename[:35] + "…") if len(filename) > 36 else filename
        ts = job.created_at.strftime("%b %d %H:%M")
        view_btn = f'<button hx-get="/ui/jobs/{job.id}" hx-target="#result">View</button>'

        if st in ("pending", "failed"):
            retry = f'<button hx-post="/ui/jobs/{job.id}/retry" hx-target="#result">Retry</button>'
        else:
            retry = ""

        table_rows += (
            f"<tr>"
            f"<td>{badge}</td>"
            f"<td>{fn}</td>"
            f"<td>{ts}</td>"
            f"<td>{view_btn} {retry}</td>"
            f"</tr>"
        )

    prev_disabled = "disabled" if offset == 0 else ""
    next_disabled = "disabled" if offset + limit >= total else ""
    prev_offset = max(0, offset - limit)
    next_offset = offset + limit
    page = (offset // limit) + 1
    pages = max(1, (total + limit - 1) // limit)

    pagination = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:0.5rem;font-size:0.875rem">
      <button hx-get="/ui/jobs?offset={prev_offset}&limit={limit}" hx-target="#tab-history" {prev_disabled}>← Prev</button>
      <span>Page {page} of {pages}</span>
      <button hx-get="/ui/jobs?offset={next_offset}&limit={limit}" hx-target="#tab-history" {next_disabled}>Next →</button>
    </div>"""

    html = f"""
    <table>
      <thead><tr><th></th><th>File</th><th>Date</th><th></th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
    {pagination}"""

    return HTMLResponse(html)


@app.get("/schemas")
async def list_schemas(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SavedSchema).order_by(SavedSchema.created_at.desc()))
    schemas = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "pydantic_schema": s.pydantic_schema,
            "created_at": s.created_at.isoformat(),
        }
        for s in schemas
    ]


@app.post("/schemas")
async def create_schema(body: dict = Body(...), db: AsyncSession = Depends(get_db)):
    name = body.get("name", "").strip()
    pydantic_schema = body.get("pydantic_schema", "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name is required")
    if not pydantic_schema:
        raise HTTPException(status_code=422, detail="Schema code is required")
    if len(pydantic_schema) > 10000:
        raise HTTPException(status_code=422, detail="Schema code too long")

    schema = SavedSchema(name=name, pydantic_schema=pydantic_schema)
    db.add(schema)
    await db.commit()
    await db.refresh(schema)
    return {"id": str(schema.id), "name": schema.name}


@app.get("/schemas/{schema_id}")
async def get_schema(schema_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    schema = await db.get(SavedSchema, schema_id)
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    return {
        "id": str(schema.id),
        "name": schema.name,
        "pydantic_schema": schema.pydantic_schema,
        "created_at": schema.created_at.isoformat(),
        "updated_at": schema.updated_at.isoformat(),
    }


@app.put("/schemas/{schema_id}")
async def update_schema(schema_id: uuid.UUID, body: dict = Body(...), db: AsyncSession = Depends(get_db)):
    schema = await db.get(SavedSchema, schema_id)
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    if "name" in body:
        name = body["name"].strip()
        if not name:
            raise HTTPException(status_code=422, detail="Name is required")
        schema.name = name
    if "pydantic_schema" in body:
        pydantic_schema = body["pydantic_schema"].strip()
        if not pydantic_schema:
            raise HTTPException(status_code=422, detail="Schema code is required")
        if len(pydantic_schema) > 10000:
            raise HTTPException(status_code=422, detail="Schema code too long")
        schema.pydantic_schema = pydantic_schema
    await db.commit()
    await db.refresh(schema)
    return {"id": str(schema.id), "name": schema.name}


@app.delete("/schemas/{schema_id}")
async def delete_schema(schema_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    schema = await db.get(SavedSchema, schema_id)
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    await db.delete(schema)
    await db.commit()
    return {"ok": True}


@app.get("/schemas/{schema_id}/export")
async def export_schema(schema_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    schema = await db.get(SavedSchema, schema_id)
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    content = (
        f"# name: {schema.name}\n"
        f"# exported: {schema.created_at.isoformat()}\n"
        f"# structmydata-schema v1\n"
        f"\n"
        f"{schema.pydantic_schema}"
    )
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{schema.name}.py"'},
    )


@app.post("/schemas/import")
async def import_schema(file: UploadFile, db: AsyncSession = Depends(get_db)):
    content = await file.read()
    if len(content) > 10000:
        raise HTTPException(status_code=422, detail="File too large")

    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="Invalid UTF-8 file")

    if decoded.lstrip().startswith("{"):
        try:
            data = json.loads(decoded)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="Invalid JSON file")
        name = data.get("name", "").strip()
        pydantic_schema = data.get("pydantic_schema", "").strip()
    else:
        name = file.filename.replace(".py", "").replace(".txt", "").strip() if file.filename else "Untitled"
        pydantic_schema = decoded

    if not name:
        name = "Imported Schema"
    if not pydantic_schema:
        raise HTTPException(status_code=422, detail="No schema code found in file")

    schema = SavedSchema(name=name, pydantic_schema=pydantic_schema)
    db.add(schema)
    await db.commit()
    await db.refresh(schema)
    return {"id": str(schema.id), "name": schema.name}


@app.websocket("/ws/jobs/{job_id}")
async def websocket_endpoint(ws: WebSocket, job_id: uuid.UUID):
    await manager.connect(job_id, ws)
    try:
        async with async_session() as db:
            job = await db.get(ExtractionJob, job_id)
            if job:
                await ws.send_json({
                    "event": "status",
                    "job_id": str(job.id),
                    "status": job.status,
                    "output_data": job.output_data,
                    "error_message": job.error_message,
                })
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(job_id, ws)
