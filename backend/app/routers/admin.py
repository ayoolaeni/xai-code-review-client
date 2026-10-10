"""Administrator endpoints: users, statistics and settings (FR16, Section 13)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError, not_found
from app.models import Submission, User
from app.schemas import AdminUserPatch
from app.security import require_admin
from app.services import settings_service, stats_service
from app.time_utils import as_utc

router = APIRouter(prefix="/api/admin", tags=["admin"])
PAGE_SIZE = 20


def _user_out(u: User, count: int) -> dict:
    return {
        "user_id": u.user_id,
        "full_name": u.full_name,
        "email": u.email,
        "role": u.role,
        "is_active": u.is_active,
        "store_code_default": u.store_code_default,
        "created_at": as_utc(u.created_at),
        "last_login_at": as_utc(u.last_login_at),
        "analysis_count": count,
    }


def _other_active_admins(db: Session, exclude_id: int) -> int:
    return (
        db.scalar(
            select(func.count(User.user_id)).where(
                User.role == "admin",
                User.is_active.is_(True),
                User.user_id != exclude_id,
            )
        )
        or 0
    )


@router.get("/users")
def list_users(
    request: Request,
    page: int = Query(1, ge=1),
    q: str = Query("", max_length=200),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    counts = (
        select(Submission.user_id, func.count(Submission.submission_id).label("n"))
        .group_by(Submission.user_id)
        .subquery()
    )
    stmt = select(User, func.coalesce(counts.c.n, 0)).outerjoin(counts, counts.c.user_id == User.user_id)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(User.full_name).like(like), func.lower(User.email).like(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(User.created_at.desc(), User.user_id.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    return {
        "items": [_user_out(u, n) for u, n in rows],
        "total": total,
        "page": page,
        "page_size": PAGE_SIZE,
    }


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    request: Request,
    body: AdminUserPatch,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None:
        raise not_found("This user does not exist.")
    if target.user_id == admin.user_id:
        if body.role == "user":
            raise AppError(400, "BAD_REQUEST", "You cannot remove your own administrator role.")
        if body.is_active is False:
            raise AppError(400, "BAD_REQUEST", "You cannot deactivate your own account.")
    losing_admin = target.role == "admin" and (body.role == "user" or body.is_active is False)
    if losing_admin and _other_active_admins(db, target.user_id) == 0:
        raise AppError(
            400,
            "BAD_REQUEST",
            "The system must keep at least one active administrator.",
        )
    if body.role is not None:
        target.role = body.role
    if body.is_active is not None:
        target.is_active = body.is_active
    db.commit()
    count = (
        db.scalar(select(func.count(Submission.submission_id)).where(Submission.user_id == target.user_id))
        or 0
    )
    return _user_out(target, count)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None:
        raise not_found("This user does not exist.")
    if target.user_id == admin.user_id:
        raise AppError(400, "BAD_REQUEST", "You cannot delete your own account.")
    if target.role == "admin" and _other_active_admins(db, target.user_id) == 0:
        raise AppError(
            400,
            "BAD_REQUEST",
            "The system must keep at least one active administrator.",
        )
    db.delete(target)  # cascades to submissions, reports, findings and feedback
    db.commit()
    return Response(status_code=204)


@router.get("/stats")
def stats(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return stats_service.compute(db, days)


@router.get("/settings")
def get_settings_endpoint(
    request: Request,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return settings_service.describe(db)


@router.put("/settings")
def put_settings(
    request: Request,
    changes: dict[str, Any] = Body(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    settings_service.update(db, changes, admin.user_id)
    return settings_service.describe(db)
