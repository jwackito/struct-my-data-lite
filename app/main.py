import hashlib
import json
import time
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Body, Depends, FastAPI, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

from app.auth import create_jwt, decode_jwt, get_admin_user, get_current_user, hash_password, verify_password
from app.config import settings
from app.connections import (
    delete_connection,
    get_connection,
    list_connections,
    set_connection,
    test_connection,
)
from app.database import get_db, async_session, wait_for_db
from app.models import ApiToken, Batch, Document, ExtractionJob, JobStatus, SavedSchema, User, UserRole
from app.pricing import calculate_cost
from app.processing import process_job
from sqlalchemy import cast, Date
from app.providers import list_all_models
from app.schema_parser import parse_schema
from app.storage import save_file
from app.ws import manager
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


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


@app.post("/auth/register")
async def auth_register(body: dict, db: AsyncSession = Depends(get_db)):
    if not settings.allow_registration:
        raise HTTPException(status_code=403, detail="Registration is closed")

    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    display_name = (body.get("display_name") or "").strip()

    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Valid email is required")
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=422, detail="Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name or email.split("@")[0],
        role="user",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_jwt(str(user.id), user.role)
    resp = JSONResponse({"token": token, "user": {"id": str(user.id), "email": user.email, "display_name": user.display_name, "role": user.role}})
    resp.set_cookie(key="token", value=token, httponly=True, max_age=settings.jwt_expiry_hours * 3600)
    return resp


@app.post("/auth/login")
async def auth_login(body: dict, db: AsyncSession = Depends(get_db)):
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_jwt(str(user.id), user.role)
    resp = JSONResponse({"token": token, "user": {"id": str(user.id), "email": user.email, "display_name": user.display_name, "role": user.role}})
    resp.set_cookie(key="token", value=token, httponly=True, max_age=settings.jwt_expiry_hours * 3600)
    return resp


@app.post("/auth/logout")
async def auth_logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("token")
    return resp


@app.get("/auth/me")
async def auth_me(user: User = Depends(get_current_user)):
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
    }


@app.get("/login")
async def login_page():
    return FileResponse("app/templates/login.html")


@app.get("/register")
async def register_page():
    if not settings.allow_registration:
        return HTMLResponse('<html><body style="font-family:sans-serif;text-align:center;padding:4rem"><h1>Registration is closed</h1><p><a href="/login">Back to login</a></p></body></html>', status_code=403)
    return FileResponse("app/templates/register.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/models")
