"""Create the administrator account and default settings on startup (Section 13)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from app.security import hash_password
from app.services import settings_service

log = logging.getLogger(__name__)


def seed_admin(db: Session) -> None:
    s = get_settings()
    if db.scalar(select(User).where(User.role == "admin").limit(1)) is not None:
        return
    email = s.ADMIN_EMAIL.strip().lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        existing.role = "admin"
        existing.is_active = True
        log.info("Promoted existing user %s to administrator", existing.user_id)
    else:
        db.add(
            User(
                full_name=s.ADMIN_NAME,
                email=email,
                password_hash=hash_password(s.ADMIN_PASSWORD),
                role="admin",
                is_active=True,
            )
        )
        log.info("Created administrator account from ADMIN_EMAIL")
    db.commit()


def seed(db: Session) -> None:
    seed_admin(db)
    settings_service.seed_defaults(db)


if __name__ == "__main__":
    from app.db import SessionLocal, init_db

    init_db()
    with SessionLocal() as session:
        seed(session)
    print("Seed complete.")
