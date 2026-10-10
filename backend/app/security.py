"""Password hashing, JWT session cookies and auth dependencies (Section 12.3)."""

from __future__ import annotations

import datetime as dt
import hashlib

import bcrypt
import jwt
from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import forbidden, not_authenticated
from app.models import User

COOKIE_NAME = "xai_session"
JWT_ALGORITHM = "HS256"


# ---------- Passwords ----------
def hash_password(password: str) -> str:
    rounds = get_settings().BCRYPT_ROUNDS
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


# ---------- JWT ----------
def create_token(user: User) -> str:
    s = get_settings()
    now = dt.datetime.now(dt.UTC)
    payload = {
        "sub": str(user.user_id),
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(minutes=s.JWT_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, s.JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_settings().JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def set_session_cookie(response: Response, user: User) -> None:
    s = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        create_token(user),
        max_age=s.JWT_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=s.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, secure=s.COOKIE_SECURE, samesite="lax")


# ---------- Dependencies ----------
def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        return None
    try:
        user = db.get(User, int(payload["sub"]))
    except (TypeError, ValueError):
        return None
    # Tokens of deleted or deactivated users are rejected.
    if user is None or not user.is_active:
        return None
    request.state.user_id = user.user_id
    return user


def require_user(user: User | None = Depends(get_current_user_optional)) -> User:
    if user is None:
        raise not_authenticated()
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "admin":
        raise forbidden("Administrator access is required.")
    return user


# ---------- Client IP ----------
def client_ip(request: Request) -> str:
    """X-Forwarded-For is trusted only in production (behind the platform proxy)."""
    if get_settings().is_production:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def hash_ip(ip: str) -> str:
    return hashlib.sha256((ip + get_settings().JWT_SECRET).encode("utf-8")).hexdigest()
