import os
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.job_context import JobContext
from app.models.translation_job import StepName, StepStatus
from app.services.processing_logger import ProcessingLogger, ProcessingStage
from app.services.status_service import StatusUpdateService
from app.services.video_service import VideoService
from app.services.job_service import JobService # Added import
from app.utils.file_path_manager import FileType, get_file_path_manager

logger = logging.getLogger(__name__)


class VideoProcessorService:
    """
    Service for handling video processing operations in the workflow.
    
    This service is responsible for:
    - Preparing video input files for processing
    - Creating working copies of videos
    - Managing video file paths and metadata
    - Coordinating final video output generation
    """
    
    def __init__(self, db: Session, job_service: JobService): # Modified constructor
        self.db = db
        self.job_service = job_service # Stored job_service
        self.file_manager = get_file_path_manager()
        self.video_service = VideoService(file_manager=self.file_manager)
        
    def prepare_video_input(self, job: Job, context: JobContext, proc_logger: ProcessingLogger) -> str:
        """
        Prepare video input for processing workflow.
        
        Args:
            job: The job being processed
            context: Job context with user and job information
            proc_logger: Processing logger for tracking progress
            
        Returns:
            str: Path to the prepared video file ready for processing
        """
        video_path = job.source_video_url
        if not video_path or not os.path.exists(video_path):
            error_msg = f"Video file not found: {video_path}"
            proc_logger.log_error(error_msg)
            raise FileNotFoundError(error_msg)
            
        # 1. Video Download/Upload Stage
        proc_logger.start_stage(ProcessingStage.VIDEO_DOWNLOAD, f"Processing video: {os.path.basename(video_path)}")
        proc_logger.log_info(f"==========================🎥 Processing video: {os.path.basename(video_path)}====================================")
        
        # Get video file name information
        video_filename = os.path.basename(video_path)
        video_name = os.path.splitext(video_filename)[0]
        
        # Create a working copy of the video using FilePathManager
        try:
            video_filename = os.path.basename(job.source_video_url)
            dest_video_path = self.file_manager.get_file_path(
                context=context,
                file_type=FileType.SOURCE_VIDEO,
                filename=os.path.basename(job.source_video_url)
            )
            
            # Ensure the directory exists
            # Directory creation handled by file_manager
            
            # Only copy if source and destination are different
            if os.path.abspath(job.source_video_url) != os.path.abspath(dest_video_path):
                self.file_manager.copy(job.source_video_url, dest_video_path)
                proc_logger.log_info(f"📋 Created working copy at {dest_video_path}")
            else:
                proc_logger.log_info(f"ℹ️  Source and destination paths are the same, skipping copy: {dest_video_path}")
                
        except Exception as e:
            error_msg = f"Failed to create a working copy of the video: {str(e)}"
            proc_logger.log_error(error_msg)
            raise RuntimeError(error_msg) from e
            
        # Update video_path to the new location
        video_path = dest_video_path
        
        # Generate thumbnails for the video
        try:
            from app.services.thumbnail_service import ThumbnailService
            thumbnail_service = ThumbnailService()
            
            proc_logger.log_info("🖼️  Generating video thumbnails...")
            
            # Generate thumbnails in the background
            thumbnail_results = thumbnail_service.generate_multiple_thumbnails(
                video_path=video_path,
                output_dir=self.file_manager.get_directory_path(
                    context=context,
                    dir_type=FileType.THUMBNAIL
                ),
                base_name="thumbnail",
                sizes=['small', 'medium', 'large'],
                timestamps=['00:00:05']  # Extract at 5 seconds
            )
            
            if thumbnail_results:
                proc_logger.log_info(f"✅ Generated {len(thumbnail_results)} thumbnails")
                for size, path in thumbnail_results.items():
                    proc_logger.log_info(f"   - {size}: {os.path.basename(path)}")
                    # Add thumbnail to job results
                    from app.models.job import ResultType as RT
                    self.job_service.add_job_result(
                        job_id=job.id,
                        result_type=RT[f"THUMBNAIL_{size.upper()}"],
                        language=None, # Thumbnails are language-agnostic
                        file_path=path,
                        file_name=os.path.basename(path),
                        mime_type='image/jpeg'
                    )
            else:
                proc_logger.log_warning("⚠️  No thumbnails were generated")
                
        except Exception as e:
            # Don't fail the entire process if thumbnail generation fails
            proc_logger.log_warning(f"⚠️  Thumbnail generation failed: {str(e)}")
        
        # 🔥 FIX: Add ORIGINAL_VIDEO record to database
        try:
            import mimetypes
            from app.models.job import ResultType as RT
            
            # Get file size and mime type
            file_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0
            mime_type, _ = mimetypes.guess_type(video_path)
            if not mime_type:
                mime_type = 'video/mp4'  # Default fallback
            
            proc_logger.log_info(f"📝 Creating ORIGINAL_VIDEO database record: {os.path.basename(video_path)}")
            
            # Create the ORIGINAL_VIDEO record in database
            self.job_service.add_job_result(
                job_id=job.id,
                result_type=RT.ORIGINAL_VIDEO,
                language=None,  # Original video is language-agnostic
                file_path=video_path,
                file_name=os.path.basename(video_path),
                mime_type=mime_type,
                metadata={
                    "file_name": os.path.basename(video_path),
                    "file_size": file_size,
                    "mime_type": mime_type
                }
            )
            proc_logger.log_info(f"✅ Successfully created ORIGINAL_VIDEO record")
            
        except Exception as e:
            proc_logger.log_error(f"❌ Failed to create ORIGINAL_VIDEO database record: {str(e)}")
            # Don't fail the entire process, but log the error
        
        proc_logger.complete_stage(ProcessingStage.VIDEO_DOWNLOAD, "Video file prepared successfully")
        
        return video_path

    def create_final_output_video(self, job: Job, context: JobContext, subtitle_files: dict, proc_logger: ProcessingLogger) -> Optional[str]:
        """
        Create the final output video with embedded subtitles.
        
        Args:
            job: The job being processed
            context: Job context with user and job information
            subtitle_files: Dictionary mapping languages to subtitle file paths
            proc_logger: Processing logger for tracking progress
            
        Returns:
            Optional[str]: Path to the final output video, or None if creation failed
        """
        proc_logger.start_stage(ProcessingStage.VIDEO_PROCESSING, "==========================Creating final output video==========================")
        
        # Update progress - Starting video integration
        StatusUpdateService.update_step_status(
            self.db, job.id, StepName.INTEGRATING, 
            StepStatus.IN_PROGRESS, 5.0, "Starting final video integration"
        )
        
        try:
            # Get the source video path
            source_video_path = self.file_manager.get_file_path(
                context=context,
                file_type=FileType.SOURCE_VIDEO,
                filename=os.path.basename(job.source_video_url)
            )
            
            if not os.path.exists(source_video_path):
                proc_logger.log_error(f"Source video not found: {source_video_path}")
                return None
            
            # Get target languages from job
            target_languages = []
            if job.target_languages:
                if isinstance(job.target_languages, list):
                    target_languages = job.target_languages
                else:
                    target_languages = [lang.strip() for lang in job.target_languages.split(',') if lang.strip()]
            
            proc_logger.log_info(f"Target languages for subtitle embedding: {target_languages}")
            
            # Update progress - Video preparation
            StatusUpdateService.update_step_status(
                self.db, job.id, StepName.INTEGRATING, 
                StepStatus.IN_PROGRESS, 20.0, "Preparing video for subtitle embedding"
            )
            
            # Update progress - Creating subtitled video
            StatusUpdateService.update_step_status(
                self.db, job.id, StepName.INTEGRATING, 
                StepStatus.IN_PROGRESS, 50.0, "Embedding subtitles into video"
            )
            
            # Skip video creation for now - not implemented
            proc_logger.log_warning("Subtitled video creation is not implemented yet, skipping...")
            target_video_path = None
            
            if target_video_path and os.path.exists(target_video_path):
                proc_logger.log_progress(ProcessingStage.VIDEO_PROCESSING, 80, f"Video processing completed: {os.path.basename(target_video_path)}")
                
                # Add the subtitled video as a job result
                from app.models.job import JobResult
                from app.models.job import ResultType as RT
                from datetime import datetime
                
                result = JobResult(
                    job_id=job.id,
                    result_type=RT.SUBTITLED_VIDEO,
                    file_path=target_video_path,
                    created_at=datetime.utcnow(),
                    metadata_={
                        "file_name": os.path.basename(target_video_path),
                        "file_size": os.path.getsize(target_video_path),
                        "mime_type": "video/mp4"
                    }
                )
                self.db.add(result)
                self.db.commit()
                
                # Auto-sync the subtitled video to remote storage
                self.file_manager.auto_sync_file_to_remote(target_video_path, proc_logger.log_info)
                
                proc_logger.log_info(f"Registered subtitled video as job result: {target_video_path}")
                
                # Update job step status with gradual completion
                try:
                    StatusUpdateService.update_step_status(
                        self.db, job.id, StepName.INTEGRATING, 
                        StepStatus.IN_PROGRESS, 85.0, "Finalizing video output"
                    )
                    
                    StatusUpdateService.update_step_status(
                        self.db, job.id, StepName.INTEGRATING, 
                        StepStatus.IN_PROGRESS, 95.0, "Validating final video"
                    )
                    
                    StatusUpdateService.update_step_status(
                        self.db, job.id, StepName.INTEGRATING, 
                        StepStatus.COMPLETED, 100.0, f"Video integration completed: {os.path.basename(target_video_path)}"
                    )
                except Exception as e_status:
                    proc_logger.log_error(f"Error updating video integration status: {str(e_status)}")
                
                proc_logger.complete_stage(ProcessingStage.VIDEO_PROCESSING,
                                         f"Video processing completed successfully: {os.path.basename(target_video_path)}")
                
                return target_video_path
            else:
                proc_logger.log_error("Failed to create subtitled video")
                return None
                
        except Exception as e:
            error_msg = f"Error creating final output video: {str(e)}"
            proc_logger.log_error(error_msg)
            logger.exception("Full stack trace for video processing error:")
            return None



    



    
