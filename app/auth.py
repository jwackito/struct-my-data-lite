import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import ApiToken, User

_jwt_secret_cache: str | None = None


def _jwt_secret() -> str:
    global _jwt_secret_cache
    if _jwt_secret_cache is not None:
        return _jwt_secret_cache
    _jwt_secret_cache = settings.jwt_secret or secrets.token_urlsafe(32)
    return _jwt_secret_cache


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_jwt(user_id: str, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours)
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": exp},
        _jwt_secret(),
        algorithm=settings.jwt_algorithm,
    )


def decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def generate_api_token() -> tuple[str, str, str]:
    raw_base = secrets.token_urlsafe(32)
    raw = "smd_" + raw_base
    prefix = raw[:11]
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, token_hash, prefix


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get("token")


async def _resolve_api_token(raw_token: str, db: AsyncSession) -> User | None:
    """If raw_token looks like an API token, look it up by hash."""
    if not raw_token.startswith("smd_"):
        return None
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    result = await db.execute(select(ApiToken).where(ApiToken.token_hash == token_hash))
    tok = result.scalar_one_or_none()
    if not tok or not tok.is_active:
        return None
    if tok.expires_at and datetime.now(timezone.utc) > tok.expires_at:
        return None
    tok.last_used_at = datetime.now(timezone.utc)
    user = await db.get(User, tok.user_id)
    return user


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_jwt(token)
    if payload:
        user = await db.get(User, payload.get("sub"))
        if user and user.is_active:
            request.state.user = user
            return user

    api_user = await _resolve_api_token(token, db)
    if api_user:
        request.state.user = api_user
        return api_user

    raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
