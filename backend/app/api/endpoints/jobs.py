from typing import Any, Dict, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks, Path, Query
from sqlalchemy.orm import Session
import logging
import os
import shutil
import json

from app.api import deps
from app.models.user import User
from app.models.job import Job, JobStatus
from app.models.job import JobResult, ResultType
from app.schemas.job import Job as JobSchema, JobCreate, JobUpdate, JobBulkDelete
from app.core.config import settings
from app.services.workflow_service import WorkflowService
from app.services.video_tracking_service import VideoTrackingService
# Import the new status service
from app.services.status_service import StatusUpdateService
# Import stage mapping service for user-friendly progress display
from app.services.stage_mapping_service import StageMappingService
from app.services import progress_cache
# Import the new models from app.models.py file
from app import models as app_models

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{user_job_number}/status", response_model=Dict[str, Any])
def get_job_status(
    user_job_number: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Dict[str, Any]:
    """
    Get detailed status information for a job, including all workflow steps.
    
    Returns a dictionary with:
    - job_id: The job ID
    - status: Overall job status (PENDING, PROCESSING, COMPLETED, FAILED, CANCELED)
    - progress: Overall job progress percentage (0-100)
    - status_message: Current status message
    - steps: List of all workflow steps with their individual status and progress
    """
    # Import the job numbering service
    from app.services.job_numbering_service import JobNumberingService
    
    # Get job by user job number
    job = JobNumberingService.get_job_by_user_number(db, current_user.id, user_job_number)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job #{user_job_number} not found for current user"
        )
    
    # Use the StatusUpdateService to get the detailed job status, which includes all steps.
    detailed_status = StatusUpdateService.get_job_status(db, job.id)
    
    # If the service returns None (e.g., job not found in the new system),
    # we can fall back to a basic status or raise an error.
    # For now, we rely on the initial job query for the existence check.
    if detailed_status is None:
        # This might happen if the job exists in the `jobs` table but not in `job_steps`.
        # We can construct a minimal response to avoid a crash.
        detailed_status = {
            "job_id": job.id,
            "status": job.status.value,
            "progress": job.progress or 0,
            "status_message": job.error_message or "Status tracking not fully initialized.",
            "steps": []
        }
    
    # Transform detailed backend status to user-friendly frontend format
    # This provides simplified stage grouping for better UX
    try:
        # Create user-friendly progress update using stage mapping
        frontend_status = StageMappingService.create_progress_update_for_frontend(
            job_id=job.id,
            backend_stages_completed=[],  # Would be populated from detailed_status
            current_stage=None,  # Would be extracted from detailed_status  
            current_progress=detailed_status.get("progress", 0),
            status_message=detailed_status.get("status_message", "")
        )
        
        # Merge frontend-friendly data with existing detailed status
        detailed_status["simplified_steps"] = frontend_status["steps"]
        detailed_status["current_frontend_stage"] = frontend_status.get("current_stage")
        detailed_status["user_friendly_message"] = frontend_status.get("message", detailed_status.get("status_message", ""))
        
        logger.info(f"Enhanced job {job_id} status with simplified frontend stages")
        
    except Exception as e:
        logger.warning(f"Failed to create simplified frontend stages for job {job_id}: {str(e)}")
        # Continue with original detailed_status if mapping fails
    
    print("\n" + "="*20 + f" DEBUG: API RESPONSE FOR JOB {job_id} " + "="*20)
    import json
    print(json.dumps(detailed_status, indent=2))
    print("="*80 + "\n")

    return detailed_status


