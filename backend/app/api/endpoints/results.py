import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.models.job import Job
from app.models.job_result import JobResult, ResultType

def is_browser_compatible_format(file_path: str) -> bool:
    """Check if video format is browser-compatible"""
    ext = os.path.splitext(file_path.lower())[1]
    # Formats that are widely supported by modern browsers
    compatible_formats = {'.mp4', '.webm', '.ogg', '.m4v'}
    return ext in compatible_formats

router = APIRouter()
logger = logging.getLogger(__name__)

@router.api_route("/{job_id}/original_video", methods=["GET", "HEAD"])
async def get_original_video(
    request: Request,
    job_id: int,
    streamable: bool = Query(False, description="Whether to set Content-Disposition to inline for streaming"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> FileResponse:
    """
    Get the original video for a job
    """
    logger.info(f"Original video request for job {job_id}, streamable: {streamable}")
    
    # Validate job ownership
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to access this job")
    
    # Optimized: Try jobs.source_video_url first (fastest)
    video_path = job.source_video_url
    logger.info(f"Job {job_id} source_video_url: {video_path}")
    
    # If no source_video_url, try job_results table (indexed query)
    if not video_path:
        logger.info(f"No source_video_url for job {job_id}, checking job_results table")
        original_result = db.query(JobResult).filter(
            JobResult.job_id == job_id,
            JobResult.result_type == ResultType.ORIGINAL_VIDEO
        ).first()
        
        if original_result and original_result.file_path:
            video_path = original_result.file_path
            logger.info(f"Found original video in results table: {video_path}")
    
    # Final validation - only check if we have a path
    if not video_path:
        logger.error(f"No video path found for job {job_id}")
        raise HTTPException(status_code=404, detail="Original video not found")
    
    # Quick existence check (removed expensive filesystem search)
    if not os.path.exists(video_path):
        logger.error(f"Video file does not exist: {video_path}")
        raise HTTPException(status_code=404, detail="Video file not found on disk")
    
    mime_type = get_video_mime_type(video_path)
    logger.info(f"Serving original video: {video_path} with MIME type: {mime_type}")
    
    return FileResponse(
        path=video_path,
        media_type=mime_type,
        filename=os.path.basename(video_path),
        content_disposition_type="inline" if streamable else "attachment",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Type": mime_type
        }
    )

@router.api_route("/{job_id}/subtitled_video", methods=["GET", "HEAD"])
async def get_subtitled_video(
    request: Request,
    job_id: int,
    language: str = Query(..., description="Language code (e.g., 'en', 'zh')"),
    streamable: bool = Query(False, description="Whether to set Content-Disposition to inline for streaming"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> FileResponse:
    """
    Get the subtitled video for a job
    """
    logger.info(f"Subtitled video request for job {job_id}, language: {language}, streamable: {streamable}")
    
    # Validate job ownership
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to access this job")
    
    # Directly query the database for subtitled video
    try:
        # Get exact match first
        result = db.query(JobResult).filter(
            JobResult.job_id == job_id,
            JobResult.result_type == ResultType.SUBTITLED_VIDEO,
            JobResult.language == language
        ).first()
        
        # If not found with that language, try any language
        if not result:
            result = db.query(JobResult).filter(
                JobResult.job_id == job_id,
                JobResult.result_type == ResultType.SUBTITLED_VIDEO
            ).first()
        
        if not result or not (getattr(result, 'file_url', None) or getattr(result, 'file_path', None)):
            # Try to find subtitled video files by searching common locations
            logger.info(f"Attempting to find subtitled video for job {job_id} language {language} in file system")
            job = db.query(Job).filter(Job.id == job_id).first()
            
            from app.core.config import get_settings
            settings = get_settings()
            storage_base = settings.STORAGE_BASE_DIR
            possible_paths = [
                os.path.join(storage_base, "users", str(job.owner_id), "jobs", str(job_id), "source", f"{job.title}_subtitled.mp4"),
                os.path.join(storage_base, "users", str(job.owner_id), "jobs", str(job_id), "source"),
                os.path.join(storage_base, "jobs", str(job_id)),
            ]
            
            found_video = None
            for search_path in possible_paths:
                if os.path.isfile(search_path):
                    found_video = search_path
                    break
                elif os.path.isdir(search_path):
                    # Search for subtitled video files in directory
                    for file in os.listdir(search_path):
                        if file.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')) and 'subtitled' in file.lower():
                            found_video = os.path.join(search_path, file)
                            break
                    if found_video:
                        break
            
            if found_video and os.path.exists(found_video):
                logger.info(f"Found subtitled video at: {found_video}")
                mime_type = get_video_mime_type(found_video)
                return FileResponse(
                    path=found_video,
                    media_type=mime_type,
                    filename=os.path.basename(found_video),
                    content_disposition_type="inline" if streamable else "attachment",
                    headers={
                        "Accept-Ranges": "bytes",
                        "Content-Type": mime_type
                    }
                )
            else:
                raise HTTPException(status_code=404, detail="Subtitled video not found")
        
        video_path = getattr(result, 'file_url', None) or getattr(result, 'file_path', None)
        
        # Simple check if file exists
        if not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Subtitled video file not found on disk")
        
        # Use result mime_type if available, otherwise detect from file
        mime_type = result.mime_type or get_video_mime_type(video_path)
        logger.info(f"Serving subtitled video: {video_path} with MIME type: {mime_type}")
        
        return FileResponse(
            path=video_path,
            media_type=mime_type,
            filename=result.file_name or os.path.basename(video_path),
            content_disposition_type="inline" if streamable else "attachment",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Type": mime_type
            }
        )
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Error in subtitled video retrieval: {e}")
        raise HTTPException(status_code=500, detail=f"Error streaming video: {str(e)}")
