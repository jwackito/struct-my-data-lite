import hashlib
import json
import logging
import os
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Body, Depends, FastAPI, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from sqlalchemy import and_, func, or_, select, text
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
from app.i18n import DICTS, SUPPORTED_LANGS, current_lang, resolve_lang, t, t_req
from app.models import ApiToken, Batch, Document, ExtractionJob, JobStatus, LLMConnection, ModelRegistry, SavedSchema, User, UserModelAccess, UserRole
from app.pricing import calculate_cost, refresh_pricing
from app.processing import process_job, try_reserve_slot
from sqlalchemy import cast, Date, update
from app.providers import list_all_models
from app.providers.factory import _build_provider, _parse_model_id, _sync_registry, authorize_model
from app.quotas import enforce_job_quota
from app.ratelimit import apply_rate_limit, bucket_for, make_limiters
from app.schema_parser import parse_schema
from app.storage import sanitize_filename, save_file
from app.version import get_version
from app.ws import manager
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["t"] = t


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    if not settings.skip_db_wait:
        await wait_for_db()
    try:
        async with async_session() as db:
            await refresh_pricing(db)
    except Exception:
        pass
    yield


app = FastAPI(title="Struct My Data", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    lang_token = current_lang.set(resolve_lang(request))
    try:
        response = await call_next(request)
    finally:
        current_lang.reset(lang_token)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=500,
        content={"detail": t_req("Internal server error"), "request_id": request_id},
    )


_rate_limiters = make_limiters()


class _RateLimitUser:
    __slots__ = ("id",)

    def __init__(self, user_id: str):
        self.id = user_id


def _rate_limit_user(request: Request):
    token = request.headers.get("Authorization", "")
    token = token[7:] if token.startswith("Bearer ") else request.cookies.get("token")
    if not token:
        return None
    payload = decode_jwt(token)
    if not payload or not payload.get("sub"):
        return None
    return _RateLimitUser(payload["sub"])


def _enqueue_jobs(background_tasks: BackgroundTasks, job_ids: list) -> None:
    """Reserve a queue slot per job; reject the whole request if the queue is full."""
    from app.processing import _queue

    reserved = 0
    for _ in job_ids:
        if not try_reserve_slot():
            for _ in range(reserved):
                _queue.release()
            raise HTTPException(status_code=503, detail=t_req("Server is busy, try again shortly"))
        reserved += 1
    for job_id in job_ids:
        background_tasks.add_task(process_job, job_id)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    name = bucket_for(request.url.path, request.method)
    if name:
        user = getattr(request.state, "user", None)
        if user is None:
            user = _rate_limit_user(request)
        blocked = apply_rate_limit(request, _rate_limiters[name], user)
        if blocked is not None:
            return blocked
    return await call_next(request)


@app.get("/docs", include_in_schema=False)
async def docs(user: User = Depends(get_current_user)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="Struct My Data API")


@app.get("/redoc", include_in_schema=False)
async def redoc(user: User = Depends(get_current_user)):
    return get_redoc_html(openapi_url="/openapi.json", title="Struct My Data API")


@app.get("/openapi.json", include_in_schema=False)
async def openapi_schema(user: User = Depends(get_current_user)):
    return JSONResponse(app.openapi())


@app.post("/auth/register")
async def auth_register(body: dict, db: AsyncSession = Depends(get_db)):
    if not settings.allow_registration:
        raise HTTPException(status_code=403, detail=t_req("Registration is closed"))

    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    display_name = (body.get("display_name") or "").strip()

    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail=t_req("Valid email is required"))
    if len(password) < 8:
        raise HTTPException(status_code=422, detail=t_req("Password must be at least 8 characters"))

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=422, detail=t_req("Email already registered"))

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
        raise HTTPException(status_code=401, detail=t_req("Invalid email or password"))
    if not user.is_active:
        raise HTTPException(status_code=403, detail=t_req("Account is disabled"))

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
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"user": None, "lang": resolve_lang(request)})


@app.get("/register")
async def register_page(request: Request):
    if not settings.allow_registration:
        return HTMLResponse(f'<html><body style="font-family:sans-serif;text-align:center;padding:4rem"><h1>{t_req("Registration is closed")}</h1><p><a href="/login">{t_req("Back to login")}</a></p></body></html>', status_code=403)
    return templates.TemplateResponse(request, "register.html", {"user": None, "lang": resolve_lang(request)})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ok"}


