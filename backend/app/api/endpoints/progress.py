from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional

from app.services import progress_cache
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.job_service import JobService
from app.services.status_service import StatusUpdateService
from app.services.stage_mapping_service import StageMappingService
from app.core.config import get_settings
import time

router = APIRouter()

@router.get("/jobs/{job_id}/status")
def get_job_status(job_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get the status and progress of a job.

    This endpoint provides the authoritative status from the database, supplemented
    by real-time progress information from the cache.
    """
    settings = get_settings()
    job_service = JobService(db, settings.STORAGE_BASE_DIR)
    
    # The database is the source of truth for job existence and status.
    job = job_service.get_job(job_id)
    if not job or job.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found.")

    # The cache provides real-time, fine-grained progress updates.
    progress_data = progress_cache.get_progress(job_id)

    # Get database step information
    db_status = StatusUpdateService.get_job_status(db, job_id)
    
    # Combine realtime cache data with database data
    combined_data = {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "realtime_progress": progress_data,  # ProcessingLogger detailed progress
        "database_steps": db_status.get("steps", []) if db_status else [],  # StatusUpdateService steps
    }
    
    return combined_data


@router.get("/jobs/{job_id}/status/unified")
def get_unified_job_status(job_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get unified job status that combines ProcessingLogger real-time data with database persistence.
    
    This endpoint provides the best of both worlds:
    - Real-time detailed progress from ProcessingLogger cache
    - Persistent step status from database 
    - Simplified frontend-friendly format via StageMappingService
    """
    settings = get_settings()
    job_service = JobService(db, settings.STORAGE_BASE_DIR)
    
    # Verify job exists and belongs to user
    job = job_service.get_job(job_id)
    if not job or job.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found.")
    
    # Get real-time progress from cache (ProcessingLogger data)
    realtime_data = progress_cache.get_progress(job_id)
    
    # Get persistent data from database (StatusUpdateService data)
    db_status = StatusUpdateService.get_job_status(db, job_id)
    
    # Extract information for stage mapping
    completed_backend_stages = []
    current_backend_stage = None
    current_progress = 0.0
    status_message = ""
    
    if realtime_data and "events" in realtime_data:
        # Process real-time events to determine completed stages
        for event in realtime_data["events"]:
            if event.get("event_type") == "stage_complete" and event.get("status") == "completed":
                stage_name = event.get("stage")
                if stage_name:
                    completed_backend_stages.append(stage_name)
            elif event.get("event_type") == "stage_start":
                current_backend_stage = event.get("stage")
                current_progress = event.get("progress", 0.0)
                status_message = event.get("detail", "")
    
    # Fallback to database data if cache is empty
    if not completed_backend_stages and db_status and "steps" in db_status:
        for step in db_status["steps"]:
            if step.get("status") == "completed":
                # Map database step names back to processing stages (reverse mapping)
                pass  # This would need a reverse mapping implementation
    
    # Create unified response using StageMappingService
    try:
        unified_response = StageMappingService.create_progress_update_for_frontend(
            job_id=job_id,
            backend_stages_completed=completed_backend_stages,
            current_stage=current_backend_stage,
            current_progress=current_progress,
            status_message=status_message or db_status.get("status_message", "") if db_status else ""
        )
        
        # Add additional context
        unified_response["job_status"] = job.status
        unified_response["error_message"] = job.error_message
        unified_response["has_realtime_data"] = bool(realtime_data)
        unified_response["has_database_data"] = bool(db_status)
        
        return unified_response
        
    except Exception as e:
        # Fallback response
        return {
            "job_id": job_id,
            "status": job.status,
            "progress": job.progress or 0,
            "message": job.error_message or "Processing...",
            "error": f"Failed to create unified response: {str(e)}",
            "steps": StageMappingService.get_simplified_steps_for_frontend()
        }
