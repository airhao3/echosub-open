import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.services.cache_cleanup_service import cache_cleanup_service
from app.core.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()


@router.get("/stats")
async def get_cache_stats(
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    Get local cache usage statistics.
    Only available to superusers.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        stats = cache_cleanup_service.get_cache_usage_stats()
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cache statistics")


@router.post("/cleanup/job/{job_id}")
async def cleanup_job_cache(
    job_id: int,
    force: bool = Query(False, description="Force cleanup without safety checks"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    Clean up local cache for a specific job.
    """
    # Get the job to verify ownership
    from app.models.job import Job
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if user owns the job or is superuser
    if job.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to manage this job")
    
    try:
        # Run cleanup in background
        background_tasks.add_task(
            cache_cleanup_service.cleanup_completed_job,
            job_id=job_id,
            user_id=job.owner_id,
            force=force
        )
        
        return {
            "success": True,
            "message": f"Cache cleanup started for job {job_id}",
            "job_id": job_id,
            "force": force
        }
        
    except Exception as e:
        logger.error(f"Error starting cache cleanup for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start cache cleanup")


@router.post("/cleanup/old-jobs")
async def cleanup_old_jobs(
    max_jobs: int = Query(50, description="Maximum number of jobs to process"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    Clean up local cache for old completed jobs.
    Only available to superusers.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Run cleanup in background
        background_tasks.add_task(
            cache_cleanup_service.cleanup_old_jobs,
            db=db,
            max_jobs=max_jobs
        )
        
        return {
            "success": True,
            "message": f"Bulk cache cleanup started for up to {max_jobs} old jobs",
            "max_jobs": max_jobs
        }
        
    except Exception as e:
        logger.error(f"Error starting bulk cache cleanup: {e}")
        raise HTTPException(status_code=500, detail="Failed to start bulk cache cleanup")


@router.post("/sync-file")
async def sync_file_to_s3(
    file_path: str = Query(..., description="File path to sync to S3"),
    cleanup_after: bool = Query(True, description="Clean up local file after sync"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    Manually sync a file to S3 and optionally clean up local copy.
    Only available to superusers.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Run sync in background
        background_tasks.add_task(
            cache_cleanup_service.sync_and_cleanup_file,
            file_path=file_path,
            cleanup_after_sync=cleanup_after
        )
        
        return {
            "success": True,
            "message": f"File sync started: {file_path}",
            "file_path": file_path,
            "cleanup_after": cleanup_after
        }
        
    except Exception as e:
        logger.error(f"Error starting file sync for {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start file sync")


@router.get("/config")
async def get_cleanup_config(
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    Get current cache cleanup configuration.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return {
        "success": True,
        "config": {
            "auto_cleanup_enabled": settings.AUTO_CLEANUP_LOCAL_CACHE,
            "cleanup_delay_hours": settings.CLEANUP_DELAY_HOURS,
            "keep_recent_files_hours": settings.KEEP_RECENT_FILES_HOURS,
            "s3_direct_access": settings.S3_DIRECT_ACCESS,
            "cache_only_mode": settings.CACHE_ONLY_MODE,
            "storage_backend": settings.STORAGE_BACKEND
        }
    }
