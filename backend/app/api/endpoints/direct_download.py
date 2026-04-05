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
from app.api.url_token_auth import get_user_from_url_token

import traceback

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/results/{job_id}/original_video")
async def get_original_video_for_preview(
    request: Request,
    job_id: int,
    streamable: bool = Query(False, description="Whether to serve the video for streaming"),
    db: Session = Depends(deps.get_db)
):
    """
    Direct endpoint for original video preview that exactly matches the frontend URL pattern
    """
    logger.info(f"🎯 Direct original video preview request for job {job_id}, streamable: {streamable}")
    
    # Try to get the current user - prioritize URL token first for video requests
    current_user = None
    
    # First try URL token (most common for video requests)
    try:
        current_user = await get_user_from_url_token(request, db)
        if current_user:
            logger.info(f"✅ Authenticated via URL token: User {current_user.id}")
    except Exception as e:
        logger.error(f"Error getting user from URL token: {str(e)}")
        current_user = None
        
    # If no user from URL token, try Authorization header
    if not current_user:
        try:
            current_user = await deps.get_current_user_or_none(request, db)
            if current_user:
                logger.info(f"✅ Authenticated via Authorization header: User {current_user.id}")
        except Exception as e:
            logger.error(f"Error getting current user from header: {str(e)}\n{traceback.format_exc()}")
            current_user = None
    
    # Validate job ownership (if authenticated)
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # If user is authenticated, check authorization
    if current_user and job.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to access this job")
    
    # Optimized: Use job_results table (indexed) for accurate file paths
    result = db.query(JobResult).filter(
        JobResult.job_id == job_id,
        JobResult.result_type == ResultType.ORIGINAL_VIDEO
    ).first()
    
    video_path = None
    if result and result.file_path:
        video_path = result.file_path
        logger.info(f"✅ Found original video in job_results: {video_path}")
    elif job.source_video_url:
        video_path = job.source_video_url
        logger.info(f"⚠️ Using job.source_video_url fallback: {video_path}")
    
    if not video_path:
        logger.error(f"❌ No video path found for job {job_id}")
        raise HTTPException(status_code=404, detail="Original video not found")
    
    # Only check existence if really necessary (remove for performance)
    if not os.path.exists(video_path):
        logger.error(f"❌ Video file not found on disk: {video_path}")
        raise HTTPException(status_code=404, detail="Video file not found on disk")
    
    logger.info(f"Serving original video: {video_path}")
    
    # Use filename from the path
    filename = os.path.basename(video_path)
    
    # Determine MIME type based on file extension
    ext = os.path.splitext(video_path)[1].lower()
    if ext in [".mp4"]:
        media_type = "video/mp4"
    elif ext in [".webm"]:
        media_type = "video/webm"
    elif ext in [".ogg", ".ogv"]:
        media_type = "video/ogg"
    elif ext in [".mov", ".qt"]:
        media_type = "video/quicktime"
    else:
        media_type = "application/octet-stream"
    
    return FileResponse(
        path=video_path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline" if streamable else "attachment"
    )

@router.get("/results/{job_id}/subtitled_video")
async def get_subtitled_video_for_preview(
    request: Request,
    job_id: int,
    language: str = Query(..., description="Language code (e.g., 'en', 'zh')"),
    streamable: bool = Query(False, description="Whether to serve the video for streaming"),
    db: Session = Depends(deps.get_db)
):
    """
    Direct endpoint for subtitled video preview that exactly matches the frontend URL pattern
    """
    logger.info(f"Direct subtitled video preview request for job {job_id}, language: {language}, streamable: {streamable}")
    
    # Try to get the current user - prioritize URL token first for video requests
    current_user = None
    
    # First try URL token (most common for video requests)
    try:
        current_user = await get_user_from_url_token(request, db)
        if current_user:
            logger.info(f"✅ Authenticated via URL token: User {current_user.id}")
    except Exception as e:
        logger.error(f"Error getting user from URL token: {str(e)}")
        current_user = None
        
    # If no user from URL token, try Authorization header
    if not current_user:
        try:
            current_user = await deps.get_current_user_or_none(request, db)
            if current_user:
                logger.info(f"✅ Authenticated via Authorization header: User {current_user.id}")
        except Exception as e:
            logger.error(f"Error getting current user from header: {str(e)}\n{traceback.format_exc()}")
            current_user = None
    
    # Validate job ownership (if authenticated)
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # If user is authenticated, check authorization
    if current_user and job.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to access this job")
    
    # Try to get the result from job_results table
    result = db.query(JobResult).filter(
        JobResult.job_id == job_id,
        JobResult.result_type == ResultType.SUBTITLED_VIDEO,
        JobResult.language == language
    ).first()
    
    # First, check if we have a valid result in the database with a valid file
    if result and result.file_path and os.path.exists(result.file_path):
        video_path = result.file_path
        logger.info(f"Found subtitled video in database: {video_path}")
    else:
        # If not in database, try to find the file using file_path_manager
        from app.utils.file_path_manager import get_file_path_manager, FileType
        from app.models.job_context import JobContext
        
        # Create a JobContext instance with the correct user_id from the job
        job_context = JobContext(
            user_id=job.owner_id if job else 1,
            job_id=job_id,
            source_language=job.source_language if job else language
        )
        
        try:
            # Try to get the file path using file_path_manager
            file_manager = get_file_path_manager()
            video_path = file_manager.get_file_path(
                context=job_context,
                file_type=FileType.SUBTITLED_VIDEO,
                language=language,
                filename=f"subtitled_{language}.mp4"
            )
            
            if not os.path.exists(video_path):
                # If file doesn't exist, try alternative naming patterns
                alt_paths = [
                    os.path.join(os.path.dirname(video_path), f"subtitled_{language}.mp4"),
                    os.path.join(os.path.dirname(video_path), f"subtitled.mp4"),
                    os.path.join(os.path.dirname(video_path), f"output_{language}.mp4")
                ]
                
                for alt_path in alt_paths:
                    if os.path.exists(alt_path):
                        video_path = alt_path
                        logger.info(f"Found subtitled video at alternative path: {video_path}")
                        break
                else:
                    logger.error(f"Subtitled video not found at any expected location for job {job_id}, language {language}")
                    raise FileNotFoundError(f"Subtitled video not found for language {language}")
            else:
                logger.info(f"Found subtitled video using file_path_manager: {video_path}")
                
        except Exception as e:
            logger.error(f"Error getting subtitled video path: {str(e)}\n{traceback.format_exc()}")
            raise HTTPException(
                status_code=404,
                detail=f"Subtitled video not found for language {language}. Error: {str(e)}"
            )
    
    # Use filename from the path
    filename = os.path.basename(video_path)
    
    # Determine MIME type based on file extension
    ext = os.path.splitext(video_path)[1].lower()
    if ext in [".mp4"]:
        media_type = "video/mp4"
    elif ext in [".webm"]:
        media_type = "video/webm"
    elif ext in [".ogg", ".ogv"]:
        media_type = "video/ogg"
    elif ext in [".mov", ".qt"]:
        media_type = "video/quicktime"
    else:
        media_type = "application/octet-stream"
    
    return FileResponse(
        path=video_path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline" if streamable else "attachment"
    )
