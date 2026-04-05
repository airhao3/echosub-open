"""
Video Compatibility Endpoint

This module provides endpoints to handle compatibility issues with video requests, 
particularly when original videos might not be available in the database.
"""

import os
import sys
import logging
import traceback
import json
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.api import deps
from app.api.url_token_auth import get_user_from_url_token
from app.models.user import User
from app.models.job_result import JobResult, ResultType
from app.api.endpoints.downloads import download_result

router = APIRouter()
logger = logging.getLogger(__name__)

def log_error(error_type: str, error: Exception, request_info: Dict[str, Any], extra_info: Dict[str, Any] = None) -> None:
    """
    Enhanced error logging for video preview issues.
    
    Args:
        error_type: Category of error (auth, db, file_system, etc.)
        error: The exception that occurred
        request_info: Information about the request (path, params, etc.)
        extra_info: Any additional context about the error
    """
    timestamp = datetime.now().isoformat()
    
    # Get traceback information
    exc_type, exc_value, exc_traceback = sys.exc_info()
    stack_trace = traceback.format_exception(exc_type, exc_value, exc_traceback)
    
    # Build structured error log
    error_log = {
        "timestamp": timestamp,
        "error_type": error_type,
        "error_message": str(error),
        "error_class": error.__class__.__name__,
        "request": request_info,
        "stack_trace": stack_trace
    }
    
    # Add any extra information
    if extra_info:
        error_log["extra_info"] = extra_info
        
    # Log as JSON for easier parsing by log management tools
    logger.error(f"VIDEO_PREVIEW_ERROR: {json.dumps(error_log, default=str)}")
    
    # Also log a human-readable summary
    logger.error(f"VIDEO PREVIEW ERROR [{error_type}]: {error.__class__.__name__}: {str(error)}")

