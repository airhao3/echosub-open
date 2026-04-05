"""
Usage tracking service (Open Source version)
Tracks usage counters without plan-based quota enforcement.
"""
import logging
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User

logger = logging.getLogger(__name__)


class UsageTrackerService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_usage_and_limits(self, user_id: int) -> dict:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        return {
            "limits": {
                "video_minutes_per_month": None,  # Unlimited in open-source
                "storage_mb": None,
                "projects": None,
            },
            "current_usage": {
                "video_minutes_used": user.video_minutes_used,
                "storage_used_mb": user.storage_used_mb,
                "projects_used": user.projects_used,
            },
        }

    def check_and_update_video_minutes(self, user_id: int, minutes_to_add: int) -> None:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user.video_minutes_used += minutes_to_add
        self.db.commit()
        self.db.refresh(user)

    def check_and_update_storage_mb(self, user_id: int, mb_to_add: float) -> None:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user.storage_used_mb += mb_to_add
        self.db.commit()
        self.db.refresh(user)

    def check_and_update_projects(self, user_id: int, projects_to_add: int = 1) -> None:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user.projects_used += projects_to_add
        self.db.commit()
        self.db.refresh(user)

    def check_and_update_translation_chars(self, user_id: int, chars_to_add: int) -> None:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if not hasattr(user, 'translation_chars_used'):
            user.translation_chars_used = 0
        user.translation_chars_used = (user.translation_chars_used or 0) + chars_to_add
        self.db.commit()
        self.db.refresh(user)

    def reset_usage_counters(self, user_id: int) -> None:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return

        user.video_minutes_used = 0
        user.storage_used_mb = 0
        user.projects_used = 0
        self.db.commit()
        self.db.refresh(user)
