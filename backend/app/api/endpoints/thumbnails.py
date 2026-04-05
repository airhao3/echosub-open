"""
Thumbnail API Endpoints

Provides endpoints for serving and generating video thumbnails.
"""

import os
import logging
import traceback
from typing import Optional, Dict, Any
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import get_current_user_with_query_token
from app.core.config import get_settings
from app.models.user import User
from app.models.job import Job
from app.models.job_context import JobContext
from app.models.job_result import JobResult
from app.services.thumbnail_service import ThumbnailService
from app.utils.file_path_manager import get_file_path_manager, FileType

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize thumbnail service
thumbnail_service = ThumbnailService()

@router.get("/{job_id}")
async def get_thumbnail(
    job_id: int,
    request: Request,
    size: str = Query("medium", description="Thumbnail size: small, medium, large, poster"),
    regenerate: bool = Query(False, description="Force regenerate thumbnail"),
    token: Optional[str] = Query(None, description="Authentication token"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(get_current_user_with_query_token)
) -> FileResponse:
    """
    Get thumbnail for a job's video
    
    Args:
        job_id: Job ID
        size: Thumbnail size (small, medium, large, poster)
        regenerate: Force regenerate thumbnail if it exists
        
    Returns:
        FileResponse: Thumbnail image file
    """
    logger.info(f"[Thumbnail] Request for job {job_id}, size: {size}, regenerate: {regenerate}")
    
    try:
        # Validate job and authorization
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"[Thumbnail] Job {job_id} not found")
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.owner_id != current_user.id and not current_user.is_superuser:
            logger.warning(f"[Thumbnail] Unauthorized access to job {job_id} by user {current_user.id}")
            raise HTTPException(status_code=403, detail="Not authorized to access this job")
        
        # Validate size parameter
        if size not in thumbnail_service.THUMBNAIL_SIZES:
            logger.error(f"[Thumbnail] Invalid size: {size}")
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid size. Must be one of: {list(thumbnail_service.THUMBNAIL_SIZES.keys())}"
            )
        
        file_manager = get_file_path_manager()

        # Try to find the thumbnail in JobResult first
        from app.models.job import ResultType
        result_type = ResultType[f"THUMBNAIL_{size.upper()}"]
        job_result = db.query(JobResult).filter(
            JobResult.job_id == job_id,
            JobResult.result_type == result_type
        ).first()

        if job_result and file_manager.exists(job_result.file_path) and not regenerate:
            logger.info(f"[Thumbnail] Serving existing thumbnail from JobResult: {job_result.file_path}")
            return FileResponse(
                path=job_result.file_path,
                media_type="image/jpeg",
                headers={"Content-Disposition": "inline"}
            )

        # If not found in JobResult or regeneration is forced, fall back to the old logic
        logger.info(f"[Thumbnail] Thumbnail not found in JobResult or regeneration is forced. Falling back to generation.")

        # Create job context and file manager
        job_context = JobContext(
            user_id=job.owner_id,
            job_id=job_id,
            source_language=job.source_language
        )
        
        # Get thumbnail path
        thumbnail_path = file_manager.get_file_path(
            context=job_context,
            file_type=FileType.THUMBNAIL,
            language=None,
            size=size
        )

        # S3 Direct Access Handling
        if settings.S3_DIRECT_ACCESS:
            presigned_url = file_manager.generate_presigned_url(thumbnail_path)
            if presigned_url:
                logger.info(f"[Thumbnail] Redirecting to S3 presigned URL for job {job_id}")
                return RedirectResponse(url=presigned_url)
            else:
                logger.warning(f"[Thumbnail] Failed to generate presigned URL for job {job_id}. Falling back to serving file.")

        logger.debug(f"[Thumbnail] Expected thumbnail path: {thumbnail_path}")
        
        # Check if thumbnail exists and if regeneration is not forced
        if file_manager.exists(thumbnail_path) and not regenerate:
            logger.info(f"[Thumbnail] Serving existing thumbnail: {thumbnail_path}")
            # Serve inline so <img> can render it. Avoid setting filename which forces attachment.
            return FileResponse(
                path=thumbnail_path,
                media_type="image/jpeg",
                headers={"Content-Disposition": "inline"}
            )
        
        # Get source video path
        try:
            source_video_path = file_manager.get_file_path(
                context=job_context,
                file_type=FileType.SOURCE_VIDEO
            )
            
            if not file_manager.exists(source_video_path):
                logger.error(f"[Thumbnail] Source video not found: {source_video_path}")
                raise HTTPException(status_code=404, detail="Source video not found")
                
        except Exception as e:
            logger.error(f"[Thumbnail] Error getting source video path: {str(e)}")
            raise HTTPException(status_code=500, detail="Error locating source video")
        
        # Generate thumbnail
        logger.info(f"[Thumbnail] Generating thumbnail from video: {source_video_path}")
        
        # Get optimal timestamp for thumbnail
        timestamp = thumbnail_service.get_optimal_timestamp(source_video_path)
        logger.debug(f"[Thumbnail] Using timestamp: {timestamp}")
        
        # Generate thumbnail
        success = thumbnail_service.generate_thumbnail(
            video_path=source_video_path,
            output_path=thumbnail_path,
            size=size,
            timestamp=timestamp
        )
        
        if success and file_manager.exists(thumbnail_path):
            logger.info(f"[Thumbnail] Successfully generated thumbnail: {thumbnail_path}")
            # Serve inline so <img> can render it. Avoid setting filename which forces attachment.
            return FileResponse(
                path=thumbnail_path,
                media_type="image/jpeg",
                headers={"Content-Disposition": "inline"}
            )
        else:
            logger.error(f"[Thumbnail] Failed to generate thumbnail for job {job_id}")
            raise HTTPException(status_code=500, detail="Failed to generate thumbnail")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[Thumbnail] Unexpected error for job {job_id}: {str(e)}\n"
            f"{traceback.format_exc()}"
        )
        raise HTTPException(status_code=500, detail="An error occurred while processing thumbnail request")