@router.get("/compatibility/video/{job_id}")
async def get_best_available_video(
    request: Request,
    job_id: int,
    language: str = "zh",  # Default to Chinese if not specified
    streamable: bool = True,
    db: Session = Depends(deps.get_db),
):
    """
    Attempts to find the best available video for a job, trying original_video first,
    then falling back to subtitled_video if original is not available.
    
    This helps with compatibility for older jobs that might be missing certain result types.
    """
    # Capture request details for better logging
    request_info = {
        "path": f"/compatibility/video/{job_id}",
        "query_params": {
            "language": language,
            "streamable": streamable
        },
        "headers": dict(request.headers.items()),
        "client_ip": request.client.host if request.client else "unknown"
    }
    
    logger.info(f"Video compatibility request for job {job_id} with params: {request_info['query_params']}")
    
    # Authenticate user first
    try:
        user = await get_user_from_url_token(request, db)
        if not user:
            # Try standard auth from header
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.replace('Bearer ', '')
                # This is a simplified version - properly validate the token
                from app.core.security import verify_token
                
                try:
                    payload = verify_token(token)
                    user_id = int(payload.get("sub"))
                    user = db.query(User).filter(User.id == user_id).first()
                    logger.info(f"Authenticated with header token: User {user.id}")
                except Exception as auth_error:
                    log_error(
                        "authentication", 
                        auth_error, 
                        request_info,
                        {"auth_method": "header_token"}
                    )
    except Exception as auth_error:
        log_error("authentication", auth_error, request_info)
    
    if not user:
        logger.warning(f"Authentication failed for video request: job_id={job_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access this resource"
        )
        
    logger.info(f"User {user.id} authorized for video compatibility request")
    
    # Try to find original video first
    try:
        logger.info(f"Searching for original_video result for job_id={job_id}")
        original_video = db.query(JobResult).filter(
            JobResult.job_id == job_id,
            JobResult.result_type == ResultType.ORIGINAL_VIDEO
        ).first()
        
        # If found, return the original video
        if original_video:
            logger.info(f"Found original video record: ID={original_video.id}, Path={original_video.file_url}")
            file_path = original_video.file_url
            
            # Verify file exists
            if os.path.exists(file_path):
                logger.info(f"Original video file exists on disk: {file_path}")
                # Pass to standard download handler
                try:
                    # 对于原始视频，我们不使用download_result函数，而是直接返回文件，因为这种方式更可靠
                    logger.info(f"Directly returning original video file: {file_path}")
                    filename = os.path.basename(file_path)
                    
                    # 确定媒体类型
                    media_type = "application/octet-stream"  # 默认类型
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext in [".mp4"]:
                        media_type = "video/mp4"
                    elif ext in [".webm"]:
                        media_type = "video/webm"
                    elif ext in [".ogg", ".ogv"]:
                        media_type = "video/ogg"
                    elif ext in [".mov", ".qt"]:
                        media_type = "video/quicktime"
                        
                    logger.info(f"Media type for file {filename}: {media_type}")
                    
                    # 直接返回文件响应
                    return FileResponse(
                        path=file_path,
                        filename=filename,
                        media_type=media_type
                    )
                except Exception as e:
                    log_error(
                        "download", 
                        e, 
                        request_info,
                        {"file_path": file_path, "result_type": "original_video"}
                    )
                    # Continue to fallback options rather than failing
            else:
                file_info = {
                    "file_path": file_path,
                    "record_id": original_video.id,
                    "file_name": original_video.file_name if hasattr(original_video, 'file_name') else "unknown",
                    "parent_dir_exists": os.path.exists(os.path.dirname(file_path))
                }
                
                try:
                    # Try to get parent directory info
                    parent_dir = os.path.dirname(file_path)
                    if os.path.exists(parent_dir):
                        file_info["parent_dir_contents"] = os.listdir(parent_dir)[:10]
                except Exception as dir_error:
                    file_info["dir_listing_error"] = str(dir_error)
                    
                logger.warning(f"Original video file not found on disk: {file_path}")
                log_error(
                    "file_not_found", 
                    FileNotFoundError(f"File not found: {file_path}"), 
                    request_info,
                    file_info
                )
        else:
            # No original video in database
            logger.warning(f"No original_video record found for job {job_id}")
            
            # List all results for this job for debugging
            try:
                all_results = db.query(JobResult).filter(JobResult.job_id == job_id).all()
                result_info = [
                    {"id": r.id, "type": str(r.result_type), "language": r.language}
                    for r in all_results
                ]
                logger.info(f"Available results for job {job_id}: {result_info}")
            except SQLAlchemyError as db_error:
                log_error(
                    "database", 
                    db_error, 
                    request_info,
                    {"query": "all_results_for_job"}
                )
    except SQLAlchemyError as db_error:
        log_error(
            "database", 
            db_error, 
            request_info,
            {"query": "original_video_lookup"}
        )
    
    # If original video not found or file missing, try subtitled video
    try:
        logger.info(f"Searching for subtitled_video result for job_id={job_id}, language={language}")
        subtitled_video = db.query(JobResult).filter(
            JobResult.job_id == job_id,
            JobResult.result_type == ResultType.SUBTITLED_VIDEO,
            JobResult.language == language
        ).first()
        
        if subtitled_video:
            logger.info(f"Found subtitled video: ID={subtitled_video.id}, Language={language}, Path={subtitled_video.file_url}")
            file_path = subtitled_video.file_url
            
            # Verify file exists
            if os.path.exists(file_path):
                logger.info(f"Subtitled video file exists on disk: {file_path}")
                logger.info(f"Returning subtitled video as fallback for original video")
                # Return the subtitled video
                try:
                    return await download_result(
                        request=request,
                        job_id=job_id,
                        result_type="subtitled_video",
                        language=language,
                        streamable=streamable,
                        db=db
                    )
                except Exception as e:
                    log_error(
                        "download", 
                        e, 
                        request_info,
                        {"file_path": file_path, "result_type": "subtitled_video", "language": language}
                    )
            else:
                file_info = {
                    "file_path": file_path,
                    "record_id": subtitled_video.id,
                    "language": subtitled_video.language,
                    "file_name": subtitled_video.file_name if hasattr(subtitled_video, 'file_name') else "unknown",
                    "parent_dir_exists": os.path.exists(os.path.dirname(file_path))
                }
                
                try:
                    # Try to get parent directory info
                    parent_dir = os.path.dirname(file_path)
                    if os.path.exists(parent_dir):
                        file_info["parent_dir_contents"] = os.listdir(parent_dir)[:10]
                except Exception as dir_error:
                    file_info["dir_listing_error"] = str(dir_error)
                    
                logger.warning(f"Subtitled video file not found on disk: {file_path}")
                log_error(
                    "file_not_found", 
                    FileNotFoundError(f"File not found: {file_path}"), 
                    request_info,
                    file_info
                )
        else:
            logger.warning(f"No subtitled_video record with language {language} found for job {job_id}")
            
            # Try finding any subtitled video regardless of language
            try:
                any_subtitled = db.query(JobResult).filter(
                    JobResult.job_id == job_id,
                    JobResult.result_type == ResultType.SUBTITLED_VIDEO
                ).all()
                
                if any_subtitled:
                    available_langs = [sv.language for sv in any_subtitled]
                    logger.info(f"Found subtitled videos in other languages: {available_langs}")
                    
                    # Suggest using an available language
                    if available_langs:
                        logger.info(f"Suggesting alternate language: {available_langs[0]}")
                        # Try with the first available language
                        first_video = any_subtitled[0]
                        
                        if os.path.exists(first_video.file_url):
                            logger.info(f"Returning subtitled video with language {first_video.language} as fallback")
                            return await download_result(
                                request=request,
                                job_id=job_id,
                                result_type="subtitled_video",
                                language=first_video.language,
                                streamable=streamable,
                                db=db
                            )
            except SQLAlchemyError as db_error:
                log_error(
                    "database", 
                    db_error, 
                    request_info,
                    {"query": "any_subtitled_video_lookup"}
                )
    except SQLAlchemyError as db_error:
        log_error(
            "database", 
            db_error, 
            request_info,
            {"query": "subtitled_video_lookup"}
        )
    
    # If no videos found at all
    job_info = {"job_id": job_id, "requested_language": language}
    try:
        # Get job details
        from app.models.job import Job
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job_info["job_status"] = job.status
            job_info["job_owner_id"] = job.owner_id
            job_info["job_created_at"] = str(job.created_at)
    except Exception as e:
        job_info["job_query_error"] = str(e)
    
    logger.error(f"No suitable video found for job {job_id}")
    log_error(
        "no_video_available", 
        Exception(f"No video available for job {job_id}"), 
        request_info,
        job_info
    )
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No suitable video found for this job. Please check that the job has completed processing."
    )