@app.get("/api/version")
async def api_version():
    return {"version": get_version()}


@app.get("/LICENSE")
async def license_file():
    return FileResponse("LICENSE", media_type="text/plain")


@app.get("/i18n.js")
async def i18n_js():
    return FileResponse("app/static/i18n.js")


@app.get("/app.css")
async def app_css():
    return FileResponse("app/static/app.css", media_type="text/css")


@app.get("/i18n/{lang}.json")
async def i18n_json(lang: str):
    if lang not in SUPPORTED_LANGS:
        raise HTTPException(status_code=404, detail=t_req("Language not found"))
    return JSONResponse(DICTS[lang])


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
        raise HTTPException(status_code=422, detail=t_req("Name is required"))
    if provider not in ("openai", "gemini", "ollama"):
        raise HTTPException(status_code=422, detail=t_req("Unknown provider: {provider}", provider=provider))

    test_result = await test_connection(name, {**config, **secrets}, provider, db)
    if not test_result.get("ok"):
        raise HTTPException(status_code=422, detail=t_req("Connection test failed: {error}", error=test_result.get("error", "unknown error")))

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
        raise HTTPException(status_code=422, detail=t_req("Unknown provider: {provider}", provider=provider))

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
        raise HTTPException(status_code=404, detail=t_req("Key not found"))
    return {"ok": True}


@app.post("/api/tokens")
async def api_create_token(body: dict, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.auth import generate_api_token

    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail=t_req("Name is required"))

    raw, token_hash, prefix = generate_api_token()
    expires_at = None
    if body.get("expires_at"):
        try:
            expires_at = datetime.fromisoformat(body["expires_at"])
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail=t_req("Invalid expires_at format"))

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
        raise HTTPException(status_code=404, detail=t_req("Token not found"))
    tok.is_active = False
    await db.commit()
    return {"ok": True}


