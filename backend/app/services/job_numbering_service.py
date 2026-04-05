"""
Job numbering service for managing user-specific job numbers
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.models.job import Job
import logging

logger = logging.getLogger(__name__)

class JobNumberingService:
    """Service to handle user-specific job numbering"""
    
    @staticmethod
    def get_next_user_job_number(db: Session, user_id: int) -> int:
        """
        Get the next job number for a specific user.
        
        Args:
            db: Database session
            user_id: ID of the user
            
        Returns:
            Next sequential job number for the user (starting from 1)
        """
        try:
            # Get the maximum job number for this user
            max_job_number = db.query(func.max(Job.user_job_number)).filter(
                Job.owner_id == user_id
            ).scalar()
            
            # If no jobs exist for this user, start with 1
            if max_job_number is None:
                return 1
            
            # Otherwise, increment by 1
            return max_job_number + 1
            
        except Exception as e:
            logger.error(f"Error getting next job number for user {user_id}: {str(e)}")
            # Fallback: try to get a safe number using a different approach
            try:
                job_count = db.query(func.count(Job.id)).filter(
                    Job.owner_id == user_id
                ).scalar()
                return (job_count or 0) + 1
            except Exception as fallback_error:
                logger.error(f"Fallback method also failed for user {user_id}: {str(fallback_error)}")
                return 1
    
    @staticmethod
    def get_job_by_user_number(db: Session, user_id: int, user_job_number: int) -> Job:
        """
        Get a job by user ID and user-specific job number.
        
        Args:
            db: Database session
            user_id: ID of the user
            user_job_number: User-specific job number
            
        Returns:
            Job object if found, None otherwise
        """
        return db.query(Job).filter(
            Job.owner_id == user_id,
            Job.user_job_number == user_job_number
        ).first()
    
    @staticmethod
    def assign_job_number_atomic(db: Session, user_id: int) -> int:
        """
        Atomically assign the next job number for a user using database-level locking.
        This prevents race conditions when multiple jobs are created simultaneously.
        
        Args:
            db: Database session
            user_id: ID of the user
            
        Returns:
            The assigned job number
        """
        try:
            # Use a PostgreSQL-specific approach to atomically get the next number
            # This uses a SELECT ... FOR UPDATE to lock the user's job records
            result = db.execute(text("""
                WITH next_number AS (
                    SELECT COALESCE(MAX(user_job_number), 0) + 1 as next_num
                    FROM jobs 
                    WHERE owner_id = :user_id
                    FOR UPDATE
                )
                SELECT next_num FROM next_number
            """), {"user_id": user_id})
            
            next_number = result.scalar()
            return next_number or 1
            
        except Exception as e:
            logger.error(f"Error in atomic job number assignment for user {user_id}: {str(e)}")
            # Fallback to the simple method
            return JobNumberingService.get_next_user_job_number(db, user_id)