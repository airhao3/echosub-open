"""
User-specific job endpoints using user job numbers instead of global IDs
"""
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api import deps
from app.models.user import User
from app.models.job import Job, JobStatus
from app.schemas.job import Job as JobSchema
from app.services.job_numbering_service import JobNumberingService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/{user_job_number}", response_model=JobSchema)
def get_user_job(
    user_job_number: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get job by user-specific job number.
    """
    job = JobNumberingService.get_job_by_user_number(db, current_user.id, user_job_number)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job #{user_job_number} not found"
        )
    
    # Add subtitle language preferences to the job
    from app.services.subtitle_preferences import SubtitlePreferencesService
    subtitle_prefs = SubtitlePreferencesService()
    job.subtitle_languages = subtitle_prefs.get_subtitle_languages(job.id)
    
    return job

@router.get("/{user_job_number}/status", response_model=Dict[str, Any])
def get_user_job_status(
    user_job_number: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Dict[str, Any]:
    """
    Get detailed status information for a user job by job number.
    """
    job = JobNumberingService.get_job_by_user_number(db, current_user.id, user_job_number)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job #{user_job_number} not found"
        )
    
    # Import required services
    from app.services.status_service import StatusUpdateService
    from app.services.stage_mapping_service import StageMappingService
    
    # Use the StatusUpdateService to get the detailed job status
    detailed_status = StatusUpdateService.get_job_status(db, job.id)
    
    if detailed_status is None:
        # Fallback for jobs without detailed status tracking
        detailed_status = {
            "job_id": job.id,
            "user_job_number": user_job_number,
            "status": job.status.value,
            "progress": job.progress or 0,
            "status_message": job.error_message or "Status tracking not fully initialized.",
            "steps": []
        }
    else:
        # Add user job number to the response
        detailed_status["user_job_number"] = user_job_number
    
    try:
        # TEMPORARY: Disable StageMappingService due to performance issues
        # Create user-friendly progress update using stage mapping
        # frontend_status = StageMappingService.create_progress_update_for_frontend(
        #     job_id=job.id,
        #     backend_stages_completed=[],
        #     current_stage=None,
        #     current_progress=detailed_status.get("progress", 0),
        #     status_message=detailed_status.get("status_message", "")
        # )
        
        # Provide fallback simplified steps
        simplified_steps = [
            {"step_name": "UPLOADING", "name": "Uploading", "status": "pending", "progress": 0.0, "details": "Uploading and preparing your video", "icon": "📥"},
            {"step_name": "ANALYZING", "name": "Analyzing", "status": "pending", "progress": 0.0, "details": "Extracting audio and analyzing content", "icon": "🔍"},
            {"step_name": "TRANSCRIBING", "name": "Transcribing", "status": "pending", "progress": 0.0, "details": "Converting speech to text", "icon": "🔤"},
            {"step_name": "TRANSLATING", "name": "Translating", "status": "pending", "progress": 0.0, "details": "Translating and optimizing text", "icon": "🌐"},
            {"step_name": "GENERATING", "name": "Generating", "status": "pending", "progress": 0.0, "details": "Creating subtitles and processing video", "icon": "🎬"},
            {"step_name": "FINALIZING", "name": "Finalizing", "status": "pending", "progress": 0.0, "details": "Exporting files and cleanup", "icon": "📁"}
        ]
        
        # Merge frontend-friendly data with existing detailed status
        detailed_status["simplified_steps"] = simplified_steps
        detailed_status["current_frontend_stage"] = None
        detailed_status["user_friendly_message"] = detailed_status.get("status_message", "Processing...")
        
    except Exception as e:
        logger.warning(f"Failed to create simplified frontend stages for user job {user_job_number}: {str(e)}")
    
    return detailed_status

@router.delete("/{user_job_number}", response_model=Dict[str, str])
def delete_user_job(
    user_job_number: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Delete job by user-specific job number.
    """
    job = JobNumberingService.get_job_by_user_number(db, current_user.id, user_job_number)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job #{user_job_number} not found"
        )
    
    # Import cleanup function
    from app.api.endpoints.jobs import cleanup_job_files
    
    # Clean up files before deleting the job
    cleanup_job_files(job)
    
    # Delete the job
    db.delete(job)
    db.commit()
    
    return {
        "status": "success",
        "message": f"Job #{user_job_number} has been deleted"
    }

