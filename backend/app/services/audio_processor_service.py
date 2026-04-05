import os
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.job_context import JobContext
from app.models.translation_job import StepName, StepStatus
from app.services.processing_logger import ProcessingLogger, ProcessingStage
from app.services.status_service import StatusUpdateService
from app.services.video_service import VideoService
from app.utils.file_path_manager import FileType, get_file_path_manager

logger = logging.getLogger(__name__)


class AudioProcessorService:
    """
    Service for handling audio processing operations in the video workflow.
    
    This service is responsible for:
    - Extracting audio from video files
    - Converting audio to appropriate formats for transcription
    - Coordinating with transcription services
    - Managing audio metadata and file paths
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.file_manager = get_file_path_manager()
        self.video_service = VideoService(self.file_manager)
        
    def perform_audio_processing(self, job: Job, context: JobContext, video_path: str, proc_logger: ProcessingLogger) -> str:
        """
        Perform complete audio processing workflow.
        
        Args:
            job: The job being processed
            context: Job context with user and job information
            video_path: Path to the source video file
            proc_logger: Processing logger for tracking progress
            
        Returns:
            str: Path to the processed audio file ready for transcription
        """
        # 2. Video preprocessing - collect video stats
        proc_logger.start_stage(ProcessingStage.PREPROCESSING, "==========================Analyzing video properties==========================")
        
        # Update AUDIO_PROCESSING step as started
        StatusUpdateService.update_step_status(
            self.db, job.id, StepName.AUDIO_PROCESSING, 
            StepStatus.IN_PROGRESS, 10.0, "Analyzing video properties"
        )
        
        # Get video metadata using VideoService
        try:
            video_metadata = self.video_service.get_video_metadata(video_path)
            duration = video_metadata.get('duration', 'Unknown')
            resolution = f"{video_metadata.get('width', 'Unknown')}x{video_metadata.get('height', 'Unknown')}"
            fps = video_metadata.get('fps', 'Unknown')
            
            metadata_info = f"Duration: {duration}s\n" + \
                           f"Resolution: {resolution}\n" + \
                           f"FPS: {fps}"
                           
            proc_logger.log_progress(ProcessingStage.PREPROCESSING, 30, metadata_info)
            
            # Update progress to 30%
            StatusUpdateService.update_step_status(
                self.db, job.id, StepName.AUDIO_PROCESSING, 
                StepStatus.IN_PROGRESS, 30.0, f"Video analyzed: {resolution}, {duration}s"
            )
        except Exception as e:
            proc_logger.log_info(f"Could not extract complete video metadata: {str(e)}")
        
        # 3. 轻量级音频提取 - 直接提取用于API上传
        proc_logger.log_progress(ProcessingStage.PREPROCESSING, 40, "==========================Extracting audio for API transcription==========================")
        
        # Update progress to 40% 
        StatusUpdateService.update_step_status(
            self.db, job.id, StepName.AUDIO_PROCESSING, 
            StepStatus.IN_PROGRESS, 40.0, "Extracting audio for transcription"
        )
        
        # Get path for API-ready audio (.mp3)
        api_audio_path = self.file_manager.get_file_path(
            context=context,
            file_type=FileType.COMPRESSED_AUDIO,
            filename="api_ready_audio.mp3"
        )

        # 简化音频提取 - 直接提取适合API的音频格式
        self.video_service.convert_video_to_audio_with_manager(video_path, api_audio_path)
        
        # Get audio file size using file manager
        try:
            api_audio_size_mb = self.file_manager.get_file_size(api_audio_path) / (1024 * 1024)
        except Exception as e:
            logger.warning(f"Could not get audio file size for {api_audio_path}: {e}")
            api_audio_size_mb = 0
        
        proc_logger.log_progress(ProcessingStage.PREPROCESSING, 90, 
                                 f"API-ready audio extracted: {os.path.basename(api_audio_path)} ({api_audio_size_mb:.2f} MB)")
        
        # Update progress to 90%
        StatusUpdateService.update_step_status(
            self.db, job.id, StepName.AUDIO_PROCESSING, 
            StepStatus.IN_PROGRESS, 90.0, f"Audio extracted ({api_audio_size_mb:.1f} MB)"
        )
        
        # 音频已准备好直接上传到外部API
        whisper_audio = api_audio_path
        
        proc_logger.log_progress(ProcessingStage.PREPROCESSING, 100, 
                                f"Audio ready for API: {os.path.basename(whisper_audio)}\n" + 
                                f"Size: {api_audio_size_mb:.2f} MB")
        
        proc_logger.complete_stage(ProcessingStage.PREPROCESSING,
                                  f"Audio preprocessing completed successfully")

        # Update job step status using StatusUpdateService
        try:
            # Mark AUDIO_PROCESSING step as completed
            StatusUpdateService.update_step_status(
                self.db, job.id, StepName.AUDIO_PROCESSING, 
                StepStatus.COMPLETED, 100.0, "Audio processing completed"
            )
            
            # Mark TRANSCRIBING step as in progress
            StatusUpdateService.update_step_status(
                self.db, job.id, StepName.TRANSCRIBING, 
                StepStatus.IN_PROGRESS, 0.0, "Starting transcription"
            )
        except Exception as e_status:
            proc_logger.log_error(f"Error updating job status after audio processing: {str(e_status)}")
        
        return whisper_audio



