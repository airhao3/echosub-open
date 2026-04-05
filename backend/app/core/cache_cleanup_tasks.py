import logging
from celery import Celery
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.cache_cleanup_service import cache_cleanup_service

logger = logging.getLogger(__name__)
settings = get_settings()

# Create Celery instance
celery_app = Celery(
    "cache_cleanup",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)


@celery_app.task(name="cleanup_old_job_caches")
def cleanup_old_job_caches_task(max_jobs: int = 100):
    """
    Celery task to clean up old job caches.
    This task should be scheduled to run periodically.
    """
    if not settings.AUTO_CLEANUP_LOCAL_CACHE:
        logger.info("Auto cleanup is disabled, skipping cleanup task")
        return {"status": "skipped", "reason": "auto_cleanup_disabled"}
    
    logger.info(f"Starting scheduled cache cleanup for up to {max_jobs} jobs")
    
    db = SessionLocal()
    try:
        results = cache_cleanup_service.cleanup_old_jobs(db, max_jobs)
        
        # Summarize results
        total_jobs = len(results)
        successful = len([r for r in results if r.get("status") == "completed"])
        failed = len([r for r in results if r.get("status") in ["failed", "error"]])
        
        total_files_cleaned = sum(r.get("files_cleaned", 0) for r in results)
        total_bytes_freed = sum(r.get("bytes_freed", 0) for r in results)
        
        summary = {
            "status": "completed",
            "total_jobs_processed": total_jobs,
            "successful_cleanups": successful,
            "failed_cleanups": failed,
            "total_files_cleaned": total_files_cleaned,
            "total_bytes_freed": total_bytes_freed,
            "total_mb_freed": round(total_bytes_freed / (1024 * 1024), 2)
        }
        
        logger.info(f"Scheduled cache cleanup completed: {summary}")
        return summary
        
    except Exception as e:
        logger.error(f"Error in scheduled cache cleanup: {e}")
        return {"status": "error", "error": str(e)}
        
    finally:
        db.close()


@celery_app.task(name="sync_pending_files")
def sync_pending_files_task():
    """
    Celery task to sync any pending files to S3.
    This can be used to ensure all files are properly synced.
    """
    if settings.CACHE_ONLY_MODE:
        logger.info("Cache-only mode enabled, skipping sync task")
        return {"status": "skipped", "reason": "cache_only_mode"}
    
    logger.info("Starting pending files sync task")
    
    try:
        # This is a placeholder - you might want to implement a queue
        # of pending files to sync, or scan for files that exist locally
        # but not in S3
        
        # For now, just return a placeholder response
        return {
            "status": "completed",
            "message": "Pending files sync task completed (placeholder implementation)"
        }
        
    except Exception as e:
        logger.error(f"Error in pending files sync: {e}")
        return {"status": "error", "error": str(e)}


# Celery beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    'cleanup-old-caches': {
        'task': 'cleanup_old_job_caches',
        'schedule': 3600.0,  # Run every hour
        'kwargs': {'max_jobs': 50}
    },
    'sync-pending-files': {
        'task': 'sync_pending_files',
        'schedule': 1800.0,  # Run every 30 minutes
    },
}

celery_app.conf.timezone = 'UTC'


def setup_cleanup_tasks():
    """
    Setup function to initialize cleanup tasks.
    Call this during application startup.
    """
    if settings.AUTO_CLEANUP_LOCAL_CACHE:
        logger.info("Cache cleanup tasks enabled")
        logger.info(f"Cleanup delay: {settings.CLEANUP_DELAY_HOURS} hours")
        logger.info(f"Keep recent files: {settings.KEEP_RECENT_FILES_HOURS} hours")
    else:
        logger.info("Cache cleanup tasks disabled")
