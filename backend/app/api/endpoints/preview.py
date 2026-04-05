import glob
import logging
import os
import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api import deps
from app.models.user import User
from app.models.job import Job
from app.models.job_result import JobResult, ResultType
from app.utils.file_utils import find_video_file, ensure_directory_exists
from app.core.config import get_settings
# from app.services.subtitle.service import SubtitleService  # Imported but never used
from app.utils.file_path_manager import get_file_path_manager
from app.services.subtitle_edit_service import subtitle_edit_service

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()


def validate_job_access(db: Session, job_id: int, current_user: User) -> Job:
    """
    Validate job exists and user has access to it.
    
    Args:
        db: Database session
        job_id: Job ID to validate
        current_user: Current authenticated user
        
    Returns:
        Job: The validated job object
        
    Raises:
        HTTPException: If job not found or access denied
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to access this job")
    
    return job

class PreviewOption(BaseModel):
    type: str
    language: Optional[str] = None
    file_name: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    preview_url: str
    thumbnail_url: Optional[str] = None  # Added thumbnail URL

class PreviewOptions(BaseModel):
    job_id: int
    job_status: str
    available_previews: List[PreviewOption]

@router.get("/status")
async def preview_status():
    """
    Simple status endpoint for testing
    """
    return {"status": "ok"}


@router.get("/s3-url/{job_id}")
async def get_s3_video_url(
    job_id: int,
    video_type: str = Query("original", description="Video type: 'original' or 'subtitled'"),
    language: str = Query(None, description="Language code for subtitled video"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get S3 presigned URL for direct video access
    """
    logger.info(f"[S3 URL] Request for job {job_id}, type: {video_type}, language: {language}")
    
    # Validate job access
    job = validate_job_access(db, job_id, current_user)
    
    # Determine result type
    if video_type == "original":
        result_type = ResultType.ORIGINAL_VIDEO
    elif video_type == "subtitled":
        result_type = ResultType.SUBTITLED_VIDEO
        if not language:
            raise HTTPException(status_code=400, detail="Language required for subtitled video")
    else:
        raise HTTPException(status_code=400, detail="Invalid video_type. Use 'original' or 'subtitled'")
    
    # Find video file
    video_path = find_video_file(job_id, job, result_type, language)
    if not video_path:
        raise HTTPException(status_code=404, detail=f"{video_type.title()} video not found")
    
    # Generate presigned URL
    file_path_manager = get_file_path_manager()
    presigned_url = file_path_manager.generate_presigned_url(video_path, settings.S3_PRESIGNED_URL_EXPIRY)
    
    if not presigned_url:
        raise HTTPException(
            status_code=503, 
            detail="S3 direct access not available. File may be stored locally or S3 direct access is disabled."
        )
    
    return {
        "job_id": job_id,
        "video_type": video_type,
        "language": language,
        "s3_url": presigned_url,
        "expires_in": settings.S3_PRESIGNED_URL_EXPIRY,
        "file_path": video_path
    }


def find_video_file(job_id: int, job: Job = None, result_type: ResultType = None, language: str = None) -> Optional[str]:
    """
    Utility function to find video files using file_path_manager
    """
    logger.info(f"Finding video for job {job_id}, type {result_type}, language {language}")
    
    # If job is not provided, fetch it from the database
    if not job:
        try:
            db = next(deps.get_db())
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found in database")
                return None
        except Exception as e:
            logger.error(f"Error fetching job {job_id}: {e}")
            return None
    
    # Create job context
    from app.models.job_context import JobContext
    from app.utils.file_path_manager import FileType, get_file_path_manager
    
    job_context = JobContext(
        user_id=job.owner_id,
        job_id=job_id,
        source_language=job.source_language,
        target_languages=[language] if language else []
    )
    
    file_path_manager = get_file_path_manager()
    
    try:
        # Determine file type based on result_type
        file_type = None
        if result_type == ResultType.ORIGINAL_VIDEO:
            file_type = FileType.SOURCE_VIDEO
        elif result_type == ResultType.SUBTITLED_VIDEO and language:
            file_type = FileType.SUBTITLED_VIDEO
        
        if not file_type:
            logger.error(f"Unsupported result_type: {result_type}")
            return None
            
        # Get file path using file_path_manager
        video_path = file_path_manager.get_file_path(
            context=job_context,
            file_type=file_type,
            language=language if language else None
        )
        
        # Verify the file exists and is not empty using file manager
        if video_path and file_path_manager.exists(video_path):
            try:
                file_size = file_path_manager.get_file_size(video_path)
                if file_size > 0:
                    logger.info(f"Found video file: {video_path}")
                    return video_path
                else:
                    logger.warning(f"Video file is empty: {video_path}")
                    return None
            except Exception as e:
                logger.warning(f"Error checking video file size: {e}")
                return None
        else:
            logger.warning(f"Video file not found: {video_path}")
            return None
            
    except Exception as e:
        logger.error(f"Error finding video file: {e}")
        return None


