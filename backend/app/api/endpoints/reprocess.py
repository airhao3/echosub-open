import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.models.job import Job, JobStatus
from app.schemas.job import Job as JobSchema
from app.services.workflow_service import WorkflowService
from app.services.video_tracking_service import VideoTrackingService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/{job_id}", response_model=Dict[str, Any])
def reprocess_job(
    *,
    job_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    background_tasks: BackgroundTasks,
) -> Any:
    """
    Reprocess an existing job.
    This will increment the processing count in the video tracking system.
    """
    # Check if job exists and belongs to the current user
    job = db.query(Job).filter(Job.id == job_id, Job.owner_id == current_user.id).first()
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found or you don't have permission to access it"
        )
    
    # Initialize services
    workflow_service = WorkflowService(db)
    video_tracking = VideoTrackingService(db)
    
    try:
        # Check if content hash is available
        if not job.content_hash:
            logger.warning(f"Job {job_id} doesn't have a content hash. Cannot track reprocessing.")
            return {
                "job_id": job_id,
                "status": "reprocessing",
                "message": "Job is being reprocessed, but tracking is limited (no content hash)"
            }
        
        # Update video processing record to indicate reprocessing
        if job.content_hash:
            # Update processing count for this video
            lang = job.target_languages if job.target_languages else "auto"
            result = video_tracking.register_processing_start(
                job.content_hash, 
                lang, 
                "subtitled_video", 
                job.video_filename,
                job_id
            )
            logger.info(f"Registered reprocessing for job {job_id} with hash {job.content_hash}. " +
                       f"Processing count: {result.get('process_count', 0)}")
        
        # Reset job status to start reprocessing
        job.status = JobStatus.QUEUED
        job.progress = 0
        job.completed_at = None
        db.commit()
        
        # Start processing in background
        background_tasks.add_task(
            workflow_service.process_job,
            job_id=job_id,
            force_reprocess=True  # Ensure we reprocess even if results exist
        )
        
        return {
            "job_id": job_id,
            "status": "reprocessing",
            "message": "Job has been queued for reprocessing"
        }
        
    except Exception as e:
        logger.error(f"Error reprocessing job {job_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error reprocessing job: {str(e)}"
        )
