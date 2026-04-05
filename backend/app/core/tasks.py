"""Celery task definitions for EchoSub"""

import logging
from datetime import datetime
from celery import Celery
from sqlalchemy.sql.expression import text
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

celery_app = Celery(
    "videolingo_worker",
    backend=settings.CELERY_RESULT_BACKEND,
    broker=settings.CELERY_BROKER_URL,
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],  # Only accept json content
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    beat_schedule = {}
)

@celery_app.task(name="process_video_job", bind=True, max_retries=3, default_retry_delay=60)
def process_video_job(self, job_id: int):
    """
    Process video job in the background.
    This task now accepts content_hash to prevent race conditions.
    """
    import time
    import socket
    import os
    import json
    import traceback
    from sqlalchemy.exc import SQLAlchemyError
    from app.core.database import SessionLocal
    from app.services.workflow_service import WorkflowService
    from app.services.job_service import JobService
    from app.models.job import Job, JobStatus
    from app.core.config import get_settings

    settings = get_settings()
    task_id = self.request.id or "<unknown>"
    hostname = socket.gethostname()
    process_id = os.getpid()
    start_time = time.time()
    
    logger.info(f"[TASK:{task_id}] Starting video processing for job {job_id} on {hostname} (PID: {process_id})")
    
    # Create a new database session for this task
    db = SessionLocal()
    try:
        # Step 1: Get job and validate
        job_service = JobService(db, settings.STORAGE_BASE_DIR)
        job = job_service.get_job_by_id(job_id)

        if not job:
            logger.error(f"[TASK:{task_id}] Job {job_id} not found in database.")
            return {"job_id": job_id, "status": "not_found", "error": f"Job {job_id} not found"}

        # Step 2: Update job status to PROCESSING.
        old_status = job.status.value if hasattr(job.status, 'value') else str(job.status)
        job.status = JobStatus.PROCESSING
        job.progress = max(job.progress or 0, 5) # Ensure progress is at least 5%
        db.commit()
        db.refresh(job)
        logger.info(f"[TASK:{task_id}] Updated job status from {old_status} to {job.status.value}.")

        # Step 3: Log execution context for debugging.
        execution_context = {
            "task_id": task_id,
            "job_id": job_id,
            "hostname": hostname,
            "pid": process_id,
            "start_time": time.strftime('%Y-%m-%d %H:%M:%S'),
            "task_retries": self.request.retries,
        }
        logger.info(f"[TASK:{task_id}] Execution context: {json.dumps(execution_context)}")

        # Step 4: Initialize workflow and process the job.
        logger.info(f"[TASK:{task_id}] Initializing WorkflowService...")
        workflow_service = WorkflowService(db)
        
        try:
            # Process the job
            logger.info(f"[TASK:{task_id}] Starting job processing...")
            result = workflow_service.process_job(job_id)
            
            # Refresh the job object to ensure it's still attached to the session
            db.refresh(job)
            
            # If we get here, processing was successful
            if result:
                # Update the job status using the job we already have in the session
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.utcnow()
                job.progress = 100
                db.commit()
                
                execution_time = time.time() - start_time
                logger.info(f"[TASK:{task_id}] Successfully processed job {job_id} in {execution_time:.2f}s")
                
                # Schedule cache cleanup if enabled
                try:
                    from app.core.config import get_settings
                    from app.services.cache_cleanup_service import cache_cleanup_service
                    
                    settings = get_settings()
                    if settings.AUTO_CLEANUP_LOCAL_CACHE and not settings.CACHE_ONLY_MODE:
                        # Schedule cleanup task to run after delay
                        from app.core.cache_cleanup_tasks import cleanup_old_job_caches_task
                        cleanup_old_job_caches_task.apply_async(
                            kwargs={"max_jobs": 1},
                            countdown=settings.CLEANUP_DELAY_HOURS * 3600  # Convert hours to seconds
                        )
                        logger.info(f"[TASK:{task_id}] Scheduled cache cleanup for job {job_id} in {settings.CLEANUP_DELAY_HOURS} hours")
                        
                except Exception as cleanup_error:
                    logger.warning(f"[TASK:{task_id}] Failed to schedule cleanup for job {job_id}: {cleanup_error}")
                    # Don't fail the job if cleanup scheduling fails
                
                return {
                    "job_id": job_id,
                    "status": job.status.value,
                    "progress": job.progress,
                    "execution_time": f"{execution_time:.2f}s"
                }
            else:
                raise ValueError(f"Job {job_id} processing returned None")
                
        except Exception as e:
            # Log the error and update job status
            logger.error(f"[TASK:{task_id}] Error processing job {job_id}: {str(e)}")
            logger.error(f"[TASK:{task_id}] Stack trace: {traceback.format_exc()}")
            
            # Try to update job status to failed
            try:
                # Use a new session to avoid any transaction issues
                with SessionLocal() as new_db:
                    job_to_update = new_db.query(Job).filter(Job.id == job_id).first()
                    if job_to_update:
                        job_to_update.status = JobStatus.FAILED
                        job_to_update.error_message = str(e)[:500]  # Truncate to avoid DB errors
                        new_db.commit()
                        logger.info(f"[TASK:{task_id}] Successfully updated job {job_id} status to FAILED")
            except Exception as update_error:
                logger.error(f"[TASK:{task_id}] Failed to update job status to failed: {str(update_error)}")
                logger.error(f"[TASK:{task_id}] Error details: {traceback.format_exc()}")
            
            # Consider retrying for certain errors
            if self.request.retries < self.max_retries:
                logger.warning(f"[TASK:{task_id}] Retrying job {job_id} (attempt {self.request.retries + 1}/{self.max_retries})")
                try:
                    # Reset job status to PROCESSING for retry
                    with SessionLocal() as retry_db:
                        retry_job = retry_db.query(Job).filter(Job.id == job_id).first()
                        if retry_job:
                            retry_job.status = JobStatus.PROCESSING
                            retry_job.error_message = f"Retrying... (attempt {self.request.retries + 1})"
                            retry_db.commit()
                    raise self.retry(countdown=60, exc=e)
                except Exception as retry_error:
                    logger.error(f"[TASK:{task_id}] Failed to setup retry: {retry_error}")
            
            logger.error(f"[TASK:{task_id}] Job {job_id} failed after {self.request.retries} retries.")

    except Exception as e:
        execution_time = time.time() - start_time
        error_message = f"Error in process_video_job task for job {job_id} after {execution_time:.2f}s: {e}"
        logger.error(f"[TASK:{task_id}] {error_message}")
        logger.error(f"[TASK:{task_id}] Stack trace: {traceback.format_exc()}")
        
        # Attempt to mark the job as FAILED in the database.
        try:
            # Re-fetch job in case the session is in a bad state
            job_to_fail = db.query(Job).filter(Job.id == job_id).first()
            if job_to_fail:
                job_to_fail.status = JobStatus.FAILED

                db.commit()
                logger.info(f"[TASK:{task_id}] Successfully marked job {job_id} as FAILED.")
            else:
                logger.error(f"[TASK:{task_id}] Job {job_id} not found in database when trying to mark as FAILED")
        except Exception as db_error:
            logger.error(f"[TASK:{task_id}] Could not mark job {job_id} as FAILED due to DB error: {db_error}")
            if db:
                db.rollback()
        
        # Do not retry, just log the error
        logger.error(f"[TASK:{task_id}] Job {job_id} failed and will not be retried.")
        
    finally:
        db.close()