@router.get("/video/{job_id}")
async def preview_video(
    job_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> FileResponse:
    """
    Stream the original video for preview
    """
    logger.info(f"Original video preview request for job {job_id}")
    
    # Get job and validate ownership
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        logger.warning(f"Job {job_id} not found")
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    if job.owner_id != current_user.id and not current_user.is_superuser:
        logger.warning(f"User {current_user.id} not authorized for job {job_id}")
        raise HTTPException(status_code=403, detail="Not authorized to access this job")
    
    # Find the video file
    video_path = find_video_file(job_id, job, ResultType.ORIGINAL_VIDEO)
    
    if not video_path:
        raise HTTPException(status_code=404, detail="Original video not found")
    
    # Check if S3 direct access is enabled
    file_path_manager = get_file_path_manager()
    
    # Try to generate S3 presigned URL first
    presigned_url = file_path_manager.generate_presigned_url(video_path, settings.S3_PRESIGNED_URL_EXPIRY)
    if presigned_url:
        logger.info(f"[Preview] Redirecting to S3 presigned URL for job {job_id}")
        return RedirectResponse(url=presigned_url, status_code=302)
    
    # Fallback to local file serving
    local_video_path = file_path_manager.get_local_path(video_path)
    logger.info(f"[Preview] Serving from local file: {local_video_path}")
    return FileResponse(
        path=local_video_path,
        media_type="video/mp4",
        filename=os.path.basename(video_path)
    )


@router.get("/subtitled_video/{job_id}")
async def preview_subtitled_video(
    job_id: int,
    language: str = Query(None, description="Language code (e.g., 'en', 'zh')"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> FileResponse:
    """
    Stream a video file with subtitles for preview
    """
    logger.info(f"[Preview] Starting subtitled video preview for job_id={job_id}, language={language}")
    
    try:
        # Get job and validate ownership
        logger.debug(f"[Preview] Fetching job {job_id} from database")
        job = db.query(Job).filter(Job.id == job_id).first()
        
        if not job:
            logger.error(f"[Preview] Job not found - job_id={job_id}, user_id={getattr(current_user, 'id', 'N/A')}")
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        logger.debug(f"[Preview] Job found - owner_id={job.owner_id}, status={job.status}")
        
        # Check authorization
        if job.owner_id != current_user.id and not current_user.is_superuser:
            logger.warning(
                f"[Preview] Unauthorized access - "
                f"job_owner={job.owner_id}, "
                f"current_user={current_user.id}, "
                f"is_superuser={current_user.is_superuser}"
            )
            raise HTTPException(status_code=403, detail="Not authorized to access this job")
        
        # Find the video file
        logger.info(f"[Preview] Locating subtitled video for job {job_id}, language: {language or 'any'}")
        video_path = find_video_file(job_id, job, ResultType.SUBTITLED_VIDEO, language)
        
        if not video_path:
            logger.error(
                f"[Preview] Subtitled video not found - "
                f"job_id={job_id}, "
                f"language={language}, "
                f"job_status={job.status}, "
                f"source_video={getattr(job, 'source_video_url', 'N/A')}"
            )
            raise HTTPException(status_code=404, detail=f"Subtitled video not found for job {job_id}")
        
        # Verify file exists and is accessible using file manager
        file_path_manager = get_file_path_manager()
        if not file_path_manager.exists(video_path):
            local_path = file_path_manager.get_local_path(video_path)
            dir_path = os.path.dirname(local_path)
            logger.error(
                f"[Preview] Video file not found - "
                f"path={video_path}, "
                f"local_path={local_path}, "
                f"directory_exists={os.path.exists(dir_path)}, "
                f"directory_contents={os.listdir(dir_path) if os.path.exists(dir_path) else 'N/A'}"
            )
            raise HTTPException(status_code=404, detail="Video file not found on server")
            
        try:
            file_size_mb = file_path_manager.get_file_size(video_path) / (1024*1024)
            logger.info(f"[Preview] Serving subtitled video - path={video_path}, size={file_size_mb:.2f}MB")
        except Exception as e:
            logger.warning(f"[Preview] Could not get file size: {e}")
            logger.info(f"[Preview] Serving subtitled video - path={video_path}")
        
        # Try to generate S3 presigned URL first
        presigned_url = file_path_manager.generate_presigned_url(video_path, settings.S3_PRESIGNED_URL_EXPIRY)
        if presigned_url:
            logger.info(f"[Preview] Redirecting to S3 presigned URL for subtitled video job {job_id}, language {language}")
            return RedirectResponse(url=presigned_url, status_code=302)
        
        # Fallback to local file serving
        local_video_path = file_path_manager.get_local_path(video_path)
        logger.info(f"[Preview] Serving subtitled video from local file: {local_video_path}")
        return FileResponse(
            path=local_video_path,
            media_type="video/mp4",
            filename=os.path.basename(video_path)
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as they are already handled
        raise
        
    except Exception as e:
        logger.error(
            f"[Preview] Unexpected error - "
            f"job_id={job_id}, "
            f"error={str(e)}\n"
            f"{traceback.format_exc()}"
        )
        raise HTTPException(status_code=500, detail="An error occurred while processing your request")
        
    except HTTPException:
        raise
        
    except Exception as e:
        logger.error(
            f"[Get Subtitles] Unexpected error - "
            f"job_id={job_id}, "
            f"error={str(e)}\n"
            f"{traceback.format_exc()}"
        )
        raise HTTPException(status_code=500, detail="An error occurred while processing your request")


@router.get("/subtitled/{job_id}")
async def legacy_preview_subtitled(
    job_id: int,
    language: str = Query(None, description="Language code (e.g., 'en', 'zh')"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> FileResponse:
    """
    Legacy endpoint for backward compatibility
    """
    logger.info(f"[Legacy Preview] Starting legacy subtitled video request for job {job_id}, language: {language}")
    
    try:
        # Get job and validate ownership
        logger.debug(f"[Legacy Preview] Fetching job {job_id} from database")
        job = db.query(Job).filter(Job.id == job_id).first()
        
        if not job:
            logger.error(f"[Legacy Preview] Job not found - job_id={job_id}, user_id={getattr(current_user, 'id', 'N/A')}")
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
            
        logger.debug(f"[Legacy Preview] Job found - owner_id={job.owner_id}, status={job.status}")
        
        # Check authorization
        if job.owner_id != current_user.id and not current_user.is_superuser:
            logger.warning(
                f"[Legacy Preview] Unauthorized access - "
                f"job_owner={job.owner_id}, "
                f"current_user={current_user.id}, "
                f"is_superuser={current_user.is_superuser}"
            )
            raise HTTPException(status_code=403, detail="Not authorized to access this job")
            
        logger.info(f"[Legacy Preview] Using new preview endpoint for job {job_id}")
        
        # Use the new preview endpoint
        return await preview_subtitled_video(job_id, language, db, current_user)
        
    except HTTPException as he:
        logger.error(
            f"[Legacy Preview] HTTP Error - "
            f"job_id={job_id}, "
            f"status_code={he.status_code}, "
            f"detail={he.detail}"
        )
        raise
        
    except Exception as e:
        logger.error(
            f"[Legacy Preview] Unexpected error - "
            f"job_id={job_id}, "
            f"error={str(e)}\n"
            f"{traceback.format_exc()}"
        )
        raise HTTPException(status_code=500, detail="An error occurred while processing your request")


@router.get("/subtitles/{job_id}")
async def get_subtitles(
    job_id: int,
    language: str = Query(..., description="Language code (e.g., 'en', 'zh')"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Response:
    """
    Get subtitles for a job in the specified language.
    This endpoint serves the same subtitle files that are used during video processing.
    """
    logger.info(f"[Get Subtitles] Request for job {job_id}, language: {language}")
    
    try:
        # Verify job exists and user has access
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"[Get Subtitles] Job not found - job_id={job_id}")
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Check authorization
        if job.owner_id != current_user.id and not current_user.is_superuser:
            logger.warning(
                f"[Get Subtitles] Unauthorized access - "
                f"job_owner={job.owner_id}, "
                f"current_user={current_user.id}"
            )
            raise HTTPException(status_code=403, detail="Not authorized to access this job")
        
        # Get file path manager and create job context
        file_path_manager = get_file_path_manager()
        from app.models.job_context import JobContext
        from app.utils.file_path_manager import FileType
        
        # Create job context with required fields
        job_context = JobContext(
            user_id=job.owner_id,
            job_id=job_id,
            source_language=job.source_language,
            target_languages=[language] if language else []
        )
        
        logger.info(f"[Get Subtitles] Using job context - user_id: {job_context.user_id}, job_id: {job_context.job_id}")
        
        # Get the subtitle file path using FilePathManager
        try:
            # 1. First try to read the modified.json file (edited version)
            modified_subtitle_file = file_path_manager.get_file_path(job_context, FileType.MODIFIED_SUBTITLE, language=language)
            
            if os.path.exists(modified_subtitle_file):
                logger.info(f"[Get Subtitles] Found modified subtitle file at: {modified_subtitle_file}")
                
                # Read and return JSON content as parsed JSON
                import json
                with open(modified_subtitle_file, 'r', encoding='utf-8') as f:
                    subtitle_data = json.load(f)
                
                # Handle both array format and object format
                if isinstance(subtitle_data, list):
                    subtitles = subtitle_data
                elif isinstance(subtitle_data, dict) and "subtitles" in subtitle_data:
                    subtitles = subtitle_data["subtitles"]
                else:
                    logger.warning(f"[Get Subtitles] Unexpected modified file format, treating as empty")
                    subtitles = []
                
                logger.info(f"[Get Subtitles] Loaded {len(subtitles)} subtitles from modified file")
                
                # Return the parsed JSON data as JSONResponse
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    content=subtitles,
                    headers={"Content-Disposition": f"inline; filename=subtitles_{language}.json"}
                )
            
            # 2. Try to read the original JSON working file
            json_subtitle_file = file_path_manager.get_file_path(job_context, FileType.SUBTITLE_LANG_JSON, language=language)
            
            if os.path.exists(json_subtitle_file):
                logger.info(f"[Get Subtitles] Found original JSON file at: {json_subtitle_file}")
                
                # Read and return JSON content as parsed JSON
                import json
                with open(json_subtitle_file, 'r', encoding='utf-8') as f:
                    subtitle_data = json.load(f)
                
                logger.info(f"[Get Subtitles] Loaded {len(subtitle_data)} subtitles from original JSON file")
                
                # Return the parsed JSON data as JSONResponse
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    content=subtitle_data,
                    headers={"Content-Disposition": f"inline; filename=subtitles_{language}.json"}
                )
            
            # 3. Fallback to SRT/VTT files if no JSON found
            logger.info(f"[Get Subtitles] No JSON files found, falling back to SRT/VTT files")
            
            # First try with SRT
            subtitle_file = file_path_manager.get_file_path(
                context=job_context,
                file_type=FileType.SUBTITLE_SRT,
                language=language
            )
            
            # If SRT not found, try VTT
            if not os.path.exists(subtitle_file):
                logger.info(f"[Get Subtitles] SRT not found at {subtitle_file}, trying VTT")
                subtitle_file = file_path_manager.get_file_path(
                    context=job_context,
                    file_type=FileType.SUBTITLE_VTT,
                    language=language
                )
            
            # Log the exact path we're checking
            logger.info(f"[Get Subtitles] Looking for subtitle file at: {subtitle_file}")
            
            if not os.path.exists(subtitle_file):
                # Try to find any subtitle file in the expected directory
                subtitles_dir = os.path.dirname(subtitle_file)
                if os.path.exists(subtitles_dir):
                    available_files = os.listdir(subtitles_dir)
                    logger.error(
                        f"[Get Subtitles] Subtitle file not found at {subtitle_file}. "
                        f"Available files in directory: {available_files}"
                    )
                else:
                    logger.error(f"[Get Subtitles] Subtitles directory not found: {subtitles_dir}")
                
                raise HTTPException(
                    status_code=404, 
                    detail=f"Subtitle file for language '{language}' not found. "
                          f"Please ensure the subtitles have been generated for this language."
                )
                
        except Exception as e:
            logger.error(f"[Get Subtitles] Error getting subtitle file path: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error locating subtitle file: {str(e)}"
            )
            
        # Verify the file is not empty
        if os.path.getsize(subtitle_file) == 0:
            logger.error(f"[Get Subtitles] Subtitle file is empty: {subtitle_file}")
            raise HTTPException(
                status_code=404,
                detail=f"Subtitle file for language {language} is empty"
            )
            
        logger.info(f"[Get Subtitles] Found subtitle file: {subtitle_file}")
        
        # Read the subtitle file content
        with open(subtitle_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Return the subtitle content with appropriate headers
        return Response(
            content=content,
            media_type="text/vtt" if subtitle_file.endswith('.vtt') else "text/plain; charset=utf-8",
            headers={"Content-Disposition": f"inline; filename=subtitles_{language}.srt"}
        )
    except HTTPException:
        # Re-raise HTTP exceptions as they are already handled
        raise
    except Exception as e:
        logger.error(
            f"[Get Subtitles] Unexpected error - "
            f"Job: {job_id}, Language: {language}, Error: {str(e)}\n"
            f"{traceback.format_exc()}"
        )
        raise HTTPException(
            status_code=500,
            detail="An error occurred while retrieving subtitles"
        )

@router.get("/options/{job_id}", response_model=PreviewOptions)
async def get_preview_options(
    job_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> PreviewOptions:
    """
    Get available preview options for a job.
    This endpoint returns a list of available preview options for a given job,
    including the original video and any processed videos (subtitled, etc.)
    """
    # Force reload by adding a comment
    logger.info(f"[Preview Options] Request for job {job_id}")
    
    # Get the job from the database
    job = db.query(Job).filter(Job.id == job_id, Job.owner_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get job results
    results = db.query(JobResult).filter(JobResult.job_id == job_id).all()
    
    available_previews = []
    
    # Add original video option if available
    if job.source_video_url:
        try:
            if os.path.exists(job.source_video_url):
                available_previews.append(PreviewOption(
                    type="original_video",
                    file_name=os.path.basename(job.source_video_url),
                    file_size=os.path.getsize(job.source_video_url),
                    mime_type="video/mp4",
                    preview_url=f"/api/v1/preview/video/{job_id}",
                    thumbnail_url=f"/api/v1/thumbnails/{job_id}?size=medium"
                ))
        except Exception as e:
            logger.warning(f"Error adding original video preview: {e}")
    
    # Add subtitled video options
    for result in results:
        try:
            if result.result_type == ResultType.SUBTITLED_VIDEO and result.file_path and os.path.exists(result.file_path):
                language = result.language or "unknown"
                metadata = result.metadata_ or {}
                available_previews.append(PreviewOption(
                    type="subtitled_video",
                    language=language,
                    file_name=os.path.basename(result.file_path),
                    file_size=os.path.getsize(result.file_path),
                    mime_type=metadata.get('mime_type', 'video/mp4'),
                    preview_url=f"/api/v1/preview/subtitled_video/{job_id}?language={language}",
                    thumbnail_url=f"/api/v1/thumbnails/{job_id}?size=medium"
                ))
        except AttributeError as e:
            logger.error(f"AttributeError in get_preview_options: {e}")
            logger.error(f"Attributes of result object: {dir(result)}")
            # Decide how to handle this - maybe try file_url as a fallback?
            if 'file_url' in dir(result) and result.file_url and os.path.exists(result.file_url):
                 language = result.language or "unknown"
                 metadata = result.metadata_ or {}
                 available_previews.append(PreviewOption(
                    type="subtitled_video",
                    language=language,
                    file_name=os.path.basename(result.file_url),
                    file_size=os.path.getsize(result.file_url),
                    mime_type=metadata.get('mime_type', 'video/mp4'),
                    preview_url=f"/api/v1/preview/subtitled_video/{job_id}?language={language}",
                    thumbnail_url=f"/api/v1/thumbnails/{job_id}?size=medium"
                ))
    
    # Check for any additional subtitle files that might exist but aren't in the database
    try:
        from app.models.job_context import JobContext
        from app.utils.file_path_manager import FileType, get_file_path_manager
        
        file_path_manager = get_file_path_manager()
        job_context = JobContext(
            user_id=job.owner_id,
            job_id=job_id,
            source_language=job.source_language,
            target_languages=[]
        )
        
        # Get the subtitles directory path
        subtitles_dir = file_path_manager.get_directory_path(
            context=job_context,
            dir_type=FileType.SUBTITLE_SRT  # Use SUBTITLE_SRT to get the subtitles directory
        )
        
        if os.path.exists(subtitles_dir):
            for sub_file in os.listdir(subtitles_dir):
                if sub_file.endswith(('.srt', '.vtt')):
                    language = os.path.splitext(sub_file)[0]
                    # Keep "src" as is to represent source language subtitles
                    # Don't convert to "auto" as we want to distinguish source from auto-detect
                    
                    # Check if we already have this language in our previews
                    if not any(p.language == language for p in available_previews):
                        sub_path = os.path.join(subtitles_dir, sub_file)
                        available_previews.append(PreviewOption(
                            type="subtitles",
                            language=language,
                            file_name=sub_file,
                            file_size=os.path.getsize(sub_path),
                            mime_type="text/vtt" if sub_file.endswith('.vtt') else "text/plain",
                            preview_url=f"/api/v1/preview/subtitles/{job_id}?language={language}"
                        ))
    except Exception as e:
        logger.warning(f"Error checking for additional subtitle files: {e}")
    
    logger.info(f"[Preview Options] Found {len(available_previews)} preview options for job {job_id}")
    
    return PreviewOptions(
        job_id=job_id,
        job_status=job.status,
        available_previews=available_previews
    )


@router.get("/subtitles/{job_id}")
async def get_subtitle_preview(
    job_id: int,
    language: str,
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    获取字幕预览数据（JSON格式）
    优先返回临时编辑缓存，然后是修改版本，最后是原始版本
    """
    try:
        from app.services.subtitle_edit_service import subtitle_edit_service
        from app.utils.file_path_manager import get_file_path_manager
        
        file_manager = get_file_path_manager()
        job_dir = file_manager._get_job_dir(current_user.id, job_id)
        
        # 1. 优先检查临时编辑缓存
        temp_cache_file = os.path.join(job_dir, "temp", f"editing_{language}.json")
        if os.path.exists(temp_cache_file):
            logger.info(f"Loading from temporary editing cache: {temp_cache_file}")
            try:
                with open(temp_cache_file, 'r', encoding='utf-8') as f:
                    temp_data = json.load(f)
                    if isinstance(temp_data, dict) and "subtitles" in temp_data:
                        logger.info(f"Successfully loaded {len(temp_data['subtitles'])} subtitles from temp cache")
                        return temp_data["subtitles"]
                    elif isinstance(temp_data, list):
                        logger.info(f"Successfully loaded {len(temp_data)} subtitles from temp cache (array format)")
                        return temp_data
            except Exception as e:
                logger.warning(f"Error reading temp cache {temp_cache_file}: {str(e)}")
        
        # 2. 使用字幕编辑服务的智能加载功能
        subtitles = subtitle_edit_service._load_subtitle_file(
            job_id=job_id,
            language=language,
            user_id=current_user.id
        )
        
        if not subtitles:
            raise HTTPException(
                status_code=404,
                detail=f"No subtitles found for job {job_id}, language {language}"
            )
        
        return subtitles
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting subtitle preview for job {job_id}, language {language}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while getting subtitle preview"
        )


@router.post("/subtitles/{job_id}/temp-cache")
async def update_temp_subtitle_cache(
    job_id: int,
    language: str,
    subtitles: List[Dict[str, Any]],
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    更新临时字幕缓存，用于实时编辑预览
    """
    try:
        from app.utils.file_path_manager import get_file_path_manager
        
        file_manager = get_file_path_manager()
        job_dir = file_manager._get_job_dir(current_user.id, job_id)
        
        # 创建临时目录
        temp_dir = os.path.join(job_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # 保存临时缓存
        temp_cache_file = os.path.join(temp_dir, f"editing_{language}.json")
        temp_data = {
            "subtitles": subtitles,
            "language": language,
            "job_id": job_id,
            "timestamp": datetime.now().isoformat(),
            "type": "temp_editing_cache"
        }
        
        with open(temp_cache_file, 'w', encoding='utf-8') as f:
            json.dump(temp_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Updated temp cache for job {job_id}, language {language}: {len(subtitles)} subtitles")
        
        return {
            "success": True,
            "message": f"Temporary cache updated for {len(subtitles)} subtitles",
            "cache_file": temp_cache_file
        }
        
    except Exception as e:
        logger.error(f"Error updating temp subtitle cache: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while updating temporary cache"
        )


@router.delete("/subtitles/{job_id}/temp-cache")
async def clear_temp_subtitle_cache(
    job_id: int,
    language: str,
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    清除临时字幕缓存（保存时调用）
    """
    try:
        from app.utils.file_path_manager import get_file_path_manager
        
        file_manager = get_file_path_manager()
        job_dir = file_manager._get_job_dir(current_user.id, job_id)
        
        temp_cache_file = os.path.join(job_dir, "temp", f"editing_{language}.json")
        
        if os.path.exists(temp_cache_file):
            os.remove(temp_cache_file)
            logger.info(f"Cleared temp cache: {temp_cache_file}")
            return {"success": True, "message": "Temporary cache cleared"}
        else:
            return {"success": True, "message": "No temporary cache to clear"}
        
    except Exception as e:
        logger.error(f"Error clearing temp subtitle cache: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while clearing temporary cache"
        )


@router.post("/subtitles/save-modified/{job_id}")
async def save_modified_subtitles(
    job_id: int,
    subtitles: List[Dict[str, Any]],
    language: str = Query(..., description="Language code"),
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db)
):
    """
    简化的字幕保存端点 - 直接保存到modified.json
    """
    try:
        subtitle_count = len(subtitles)
        logger.info(f"[Save Modified] Starting save for job {job_id}, language {language}, {subtitle_count} subtitles")
        
        # 验证作业存在和权限
        validate_job_access(db, job_id, current_user)
        
        # 使用字幕编辑服务保存
        subtitle_edit_service._save_subtitle_file(
            job_id=job_id,
            language=language,
            subtitles=subtitles,
            user_id=current_user.id
        )
        
        logger.info(f"[Save Modified] Successfully saved {subtitle_count} subtitles")
        
        return {
            "success": True,
            "message": f"Successfully saved {subtitle_count} subtitles for {language}",
            "language": language,
            "subtitle_count": subtitle_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Save Modified] Error saving subtitles: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while saving subtitles: {str(e)}"
        )


@router.post("/subtitles/bulk-save/{job_id}")
async def bulk_save_subtitles(
    job_id: int,
    request_data: Dict[str, Any],
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db)
):
    """
    批量保存前端编辑的字幕到后端（保持向后兼容）
    重定向到新的简化保存端点
    """
    language = request_data.get('language')
    subtitles = request_data.get('subtitles')
    
    if not language or not subtitles:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: language and subtitles"
        )
    
    # 重定向到新的简化保存端点
    return await save_modified_subtitles(
        job_id=job_id,
        subtitles=subtitles,
        language=language,
        current_user=current_user,
        db=db
    )