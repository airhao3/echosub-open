"""
Auth endpoints — open-source mode (no login required).

The /login endpoint still exists for API compatibility but always returns
a valid token for the default local user.
"""
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.core import security
from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.token import Token

router = APIRouter()
settings = get_settings()


@router.post("/login", response_model=Token)
def login_access_token(db: Session = Depends(get_db)) -> Any:
    """
    Always returns a valid token for the default local user.
    Accepts any (or no) form data for backward compatibility.
    """
    user = deps._get_or_create_default_user(db)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }


@router.get("/me", response_model=dict)
def read_users_me(current_user=Depends(deps.get_current_user)) -> Any:
    """Get current user information."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser,
    }


@router.post("/test-token", response_model=None)
async def test_token(current_user=Depends(deps.get_current_user)) -> Any:
    """Test access token — always succeeds in open-source mode."""
    return {
        "msg": "Token is valid",
        "user_id": current_user.id,
        "username": current_user.username,
    }
