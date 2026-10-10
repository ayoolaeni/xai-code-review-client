"""Registration, login, logout and profile (FR14)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import User, utcnow
from app.rate_limit import AUTH_LIMIT, limiter
from app.schemas import LoginIn, RegisterIn, UpdateMeIn, UserOut
from app.security import (
    clear_session_cookie,
    hash_password,
    require_user,
    set_session_cookie,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

LOGIN_FAILED = "Incorrect email or password."
# Used to make failed logins for unknown emails take as long as real ones (no user enumeration by timing).
_DUMMY_HASH = hash_password("dummy-password-1")


@router.post("/register", status_code=201, response_model=UserOut)
@limiter.limit(AUTH_LIMIT)
def register(
    request: Request,
    response: Response,
    body: RegisterIn,
    db: Session = Depends(get_db),
):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise AppError(
            409,
            "EMAIL_TAKEN",
            "An account with this email already exists. Please log in.",
        )
    user = User(
        full_name=body.full_name,
        email=email,
        password_hash=hash_password(body.password),
        role="user",
        is_active=True,
        store_code_default=body.store_code_default,
        last_login_at=utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    set_session_cookie(response, user)
    return user


@router.post("/login", response_model=UserOut)
@limiter.limit(AUTH_LIMIT)
def login(request: Request, response: Response, body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None:
        verify_password(body.password, _DUMMY_HASH)
        raise AppError(401, "NOT_AUTHENTICATED", LOGIN_FAILED)
    if not verify_password(body.password, user.password_hash):
        raise AppError(401, "NOT_AUTHENTICATED", LOGIN_FAILED)
    if not user.is_active:
        raise AppError(403, "FORBIDDEN", "This account has been deactivated.")
    user.last_login_at = utcnow()
    db.commit()
    set_session_cookie(response, user)
    return user


@router.post("/logout", status_code=204)
def logout(request: Request):
    response = Response(status_code=204)
    clear_session_cookie(response)
    return response


@router.get("/me", response_model=UserOut)
def me(request: Request, user: User = Depends(require_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(
    request: Request,
    body: UpdateMeIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    db_user = db.get(User, user.user_id)
    if body.full_name is not None:
        name = body.full_name.strip()
        if not name:
            raise AppError(422, "VALIDATION_ERROR", "Please enter your name.")
        db_user.full_name = name
    if body.store_code_default is not None:
        db_user.store_code_default = body.store_code_default
    db.commit()
    db.refresh(db_user)
    return db_user
