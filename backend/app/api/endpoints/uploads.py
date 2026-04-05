import os
import logging
import shutil
import time
import tempfile
import json
from datetime import datetime
from typing import Any, Dict, Union

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Form, status
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.models.job import Job, JobStatus
from app.schemas.job import JobCreate
from app.core.config import get_settings
from app.core.config import settings
from app.services.video_service import VideoService
from app.services.job_service import JobService
from app.services.usage_tracker_service import UsageTrackerService
from app.utils.file_path_manager import get_file_path_manager, FileType
from app.utils.file_utils import ensure_directory_exists
from app.core.tasks import process_video_job

router = APIRouter()
logger = logging.getLogger(__name__)

config_settings = get_settings()

if not hasattr(config_settings, 'FRONTEND_URL') or not config_settings.FRONTEND_URL:
    config_settings.FRONTEND_URL = "http://localhost:8080"

@router.post("/video", status_code=status.HTTP_201_CREATED)
async def upload_video(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    file: UploadFile = File(...),
    title: str = Form(None),
    description: str = Form(None),
    source_language: str = Form("auto"),
    target_languages: str = Form("zh"),
    generate_subtitles: bool = Form(True),
    generate_dubbing: bool = Form(False),
    video_format: str = Form("mp4"),
    resolution: str = Form("1080p"),
    subtitle_style: Union[str, Dict[str, Any]] = Form("default", description="Subtitle style as JSON string or preset name")
) -> Any:
    """
    Upload a video file, create a new processing job, and queue it.
    This endpoint no longer checks for duplicates based on content hash.
    """
    job_title = title or os.path.splitext(file.filename)[0]
    logger.info(f"[USER:{current_user.id}] Starting upload for new job: {file.filename}, Title: {job_title}")

    if not file.filename or not VideoService.is_valid_video_extension(file.filename):
        logger.warning(f"[USER:{current_user.id}] Invalid video format: {file.filename}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video file format.")

    tmp_path = None
    job_service = JobService(db, data_dir=settings.STORAGE_BASE_DIR)
    job = None
    try:
        # 1. Create a job record first to get a job_id
        job_data = {
            "title": job_title,
            "description": description,
            "status": JobStatus.PENDING,
            "source_language": source_language,
            "target_languages": target_languages,
            "video_filename": file.filename,
            "subtitle_style": subtitle_style
        }
        job = job_service.create_job(
            user_id=current_user.id,
            job_data=job_data
        )
        logger.info(f"[USER:{current_user.id}, JOB:{job.id}] Job record created with status PENDING.")

        # 2. Determine final storage path
        from app.models.job_context import JobContext
        file_manager = get_file_path_manager()
        context = JobContext(
            user_id=current_user.id,
            job_id=job.id,
            source_language=source_language,
            target_languages=target_languages.split(',') if target_languages else []
        )
        final_file_path = file_manager.get_file_path(
            context=context,
            file_type=FileType.SOURCE_VIDEO,
            filename=file.filename
        )
        ensure_directory_exists(os.path.dirname(final_file_path))

        # 3. Save the uploaded file directly to the final destination
        try:
            file_manager.copy_fileobj(file.file, final_file_path)
            logger.info(f"[JOB:{job.id}] Video file saved directly to final storage: {final_file_path}")
        except Exception as e:
            logger.error(f"[JOB:{job.id}] Failed to save uploaded file to {final_file_path}: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save uploaded file.")
        finally:
            file.file.close()

        # 4. Get video metadata and check usage
        video_service = VideoService(file_manager)
        usage_tracker_service = UsageTrackerService(db)
        
        # Use the new method that handles file path resolution automatically
        metadata = video_service.get_video_metadata_with_manager(final_file_path)
        video_duration = metadata.get('duration')
        if video_duration:
            try:
                duration_seconds = float(video_duration)
                minutes_to_add = (duration_seconds + 59) // 60
                usage_tracker_service.check_and_update_video_minutes(user_id=current_user.id, minutes_to_add=int(minutes_to_add))
                job.video_duration = duration_seconds # Save duration to job
            except (ValueError, TypeError):
                logger.warning(f"[JOB:{job.id}] Could not parse video duration '{video_duration}'.")
        else:
            logger.warning(f"[JOB:{job.id}] Could not extract video duration.")

        # 5. Update job status to QUEUED and save final details
        # Use file_manager to get file size instead of os.path.getsize
        try:
            file_size_bytes = file_manager.get_file_size(final_file_path)
        except Exception as e:
            logger.error(f"[JOB:{job.id}] Failed to get file size for {final_file_path}: {e}")
            # Fallback: try to get size from local path
            try:
                local_path = file_manager.get_local_path(final_file_path)
                file_size_bytes = os.path.getsize(local_path)
            except Exception as fallback_e:
                logger.error(f"[JOB:{job.id}] Fallback file size check also failed: {fallback_e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to verify uploaded file.")
        
        job.file_path = final_file_path
        job.source_video_url = final_file_path # Ensure worker can find the file
        job.file_size = file_size_bytes
        db.commit() # Commit changes like file_path, file_size, and video_duration

        # 6. Track storage usage
        try:
            file_size_mb = file_size_bytes / (1024 * 1024)
            usage_tracker_service.check_and_update_storage_mb(user_id=current_user.id, mb_to_add=file_size_mb)
            logger.info(f"[USER:{current_user.id}] Storage usage updated by {file_size_mb:.2f} MB for file {file.filename}")
        except Exception as e:
            logger.error(f"[USER:{current_user.id}] Failed to track storage for uploaded file {final_file_path}: {e}", exc_info=True)

        # 7. Sync uploaded file to remote storage (R2/S3) if configured
        if config_settings.STORAGE_BACKEND.lower() == 's3':
            try:
                logger.info(f"[JOB:{job.id}] Starting sync of uploaded file to R2...")
                if file_manager.sync_to_remote(final_file_path):
                    logger.info(f"[JOB:{job.id}] Successfully synced uploaded file to R2: {final_file_path}")
                else:
                    logger.warning(f"[JOB:{job.id}] Failed to sync uploaded file to R2: {final_file_path}")
            except Exception as e:
                logger.error(f"[JOB:{job.id}] Error syncing uploaded file to R2: {e}", exc_info=True)
                # Don't fail the upload if sync fails

        logger.info(f"[USER:{current_user.id}, JOB:{job.id}] Job successfully created and queued for processing.")
        
        # Enqueue the job for background processing using Celery
        process_video_job.delay(job.id)
        logger.info(f"[JOB:{job.id}] Job enqueued for background processing via Celery.")

        return {
            "job_id": job.id,
            "user_job_number": job.user_job_number,  # Add user job number for frontend routing
            "status": job.status.value,
            "message": "Video uploaded successfully and job is queued for processing.",
            "filename": file.filename,
            "file_size": file_size_bytes,
        }

    except HTTPException as http_exc:
        logger.error(f"[USER:{current_user.id}] HTTPException during upload: {http_exc.detail}")
        if job:
            job.status = JobStatus.FAILED
            job.error_message = f"Upload failed: {http_exc.detail}"
            db.commit()
        raise http_exc

    except Exception as e:
        error_message = f"An unexpected error occurred during the upload process: {str(e)}"
        logger.error(f"[USER:{current_user.id}] {error_message}", exc_info=True)
        if job:
            job.status = JobStatus.FAILED
            job.error_message = error_message
            db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_message)

    finally:
        # Clean up the temporary file if it still exists
        if tmp_path and file_manager.exists(tmp_path):
            file_manager.remove(tmp_path)
            logger.info(f"[USER:{current_user.id}] Cleaned up temporary file: {tmp_path}")

