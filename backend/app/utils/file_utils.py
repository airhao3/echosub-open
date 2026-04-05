"""
Utility functions for file handling operations.

This module provides general file utility functions that are not specific to
path management. For path-related utilities, see file_path_manager.py.
"""
import glob
import os
import hashlib
import logging
import mimetypes
from typing import Optional, List, Union

from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.job import JobResult, ResultType
from app.api import deps
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)



def parse_time_to_seconds(time_str: str) -> float:
    """
    Parse a time string (e.g., '00:00:21,480' or '00:00:21.480') and convert it to seconds.
    """
    if ',' in time_str:
        time_part, ms_part = time_str.split(',')
    elif '.' in time_str:
        time_part, ms_part = time_str.split('.')
    else:
        time_part = time_str
        ms_part = '0'

    parts = list(map(int, time_part.split(':')))
    seconds = parts[-1]
    minutes = parts[-2] if len(parts) > 1 else 0
    hours = parts[-3] if len(parts) > 2 else 0

    total_seconds = hours * 3600 + minutes * 60 + seconds + int(ms_part) / 1000.0
    return total_seconds


def get_file_size(file_path: str) -> int:
    """
    Get the size of a file in bytes.

    Args:
        file_path: The path to the file.

    Returns:
        The size of the file in bytes.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        PermissionError: If there's a permission error reading the file.
        Exception: For other errors during file size retrieval.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    if not os.access(file_path, os.R_OK):
        raise PermissionError(f"No read permission for file: {file_path}")
    try:
        return os.path.getsize(file_path)
    except Exception as e:
        logger.error(f"Error getting file size for {file_path}: {str(e)}")
        raise

def get_mime_type(file_path: str) -> Optional[str]:
    """
    Get the MIME type of a file.

    Args:
        file_path: The path to the file.

    Returns:
        The MIME type string (e.g., 'video/mp4') or None if it cannot be determined.
    
    Raises:
        FileNotFoundError: If the file doesn't exist.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found for MIME type detection: {file_path}")
    
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        return mime_type
    else:
        # Fallback for common types if mimetypes fails for some reason
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.mp4':
            return 'video/mp4'
        elif ext == '.srt':
            return 'application/x-subrip'
        elif ext == '.vtt':
            return 'text/vtt'
        logger.warning(f"Could not determine MIME type for {file_path}")
        return None

def ensure_directory_exists(dir_path: str):
    """
    Ensure that a directory exists. If it doesn't, create it.

    Args:
        dir_path: The path to the directory.
    
    Raises:
        OSError: If there's an error creating the directory.
    """
    try:
        os.makedirs(dir_path, exist_ok=True)
        logger.info(f"Ensured directory exists: {dir_path}")
    except OSError as e:
        logger.error(f"Error creating directory {dir_path}: {e}")
        raise

def find_video_file(job_id: int, job: Job = None, result_type: ResultType = None, language: str = None) -> Optional[str]:
    """
    Utility function to find video files with multiple fallback strategies
    
    Args:
        job_id: The job ID to find the video for
        job: Optional Job object containing job details
        result_type: Type of video to find (e.g., ORIGINAL_VIDEO, SUBTITLED_VIDEO)
        language: Language code for localized videos (e.g., 'en', 'zh')
        
    Returns:
        Path to the video file if found, None otherwise
    """
    logger.info(f"Finding video for job {job_id}, type {result_type}, language {language}")
    
    # Start with empty path
    video_path = None
    
    # Strategy 1: Direct job attribute (for original videos)
    if job and result_type == ResultType.ORIGINAL_VIDEO and hasattr(job, 'source_video_url') and job.source_video_url:
        video_path = job.source_video_url
        logger.info(f"Strategy 1: Found from job.source_video_url: {video_path}")
    
    # Strategy 2: Query database (works for original and subtitled)
    if not video_path or not os.path.exists(video_path):
        try:
            db = next(deps.get_db())
            query = db.query(JobResult).filter(JobResult.job_id == job_id)
            
            if result_type:
                query = query.filter(JobResult.result_type == result_type)
            
            if language:
                query = query.filter(JobResult.language == language)
                
            result = query.first()
            
            # If not found with language filter, try without language filter
            if not result and language and result_type:
                result = db.query(JobResult).filter(
                    JobResult.job_id == job_id,
                    JobResult.result_type == result_type
                ).first()
            
            if result and result.file_url:
                video_path = result.file_url
                logger.info(f"Strategy 2: Found in database: {video_path}")
        except Exception as e:
            logger.error(f"Database lookup error: {e}")
    
    # Strategy 3: Common file paths based on job ID
    if not video_path or not os.path.exists(video_path):
        video_filename = job.video_filename if job and hasattr(job, 'video_filename') else None
        
        patterns = [
            # Job directory with job ID
            os.path.join(settings.JOB_DIR, str(job_id), "*.mp4"),
            os.path.join(settings.JOB_DIR, str(job_id), "*_subtitled.mp4"),
            os.path.join(settings.JOB_DIR, str(job_id), f"*_{language}.mp4") if language else None,
            
            # Upload directory with job ID
            os.path.join(settings.UPLOAD_DIR, f"{job_id}_*.mp4"),
            
            # With filename if available
            os.path.join(settings.UPLOAD_DIR, f"{job_id}_{video_filename}") if video_filename else None,
            os.path.join(settings.JOB_DIR, str(job_id), video_filename) if video_filename else None,
        ]
        
        # Filter out None values
        patterns = [p for p in patterns if p]
        
        # Try each pattern
        for pattern in patterns:
            matches = glob.glob(pattern)
            if matches:
                video_path = matches[0]  # Take first match
                logger.info(f"Strategy 3: Found with pattern {pattern}: {video_path}")
                break
    
    # Final verification
    if video_path and os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        logger.info(f"Verified video file exists and is not empty: {video_path}")
        return video_path
    else:
        logger.error(f"Could not find valid video file for job {job_id}")
        return None