@celery_app.task(name="cleanup_job_files")
def cleanup_job_files(job_id: int, days_to_keep: int = 7):
    """
    Clean up temporary job files after a specified period
    """
    import shutil
    import os
    from datetime import datetime, timedelta
    from app.services.job_service import JobService
    from app.core.database import SessionLocal
    
    logger.info(f"Checking if job {job_id} files should be cleaned up")
    
    # Get database session
    db = SessionLocal()
    try:
        # Get data directory from environment or use a default
        from app.core.config import get_settings
        settings = get_settings()
        data_dir = os.environ.get("VIDEOLINGO_DATA_DIR", "/tmp/videolingo_jobs")
        
        # Get job details
        job_service = JobService(db, data_dir)
        job = job_service.get_job_by_id(job_id)
        
        if not job:
            logger.warning(f"Job {job_id} not found, skipping cleanup")
            return
        
        # Only clean up completed or failed jobs older than days_to_keep
        if job.completed_at and (datetime.now() - job.completed_at) > timedelta(days=days_to_keep):
            job_dir = job_service.get_job_directory(job_id)
            
            if os.path.exists(job_dir):
                logger.info(f"Cleaning up files for job {job_id} in {job_dir}")
                shutil.rmtree(job_dir)
                return {"job_id": job_id, "status": "cleaned"}
            else:
                logger.info(f"No files found for job {job_id}, already cleaned")
                return {"job_id": job_id, "status": "already_cleaned"}
        else:
            logger.info(f"Job {job_id} not eligible for cleanup yet")
            return {"job_id": job_id, "status": "not_eligible"}
    finally:
        db.close()


# reset_due_user_usage task removed — no subscription billing in open-source version
