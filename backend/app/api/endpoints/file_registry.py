from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.api import deps
from app.models.job import Job
from app.models.job_result import JobResult
from app.models.user import User

router = APIRouter()

@router.get("/jobs/{job_id}/file-registry", response_model=Dict[str, List[str]])
def get_job_file_registry(
    job_id: int = Path(..., title="The ID of the job to get file registry for"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get the file registry for a specific job.
    Returns a dictionary with file types as keys and lists of file URLs as values.
    """
    print(f"\n--- FILE REGISTRY ENDPOINT ---")
    print(f"Job ID: {job_id}")
    print(f"Authenticated as: {current_user.id} ({current_user.email})")
    
    # Verify job exists
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        print(f"Job {job_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    print(f"Found job: {job.id} (owner_id: {job.owner_id})")
    
    # Check permissions
    if job.owner_id != current_user.id and not current_user.is_superuser:
        print(f"Permission denied: User {current_user.id} is not the owner of job {job.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Get all job results for this job
    results = db.query(JobResult).filter(JobResult.job_id == job_id).all()
    
    # Organize files by type
    file_registry = {}
    
    for result in results:
        file_type = result.result_type.value  # e.g., "video", "subtitle", "audio"
        if file_type not in file_registry:
            file_registry[file_type] = []
        
        # Add the file URL to the appropriate type
        if result.file_url:
            file_registry[file_type].append(result.file_url)
    
    # Add the source video if it exists
    if job.source_video_url:
        if 'video' not in file_registry:
            file_registry['video'] = []
        file_registry['video'].append(job.source_video_url)
    
    print(f"Returning file registry: {file_registry}")
    return file_registry