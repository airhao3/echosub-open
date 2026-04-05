"""
Language Slots tracking and management service (Open Source version)
"""
import logging
from typing import List, Set, Dict, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user import User
from app.models.job import Job, JobStatus

logger = logging.getLogger(__name__)

class LanguageSlotsService:
    """Service for managing language slots usage tracking"""

    @staticmethod
    def calculate_language_slots_from_string(target_languages: str) -> int:
        """
        Calculate the number of language slots required for a target_languages string.
        """
        if not target_languages or target_languages.strip() == "":
            return 0
        languages = [lang.strip().lower() for lang in target_languages.split(',') if lang.strip()]
        return len(set(languages))

    @staticmethod
    def calculate_language_slots_from_list(target_languages: List[str]) -> int:
        """
        Calculate the number of language slots required for a list of languages.
        """
        if not target_languages:
            return 0
        return len(set(lang.strip().lower() for lang in target_languages if lang.strip()))

    @staticmethod
    def get_user_active_languages(db: Session, user_id: int) -> Set[str]:
        """
        Get all unique target languages currently being used by a user's active jobs.
        """
        active_jobs = db.query(Job).filter(
            Job.owner_id == user_id,
            Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING])
        ).all()

        all_languages = set()
        for job in active_jobs:
            if job.target_languages:
                job_languages = {
                    lang.strip().lower()
                    for lang in job.target_languages.split(',')
                    if lang.strip()
                }
                all_languages.update(job_languages)

        return all_languages

    @staticmethod
    def check_language_slots_quota(
        db: Session,
        user_id: int,
        new_target_languages: str,
        calculation_method: str = "cumulative"
    ) -> Tuple[bool, str, Dict]:
        """
        Check if user can create a job with the specified target languages.
        Open-source version: always allows (no plan limits).
        """
        return True, "", {
            'new_job_slots': LanguageSlotsService.calculate_language_slots_from_string(new_target_languages),
            'calculation_method': calculation_method
        }

    @staticmethod
    def track_language_slots_usage(
        db: Session,
        user_id: int,
        target_languages: str,
        calculation_method: str = "cumulative"
    ) -> None:
        """
        Track language slots usage when a job is created.
        Open-source version: logging only, no quota enforcement.
        """
        slots = LanguageSlotsService.calculate_language_slots_from_string(target_languages)
        logger.info(f"Language slots usage for user {user_id}: "
                    f"target_languages='{target_languages}', slots={slots}")
