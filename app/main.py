import hashlib
import json
import uuid
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Body, Depends, FastAPI, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import FileResponse, HTMLResponse, JSONResponse

from app.config import settings
from app.database import get_db, async_session, wait_for_db
from app.models import Document, ExtractionJob, JobStatus
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

    job = ExtractionJob(document_id=document_id, pydantic_schema=pydantic_schema)
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

    try:
        compile(pydantic_schema, "<schema>", "exec")
    except SyntaxError as e:
        return HTMLResponse(f'<div style="color:red">Invalid Pydantic schema: {e}</div>')

    job = ExtractionJob(document_id=doc.id, pydantic_schema=pydantic_schema)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    if background_tasks:
        background_tasks.add_task(process_job, job.id)

    return HTMLResponse(f'<div hx-get="/ui/jobs/{job.id}" hx-trigger="every 2s">⏳ Processing...</div>')


@app.get("/ui/jobs/{job_id}")
async def ui_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    job = await db.get(ExtractionJob, job_id)
    if not job:
        return HTMLResponse("<div>Job not found</div>")

    if job.status in (JobStatus.pending, JobStatus.running):
        return HTMLResponse(f'<div hx-get="/ui/jobs/{job.id}" hx-trigger="every 2s">⏳ Processing...</div>')
    elif job.status == JobStatus.completed:
        return HTMLResponse(f"<pre>{json.dumps(job.output_data, indent=2)}</pre>")
    else:
        return HTMLResponse(f'<div style="color:red">Error: {job.error_message}</div>')


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
