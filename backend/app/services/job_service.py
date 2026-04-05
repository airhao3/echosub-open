import os
import logging
import functools
import shutil
import tempfile
import json
from typing import Dict, List, Optional, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import desc
import logging
import functools
import shutil
from datetime import datetime

from app.models.job import Job, JobStatus, JobResult, ResultType
from app.utils.file_utils import (

    get_file_size,
    get_mime_type,
    ensure_directory_exists
)
from app.utils.file_path_manager import FilePathManager, FileType, get_file_path_manager
from app.models.job_context import JobContext
from app.services.usage_tracker_service import UsageTrackerService
from app.services.job_numbering_service import JobNumberingService

logger = logging.getLogger(__name__)

class JobService:
    """
    Service for managing video processing jobs.
    This is the central coordination service that orchestrates the entire video processing workflow.
    """
    
    def __init__(self, db: Session, data_dir: str):
        self.db = db
        self.data_dir = data_dir
        self.usage_tracker_service = UsageTrackerService(db)
        
    def _setup_job_directory(self, job_id: int) -> str:
        """
        Set up the directory structure for a job using user_id and job_id.

        Args:
            job_id: ID of the job

        Returns:
            Path to the job's directory

        Raises:
            ValueError: If the job doesn't exist.
        """
        job = self.get_job_by_id(job_id)
        if not job:
            raise ValueError(f"Job with ID {job_id} not found")

        file_manager = FilePathManager(self.data_dir)
        job_dir = file_manager._get_job_dir(job.owner_id, job.id)

        # Ensure the main job directory and standard subdirectories exist
        ensure_directory_exists(job_dir)
        for subdir in ["subtitles", "audio"]:
            ensure_directory_exists(os.path.join(job_dir, subdir))

        logger.info(f"Setup job directory for JOB:{job.id} at {job_dir}")
        return job_dir
    
    def get_job_by_id(self, job_id: int) -> Optional[Job]:
        """
        Retrieve a job by its ID with relationships loaded
        """
        return self.db.query(Job).filter(Job.id == job_id).first()

    def update_job_with_video_info(self, job_id: int, duration: float, video_url: str):
        """
        Update a job with video-specific information after upload and metadata extraction.

        Args:
            job_id: The ID of the job to update.
            duration: The duration of the video in seconds.
            video_url: The final path or URL of the source video file.
        """
        job = self.get_job_by_id(job_id)
        if not job:
            raise ValueError(f"Job with ID {job_id} not found")

        job.video_duration = duration
        job.source_video_url = video_url
        self.db.commit()
        self.db.refresh(job)
        logger.info(f"Updated job {job_id} with duration ({duration}s) and video_url.")
        return job
    
    @functools.lru_cache(maxsize=32)
    def get_jobs_by_user(self, user_id: int, skip: int = 0, limit: int = 100) -> List[Job]:
        """
        Retrieve jobs for a specific user with caching for performance
        
        Args:
            user_id: The ID of the user whose jobs to retrieve
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            
        Returns:
            List of Job objects belonging to the user
        """
        # Use optimized query with proper index hints
        return self.db.query(Job)\
            .filter(Job.owner_id == user_id)\
            .order_by(desc(Job.created_at))\
            .offset(skip)\
            .limit(limit)\
            .all()
    
    def create_job(self, user_id: int, job_data: Dict[str, Any]) -> Job:
        """
        Create a new video processing job with subscription quota check
        
        Args:
            user_id: ID of the user creating the job
            job_data: Dictionary containing job data including video information
            
        Returns:
            The created Job object
            
        Raises:
            QuotaExceededError: If the user has exceeded their quota
        """
        # Check if video duration is provided for quota check
        video_duration = job_data.get('video_duration')
        if video_duration is not None:
            # Convert duration to minutes and round up to nearest minute
            video_minutes = max(1, int(video_duration / 60) + (1 if video_duration % 60 > 0 else 0))
            
            # Check if user has enough video minutes quota and update usage
            self.usage_tracker_service.check_and_update_video_minutes(
                user_id=user_id,
                minutes_to_add=video_minutes
            )
        
        # Check projects quota (each job counts as a project) and update usage
        self.usage_tracker_service.check_and_update_projects(user_id=user_id, projects_to_add=1)
        
        # Fields like source_video_url and content_hash will be updated later in the process
        # We only need the essential information to create the job record initially.
        required_fields = ['source_language', 'target_languages', 'video_filename']
        missing_fields = [field for field in required_fields if field not in job_data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            
        # Get the next user job number
        user_job_number = JobNumberingService.get_next_user_job_number(self.db, user_id)
        
        # Create the new job instance
        job = Job(
            owner_id=user_id,
            user_job_number=user_job_number,
            title=job_data.get('title'),
            description=job_data.get('description'),
            source_language=job_data['source_language'],
            target_languages=job_data['target_languages'],
            video_filename=job_data['video_filename'],
            status=job_data.get('status', JobStatus.PENDING),
            video_duration=job_data.get('video_duration')
        )
        
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        

        
        # Track usage for translation characters if applicable
        # Note: This is a placeholder for a more accurate character count later
        if job_data.get('generate_dubbing') or job_data.get('generate_subtitles'):
            # Estimate character count based on duration (e.g., 15 chars/sec)
            estimated_chars = int(video_duration * 15) if video_duration else 1000
            self.usage_tracker_service.check_and_update_translation_chars(
                user_id=user_id,
                chars_to_add=estimated_chars
            )
        
        # Create working directory structure
        self._setup_job_directory(job.id)
        
        return job
    
    def update_job_status(self, job_id: int, status: JobStatus, progress: int = None, error_message: str = None) -> Job:
        """
        Update job status, progress, and error message if provided
        
        Args:
            job_id: ID of the job to update
            status: New status to set
            progress: Optional progress percentage (0-100)
            error_message: Optional error message if job failed
            
        Returns:
            Updated Job object
            
        Raises:
            ValueError: If job with the given ID doesn't exist
        """
        job = self.get_job_by_id(job_id)
        if not job:
            logger.error(f"Failed to update job status - Job with ID {job_id} not found")
            raise ValueError(f"Job with ID {job_id} not found")
        
        # Update status
        job.status = status
        
        # Update progress if provided, with bounds checking
        if progress is not None:
            job.progress = max(0, min(100, progress))  # Ensure progress is between 0-100
        
        # Update error message if provided
        if error_message is not None:
            job.error_message = error_message
        
        current_time = datetime.now()
        
        # Update timestamps based on status change
        if status == JobStatus.PROCESSING and not job.started_at:
            job.started_at = current_time
            logger.info(f"Job {job_id} started processing at {current_time}")
        
        if status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] and not job.completed_at:
            job.completed_at = current_time
            logger.info(f"Job {job_id} finished with status {status} at {current_time}")
            
            # Clear cached results for this user to ensure fresh data on next query
            if hasattr(job, 'owner_id') and job.owner_id:
                self.get_jobs_by_user.cache_clear()
        
        try:
            self.db.add(job)
            # Get fresh job data with relationships
            self.db.refresh(job)
            return job
        except Exception as e:
            self.db.rollback()
            logger.error(f"Database error updating job {job_id}: {str(e)}")
            raise
    
    def cancel_job(self, job_id: int) -> Job:
        """
        Cancel a job if it's not already completed or failed
        """
        job = self.get_job_by_id(job_id)
        if not job:
            raise ValueError(f"Job with ID {job_id} not found")
        
        if job.status in [JobStatus.PENDING, JobStatus.PROCESSING]:
            return self.update_job_status(job_id, JobStatus.CANCELLED)
        else:
            raise ValueError(f"Cannot cancel job with status {job.status}")
    
    def add_job_result(self, job_id: int, result_type: ResultType, language: str, 
                     file_path: str, file_name: str, file_size: int = None, 
                     mime_type: str = None, metadata: dict = None) -> JobResult:
        """
        Add or update a result file for a job.
        
        If a result with the same job_id, result_type, and language already exists,
        it will be updated with the new file path and metadata.
        """
        job = self.get_job_by_id(job_id)
        if not job:
            raise ValueError(f"Job with ID {job_id} not found")
        
        # Check if a result with these parameters already exists
        existing_result = self.db.query(JobResult).filter(
            JobResult.job_id == job_id,
            JobResult.result_type == result_type,
            JobResult.language == language
        ).first()
        
        # Prepare metadata, ensuring it's a dictionary
        if metadata is None:
            metadata = {}
        
        # Add file-specific info to metadata
        metadata['file_name'] = file_name
        if file_size is not None:
            metadata['file_size'] = file_size
        if mime_type is not None:
            metadata['mime_type'] = mime_type

        if existing_result:
            # Update existing result
            existing_result.file_path = file_path
            existing_result.metadata_ = metadata
            result = existing_result
        else:
            # Create new result
            result = JobResult(
                job_id=job_id,
                result_type=result_type,
                language=language,
                file_path=file_path,  # The actual file path or URL
                metadata_=metadata
            )
            self.db.add(result)
        
        try:
            self.db.commit()
            self.db.refresh(result)
            return result
        except Exception as e:
            self.db.rollback()
            raise
    
    def check_job_result_exists(self, job_id: int, result_type: ResultType, language: str) -> Optional[JobResult]:
        """
        Check if a job result already exists with the specified job_id, result_type, and language
        
        Args:
            job_id: The ID of the job
            result_type: The type of result (e.g., TRANSCRIPTION_SRT, TRANSLATED_SUBTITLE_SRT)
            language: The language code
            
        Returns:
            The JobResult object if it exists, None otherwise
        """
        return self.db.query(JobResult).filter(
            JobResult.job_id == job_id,
            JobResult.result_type == result_type,
            JobResult.language == language
        ).first()
    
    def get_job_results(self, job_id: int) -> List[JobResult]:
        """
        Get all results for a specific job
        """
        return self.db.query(JobResult).filter(JobResult.job_id == job_id).all()
    
       

        
    def package_job_results(self, job_id, direct_files: dict, **kwargs) -> str:
        """
        Package job results using only the explicitly provided files.
        No automatic file collection or searching is performed.

        Args:
            job_id: ID of the job (int or str).
            direct_files: Dictionary of files to package, organized by category.
            **kwargs: Additional keyword arguments for backward compatibility.

        Returns:
            Path to the created package directory.
        """
        try:
            logger.info(f"[PACKAGE] Starting packaging for job {job_id}")

            job_id = int(job_id) if isinstance(job_id, str) and job_id.isdigit() else job_id

            job = self.get_job_by_id(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            # Create job context for file path management
            context = JobContext(user_id=job.owner_id, job_id=job.id, job=job)
            file_manager = get_file_path_manager()
            
            # Get package directory using file_path_manager
            package_dir = file_manager.get_file_path(context, FileType.PACKAGE_DIR)
            
            # Clean up existing package directory if it exists
            if os.path.exists(package_dir):
                shutil.rmtree(package_dir)
            
            # Recreate the package directory
            os.makedirs(package_dir, exist_ok=True)

            subdirs = {
                'videos': 'videos',
                'subtitles': 'subtitles',
                'transcripts': 'transcripts',
                'translations': 'translations',
                'logs': 'logs',
                'metadata': 'metadata',
                'other': 'other'
            }

            for subdir in subdirs.values():
                os.makedirs(os.path.join(package_dir, subdir), exist_ok=True)

            files_copied = 0
            manifest_files = []
            for category, file_list in direct_files.items():
                if not file_list:
                    continue

                target_subdir_name = subdirs.get(category.lower(), 'other')
                target_dir = os.path.join(package_dir, target_subdir_name)

                for file_path in file_list:
                    if not file_path or not os.path.exists(file_path):
                        logger.warning(f"File not found or path is invalid, skipping: {file_path}")
                        continue

                    try:
                        dest_path = os.path.join(target_dir, os.path.basename(file_path))
                        shutil.copy2(file_path, dest_path)
                        files_copied += 1
                        manifest_files.append({
                            'path': os.path.join(target_subdir_name, os.path.basename(file_path)),
                            'category': category,
                            'size': os.path.getsize(dest_path)
                        })
                        logger.debug(f"Copied {file_path} to {dest_path}")
                    except Exception as e:
                        logger.error(f"Error copying {file_path}: {str(e)}")

            manifest = {
                'job_id': str(job_id),
                'package_timestamp': datetime.utcnow().isoformat(),
                'files': manifest_files
            }

            # Write manifest to file using file_path_manager
            manifest_path = file_manager.get_file_path(
                context, 
                FileType.PACKAGE_MANIFEST, 
                job_id=job_id
            )
            file_manager.write_json(manifest_path, manifest, indent=2)

            logger.info(f"Successfully packaged {files_copied} files to {package_dir}")
            return package_dir
            
        except Exception as e:
            logger.error(f"Failed to package job results: {str(e)}", exc_info=True)
            
            # Clean up partial package if it exists
            if 'package_dir' in locals() and os.path.exists(package_dir):
                shutil.rmtree(package_dir, ignore_errors=True)
            
            # Re-raise to allow caller to handle the error
            raise

    def cleanup_job_for_reprocessing(self, job_id: int):
        """
        Cleans up all files associated with a job, typically before reprocessing.
        This deletes the entire job directory.
        """
        job = self.get_job_by_id(job_id)
        if not job:
            logger.warning(f"Attempted to clean up non-existent job {job_id}")
            return

        # Create job context for file path management
        context = JobContext(user_id=job.owner_id, job_id=job.id, job=job)
        file_manager = get_file_path_manager()
        job_dir = file_manager.get_file_path(context, FileType.JOB_DIRECTORY)

        if os.path.exists(job_dir):
            try:
                shutil.rmtree(job_dir)
                logger.info(f"Successfully cleaned up job directory for job {job_id} at {job_dir}")
            except Exception as e:
                logger.error(f"Error cleaning up job directory {job_dir} for job {job_id}: {str(e)}")
                raise
        else:
            logger.info(f"Job directory for job {job_id} not found at {job_dir}, no cleanup needed.")

    def start_processing(self, job_id: int) -> Job:
        """
        Start processing a job. This method will be called by Celery worker.
        Includes quota checks before starting processing.
        """
        job = self.get_job_by_id(job_id)
        if not job:
            raise ValueError(f"Job with ID {job_id} not found")

        # Storage tracking is now handled at the point of upload (e.g., in uploads.py).
        # If start_processing can be triggered for jobs with new files not processed via the standard upload endpoint,
        # then storage tracking might be needed here, but care must be taken to avoid double-counting.

        # TODO: Implement video minute tracking before transcription begins.
        # This assumes job.video_duration (in seconds) is populated by this point.
        # If not, it needs to be determined here.
        # Example:
        # if job.video_duration:
        #     video_minutes = max(1, int(job.video_duration / 60) + (1 if job.video_duration % 60 > 0 else 0))
        #     self.usage_tracker_service.check_and_update_video_minutes(
        #         user_id=job.owner_id,
        #         minutes_to_add=video_minutes
        #     )
        # else:
        #     logger.error(f"Video duration not available for job {job.id} at start of processing. Cannot track video minutes.")
            # Optionally, raise an error or attempt to calculate duration here.

        job = self.update_job_status(job_id, JobStatus.PROCESSING, progress=0)

        try:
            # Here we'll orchestrate the processing steps using other services
            # Each step will update the job progress

            # For now, we'll just log the step
            logger.info(f"Started processing job {job_id}")

            # Mark job as completed when done
            return self.update_job_status(job_id, JobStatus.COMPLETED, progress=100)

        except Exception as e:
            logger.error(f"Error processing job {job_id}: {str(e)}")
            return self.update_job_status(job_id, JobStatus.FAILED, error_message=str(e))
