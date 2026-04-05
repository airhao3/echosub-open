"""
Dependency injection for API endpoints.

Open-source mode: Authentication is disabled.
All endpoints receive a default local user automatically.
"""
from typing import Generator, Optional
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User
from app.core.database import get_db

settings = get_settings()

# ---------------------------------------------------------------------------
# Default user cache (avoids hitting the DB on every single request)
# ---------------------------------------------------------------------------
_default_user_cache: Optional[User] = None


def _get_or_create_default_user(db: Session) -> User:
    """Return the default local user, creating it if it doesn't exist yet."""
    global _default_user_cache
    if _default_user_cache is not None:
        # Make sure the cached object is bound to the current session
        try:
            db.merge(_default_user_cache)
            return _default_user_cache
        except Exception:
            _default_user_cache = None

    user = db.query(User).filter(User.username == "admin").first()
    if not user:
        from app.core.security import get_password_hash
        user = User(
            email="admin@echosub.local",
            username="admin",
            full_name="Local User",
            hashed_password=get_password_hash("admin"),
            is_active=True,
            is_superuser=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    _default_user_cache = user
    return user


# ---------------------------------------------------------------------------
# Public dependency functions — drop-in replacements for the old auth deps
# Every endpoint that used Depends(get_current_user) etc. will now simply
# receive the default local user with zero authentication overhead.
# ---------------------------------------------------------------------------

def get_current_user(db: Session = Depends(get_db)) -> User:
    """Return the default local user (no authentication required)."""
    return _get_or_create_default_user(db)


def get_current_active_user(db: Session = Depends(get_db)) -> User:
    """Return the default local user (no authentication required)."""
    return _get_or_create_default_user(db)


def get_current_superuser(db: Session = Depends(get_db)) -> User:
    """Return the default local user (no authentication required)."""
    return _get_or_create_default_user(db)


# Alias kept for backward compatibility
get_current_active_superuser = get_current_superuser


def get_current_user_or_none(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Always return the default user (was: optional auth)."""
    return _get_or_create_default_user(db)


def get_current_user_with_query_token(
    request: Request,
    db: Session = Depends(get_db),
    token: Optional[str] = None,
) -> User:
    """Return the default local user (no token required)."""
    return _get_or_create_default_user(db)


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Kept for API compatibility — always returns the default user."""
    return _get_or_create_default_user(db)