@router.get("/{job_id}/status/simplified", response_model=Dict[str, Any])
def get_job_status_simplified(
    job_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Dict[str, Any]:
    """
    Get simplified, user-friendly status information for a job.
    
    This endpoint groups the 16 detailed backend processing stages into 6 user-friendly stages:
    - UPLOADING: Video upload and preparation (3 stages)
    - ANALYZING: Audio extraction and analysis (1 stage) 
    - TRANSCRIBING: Speech-to-text conversion and refinement (4 stages)
    - TRANSLATING: Translation and semantic optimization (3 stages)
    - GENERATING: Subtitle and video processing (3 stages)
    - FINALIZING: Export and cleanup (2 stages)
    
    Returns a dictionary optimized for frontend progress display with:
    - Simplified stage names and descriptions
    - User-friendly status messages
    - Grouped progress calculation
    - Reduced complexity for end users
    """
    # First check if the job exists and belongs to the current user
    job = db.query(Job).filter(Job.id == job_id, Job.owner_id == current_user.id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found or does not belong to current user"
        )
    
    try:
        # Get detailed status from the status service
        detailed_status = StatusUpdateService.get_job_status(db, job_id)
        
        if detailed_status is None:
            # Fallback for jobs without detailed status tracking
            simplified_status = StageMappingService.create_progress_update_for_frontend(
                job_id=job.id,
                backend_stages_completed=[],
                current_stage=None,
                current_progress=job.progress or 0,
                status_message=job.error_message or "Processing..."
            )
        else:
            # Extract backend stage information from detailed status
            completed_stages = []
            current_stage = None
            current_stage_progress = 0.0
            
            # Extract completed stages from detailed status steps
            if "steps" in detailed_status and detailed_status["steps"]:
                for step in detailed_status["steps"]:
                    step_name = step.get("step_name", "")
                    step_status = step.get("status", "")
                    step_progress = step.get("progress", 0)
                    
                    if step_status == "completed":
                        completed_stages.append(step_name)
                    elif step_status in ["processing", "in_progress"]:
                        current_stage = step_name
                        current_stage_progress = step_progress
            
            # Create simplified frontend status
            simplified_status = StageMappingService.create_progress_update_for_frontend(
                job_id=job.id,
                backend_stages_completed=completed_stages,
                current_stage=current_stage,
                current_progress=current_stage_progress,
                status_message=detailed_status.get("status_message", "")
            )
        
        logger.info(f"Generated simplified status for job {job_id}")
        return simplified_status
        
    except Exception as e:
        logger.error(f"Failed to generate simplified status for job {job_id}: {str(e)}")
        # Return basic fallback status
        return {
            "job_id": job.id,
            "status": job.status.value,
            "progress": job.progress or 0,
            "message": job.error_message or "Processing...",
            "status_message": job.error_message or "Processing...",
            "current_stage": None,
            "steps": StageMappingService.get_simplified_steps_for_frontend()
        }

@router.get("/{job_id}/progress", response_model=Dict[str, Any])
def get_job_realtime_progress(
    job_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
) -> Dict[str, Any]:
    """
    Get the real-time processing progress of a job from the cache.
    This provides the most up-to-date, granular progress information transformed for frontend consumption.
    """
    # First, verify that the job exists and belongs to the user to ensure authorization.
    job = db.query(Job).filter(Job.id == job_id, Job.owner_id == current_user.id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or you do not have permission to view it.",
        )

    progress_data = progress_cache.get_progress(job_id)

    if progress_data.get("status") == "found":
        cached_data = progress_data.get("data", {})
        
        # Transform the cached data into frontend-expected format
        events = cached_data.get("events", [])
        
        # Create steps based on processing stages - aligned with actual workflow
        stage_mapping = {
            # UPLOADING: Only frontend upload progress (handled separately in frontend)
            'INITIALIZED': 'TRANSCRIBING',           # Backend initialization starts transcription
            'VIDEO_DOWNLOAD': 'TRANSCRIBING',        # Video processing starts
            'PREPROCESSING': 'TRANSCRIBING',         # Video preprocessing
            'AUDIO_EXTRACTION': 'TRANSCRIBING',      # Extract audio for transcription
            'TRANSCRIPTION': 'TRANSCRIBING',         # Speech-to-text conversion
            'TEXT_SEGMENTATION': 'ANALYZING',        # Text analysis begins
            'TEXT_TAGGING': 'ANALYZING',            # Text tagging for alignment
            'TEXT_REFINEMENT': 'ANALYZING',          # Text refinement (refine part)
            'SEMANTIC_ANALYSIS': 'ANALYZING',        # Semantic analysis (summary part)
            'TERMINOLOGY_EXTRACTION': 'ANALYZING',   # Terminology extraction (terminology part)
            'TRANSLATION': 'TRANSLATING',            # Translation processing
            'SUBTITLE_GENERATION': 'GENERATING',     # Start generating outputs
            'DUBBING': 'GENERATING',                # Audio dubbing if enabled
            'VIDEO_PROCESSING': 'GENERATING',        # Video compression and processing
            'FILE_EXPORT': 'FINALIZING',           # Export final files
            'CLEANUP': 'FINALIZING'                 # Cleanup and finalization
        }
        
        # Initialize step status with correct order
        steps = [
            {'step_name': 'UPLOADING', 'status': 'pending', 'progress': 0, 'details': ''},
            {'step_name': 'TRANSCRIBING', 'status': 'pending', 'progress': 0, 'details': ''},
            {'step_name': 'ANALYZING', 'status': 'pending', 'progress': 0, 'details': ''},
            {'step_name': 'TRANSLATING', 'status': 'pending', 'progress': 0, 'details': ''},
            {'step_name': 'GENERATING', 'status': 'pending', 'progress': 0, 'details': ''},
            {'step_name': 'FINALIZING', 'status': 'pending', 'progress': 0, 'details': ''}
        ]
        
        # Process events to update step status
        for event in events:
            stage = event.get('stage')
            event_type = event.get('event_type')
            progress = event.get('progress', 0)
            detail = event.get('detail', '')
            
            if stage and stage in stage_mapping:
                frontend_step = stage_mapping[stage]
                step_index = next((i for i, s in enumerate(steps) if s['step_name'] == frontend_step), None)
                
                if step_index is not None:
                    if event_type == 'stage_start':
                        steps[step_index]['status'] = 'processing'
                        steps[step_index]['progress'] = max(steps[step_index]['progress'], 1)
                        if detail:
                            steps[step_index]['details'] = detail
                    elif event_type == 'stage_complete':
                        steps[step_index]['status'] = 'completed'
                        steps[step_index]['progress'] = 100
                        if detail:
                            steps[step_index]['details'] = detail
                    elif event_type == 'stage_progress' or not event_type:
                        steps[step_index]['status'] = 'processing'
                        steps[step_index]['progress'] = max(steps[step_index]['progress'], progress)
                        if detail:
                            steps[step_index]['details'] = detail
        
        # Get the latest status information
        latest_event = events[-1] if events else {}
        overall_progress = cached_data.get('overall_progress', latest_event.get('overall_progress', 0))
        status_message = latest_event.get('detail', latest_event.get('formatted_message', 'Processing...'))
        job_status = cached_data.get('status', 'processing')
        
        return {
            "job_id": job_id,
            "status": job_status,
            "progress": overall_progress,
            "status_message": status_message,
            "steps": steps,
            "message": status_message,
            "current_stage": cached_data.get('current_stage'),
            "last_updated": cached_data.get('last_updated')
        }
    
    # If not found in cache, return database status as fallback.
    return {
        "job_id": job_id,
        "status": job.status.value,
        "progress": job.progress or 0,
        "status_message": job.error_message or "Initializing...",
        "message": job.error_message or "Initializing...", 
        "steps": [
            {'step_name': 'UPLOADING', 'status': 'pending', 'progress': 0, 'details': ''},
            {'step_name': 'TRANSCRIBING', 'status': 'pending', 'progress': 0, 'details': ''},
            {'step_name': 'ANALYZING', 'status': 'pending', 'progress': 0, 'details': ''},
            {'step_name': 'TRANSLATING', 'status': 'pending', 'progress': 0, 'details': ''},
            {'step_name': 'GENERATING', 'status': 'pending', 'progress': 0, 'details': ''},
            {'step_name': 'FINALIZING', 'status': 'pending', 'progress': 0, 'details': ''}
        ]
    }


@router.get("/", response_model=List[JobSchema])
def read_jobs(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve jobs owned by the current user.
    """
    jobs = db.query(Job).filter(Job.owner_id == current_user.id).offset(skip).limit(limit).all()
    
    # Add subtitle language preferences to each job
    from app.services.subtitle_preferences import SubtitlePreferencesService
    subtitle_prefs = SubtitlePreferencesService()
    
    for job in jobs:
        job.subtitle_languages = subtitle_prefs.get_subtitle_languages(job.id)
        
    return jobs

@router.post("/", response_model=JobSchema)
def create_job(
    *,
    db: Session = Depends(deps.get_db),
    job_in: JobCreate,
    current_user: User = Depends(deps.get_current_user),
    background_tasks: BackgroundTasks,
) -> Any:
    """
    Create new job for video processing.
    """
    logger.info(f"Received request to create job for user {current_user.id} with payload: {job_in.dict()}")
    # In a complete implementation, we would:
    # 1. Upload the video file to storage (S3, etc.)
    # 2. Create the job record
    # 3. Start the processing with Celery
    
    # For now, we simply create the job record
    job_data = job_in.dict()
    
    # Handle subtitle languages - if not provided but subtitles are enabled,
    # use a default of source language (if not auto) and target language
    if job_data.get('generate_subtitles') and not job_data.get('subtitle_languages'):
        subtitle_langs = []
        
        # Add source language if not auto
        if job_data.get('source_language') != 'auto':
            subtitle_langs.append(job_data.get('source_language'))
            
        # Add target language
        if job_data.get('target_languages'):
            target_langs = job_data.get('target_languages').split(',')
            subtitle_langs.extend(target_langs)
            
        # Limit to 2 languages max
        job_data['subtitle_languages'] = subtitle_langs[:2]
    
    # Remove subtitle_languages from job_data to avoid database errors
    subtitle_langs = job_data.pop('subtitle_languages', [])
    
    # Import services
    from app.services.subtitle_preferences import SubtitlePreferencesService
    from app.services.job_numbering_service import JobNumberingService
    from app.services.language_slots_service import LanguageSlotsService
    
    subtitle_prefs = SubtitlePreferencesService()
    
    # Check language slots quota before creating the job
    target_languages = job_data.get('target_languages', '')
    language_slots_needed = LanguageSlotsService.calculate_language_slots_from_string(target_languages)
    
    if language_slots_needed > 0:
        # Check quota using the cumulative method (recommended for fairness)
        allowed, message, details = LanguageSlotsService.check_language_slots_quota(
            db, current_user.id, target_languages, calculation_method="cumulative"
        )
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": message,
                    "quota_details": details,
                    "language_slots_needed": language_slots_needed
                }
            )
    
    # Get the next job number for this user
    user_job_number = JobNumberingService.assign_job_number_atomic(db, current_user.id)
    
    job = Job(
        **job_data,
        owner_id=current_user.id,
        user_job_number=user_job_number,
        status=JobStatus.PENDING,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Track language slots usage after successful job creation
    if language_slots_needed > 0:
        try:
            LanguageSlotsService.track_language_slots_usage(
                db, current_user.id, target_languages, calculation_method="cumulative"
            )
        except Exception as e:
            logger.warning(f"Failed to track language slots usage for job {job.id}: {str(e)}")
            # Don't fail the job creation if usage tracking fails
    
    # Save subtitle language preferences
    if subtitle_langs:
        subtitle_prefs.save_subtitle_languages(job.id, subtitle_langs)
        logger.info(f"Saved subtitle languages for job {job.id}: {subtitle_langs}")
    
    # The content_hash must be provided when creating a job this way
    if not job.content_hash:
        raise HTTPException(
            status_code=422,
            detail="content_hash is required when creating a job without a file upload."
        )

    # Trigger the Celery task to process the job in the background
    from app.core.tasks import process_video_job
    logger.info(f"Submitting job {job.id} to Celery worker...")
    process_video_job.delay(job.id)
    logger.info(f"Dispatched job {job.id} to Celery worker for processing with hash {job.content_hash}")
    
    return job

@router.get("/{job_id}", response_model=JobSchema)
def read_job(
    *,
    db: Session = Depends(deps.get_db),
    job_id: int,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get job by ID.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # Add subtitle language preferences to the job
    from app.services.subtitle_preferences import SubtitlePreferencesService
    subtitle_prefs = SubtitlePreferencesService()
    
    # Attach subtitle_languages to the job object before returning
    # The JobSchema will automatically pick it up if configured correctly
    job.subtitle_languages = subtitle_prefs.get_subtitle_languages(job.id)
    
    return job

@router.put("/{job_id}", response_model=JobSchema)
def update_job(
    *,
    db: Session = Depends(deps.get_db),
    job_id: int,
    job_in: JobUpdate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update job by ID.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # If job is already processing/completed, don't allow changes to settings
    if job.status != JobStatus.PENDING and not current_user.is_superuser:
        raise HTTPException(
            status_code=400,
            detail="Cannot modify job that is already in progress or completed",
        )
    
    # Update job
    for field, value in job_in.dict(exclude_unset=True).items():
        setattr(job, field, value)
    
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

@router.post("/{job_id}/reprocess", response_model=Dict[str, Any])
def reprocess_job(
    *,
    job_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Reprocess an existing job.
    This will increment the processing count in the video tracking system.
    """
    # Check if job exists and belongs to the current user
    job = db.query(Job).filter(Job.id == job_id, Job.owner_id == current_user.id).first()
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found or you don't have permission to access it"
        )
    
    # Initialize services
    workflow_service = WorkflowService(db)
    video_tracking = VideoTrackingService(db)
    
    try:
        # Check if content hash is available
        if not job.content_hash:
            logger.warning(f"Job {job_id} doesn't have a content hash. Cannot track reprocessing.")
            return {
                "job_id": job_id,
                "status": "reprocessing",
                "message": "Job is being reprocessed, but tracking is limited (no content hash)"
            }
        
        # Update video processing record to indicate reprocessing
        if job.content_hash:
            # Update processing count for this video
            lang = job.target_languages if job.target_languages else "auto"
            result = video_tracking.register_processing_start(
                job.content_hash, 
                lang, 
                "subtitled_video", 
                job.video_filename,
                job_id
            )
            logger.info(f"Registered reprocessing for job {job_id} with hash {job.content_hash}. " +
                       f"Processing count: {result.process_count if result else 0}")
        
        # Reset job status to start reprocessing
        job.status = JobStatus.PENDING  # Using PENDING instead of non-existent QUEUED
        job.progress = 0
        job.completed_at = None
        db.commit()
        
        # Trigger the Celery task to reprocess the job
        from app.core.tasks import process_video_job
        process_video_job.delay(job.id)
        logger.info(f"Dispatched job {job.id} to Celery worker for reprocessing with hash {job.content_hash}")

        return {
            "job_id": job_id,
            "status": "reprocessing",
            "message": "Job has been queued for reprocessing"
        }
        
    except Exception as e:
        logger.error(f"Error reprocessing job {job_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error reprocessing job: {str(e)}"
        )

def cleanup_job_files(job: Job) -> None:
    """
    Clean up files associated with a job.
    
    Args:
        job: The job to clean up files for
    """
    def log_file_info(path: str) -> None:
        """Log detailed info about a file or directory"""
        try:
            if os.path.exists(path):
                stat = os.stat(path)
                logger.info(f"  Path: {path}")
                logger.info(f"  Type: {'Directory' if os.path.isdir(path) else 'File'}")
                logger.info(f"  Size: {stat.st_size} bytes")
                logger.info(f"  Permissions: {oct(stat.st_mode)}")
                logger.info(f"  Owner: {stat.st_uid}:{stat.st_gid}")
                logger.info(f"  Last modified: {datetime.fromtimestamp(stat.st_mtime)}")
            else:
                logger.info(f"  Path does not exist: {path}")
        except Exception as e:
            logger.error(f"  Error getting info for {path}: {str(e)}")

    def safe_remove(path: str) -> bool:
        """Safely remove a file or directory with error handling"""
        try:
            if os.path.isfile(path) or os.path.islink(path):
                os.remove(path)
                logger.info(f"  Deleted file: {path}")
                return True
            elif os.path.isdir(path):
                shutil.rmtree(path)
                logger.info(f"  Deleted directory: {path}")
                return True
            return False
        except Exception as e:
            logger.error(f"  Failed to delete {path}: {str(e)}")
            log_file_info(path)
            return False

    try:
        logger.info("\n" + "="*80)
        logger.info(f"=== STARTING JOB CLEANUP FOR JOB {job.id} ===")
        logger.info(f"Job details: {job.__dict__}")
        
        # Log important directories and permissions
        logger.info("\n=== DIRECTORY INFO ===")
        for dir_path in [settings.STORAGE_BASE_DIR, settings.UPLOAD_DIR]:
            logger.info(f"\nDirectory: {dir_path}")
            log_file_info(dir_path)
        
        # Clean up content directory using content_hash
        if job.content_hash:
            logger.info("\n=== CLEANING CONTENT DIRECTORY ===")
            content_dir = os.path.join(settings.STORAGE_BASE_DIR, "content", job.content_hash)
            logger.info(f"Content directory: {content_dir}")
            
            if os.path.exists(content_dir):
                logger.info("Found content directory. Contents:")
                for root, dirs, files in os.walk(content_dir):
                    for name in files:
                        logger.info(f"  {os.path.join(root, name)}")
                
                # Try to remove the entire directory first
                if not safe_remove(content_dir):
                    # If that fails, try to remove files individually
                    logger.warning("Failed to remove content directory, trying to remove files individually")
                    for root, dirs, files in os.walk(content_dir, topdown=False):
                        for name in files:
                            file_path = os.path.join(root, name)
                            safe_remove(file_path)
                        for name in dirs:
                            dir_path = os.path.join(root, name)
                            safe_remove(dir_path)
                    # Try removing the directory again
                    safe_remove(content_dir)
            else:
                logger.warning(f"Content directory does not exist: {content_dir}")
        
        # Clean up uploaded video file
        if job.video_filename:
            logger.info("\n=== CLEANING UPLOADED FILES ===")
            logger.info(f"Original video filename: {job.video_filename}")
            
            # Get the base filename without path if it includes one
            base_video_filename = os.path.basename(job.video_filename)
            logger.info(f"Base video filename: {base_video_filename}")
            
            # Get the content hash if available (without any extensions)
            content_hash = job.content_hash or ''
            name_without_ext, ext = os.path.splitext(base_video_filename)
            
            # Check all possible locations and variations
            filename_variations = []
            
            # 1. Original filename variations
            filename_variations.append(base_video_filename)  # Original filename
            
            # 2. Content hash based variations (if available)
            if content_hash:
                # Just the hash
                filename_variations.append(content_hash)
                # Common video extensions
                for ext in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']:
                    filename_variations.append(f"{content_hash}{ext}")
                    filename_variations.append(f"{content_hash.upper()}{ext}")
            
            # 3. Original filename with different extensions
            if name_without_ext:
                # Original extension variations
                extensions = [ext.lower(), ext.upper()] if ext else []
                # Common video extensions
                extensions.extend(['.mp4', '.mkv', '.avi', '.mov'])
                
                for ext in set(extensions):  # Remove duplicates
                    filename_variations.append(f"{name_without_ext}{ext}")
            
            # Make sure we don't have duplicate filenames
            filename_variations = list(dict.fromkeys(filename_variations))
            
            # Check in all possible base directories
            base_dirs = [
                settings.UPLOAD_DIR,
                os.path.join(settings.STORAGE_BASE_DIR, "uploads"),
                os.path.join(settings.STORAGE_BASE_DIR, "content"),
                settings.STORAGE_BASE_DIR,
                "/tmp"  # Sometimes files might be in /tmp
            ]
            
            # Also check in the uploads directory one level up
            parent_dir = os.path.dirname(settings.STORAGE_BASE_DIR.rstrip('/'))
            if parent_dir:
                base_dirs.append(os.path.join(parent_dir, "uploads"))
            
            # Remove duplicates while preserving order
            base_dirs = list(dict.fromkeys(base_dirs))
            
            logger.info(f"Will check for these filename patterns: {filename_variations}")
            
            locations_checked = []
            files_deleted = False
            
            for base_dir in base_dirs:
                if not os.path.isdir(base_dir):
                    logger.info(f"Skipping non-existent directory: {base_dir}")
                    continue
                    
                logger.info(f"\nSearching in directory: {base_dir}")
                
                # First try exact matches
                for filename in filename_variations:
                    file_path = os.path.join(base_dir, filename)
                    locations_checked.append(file_path)
                    
                    if os.path.exists(file_path):
                        logger.info(f"Found file at: {file_path}")
                        log_file_info(file_path)
                        if safe_remove(file_path):
                            logger.info(f"Successfully deleted: {file_path}")
                            files_deleted = True
                
                # Then try to find files that start with the same name
                try:
                    for filename in os.listdir(base_dir):
                        file_path = os.path.join(base_dir, filename)
                        if any(filename.startswith(name.split('.')[0]) for name in filename_variations):
                            locations_checked.append(file_path)
                            if os.path.exists(file_path):
                                logger.info(f"Found matching file by prefix: {file_path}")
                                log_file_info(file_path)
                                if safe_remove(file_path):
                                    logger.info(f"Successfully deleted: {file_path}")
                                    files_deleted = True
                except Exception as e:
                    logger.error(f"Error listing directory {base_dir}: {str(e)}")
            
            if not files_deleted:
                logger.warning("\nNo matching files were found or deleted. Checked locations:")
                for loc in locations_checked:
                    logger.info(f"  - {loc}")
                
                # List all files in upload directories for debugging
                for upload_dir in [settings.UPLOAD_DIR, os.path.join(settings.STORAGE_BASE_DIR, "uploads")]:
                    if os.path.isdir(upload_dir):
                        try:
                            logger.info(f"\nContents of {upload_dir}:")
                            for f in os.listdir(upload_dir):
                                logger.info(f"  - {f}")
                        except Exception as e:
                            logger.error(f"Error listing {upload_dir}: {str(e)}")
        
        # Clean up any job-specific output directory
        if job.output_directory and os.path.exists(job.output_directory):
            logger.info("\n=== CLEANING OUTPUT DIRECTORY ===")
            logger.info(f"Output directory: {job.output_directory}")
            safe_remove(job.output_directory)
        
        logger.info("\n=== CLEANUP COMPLETED ===")
        logger.info("="*80 + "\n")
            
    except Exception as e:
        logger.error(f"\n!!! ERROR DURING CLEANUP: {str(e)}", exc_info=True)
        logger.error("!!! Cleanup may be incomplete. Please check the logs above for details.\n")

@router.delete("/{job_id}", response_model=Dict[str, str])
def delete_job(
    *,
    db: Session = Depends(deps.get_db),
    job_id: int = Path(..., title="Job ID"),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Delete job by ID.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # Clean up files before deleting the job
    cleanup_job_files(job)
    
    # Save job ID before deletion for response
    deleted_job_id = job.id
    
    # Delete the job
    db.delete(job)
    db.commit()
    
    # Return a dictionary as specified in the response model
    return {
        "status": "success",
        "message": f"Job {deleted_job_id} has been deleted"
    }


@router.post("/bulk_delete", response_model=Dict[str, str])
def delete_multiple_jobs(
    *,
    db: Session = Depends(deps.get_db),
    jobs_to_delete: JobBulkDelete,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Delete multiple jobs by a list of IDs.
    """
    if not jobs_to_delete.job_ids:
        raise HTTPException(status_code=400, detail="No job IDs provided")

    jobs = db.query(Job).filter(Job.id.in_(jobs_to_delete.job_ids)).all()
    
    if len(jobs) != len(jobs_to_delete.job_ids):
        found_ids = {job.id for job in jobs}
        missing_ids = set(jobs_to_delete.job_ids) - found_ids
        logger.warning(f"Could not find jobs with IDs: {list(missing_ids)}")
        # Depending on desired behavior, you might raise an error or just proceed

    jobs_to_actually_delete = []
    for job in jobs:
        if job.owner_id != current_user.id and not current_user.is_superuser:
            logger.warning(f"User {current_user.id} does not have permission to delete job {job.id}")
            continue # Skip this job
        jobs_to_actually_delete.append(job)

    if not jobs_to_actually_delete:
        raise HTTPException(status_code=403, detail="No jobs could be deleted due to permission issues or because they were not found.")

    deleted_count = len(jobs_to_actually_delete)

    for job in jobs_to_actually_delete:
        logger.info(f"Cleaning up files for job {job.id}")
        cleanup_job_files(job)
        db.delete(job)
    
    db.commit()
    
    return {
        "status": "success",
        "message": f"{deleted_count} jobs have been deleted successfully."
    }

@router.post("/{job_id}/cancel", response_model=JobSchema)
def cancel_job(
    *,
    db: Session = Depends(deps.get_db),
    job_id: int,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Cancel a running job.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # Only allow cancellation of pending or processing jobs
    if job.status not in [JobStatus.PENDING, JobStatus.PROCESSING]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status {job.status}",
        )
    
    # In a complete implementation, we would:
    # 1. Send a signal to cancel the Celery task
    # 2. Update the job status
    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.now()
    
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

@router.post("/{job_id}/reprocess", response_model=JobSchema)
def reprocess_job(
    *,
    db: Session = Depends(deps.get_db),
    job_id: int,
    current_user: User = Depends(deps.get_current_user),
    background_tasks: BackgroundTasks,
    force_reprocess: bool = Query(False, description="Force reprocessing of a completed job (requires confirmation)"),
) -> Any:
    """
    Reprocess a failed job by cleaning up previous files and restarting the job.
    Preserves the original video file to avoid requiring a new upload.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # Check when the job was last reprocessed to prevent rapid re-triggering
    current_time = datetime.utcnow()
    cooldown_minutes = 5  # Set a 5-minute cooldown between reprocessing attempts
    
    # If the job was completed, require explicit force_reprocess parameter
    if job.status == JobStatus.COMPLETED and not force_reprocess:
        raise HTTPException(
            status_code=400,
            detail="This job is already completed. To reprocess a completed job, set force_reprocess=true.",
        )
    
    # Check if job is in a valid state for reprocessing
    if job.status not in [JobStatus.FAILED, JobStatus.COMPLETED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reprocess job with status {job.status}. Only failed or completed jobs can be reprocessed.",
        )
        
    # Check if the job was recently reprocessed (using the started_at field)
    if job.started_at and (current_time - job.started_at) < timedelta(minutes=cooldown_minutes):
        raise HTTPException(
            status_code=429,  # Too Many Requests
            detail=f"This job was recently reprocessed. Please wait at least {cooldown_minutes} minutes between reprocessing attempts.",
        )
    
    import os
    import shutil
    import logging
    from app.core.config import get_settings
    from app.models.job_result import JobResult
    
    logger = logging.getLogger(__name__)
    settings = get_settings()
    
    # Save information about the original video file and preferences
    original_video_url = job.source_video_url
    original_video_filename = job.video_filename
    
    # Import the subtitle preferences service
    from app.services.subtitle_preferences import SubtitlePreferencesService
    subtitle_prefs = SubtitlePreferencesService()
    
    # Save the current subtitle language preferences before cleaning up
    subtitle_langs = subtitle_prefs.get_subtitle_languages(job_id)
    
    logger.info(f"Reprocessing job {job_id}, preserving original video: {original_video_filename}")
    
    # Clean up job results from the database
    db.query(JobResult).filter(JobResult.job_id == job_id).delete()

    # Update job status to pending and reset progress and error message
    job.status = JobStatus.PENDING
    job.progress = 0
    job.error_message = None
    job.started_at = None
    job.completed_at = None

    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Setup paths
    job_dir = os.path.join(settings.JOB_DIR, f"job{job_id}")
    upload_dir = settings.UPLOAD_DIR
    
    # Keep track of the original video file path if it exists
    source_video_path = None
    if original_video_url and original_video_url.startswith('file://'):
        source_video_path = original_video_url.replace('file://', '')
        # Make sure the file exists
        if not os.path.exists(source_video_path):
            source_video_path = None
            logger.warning(f"Original video file not found at {source_video_path}")
    
    # Clean up the job directory but preserve important files
    if os.path.exists(job_dir):
        # Before deleting, try to find the original source video in case we need a backup
        if not source_video_path:
            for root, _, files in os.walk(job_dir):
                for file in files:
                    if file == original_video_filename:
                        source_video_path = os.path.join(root, file)
                        logger.info(f"Found original video file in job directory: {source_video_path}")
                        # Make a temporary backup
                        temp_backup = os.path.join(upload_dir, f"temp_backup_{job_id}_{file}")
                        shutil.copy2(source_video_path, temp_backup)
                        source_video_path = temp_backup
                        break
        
        # Now we can safely delete the job directory
        logger.info(f"Cleaning up job directory: {job_dir}")
        shutil.rmtree(job_dir)
    
    # Recreate job directory structure
    os.makedirs(job_dir, exist_ok=True)
    os.makedirs(os.path.join(job_dir, "audio"), exist_ok=True)
    os.makedirs(os.path.join(job_dir, "videos"), exist_ok=True)
    os.makedirs(os.path.join(job_dir, "packages"), exist_ok=True)
    
    # If we have the original video, put it back in the job directory or use the backup
    if source_video_path and os.path.exists(source_video_path):
        video_target = os.path.join(job_dir, "videos", original_video_filename)
        logger.info(f"Restoring original video file to {video_target}")
        shutil.copy2(source_video_path, video_target)
        
        # If this was a temporary backup, remove it
        if "temp_backup_" in source_video_path:
            os.remove(source_video_path)
    else:
        logger.warning(f"Could not find original video file for job {job_id}. User may need to upload again.")
    
    # Restore the subtitle language preferences
    if subtitle_langs:
        subtitle_prefs.save_subtitle_languages(job_id, subtitle_langs)
        logger.info(f"Restored subtitle language preferences for job {job_id}: {subtitle_langs}")
    
    # Restart the job processing
    from app.core.tasks import process_video_job
    process_video_job.delay(job.id)
    logger.info(f"Reprocessing job {job_id} started")
    
    return job