@app.post("/api/batches/estimate")
async def api_batch_estimate(body: dict, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.pricing import calculate_cost

    file_sizes = body.get("file_sizes", [])
    model_id = body.get("model_id", "")
    if not file_sizes:
        raise HTTPException(status_code=422, detail=t_req("file_sizes is required"))
    if len(file_sizes) > settings.max_batch_size:
        raise HTTPException(status_code=422, detail=t_req("Batch exceeds max size of {max}", max=settings.max_batch_size))

    provider_type, connection_name, model_name = await _parse_model_id(model_id, db)
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
        raise HTTPException(status_code=422, detail=t_req("document_ids is required"))
    if len(document_ids) > settings.max_batch_size:
        raise HTTPException(status_code=422, detail=t_req("Batch exceeds max size of {max}", max=settings.max_batch_size))
    if not pydantic_schema:
        raise HTTPException(status_code=422, detail=t_req("pydantic_schema is required"))
    try:
        compile(pydantic_schema, "<schema>", "exec")
    except SyntaxError as e:
        raise HTTPException(status_code=422, detail=t_req("Invalid Pydantic schema: {error}", error=e))

    batch = Batch(user_id=user.id, name=name)
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    provider_type, connection_name, model_name = await _parse_model_id(model_id, db)
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

    _enqueue_jobs(background_tasks, job_ids)

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
        raise HTTPException(status_code=404, detail=t_req("Batch not found"))

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
        raise HTTPException(status_code=404, detail=t_req("Batch not found"))

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
        _enqueue_jobs(background_tasks, [job_id])

    return {"ok": True, "retried": [str(j) for j in retried]}


@app.post("/api/batches/{batch_id}/cancel")
async def api_batch_cancel(batch_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    batch = await db.get(Batch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(status_code=404, detail=t_req("Batch not found"))

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
        raise HTTPException(status_code=404, detail=t_req("Batch not found"))

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
async def admin_usage_page(request: Request, admin: User = Depends(get_admin_user)):
    return templates.TemplateResponse(request, "admin_usage.html", {"user": admin, "active": "admin_usage", "lang": resolve_lang(request)})


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
        raise HTTPException(status_code=404, detail=t_req("Connection not found"))
    return conn


@app.put("/providers/connections/{name}")
async def put_connection(name: str, body: dict, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    provider = body.get("provider", "")
    config = body.get("config", {})
    secrets = body.get("secrets", {})

    if not provider:
        raise HTTPException(status_code=422, detail=t_req("provider is required"))
    if provider not in ("ollama", "openai", "gemini"):
        raise HTTPException(status_code=422, detail=t_req("Unknown provider: {provider}", provider=provider))

    test_result = await test_connection(name, {**config, **secrets}, provider, db)
    if not test_result.get("ok"):
        raise HTTPException(status_code=422, detail=t_req("Connection test failed: {error}", error=test_result.get("error", "unknown error")))

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
        raise HTTPException(status_code=404, detail=t_req("Connection not found"))
    return {"ok": True}


@app.post("/providers/connections/{name}/test")
async def test_connection_endpoint(name: str, body: dict, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    config = body.get("config", {})
    secrets = body.get("secrets", {})
    provider = body.get("provider", "")
    if not provider:
        raise HTTPException(status_code=422, detail=t_req("provider is required"))
    result = await test_connection(name, {**config, **secrets}, provider, db)
    return result


def _can_access(owner_id, user: User) -> bool:
    if user.role == "admin":
        return True
    return owner_id is not None and owner_id == user.id


@app.post("/upload")
async def upload(file: UploadFile, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    content = await file.read()
    if len(content) > settings.max_upload_size:
        raise HTTPException(status_code=413, detail=t_req("File exceeds maximum upload size"))

    content_hash = hashlib.sha256(content).hexdigest()

    stmt = select(Document).where(Document.user_id == user.id, Document.content_hash == content_hash)
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
    model_id: str = Body(""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=t_req("Document not found"))
    if not _can_access(doc.user_id, user):
        raise HTTPException(status_code=403, detail=t_req("Access denied"))

    try:
        compile(pydantic_schema, "<schema>", "exec")
    except SyntaxError as e:
        raise HTTPException(status_code=422, detail=t_req("Invalid Pydantic schema: {error}", error=e))

    provider_type, connection_name, model_name = await authorize_model(db, user, model_id)
    await enforce_job_quota(db, user, 1)
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
        _enqueue_jobs(background_tasks, [job.id])

    return {
        "id": str(job.id),
        "status": job.status,
    }


@app.get("/jobs/{job_id}")
async def get_job(job_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    job = await db.get(ExtractionJob, job_id)
    if not job or not _can_access(job.user_id, user):
        raise HTTPException(status_code=404, detail=t_req("Job not found"))

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
async def index(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("token")
    payload = decode_jwt(token) if token else None
    if not payload:
        return RedirectResponse(url="/login")
    user = await db.get(User, payload.get("sub"))
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request, "index.html", {"user": user, "active": "extraction", "lang": resolve_lang(request)})


@app.get("/ui/settings")
async def ui_settings(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request, "settings.html", {"user": user, "active": "settings", "lang": resolve_lang(request)})


@app.get("/usage")
async def usage_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request, "usage.html", {"user": user, "active": "usage", "lang": resolve_lang(request)})


@app.get("/ui/batches")
async def ui_batches_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request, "batches.html", {"user": user, "active": "batches", "lang": resolve_lang(request)})


@app.get("/ui/batches/{batch_id}")
async def ui_batch_page(request: Request, batch_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    batch = await db.get(Batch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(status_code=404, detail=t_req("Batch not found"))
    return templates.TemplateResponse(request, "batch.html", {"user": user, "active": "batches", "lang": resolve_lang(request)})


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
        return HTMLResponse(f'<div style="color:red">{t_req("Batch exceeds max size of {max}", max=settings.max_batch_size)}</div>')

    try:
        compile(pydantic_schema, "<schema>", "exec")
    except SyntaxError as e:
        return HTMLResponse(f'<div style="color:red">{t_req("Invalid Pydantic schema: {error}", error=e)}</div>')

    batch = Batch(user_id=user.id, name=f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    provider_type, connection_name, model_name = await _parse_model_id(model_id, db)
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

    _enqueue_jobs(background_tasks, job_ids)

    resp = HTMLResponse(f'<div>{t_req("Batch started")}</div>')
    resp.headers["HX-Redirect"] = f"/ui/batches/{batch.id}"
    return resp


def _render_output(data):
    return f"<pre>{json.dumps(data, indent=2, ensure_ascii=False)}</pre>"


def _job_stats_html(job, lang="en") -> str:
    from app.pricing import calculate_cost

    cards = []

    if job.input_tokens is not None:
        cards.append(f"""<div class="stat-card">
          <div class="stat-label">{t("Tokens", lang)} <span class="stat-info" title="{t('Tokens sent to and received from the AI model', lang)}">&#9432;</span></div>
          <div class="stat-value">{job.input_tokens} in / {job.output_tokens} out</div>
        </div>""")
        cost = calculate_cost(job.provider_type or "", job.model_name or "", job.input_tokens, job.output_tokens)
        if cost > 0:
            cards.append(f"""<div class="stat-card">
              <div class="stat-label">{t("Cost", lang)} <span class="stat-info" title="{t('Estimated cost in USD based on model pricing', lang)}">&#9432;</span></div>
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
              <div class="stat-label">{t(label, lang)} <span class="stat-info" title="{t(desc, lang)}">&#9432;</span></div>
              <div class="stat-value">{_fmt_ms(ms)}</div>
            </div>""")

    if job.model_name:
        cards.append(f"""<div class="stat-card">
          <div class="stat-label">{t("Model", lang)} <span class="stat-info" title="{t('The AI model used for extraction', lang)}">&#9432;</span></div>
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
        return HTMLResponse(f'<div>{t_req("Job not found")}</div>')

    if job.status in (JobStatus.pending, JobStatus.running):
        return HTMLResponse(f'<div hx-get="/ui/jobs/{job.id}" hx-trigger="every 2s" hx-swap="outerHTML">⏳ {t_req("Processing...")}</div>')

    resp = HTMLResponse(f'<div hx-redirect="/ui/jobs/{job.id}/result">{t_req("Complete")}</div>')
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
        return HTMLResponse(f'<div>{t_req("Job not found")}</div>')

    st = job.status
    if hasattr(st, "value"):
        st = st.value
    if st not in ("pending", "failed"):
        return HTMLResponse(f'<div>{t_req("Can only retry failed or pending jobs")}</div>')

    job.status = JobStatus.pending
    job.error_message = None
    job.completed_at = None
    job.input_tokens = None
    job.output_tokens = None
    job.parsing_duration_ms = None
    job.llm_duration_ms = None
    await db.commit()

    _enqueue_jobs(background_tasks, [job.id])
    return HTMLResponse(f'<div hx-get="/ui/jobs/{job.id}" hx-trigger="every 2s" hx-swap="outerHTML">⏳ {t_req("Retrying...")}</div>')


@app.get("/ui/jobs/{job_id}/download")
async def ui_job_download(job_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    job = await db.get(ExtractionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=t_req("Job not found"))
    if not job.output_data:
        raise HTTPException(status_code=404, detail=t_req("No output data available"))

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
        raise HTTPException(status_code=404, detail=t_req("Job not found"))

    st = job.status
    if hasattr(st, "value"):
        st = st.value

    output_html = _render_output(job.output_data) if job.output_data else ""
    stats_html = _job_stats_html(job, resolve_lang(request)) if job.completed_at else ""

    return templates.TemplateResponse(request, "result.html", {
        "job_id": job.id,
        "status": st,
        "output_html": output_html,
        "stats_html": stats_html,
        "error_message": job.error_message or "",
        "user": user,
        "active": "",
        "lang": resolve_lang(request),
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
        view_btn = f'<button hx-get="/ui/jobs/{job.id}" hx-target="#result">{t_req("View")}</button>'

        if st in ("pending", "failed"):
            retry = f'<button hx-post="/ui/jobs/{job.id}/retry" hx-target="#result">{t_req("Retry")}</button>'
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
      <button hx-get="/ui/jobs?offset={prev_offset}&limit={limit}" hx-target="#tab-history" {prev_disabled}>← {t_req("Prev")}</button>
      <span>{t_req("Page {page} of {pages}", page=page, pages=pages)}</span>
      <button hx-get="/ui/jobs?offset={next_offset}&limit={limit}" hx-target="#tab-history" {next_disabled}>{t_req("Next")} →</button>
    </div>"""

    html = f"""
    <table>
      <thead><tr><th></th><th>{t_req("File")}</th><th>{t_req("Date")}</th><th></th></tr></thead>
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


@app.get("/schemas/shared")
async def list_shared_schemas(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SavedSchema, User)
        .join(User, SavedSchema.user_id == User.id)
        .where(SavedSchema.is_public.is_(True), SavedSchema.user_id != user.id)
        .order_by(SavedSchema.name)
    )
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "pydantic_schema": s.pydantic_schema,
            "owner_name": u.display_name or u.email,
            "updated_at": s.updated_at.isoformat(),
        }
        for s, u in result.all()
    ]


@app.post("/schemas")
async def create_schema(body: dict = Body(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    name = body.get("name", "").strip()
    pydantic_schema = body.get("pydantic_schema", "").strip()
    if not name:
        raise HTTPException(status_code=422, detail=t_req("Name is required"))
    if not pydantic_schema:
        raise HTTPException(status_code=422, detail=t_req("Schema code is required"))
    if len(pydantic_schema) > 10000:
        raise HTTPException(status_code=422, detail=t_req("Schema code too long"))

    existing = await db.execute(
        select(SavedSchema).where(SavedSchema.user_id == user.id, SavedSchema.name == name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=t_req("You already have a schema named {name}", name=name))

    schema = SavedSchema(user_id=user.id, name=name, pydantic_schema=pydantic_schema)
    db.add(schema)
    await db.commit()
    await db.refresh(schema)
    return {"id": str(schema.id), "name": schema.name}


@app.get("/schemas/{schema_id}")
async def get_schema(schema_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    schema = await db.get(SavedSchema, schema_id)
    if not schema or not (user.role == "admin" or schema.user_id == user.id or schema.is_public):
        raise HTTPException(status_code=404, detail=t_req("Schema not found"))
    return {
        "id": str(schema.id),
        "name": schema.name,
        "pydantic_schema": schema.pydantic_schema,
        "is_public": schema.is_public,
        "created_at": schema.created_at.isoformat(),
        "updated_at": schema.updated_at.isoformat(),
    }


@app.post("/schemas/{schema_id}/duplicate")
async def duplicate_schema(schema_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    schema = await db.get(SavedSchema, schema_id)
    if not schema or not (user.role == "admin" or schema.user_id == user.id or schema.is_public):
        raise HTTPException(status_code=404, detail=t_req("Schema not found"))

    existing = await db.execute(
        select(SavedSchema).where(SavedSchema.user_id == user.id, SavedSchema.name == schema.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=t_req("You already have a schema named {name}", name=schema.name))

    copy = SavedSchema(
        user_id=user.id,
        name=schema.name,
        pydantic_schema=schema.pydantic_schema,
        is_public=False,
    )
    db.add(copy)
    await db.commit()
    await db.refresh(copy)
    return {"id": str(copy.id), "name": copy.name}


@app.put("/schemas/{schema_id}")
async def update_schema(schema_id: uuid.UUID, body: dict = Body(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    schema = await db.get(SavedSchema, schema_id)
    if not schema or not (user.role == "admin" or schema.user_id == user.id):
        raise HTTPException(status_code=404, detail=t_req("Schema not found"))
    if "name" in body:
        name = body["name"].strip()
        if not name:
            raise HTTPException(status_code=422, detail=t_req("Name is required"))
        if name != schema.name and schema.user_id is not None:
            dup = await db.execute(
                select(SavedSchema).where(
                    SavedSchema.user_id == schema.user_id,
                    SavedSchema.name == name,
                    SavedSchema.id != schema.id,
                )
            )
            if dup.scalar_one_or_none():
                raise HTTPException(status_code=409, detail=t_req("You already have a schema named {name}", name=name))
        schema.name = name
    if "pydantic_schema" in body:
        pydantic_schema = body["pydantic_schema"].strip()
        if not pydantic_schema:
            raise HTTPException(status_code=422, detail=t_req("Schema code is required"))
        if len(pydantic_schema) > 10000:
            raise HTTPException(status_code=422, detail=t_req("Schema code too long"))
        schema.pydantic_schema = pydantic_schema
    if "is_public" in body:
        schema.is_public = bool(body["is_public"])
    await db.commit()
    await db.refresh(schema)
    return {"id": str(schema.id), "name": schema.name, "is_public": schema.is_public}


@app.delete("/schemas/{schema_id}")
async def delete_schema(schema_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    schema = await db.get(SavedSchema, schema_id)
    if not schema or not (user.role == "admin" or schema.user_id == user.id):
        raise HTTPException(status_code=404, detail=t_req("Schema not found"))
    await db.delete(schema)
    await db.commit()
    return {"ok": True}


@app.get("/schemas/{schema_id}/export")
async def export_schema(schema_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    schema = await db.get(SavedSchema, schema_id)
    if not schema or not (user.role == "admin" or schema.user_id == user.id or schema.is_public):
        raise HTTPException(status_code=404, detail=t_req("Schema not found"))
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
        raise HTTPException(status_code=422, detail=t_req("Empty schema"))
    try:
        result = parse_schema(code)
    except SyntaxError as e:
        raise HTTPException(status_code=422, detail=t_req("Invalid Python syntax: {error}", error=e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result


@app.post("/schemas/import")
async def import_schema(file: UploadFile, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    content = await file.read()
    if len(content) > 10000:
        raise HTTPException(status_code=422, detail=t_req("File too large"))

    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail=t_req("Invalid UTF-8 file"))

    if decoded.lstrip().startswith("{"):
        try:
            data = json.loads(decoded)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail=t_req("Invalid JSON file"))
        name = data.get("name", "").strip()
        pydantic_schema = data.get("pydantic_schema", "").strip()
    else:
        name = file.filename.replace(".py", "").replace(".txt", "").strip() if file.filename else "Untitled"
        pydantic_schema = decoded

    if not name:
        name = "Imported Schema"
    if not pydantic_schema:
        raise HTTPException(status_code=422, detail=t_req("No schema code found in file"))

    existing = await db.execute(
        select(SavedSchema).where(SavedSchema.user_id == user.id, SavedSchema.name == name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=t_req("You already have a schema named {name}", name=name))

    schema = SavedSchema(user_id=user.id, name=name, pydantic_schema=pydantic_schema)
    db.add(schema)
    await db.commit()
    await db.refresh(schema)
    return {"id": str(schema.id), "name": schema.name}


@app.get("/admin")
async def admin_index(request: Request, admin: User = Depends(get_admin_user)):
    return templates.TemplateResponse(request, "admin.html", {"user": admin, "active": "admin", "lang": resolve_lang(request)})


@app.get("/admin/models")
async def admin_models_page(request: Request, admin: User = Depends(get_admin_user)):
    return templates.TemplateResponse(request, "admin_models.html", {"user": admin, "active": "admin_models", "lang": resolve_lang(request)})


@app.get("/admin/schemas")
async def admin_schemas_page(request: Request, admin: User = Depends(get_admin_user)):
    return templates.TemplateResponse(request, "admin_schemas.html", {"user": admin, "active": "admin_schemas", "lang": resolve_lang(request)})


@app.get("/admin/schemas/data")
async def admin_schemas_data(admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SavedSchema, User)
        .join(User, SavedSchema.user_id == User.id)
        .order_by(SavedSchema.name)
    )
    return {
        "schemas": [
            {
                "id": str(s.id),
                "name": s.name,
                "owner_name": u.display_name or u.email,
                "owner_email": u.email,
                "is_public": s.is_public,
                "updated_at": s.updated_at.isoformat(),
            }
            for s, u in result.all()
        ]
    }


@app.get("/admin/models/data")
async def admin_models_data(
    connection: str = "",
    provider: str = "",
    search: str = "",
    include_hidden: int = 0,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    implicit = ModelRegistry.connection_id.is_(None)
    if connection:
        conditions.append(or_(
            LLMConnection.name == connection,
            and_(connection == "ollama", implicit),
        ))
    if provider:
        conditions.append(or_(
            LLMConnection.provider == provider,
            and_(provider == "ollama", implicit),
        ))
    if not include_hidden:
        conditions.append(ModelRegistry.enabled.is_(True))
    if search:
        pattern = f"%{search}%"
        conditions.append(ModelRegistry.model_name.ilike(pattern))

    q = (
        select(ModelRegistry, LLMConnection)
        .outerjoin(LLMConnection, ModelRegistry.connection_id == LLMConnection.id)
    )
    for cond in conditions:
        q = q.where(cond)
    q = q.order_by(func.coalesce(LLMConnection.name, "ollama"), ModelRegistry.sort_order, ModelRegistry.model_name)

    result = await db.execute(q)
    rows = []
    for reg, conn in result.all():
        rows.append({
            "id": str(reg.id),
            "connection": conn.name if conn else "ollama",
            "provider": conn.provider if conn else "ollama",
            "model_name": reg.model_name,
            "display_name": reg.display_name,
            "description": reg.description,
            "capabilities": reg.capabilities,
            "context_window": reg.context_window,
            "price_input_usd": reg.price_input_usd,
            "price_output_usd": reg.price_output_usd,
            "enabled": reg.enabled,
            "admin_only": reg.admin_only,
            "is_default": reg.is_default,
            "sort_order": reg.sort_order,
            "last_seen_at": reg.last_seen_at.isoformat() if reg.last_seen_at else None,
        })
    return {"models": rows}


@app.post("/admin/models/refresh")
async def admin_models_refresh(admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    from app.connections import get_connection as get_conn

    for conn in await list_connections(db):
        if not conn["enabled"]:
            continue
        full = await get_conn(conn["name"], db)
        if not full:
            continue
        try:
            provider = _build_provider(full["provider"], full["config"])
        except Exception:
            continue
        await _sync_registry(db, conn, provider, provider.list_models())
    await db.commit()
    await refresh_pricing(db)
    return {"ok": True}


@app.patch("/admin/models/{model_id}")
async def admin_models_patch(
    model_id: uuid.UUID,
    body: dict,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    reg = await db.get(ModelRegistry, model_id)
    if not reg:
        raise HTTPException(status_code=404, detail=t_req("Model not found"))

    allowed = {
        "display_name", "description", "capabilities", "context_window",
        "price_input_usd", "price_output_usd", "enabled", "admin_only",
        "is_default", "sort_order",
    }
    for key, value in body.items():
        if key not in allowed:
            raise HTTPException(status_code=422, detail=t_req("Unknown field: {key}", key=key))
        setattr(reg, key, value)

    if body.get("is_default"):
        await db.execute(
            update(ModelRegistry)
            .where(ModelRegistry.connection_id == reg.connection_id, ModelRegistry.is_default.is_(True))
            .where(ModelRegistry.id != reg.id)
            .values(is_default=False)
        )

    await db.commit()
    await db.refresh(reg)
    await refresh_pricing(db)
    return {"ok": True}


@app.get("/admin/users/{user_id}/models")
async def admin_user_models(
    user_id: uuid.UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail=t_req("User not found"))
    result = await db.execute(
        select(UserModelAccess, ModelRegistry)
        .join(ModelRegistry, UserModelAccess.model_id == ModelRegistry.id)
        .where(UserModelAccess.user_id == user_id)
    )
    grants = [{"model_id": str(a.model_id), "model_name": reg.model_name, "access": a.access} for a, reg in result.all()]
    return {"grants": grants}


@app.put("/admin/users/{user_id}/models")
async def admin_user_models_put(
    user_id: uuid.UUID,
    body: dict,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail=t_req("User not found"))

    grants = body.get("grants", [])
    for g in grants:
        model_id = g.get("model_id")
        access = g.get("access")
        if access not in ("allow", "deny", "default"):
            raise HTTPException(status_code=422, detail=t_req("Invalid access: {access}", access=access))
        try:
            model_uuid = uuid.UUID(str(model_id))
        except ValueError:
            raise HTTPException(status_code=422, detail=t_req("Invalid model_id"))
        if not await db.get(ModelRegistry, model_uuid):
            raise HTTPException(status_code=404, detail=t_req("Model not found"))
        result = await db.execute(
            select(UserModelAccess).where(
                UserModelAccess.user_id == user_id,
                UserModelAccess.model_id == model_uuid,
            )
        )
        row = result.scalar_one_or_none()
        if access == "default":
            if row:
                await db.delete(row)
        elif row:
            row.access = access
        else:
            db.add(UserModelAccess(user_id=user_id, model_id=model_uuid, access=access))
    await db.commit()
    return {"ok": True}


@app.get("/admin/users")
async def admin_users_page(request: Request, admin: User = Depends(get_admin_user)):
    return templates.TemplateResponse(request, "admin_users.html", {"user": admin, "active": "admin_users", "lang": resolve_lang(request)})


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


@app.get("/admin/failures")
async def admin_failures_page(request: Request, admin: User = Depends(get_admin_user)):
    return templates.TemplateResponse(request, "admin_failures.html", {"user": admin, "active": "admin_failures", "lang": resolve_lang(request)})


@app.get("/admin/failures/data")
async def admin_failures_data(
    offset: int = 0,
    limit: int = 20,
    user: str = "",
    model: str = "",
    connection: str = "",
    content_type: str = "",
    since: str = "",
    until: str = "",
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    conditions = [ExtractionJob.status == JobStatus.failed]
    if model:
        conditions.append(ExtractionJob.model_name == model)
    if connection:
        conditions.append(ExtractionJob.connection_name == connection)
    if content_type:
        conditions.append(Document.content_type == content_type)
    if user:
        pattern = f"%{user}%"
        conditions.append(or_(User.email.ilike(pattern), User.display_name.ilike(pattern)))
    if since:
        conditions.append(ExtractionJob.created_at >= datetime.fromisoformat(since))
    if until:
        conditions.append(ExtractionJob.created_at <= datetime.fromisoformat(until))

    base = (
        select(ExtractionJob, Document, User)
        .join(Document, ExtractionJob.document_id == Document.id)
        .outerjoin(User, ExtractionJob.user_id == User.id)
    )
    total_q = (
        select(func.count())
        .select_from(ExtractionJob)
        .join(Document, ExtractionJob.document_id == Document.id)
        .outerjoin(User, ExtractionJob.user_id == User.id)
    )
    for c in conditions:
        base = base.where(c)
        total_q = total_q.where(c)

    total = (await db.execute(total_q)).scalar()
    rows = (await db.execute(base.order_by(ExtractionJob.created_at.desc()).offset(offset).limit(limit))).all()

    jobs = []
    for job, doc, owner in rows:
        jobs.append({
            "id": str(job.id),
            "created_at": job.created_at.isoformat(),
            "user_email": owner.email if owner else None,
            "filename": doc.filename if doc else None,
            "content_type": doc.content_type if doc else None,
            "model_name": job.model_name,
            "connection_name": job.connection_name,
            "provider_type": job.provider_type,
            "error_message": job.error_message,
        })
    return {"jobs": jobs, "total": total}


@app.get("/admin/jobs/{job_id}")
async def admin_job_detail(
    job_id: uuid.UUID,
    request: Request,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(ExtractionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=t_req("Job not found"))
    doc = await db.get(Document, job.document_id) if job.document_id else None
    owner = await db.get(User, job.user_id) if job.user_id else None
    st = job.status.value if hasattr(job.status, "value") else job.status
    lang = resolve_lang(request)

    return templates.TemplateResponse(request, "admin_job_detail.html", {
        "user": admin,
        "active": "admin_failures",
        "lang": lang,
        "job": job,
        "status": st,
        "document": doc,
        "owner": owner,
        "stats_html": _job_stats_html(job, lang) if job.completed_at else "",
        "output_html": _render_output(job.output_data) if job.output_data else "",
    })


@app.get("/admin/jobs/{job_id}/document")
async def admin_job_document(
    job_id: uuid.UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(ExtractionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=t_req("Job not found"))
    doc = await db.get(Document, job.document_id) if job.document_id else None
    if not doc or not os.path.exists(doc.storage_path):
        raise HTTPException(status_code=404, detail=t_req("Document not found"))
    return FileResponse(
        doc.storage_path,
        media_type=doc.content_type,
        filename=sanitize_filename(doc.filename),
    )


@app.post("/admin/users/{user_id}/toggle-status")
async def admin_toggle_user_status(
    user_id: uuid.UUID,
    body: dict,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=t_req("User not found"))
    if str(user.id) == str(admin.id):
        raise HTTPException(status_code=422, detail=t_req("Cannot toggle your own status"))
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
        raise HTTPException(status_code=422, detail=t_req("Role must be 'admin' or 'user'"))
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=t_req("User not found"))
    if str(user.id) == str(admin.id):
        raise HTTPException(status_code=422, detail=t_req("Cannot change your own role"))
    user.role = role
    await db.commit()
    return {"ok": True, "role": user.role}


@app.post("/admin/users")
async def admin_create_user(
    body: dict,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    display_name = (body.get("display_name") or "").strip()
    role = body.get("role") or "user"
    if role not in ("user", "admin"):
        raise HTTPException(status_code=422, detail=t_req("Role must be 'admin' or 'user'"))
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail=t_req("Valid email is required"))
    if len(password) < 8:
        raise HTTPException(status_code=422, detail=t_req("Password must be at least 8 characters"))

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=422, detail=t_req("Email already registered"))

    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name or email.split("@")[0],
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
    }


@app.delete("/admin/users/{user_id}")
async def admin_delete_user(
    user_id: uuid.UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=t_req("User not found"))
    if str(user.id) == str(admin.id):
        raise HTTPException(status_code=422, detail=t_req("Cannot delete your own account"))
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