class BulkDeleteRequest(BaseModel):
    user_job_numbers: List[int]

@router.post("/bulk_delete", response_model=Dict[str, Any])
def bulk_delete_user_jobs(
    request: BulkDeleteRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Delete multiple jobs by user-specific job numbers.
    """
    deleted_count = 0
    failed_jobs = []
    
    for user_job_number in request.user_job_numbers:
        try:
            job = JobNumberingService.get_job_by_user_number(db, current_user.id, user_job_number)
            if not job:
                failed_jobs.append({
                    "user_job_number": user_job_number,
                    "reason": "Job not found"
                })
                continue
            
            # Import cleanup function
            from app.api.endpoints.jobs import cleanup_job_files
            
            # Clean up files before deleting the job
            cleanup_job_files(job)
            
            # Delete the job
            db.delete(job)
            deleted_count += 1
            
        except Exception as e:
            failed_jobs.append({
                "user_job_number": user_job_number,
                "reason": str(e)
            })
    
    # Commit all deletions
    db.commit()
    
    return {
        "status": "success",
        "deleted_count": deleted_count,
        "total_requested": len(request.user_job_numbers),
        "failed_jobs": failed_jobs,
        "message": f"Successfully deleted {deleted_count} out of {len(request.user_job_numbers)} jobs"
    }

@router.get("/", response_model=List[JobSchema])
def list_user_jobs(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    with_results_only: bool = Query(False, description="Only return jobs that have video results"),
) -> Any:
    """
    List all jobs for the current user, ordered by user job number.
    """
    if with_results_only:
        # Only return jobs that have original video results
        from app.models.job_result import JobResult
        jobs = db.query(Job).join(
            JobResult, Job.id == JobResult.job_id
        ).filter(
            Job.owner_id == current_user.id,
            JobResult.result_type == 'ORIGINAL_VIDEO'
        ).order_by(Job.user_job_number.asc()).offset(skip).limit(limit).all()
    else:
        jobs = db.query(Job).filter(
            Job.owner_id == current_user.id
        ).order_by(Job.user_job_number.asc()).offset(skip).limit(limit).all()
    
    # Add subtitle language preferences to each job
    from app.services.subtitle_preferences import SubtitlePreferencesService
    subtitle_prefs = SubtitlePreferencesService()
    
    for job in jobs:
        job.subtitle_languages = subtitle_prefs.get_subtitle_languages(job.id)
        
    return jobs

@router.get("/{user_job_number}/preview/options")
async def get_user_job_preview_options(
    user_job_number: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get preview options for a user job by job number.
    This endpoint provides the same functionality as /api/v1/preview/options/{job_id}
    but uses user job numbers instead of global job IDs.
    """
    logger.info(f"[User Job Preview] Request for user job number {user_job_number}")
    
    # Get the job by user job number
    job = JobNumberingService.get_job_by_user_number(db, current_user.id, user_job_number)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job #{user_job_number} not found"
        )
    
    # Use the existing preview options endpoint logic
    from app.api.endpoints.preview import get_preview_options
    
    try:
        # Call the existing preview options function with the global job ID
        preview_options = await get_preview_options(job.id, db, current_user)
        
        # Add user job number to the response for frontend convenience
        preview_options_dict = preview_options.dict() if hasattr(preview_options, 'dict') else preview_options
        preview_options_dict["user_job_number"] = user_job_number
        
        logger.info(f"[User Job Preview] Found {len(preview_options_dict.get('available_previews', []))} preview options for user job {user_job_number}")
        
        return preview_options_dict
        
    except Exception as e:
        logger.error(f"[User Job Preview] Error getting preview options for user job {user_job_number}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting preview options for job #{user_job_number}"
        )