async def models(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return {"models": await list_all_models(db, user=user)}


@app.get("/api/keys")
async def api_list_keys(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return {"keys": await list_connections(db, user=user)}


@app.post("/api/keys")
async def api_create_key(body: dict, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    name = body.get("name", "").strip()
    provider = body.get("provider", "")
    config = body.get("config", {})
    secrets = body.get("secrets", {})

    if not name:
        raise HTTPException(status_code=422, detail="Name is required")
    if provider not in ("openai", "gemini", "ollama"):
        raise HTTPException(status_code=422, detail=f"Unknown provider: {provider}")

    test_result = await test_connection(name, {**config, **secrets}, provider, db)
    if not test_result.get("ok"):
        raise HTTPException(status_code=422, detail=f"Connection test failed: {test_result.get('error', 'unknown error')}")

    try:
        conn = await set_connection(name, provider, config, secrets, db, user=user)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return conn


@app.put("/api/keys/{name}")
async def api_update_key(name: str, body: dict, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    provider = body.get("provider", "")
    config = body.get("config", {})
    secrets = body.get("secrets", {})

    if provider not in ("openai", "gemini", "ollama"):
        raise HTTPException(status_code=422, detail=f"Unknown provider: {provider}")

    try:
        conn = await set_connection(name, provider, config, secrets, db, user=user)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return conn


@app.delete("/api/keys/{name}")
async def api_delete_key(name: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        deleted = await delete_connection(name, db, user=user)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"ok": True}


@app.post("/api/tokens")
async def api_create_token(body: dict, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.auth import generate_api_token

    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name is required")

    raw, token_hash, prefix = generate_api_token()
    expires_at = None
    if body.get("expires_at"):
        try:
            expires_at = datetime.fromisoformat(body["expires_at"])
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="Invalid expires_at format")

    tok = ApiToken(user_id=user.id, name=name, token_hash=token_hash, prefix=prefix, expires_at=expires_at)
    db.add(tok)
    await db.commit()
    await db.refresh(tok)

    return {
        "id": str(tok.id),
        "name": tok.name,
        "token": raw,
        "prefix": tok.prefix,
        "expires_at": tok.expires_at.isoformat() if tok.expires_at else None,
        "created_at": tok.created_at.isoformat(),
    }


@app.get("/api/tokens")
async def api_list_tokens(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.created_at.desc())
    )
    tokens = result.scalars().all()
    return {
        "tokens": [
            {
                "id": str(t.id),
                "name": t.name,
                "prefix": t.prefix,
                "is_active": t.is_active,
                "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
                "created_at": t.created_at.isoformat(),
            }
            for t in tokens
        ]
    }


@app.delete("/api/tokens/{token_id}")
async def api_revoke_token(token_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == user.id)
    )
    tok = result.scalar_one_or_none()
    if not tok:
        raise HTTPException(status_code=404, detail="Token not found")
    tok.is_active = False
    await db.commit()
    return {"ok": True}


@app.post("/api/batches/estimate")
async def api_batch_estimate(body: dict, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.pricing import calculate_cost

    file_sizes = body.get("file_sizes", [])
    model_id = body.get("model_id", "")
    if not file_sizes:
        raise HTTPException(status_code=422, detail="file_sizes is required")
    if len(file_sizes) > settings.max_batch_size:
        raise HTTPException(status_code=422, detail=f"Batch exceeds max size of {settings.max_batch_size}")

    provider_type, connection_name, model_name = _parse_model_id(model_id)
    estimated_tokens = sum(size / 4 for size in file_sizes)
    estimated_cost = calculate_cost(provider_type, model_name, estimated_tokens, estimated_tokens / 4)

    return {
        "documents": len(file_sizes),
        "estimated_tokens": int(estimated_tokens),
        "estimated_cost": round(estimated_cost, 6),
        "model": model_name,
    }


@app.post("/api/batches")
async def api_create_batch(body: dict, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    document_ids = body.get("document_ids", [])
    pydantic_schema = body.get("pydantic_schema", "")
    model_id = body.get("model_id", "")
    name = (body.get("name") or "").strip() or f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    if not document_ids:
        raise HTTPException(status_code=422, detail="document_ids is required")
    if len(document_ids) > settings.max_batch_size:
        raise HTTPException(status_code=422, detail=f"Batch exceeds max size of {settings.max_batch_size}")
    if not pydantic_schema:
        raise HTTPException(status_code=422, detail="pydantic_schema is required")
    try:
        compile(pydantic_schema, "<schema>", "exec")
    except SyntaxError as e:
        raise HTTPException(status_code=422, detail=f"Invalid Pydantic schema: {e}")

    batch = Batch(user_id=user.id, name=name)
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    provider_type, connection_name, model_name = _parse_model_id(model_id)
    job_ids = []
    for doc_id in document_ids:
        doc = await db.get(Document, doc_id)
        if not doc:
            continue
        job = ExtractionJob(
            user_id=user.id,
            batch_id=batch.id,
            document_id=doc.id,
            pydantic_schema=pydantic_schema,
            upload_duration_ms=0,
            connection_name=connection_name,
            provider_type=provider_type,
            model_name=model_name,
        )
        db.add(job)
        await db.flush()
        job_ids.append(job.id)
    await db.commit()

    for job_id in job_ids:
        background_tasks.add_task(process_job, job_id)

    return {"batch_id": str(batch.id), "job_ids": [str(j) for j in job_ids], "name": batch.name}


@app.get("/api/batches")
async def api_list_batches(offset: int = 0, limit: int = 20, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func as sa_func

    total_q = select(sa_func.count()).select_from(Batch).where(Batch.user_id == user.id)
    total = (await db.execute(total_q)).scalar()

    result = await db.execute(
        select(Batch).where(Batch.user_id == user.id).order_by(Batch.created_at.desc()).offset(offset).limit(limit)
    )
    batches = result.scalars().all()

    items = []
    for b in batches:
        counts = await db.execute(
            select(ExtractionJob.status, sa_func.count()).where(ExtractionJob.batch_id == b.id).group_by(ExtractionJob.status)
        )
        status_counts = {st.value if hasattr(st, "value") else st: cnt for st, cnt in counts.all()}
        items.append({
            "id": str(b.id),
            "name": b.name,
            "created_at": b.created_at.isoformat(),
            "completed_at": b.completed_at.isoformat() if b.completed_at else None,
            "total": sum(status_counts.values()),
            "completed": status_counts.get("completed", 0),
            "failed": status_counts.get("failed", 0),
            "running": status_counts.get("running", 0),
            "pending": status_counts.get("pending", 0),
        })

    return {"batches": items, "total": total}


@app.get("/api/batches/{batch_id}")
async def api_batch_progress(batch_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    batch = await db.get(Batch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(status_code=404, detail="Batch not found")

    result = await db.execute(
        select(ExtractionJob, Document.filename)
        .join(Document, ExtractionJob.document_id == Document.id)
        .where(ExtractionJob.batch_id == batch.id)
        .order_by(ExtractionJob.created_at)
    )
    rows = result.all()

    jobs = []
    for job, filename in rows:
        st = job.status.value if hasattr(job.status, "value") else job.status
        jobs.append({
            "id": str(job.id),
            "filename": filename,
            "status": st,
            "error_message": job.error_message,
            "model_name": job.model_name,
        })

    completed = sum(1 for j in jobs if j["status"] == "completed")
    failed = sum(1 for j in jobs if j["status"] == "failed")
    running = sum(1 for j in jobs if j["status"] == "running")
    pending = sum(1 for j in jobs if j["status"] == "pending")

    return {
        "id": str(batch.id),
        "name": batch.name,
        "created_at": batch.created_at.isoformat(),
        "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
        "total": len(jobs),
        "completed": completed,
        "failed": failed,
        "running": running,
        "pending": pending,
        "jobs": jobs,
    }


@app.post("/api/batches/{batch_id}/retry-failed")
async def api_batch_retry_failed(batch_id: uuid.UUID, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    batch = await db.get(Batch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(status_code=404, detail="Batch not found")

    result = await db.execute(
        select(ExtractionJob).where(ExtractionJob.batch_id == batch.id, ExtractionJob.status == JobStatus.failed)
    )
    failed_jobs = result.scalars().all()

    retried = []
    for job in failed_jobs:
        job.status = JobStatus.pending
        job.error_message = None
        job.completed_at = None
        job.input_tokens = None
        job.output_tokens = None
        retried.append(job.id)

    batch.completed_at = None
    await db.commit()

    for job_id in retried:
        background_tasks.add_task(process_job, job_id)

    return {"ok": True, "retried": [str(j) for j in retried]}


@app.post("/api/batches/{batch_id}/cancel")
async def api_batch_cancel(batch_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    batch = await db.get(Batch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(status_code=404, detail="Batch not found")

    result = await db.execute(
        select(ExtractionJob).where(
            ExtractionJob.batch_id == batch.id,
            ExtractionJob.status.in_([JobStatus.pending, JobStatus.running]),
        )
    )
    pending_jobs = result.scalars().all()

    cancelled = []
    for job in pending_jobs:
        job.status = JobStatus.failed
        job.error_message = "Cancelled by user"
        job.completed_at = datetime.now()
        cancelled.append(job.id)

    await db.commit()
    return {"ok": True, "cancelled": [str(j) for j in cancelled]}


@app.get("/api/batches/{batch_id}/results")
async def api_batch_results(batch_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    batch = await db.get(Batch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(status_code=404, detail="Batch not found")

    result = await db.execute(
        select(ExtractionJob, Document.filename)
        .join(Document, ExtractionJob.document_id == Document.id)
        .where(ExtractionJob.batch_id == batch.id)
        .order_by(ExtractionJob.created_at)
    )
    rows = result.all()

    results = []
    for job, filename in rows:
        st = job.status.value if hasattr(job.status, "value") else job.status
        results.append({
            "job_id": str(job.id),
            "filename": filename,
            "status": st,
            "output_data": job.output_data,
            "error_message": job.error_message,
            "model_name": job.model_name,
        })

    content = json.dumps({"batch_id": str(batch.id), "name": batch.name, "results": results}, indent=2, ensure_ascii=False)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="batch-{batch.id}.json"'},
    )


@app.get("/api/usage")
async def api_usage(
    from_date: str = "",
    to_date: str = "",
    group: str = "none",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(ExtractionJob).where(
        ExtractionJob.user_id == user.id,
        ExtractionJob.status == JobStatus.completed,
        ExtractionJob.input_tokens.isnot(None),
    )
    from datetime import date as _dt, timedelta as _td

    if from_date:
        q = q.where(ExtractionJob.created_at >= _dt.fromisoformat(from_date))
    if to_date:
        q = q.where(ExtractionJob.created_at < _dt.fromisoformat(to_date) + _td(days=1))

    rows = (await db.execute(q)).scalars().all()
    total_jobs = len(rows)
    total_input = sum(r.input_tokens or 0 for r in rows)
    total_output = sum(r.output_tokens or 0 for r in rows)
    total_cost = sum(calculate_cost(r.provider_type or "", r.model_name or "", r.input_tokens or 0, r.output_tokens or 0) for r in rows)

    result = {
        "total_jobs": total_jobs,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cost": round(total_cost, 6),
    }

    if group == "day":
        from collections import defaultdict
        days = defaultdict(lambda: {"jobs": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0})
        for r in rows:
            day = r.created_at.strftime("%Y-%m-%d") if r.created_at else "unknown"
            days[day]["jobs"] += 1
            days[day]["input_tokens"] += r.input_tokens or 0
            days[day]["output_tokens"] += r.output_tokens or 0
            days[day]["cost"] += calculate_cost(r.provider_type or "", r.model_name or "", r.input_tokens or 0, r.output_tokens or 0)
        result["breakdown"] = [{"date": d, **v} for d, v in sorted(days.items())]
    elif group == "model":
        from collections import defaultdict
        models = defaultdict(lambda: {"jobs": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0})
        for r in rows:
            m = r.model_name or "unknown"
            models[m]["jobs"] += 1
            models[m]["input_tokens"] += r.input_tokens or 0
            models[m]["output_tokens"] += r.output_tokens or 0
            models[m]["cost"] += calculate_cost(r.provider_type or "", r.model_name or "", r.input_tokens or 0, r.output_tokens or 0)
        result["breakdown"] = [{"model": m, **v} for m, v in sorted(models.items())]

    return result


@app.get("/admin/usage")
async def admin_usage_page(admin: User = Depends(get_admin_user)):
    return FileResponse("app/templates/admin_usage.html")


@app.get("/admin/usage/data")
async def admin_usage(
    from_date: str = "",
    to_date: str = "",
    user_filter: str = "",
    group: str = "none",
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(ExtractionJob).where(
        ExtractionJob.status == JobStatus.completed,
        ExtractionJob.input_tokens.isnot(None),
    )
    from datetime import date as _dt, timedelta as _td

    if from_date:
        q = q.where(ExtractionJob.created_at >= _dt.fromisoformat(from_date))
    if to_date:
        q = q.where(ExtractionJob.created_at < _dt.fromisoformat(to_date) + _td(days=1))
    if user_filter:
        q = q.where(ExtractionJob.user_id == user_filter)

    rows = (await db.execute(q)).scalars().all()
    total_jobs = len(rows)
    total_input = sum(r.input_tokens or 0 for r in rows)
    total_output = sum(r.output_tokens or 0 for r in rows)
    total_cost = sum(calculate_cost(r.provider_type or "", r.model_name or "", r.input_tokens or 0, r.output_tokens or 0) for r in rows)

    from collections import defaultdict
    per_user = defaultdict(lambda: {"jobs": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0})
    for r in rows:
        uid = str(r.user_id) if r.user_id else "unknown"
        per_user[uid]["jobs"] += 1
        per_user[uid]["input_tokens"] += r.input_tokens or 0
        per_user[uid]["output_tokens"] += r.output_tokens or 0
        per_user[uid]["cost"] += calculate_cost(r.provider_type or "", r.model_name or "", r.input_tokens or 0, r.output_tokens or 0)

    total_users = len(per_user)
    user_ids = [uid for uid in per_user.keys() if uid != "unknown"]
    user_emails = {}
    if user_ids:
        from sqlalchemy import or_
        user_rows = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        user_emails = {str(u.id): u.email for u in user_rows}
    per_user_list = [{"user_id": uid, "email": user_emails.get(uid, uid), **v} for uid, v in sorted(per_user.items(), key=lambda x: -x[1]["jobs"])]

    result = {
        "total_users": total_users,
        "total_jobs": total_jobs,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cost": round(total_cost, 6),
        "per_user": per_user_list,
    }

    if group == "day":
        days = defaultdict(lambda: {"jobs": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0})
        for r in rows:
            day = r.created_at.strftime("%Y-%m-%d") if r.created_at else "unknown"
            days[day]["jobs"] += 1
            days[day]["input_tokens"] += r.input_tokens or 0
            days[day]["output_tokens"] += r.output_tokens or 0
            days[day]["cost"] += calculate_cost(r.provider_type or "", r.model_name or "", r.input_tokens or 0, r.output_tokens or 0)
        result["breakdown"] = [{"date": d, **v} for d, v in sorted(days.items())]

    return result


@app.get("/providers/connections")
async def get_connections(admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    return {"connections": await list_connections(db)}


@app.get("/providers/connections/{name}")
async def get_connection_endpoint(name: str, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    conn = await get_connection(name, db)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return conn


@app.put("/providers/connections/{name}")
async def put_connection(name: str, body: dict, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    provider = body.get("provider", "")
    config = body.get("config", {})
    secrets = body.get("secrets", {})

    if not provider:
        raise HTTPException(status_code=422, detail="provider is required")
    if provider not in ("ollama", "openai", "gemini"):
        raise HTTPException(status_code=422, detail=f"Unknown provider: {provider}")

    test_result = await test_connection(name, {**config, **secrets}, provider, db)
    if not test_result.get("ok"):
        raise HTTPException(status_code=422, detail=f"Connection test failed: {test_result.get('error', 'unknown error')}")

    try:
        conn = await set_connection(name, provider, config, secrets, db)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return conn


@app.delete("/providers/connections/{name}")
async def delete_connection_endpoint(name: str, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    try:
        deleted = await delete_connection(name, db)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"ok": True}


@app.post("/providers/connections/{name}/test")
async def test_connection_endpoint(name: str, body: dict, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    config = body.get("config", {})
    secrets = body.get("secrets", {})
    provider = body.get("provider", "")
    if not provider:
        raise HTTPException(status_code=422, detail="provider is required")
    result = await test_connection(name, {**config, **secrets}, provider, db)
    return result


@app.post("/upload")
async def upload(file: UploadFile, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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


def _parse_model_id(model_id: str) -> tuple[str, str, str | None]:
    if not model_id:
        return "ollama", "ollama", settings.ollama_model
    parts = model_id.split("/", 2)
    if len(parts) == 3:
        provider_type, connection_name, model_name = parts
        return provider_type, connection_name, model_name
    if len(parts) == 2:
        provider_type, model_name = parts
        return provider_type, provider_type, model_name
    return model_id, model_id, None


@app.post("/extract")
async def create_extraction(
    background_tasks: BackgroundTasks,
    document_id: uuid.UUID = Body(...),
    pydantic_schema: str = Body(..., max_length=10000),
    model_id: str = Body(""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        compile(pydantic_schema, "<schema>", "exec")
    except SyntaxError as e:
        raise HTTPException(status_code=422, detail=f"Invalid Pydantic schema: {e}")

    provider_type, connection_name, model_name = _parse_model_id(model_id)
    job = ExtractionJob(
        user_id=user.id,
        document_id=document_id,
        pydantic_schema=pydantic_schema,
        upload_duration_ms=0,
        connection_name=connection_name,
        provider_type=provider_type,
        model_name=model_name,
    )
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
async def get_job(job_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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
        "connection_name": job.connection_name,
        "provider_type": job.provider_type,
        "model_name": job.model_name,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@app.get("/")
async def index(request: Request):
    token = request.cookies.get("token")
    if not token or not decode_jwt(token):
        return RedirectResponse(url="/login")
    return FileResponse("app/templates/index.html")


@app.get("/ui/settings")
async def ui_settings(user: User = Depends(get_current_user)):
    return FileResponse("app/templates/settings.html")


@app.get("/usage")
async def usage_page(user: User = Depends(get_current_user)):
    return FileResponse("app/templates/usage.html")


@app.get("/ui/batches")
async def ui_batches_page(user: User = Depends(get_current_user)):
    return FileResponse("app/templates/batches.html")


@app.get("/ui/batches/{batch_id}")
async def ui_batch_page(batch_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    batch = await db.get(Batch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(status_code=404, detail="Batch not found")
    return FileResponse("app/templates/batch.html")


@app.post("/ui/extract")
async def ui_extract(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    pydantic_schema: str = Form(..., max_length=10000),
    model_id: str = Form(""),
    user: User = Depends(get_current_user),
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
            user_id=user.id,
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

    provider_type, connection_name, model_name = _parse_model_id(model_id)
    job = ExtractionJob(
        user_id=user.id,
        document_id=doc.id,
        pydantic_schema=pydantic_schema,
        upload_duration_ms=upload_duration_ms,
        connection_name=connection_name,
        provider_type=provider_type,
        model_name=model_name,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    if background_tasks:
        background_tasks.add_task(process_job, job.id)

    return HTMLResponse(f'<div hx-get="/ui/jobs/{job.id}" hx-trigger="every 2s" hx-swap="outerHTML">⏳ Processing...</div>')


@app.post("/ui/batch-extract")
async def ui_batch_extract(
    background_tasks: BackgroundTasks,
    file: list[UploadFile],
    pydantic_schema: str = Form(..., max_length=10000),
    model_id: str = Form(""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if len(file) > settings.max_batch_size:
        return HTMLResponse(f'<div style="color:red">Batch exceeds max size of {settings.max_batch_size}</div>')

    try:
        compile(pydantic_schema, "<schema>", "exec")
    except SyntaxError as e:
        return HTMLResponse(f'<div style="color:red">Invalid Pydantic schema: {e}</div>')

    batch = Batch(user_id=user.id, name=f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    provider_type, connection_name, model_name = _parse_model_id(model_id)
    job_ids = []
    for up in file:
        content = await up.read()
        if len(content) > settings.max_upload_size:
            continue
        content_hash = hashlib.sha256(content).hexdigest()
        result = await db.execute(select(Document).where(Document.content_hash == content_hash))
        doc = result.scalar_one_or_none()
        if not doc:
            storage_path = save_file(up.filename or "unnamed", content)
            doc = Document(
                user_id=user.id,
                filename=up.filename or "unnamed",
                content_type=up.content_type or "application/octet-stream",
                file_size=len(content),
                storage_path=storage_path,
                content_hash=content_hash,
            )
            db.add(doc)
            await db.flush()
        job = ExtractionJob(
            user_id=user.id,
            batch_id=batch.id,
            document_id=doc.id,
            pydantic_schema=pydantic_schema,
            upload_duration_ms=0,
            connection_name=connection_name,
            provider_type=provider_type,
            model_name=model_name,
        )
        db.add(job)
        await db.flush()
        job_ids.append(job.id)
    await db.commit()

    for job_id in job_ids:
        background_tasks.add_task(process_job, job_id)

    resp = HTMLResponse('<div>Batch started</div>')
    resp.headers["HX-Redirect"] = f"/ui/batches/{batch.id}"
    return resp


def _render_output(data):
    return f"<pre>{json.dumps(data, indent=2, ensure_ascii=False)}</pre>"


def _job_stats_html(job) -> str:
    from app.pricing import calculate_cost

    cards = []

    if job.input_tokens is not None:
        cards.append(f"""<div class="stat-card">
          <div class="stat-label">Tokens <span class="stat-info" title="Tokens sent to and received from the AI model">&#9432;</span></div>
          <div class="stat-value">{job.input_tokens} in / {job.output_tokens} out</div>
        </div>""")
        cost = calculate_cost(job.provider_type or "", job.model_name or "", job.input_tokens, job.output_tokens)
        if cost > 0:
            cards.append(f"""<div class="stat-card">
              <div class="stat-label">Cost <span class="stat-info" title="Estimated cost in USD based on model pricing">&#9432;</span></div>
              <div class="stat-value">${cost:.6f}</div>
            </div>""")

    timing = [
        ("Upload", job.upload_duration_ms, "Time to upload and store the file"),
        ("Parse", job.parsing_duration_ms, "Time to extract text from the document"),
        ("LLM", job.llm_duration_ms, "Time the AI model took to generate the result"),
    ]
    for label, ms, desc in timing:
        if ms is not None:
            cards.append(f"""<div class="stat-card">
              <div class="stat-label">{label} <span class="stat-info" title="{desc}">&#9432;</span></div>
              <div class="stat-value">{_fmt_ms(ms)}</div>
            </div>""")

    if job.model_name:
        cards.append(f"""<div class="stat-card">
          <div class="stat-label">Model <span class="stat-info" title="The AI model used for extraction">&#9432;</span></div>
          <div class="stat-value">{job.model_name}</div>
        </div>""")

    if not cards:
        return ""

    return '<div class="stats-bar">' + "".join(cards) + "</div>"


def _fmt_ms(ms: int) -> str:
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms / 1000:.1f}s"


@app.get("/ui/jobs/{job_id}")
async def ui_job(job_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    job = await db.get(ExtractionJob, job_id)
    if not job:
        return HTMLResponse("<div>Job not found</div>")

    if job.status in (JobStatus.pending, JobStatus.running):
        return HTMLResponse(f'<div hx-get="/ui/jobs/{job.id}" hx-trigger="every 2s" hx-swap="outerHTML">⏳ Processing...</div>')

    resp = HTMLResponse(f'<div hx-redirect="/ui/jobs/{job.id}/result">Complete</div>')
    resp.headers["HX-Redirect"] = f"/ui/jobs/{job.id}/result"
    return resp


@app.post("/ui/jobs/{job_id}/retry")
async def ui_job_retry(
    job_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
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
    job.input_tokens = None
    job.output_tokens = None
    job.parsing_duration_ms = None
    job.llm_duration_ms = None
    await db.commit()

    background_tasks.add_task(process_job, job.id)
    return HTMLResponse(f'<div hx-get="/ui/jobs/{job.id}" hx-trigger="every 2s" hx-swap="outerHTML">⏳ Retrying...</div>')


@app.get("/ui/jobs/{job_id}/download")
async def ui_job_download(job_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    job = await db.get(ExtractionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.output_data:
        raise HTTPException(status_code=404, detail="No output data available")

    content = json.dumps(job.output_data, indent=2, ensure_ascii=False)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="extraction-{job_id}.json"'},
    )


@app.get("/ui/jobs/{job_id}/result")
async def ui_job_result_page(job_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    job = await db.get(ExtractionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    st = job.status
    if hasattr(st, "value"):
        st = st.value

    output_html = _render_output(job.output_data) if job.output_data else ""
    stats_html = _job_stats_html(job) if job.completed_at else ""

    return templates.TemplateResponse(request, "result.html", {
        "job_id": job.id,
        "status": st,
        "output_html": output_html,
        "stats_html": stats_html,
        "error_message": job.error_message or "",
    })


@app.get("/ui/jobs")
async def ui_jobs(
    offset: int = 0,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_q = select(func.count()).select_from(ExtractionJob).where(ExtractionJob.user_id == user.id)
    total = (await db.execute(total_q)).scalar()

    q = (
        select(ExtractionJob, Document.filename)
        .join(Document, ExtractionJob.document_id == Document.id)
        .where(ExtractionJob.user_id == user.id)
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
async def list_schemas(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SavedSchema).where(SavedSchema.user_id == user.id).order_by(SavedSchema.created_at.desc())
    )
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
async def create_schema(body: dict = Body(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    name = body.get("name", "").strip()
    pydantic_schema = body.get("pydantic_schema", "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name is required")
    if not pydantic_schema:
        raise HTTPException(status_code=422, detail="Schema code is required")
    if len(pydantic_schema) > 10000:
        raise HTTPException(status_code=422, detail="Schema code too long")

    schema = SavedSchema(user_id=user.id, name=name, pydantic_schema=pydantic_schema)
    db.add(schema)
    await db.commit()
    await db.refresh(schema)
    return {"id": str(schema.id), "name": schema.name}


@app.get("/schemas/{schema_id}")
async def get_schema(schema_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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
async def update_schema(schema_id: uuid.UUID, body: dict = Body(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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
async def delete_schema(schema_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    schema = await db.get(SavedSchema, schema_id)
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    await db.delete(schema)
    await db.commit()
    return {"ok": True}


@app.get("/schemas/{schema_id}/export")
async def export_schema(schema_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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


@app.post("/schemas/parse")
async def parse_schema_endpoint(body: dict = Body(...), user: User = Depends(get_current_user)):
    code = body.get("pydantic_schema", "")
    if not code:
        raise HTTPException(status_code=422, detail="Empty schema")
    try:
        result = parse_schema(code)
    except SyntaxError as e:
        raise HTTPException(status_code=422, detail=f"Invalid Python syntax: {e}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result


@app.post("/schemas/import")
async def import_schema(file: UploadFile, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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

    schema = SavedSchema(user_id=user.id, name=name, pydantic_schema=pydantic_schema)
    db.add(schema)
    await db.commit()
    await db.refresh(schema)
    return {"id": str(schema.id), "name": schema.name}


@app.get("/admin")
async def admin_index(admin: User = Depends(get_admin_user)):
    return FileResponse("app/templates/admin.html")


@app.get("/admin/users")
async def admin_users_page(admin: User = Depends(get_admin_user)):
    return FileResponse("app/templates/admin_users.html")


@app.get("/admin/users/data")
async def admin_users(
    offset: int = 0,
    limit: int = 20,
    search: str = "",
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if search:
        pattern = f"%{search}%"
        conditions.append(
            User.email.ilike(pattern) | User.display_name.ilike(pattern)
        )

    total_q = select(func.count()).select_from(User)
    for c in conditions:
        total_q = total_q.where(c)
    total = (await db.execute(total_q)).scalar()

    q = select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
    for c in conditions:
        q = q.where(c)
    rows = (await db.execute(q)).scalars().all()

    users = []
    for u in rows:
        job_count_q = select(func.count()).select_from(ExtractionJob).where(ExtractionJob.user_id == u.id)
        job_count = (await db.execute(job_count_q)).scalar()
        users.append({
            "id": str(u.id),
            "email": u.email,
            "display_name": u.display_name,
            "role": u.role,
            "is_active": u.is_active,
            "job_count": job_count,
            "created_at": u.created_at.isoformat(),
        })

    return {"users": users, "total": total}


@app.post("/admin/users/{user_id}/toggle-status")
async def admin_toggle_user_status(
    user_id: uuid.UUID,
    body: dict,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if str(user.id) == str(admin.id):
        raise HTTPException(status_code=422, detail="Cannot toggle your own status")
    user.is_active = body.get("is_active", True)
    await db.commit()
    return {"ok": True, "is_active": user.is_active}


@app.post("/admin/users/{user_id}/set-role")
async def admin_set_user_role(
    user_id: uuid.UUID,
    body: dict,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    role = body.get("role", "")
    if role not in ("admin", "user"):
        raise HTTPException(status_code=422, detail="Role must be 'admin' or 'user'")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if str(user.id) == str(admin.id):
        raise HTTPException(status_code=422, detail="Cannot change your own role")
    user.role = role
    await db.commit()
    return {"ok": True, "role": user.role}


@app.delete("/admin/users/{user_id}")
async def admin_delete_user(
    user_id: uuid.UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if str(user.id) == str(admin.id):
        raise HTTPException(status_code=422, detail="Cannot delete your own account")
    user.is_active = False
    await db.commit()
    return {"ok": True}


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
                    "input_tokens": job.input_tokens,
                    "output_tokens": job.output_tokens,
                    "upload_duration_ms": job.upload_duration_ms,
                    "parsing_duration_ms": job.parsing_duration_ms,
                    "llm_duration_ms": job.llm_duration_ms,
                    "connection_name": job.connection_name,
                    "provider_type": job.provider_type,
                    "model_name": job.model_name,
                })
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(job_id, ws)