@router.post("/{job_id}/generate")
async def generate_thumbnails(
    job_id: int,
    background_tasks: BackgroundTasks,
    sizes: list[str] = Query(["small", "medium", "large"], description="Thumbnail sizes to generate"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> JSONResponse:
    """
    Generate thumbnails for a job in the background
    
    Args:
        job_id: Job ID
        sizes: List of thumbnail sizes to generate
        background_tasks: FastAPI background tasks
        
    Returns:
        JSONResponse: Status of thumbnail generation request
    """
    logger.info(f"[Thumbnail Generate] Request for job {job_id}, sizes: {sizes}")
    
    try:
        # Validate job and authorization
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.owner_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Not authorized to access this job")
        
        # Validate sizes
        invalid_sizes = [s for s in sizes if s not in thumbnail_service.THUMBNAIL_SIZES]
        if invalid_sizes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sizes: {invalid_sizes}. Must be one of: {list(thumbnail_service.THUMBNAIL_SIZES.keys())}"
            )
        
        # Add background task
        background_tasks.add_task(
            _generate_thumbnails_background,
            job_id=job_id,
            user_id=job.owner_id,
            source_language=job.source_language,
            sizes=sizes
        )
        
        return JSONResponse(
            content={
                "message": "Thumbnail generation started",
                "job_id": job_id,
                "sizes": sizes
            },
            status_code=202
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Thumbnail Generate] Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error starting thumbnail generation")

async def _generate_thumbnails_background(job_id: int, user_id: int, source_language: str, sizes: list[str]):
    """
    Background task to generate thumbnails
    """
    try:
        logger.info(f"[Background] Starting thumbnail generation for job {job_id}")
        
        # Create job context and file manager
        job_context = JobContext(
            user_id=user_id,
            job_id=job_id,
            source_language=source_language
        )
        file_manager = get_file_path_manager()
        
        # Get source video path
        source_video_path = file_manager.get_file_path(
            context=job_context,
            file_type=FileType.SOURCE_VIDEO
        )
        
        if not os.path.exists(source_video_path):
            logger.error(f"[Background] Source video not found: {source_video_path}")
            return
        
        # Ensure thumbnail directory exists
        file_manager.get_directory_path(
            context=job_context,
            dir_type=FileType.THUMBNAIL_DIR
        )
        
        # Generate thumbnails for each size
        timestamp = thumbnail_service.get_optimal_timestamp(source_video_path)
        
        for size in sizes:
            thumbnail_path = file_manager.get_file_path(
                context=job_context,
                file_type=FileType.THUMBNAIL,
                size=size
            )
            
            success = thumbnail_service.generate_thumbnail(
                video_path=source_video_path,
                output_path=thumbnail_path,
                size=size,
                timestamp=timestamp
            )
            
            if success:
                logger.info(f"[Background] Generated {size} thumbnail for job {job_id}")
            else:
                logger.error(f"[Background] Failed to generate {size} thumbnail for job {job_id}")
        
        logger.info(f"[Background] Completed thumbnail generation for job {job_id}")
        
    except Exception as e:
        logger.error(f"[Background] Error generating thumbnails for job {job_id}: {str(e)}")

@router.get("/{job_id}/info")
async def get_thumbnail_info(
    job_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    Get information about available thumbnails for a job
    
    Args:
        job_id: Job ID
        
    Returns:
        Dict: Information about available thumbnails
    """
    logger.info(f"[Thumbnail Info] Request for job {job_id}")
    
    try:
        # Validate job and authorization
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.owner_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Not authorized to access this job")
        
        # Create job context and file manager
        job_context = JobContext(
            user_id=job.owner_id,
            job_id=job_id,
            source_language=job.source_language
        )
        file_manager = get_file_path_manager()
        
        # Check which thumbnails exist
        available_thumbnails = {}
        
        for size in thumbnail_service.THUMBNAIL_SIZES:
            thumbnail_path = file_manager.get_file_path(
                context=job_context,
                file_type=FileType.THUMBNAIL,
                size=size
            )
            
            if os.path.exists(thumbnail_path):
                stat = os.stat(thumbnail_path)
                available_thumbnails[size] = {
                    "exists": True,
                    "path": thumbnail_path,
                    "size_bytes": stat.st_size,
                    "modified": stat.st_mtime,
                    "url": f"/api/v1/thumbnails/{job_id}?size={size}"
                }
            else:
                available_thumbnails[size] = {
                    "exists": False,
                    "url": f"/api/v1/thumbnails/{job_id}?size={size}"
                }
        
        return {
            "job_id": job_id,
            "thumbnails": available_thumbnails,
            "total_available": len([t for t in available_thumbnails.values() if t["exists"]])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Thumbnail Info] Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error getting thumbnail information")