@router.post("/audio", status_code=status.HTTP_201_CREATED)
async def upload_audio(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    file: UploadFile = File(...),
    title: str = Form(None),
    description: str = Form(None),
    source_language: str = Form("auto"),
    target_languages: str = Form("zh"),
    generate_subtitles: bool = Form(True),
    generate_dubbing: bool = Form(False),
    video_filename: str = Form(""),
    subtitle_style: Union[str, Dict[str, Any]] = Form("default"),
) -> Any:
    """
    Upload an audio file (extracted on the client side from a video).
    Creates a new processing job that skips video preparation and audio extraction,
    going directly to transcription.
    """
    job_title = title or (os.path.splitext(video_filename)[0] if video_filename else os.path.splitext(file.filename)[0])
    logger.info(f"[USER:{current_user.id}] Audio upload for new job: {file.filename}, Title: {job_title}")

    # Validate audio format
    valid_audio_extensions = {'.mp3', '.wav', '.flac', '.ogg', '.webm', '.m4a'}
    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ''
    if file_ext not in valid_audio_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid audio file format: {file_ext}. Supported: {', '.join(valid_audio_extensions)}"
        )

    job_service = JobService(db, data_dir=settings.STORAGE_BASE_DIR)
    job = None
    try:
        # 1. Create a job record
        job_data = {
            "title": job_title,
            "description": description,
            "status": JobStatus.PENDING,
            "source_language": source_language,
            "target_languages": target_languages,
            "video_filename": video_filename or file.filename,
            "subtitle_style": subtitle_style,
        }
        job = job_service.create_job(user_id=current_user.id, job_data=job_data)
        logger.info(f"[USER:{current_user.id}, JOB:{job.id}] Job record created (audio-only mode).")

        # 2. Determine storage path for the audio file
        from app.models.job_context import JobContext
        file_manager = get_file_path_manager()
        context = JobContext(
            user_id=current_user.id,
            job_id=job.id,
            source_language=source_language,
            target_languages=target_languages.split(',') if target_languages else []
        )
        audio_file_path = file_manager.get_file_path(
            context=context,
            file_type=FileType.COMPRESSED_AUDIO,
            filename="api_ready_audio.mp3"
        )
        ensure_directory_exists(os.path.dirname(audio_file_path))

        # 3. Save the uploaded audio file
        try:
            file_manager.copy_fileobj(file.file, audio_file_path)
            logger.info(f"[JOB:{job.id}] Audio file saved to: {audio_file_path}")
        except Exception as e:
            logger.error(f"[JOB:{job.id}] Failed to save audio: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save audio file.")
        finally:
            file.file.close()

        # 4. Get audio file size
        try:
            file_size_bytes = file_manager.get_file_size(audio_file_path)
        except Exception:
            file_size_bytes = 0

        # 5. Update job - mark as audio-only mode so workflow skips video/audio steps
        job.file_path = audio_file_path
        job.source_video_url = None  # No video uploaded
        job.file_size = file_size_bytes
        # Store metadata to signal audio-only mode to the workflow
        job.result_metadata = job.result_metadata or {}
        job.result_metadata['upload_mode'] = 'audio_only'
        job.result_metadata['audio_file_path'] = audio_file_path
        db.commit()

        # 6. Enqueue for background processing
        process_video_job.delay(job.id)
        logger.info(f"[JOB:{job.id}] Audio-only job enqueued for processing.")

        return {
            "job_id": job.id,
            "user_job_number": job.user_job_number,
            "status": job.status.value,
            "message": "Audio uploaded successfully. Skipping video processing, going directly to transcription.",
            "filename": file.filename,
            "file_size": file_size_bytes,
        }

    except HTTPException:
        raise
    except Exception as e:
        error_message = f"Unexpected error during audio upload: {str(e)}"
        logger.error(f"[USER:{current_user.id}] {error_message}", exc_info=True)
        if job:
            job.status = JobStatus.FAILED
            job.error_message = error_message
            db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_message)


@router.get("/supported-formats")
def get_supported_formats():
    """
    Get supported video and subtitle formats
    """
    return {
        "video_formats": VideoService.get_supported_video_formats(),
        "subtitle_formats": ["srt", "vtt"],
        "audio_formats": ["mp3", "wav"],
    }

@router.get("/supported-languages")
def get_supported_languages():
    """
    Get supported languages for transcription and translation
    """
    from app.core.languages import SOURCE_LANGUAGES, TARGET_LANGUAGES
    
    return {
        "source_languages": SOURCE_LANGUAGES,
        "target_languages": TARGET_LANGUAGES,
        # Legacy format for backward compatibility
        "language_codes": SOURCE_LANGUAGES[:13]  # Keep first 13 for legacy support
    }
