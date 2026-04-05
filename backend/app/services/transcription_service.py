"""
Transcription service for VideoLingo.
This file provides backward compatibility with the original interface while
using the new modular implementation under the hood.
"""

import os
import sys
import logging
import tempfile
from typing import List, Dict, Any, Optional, Union

# Set environment variables to handle CUDA errors gracefully
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TensorFlow warnings
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:256'  # Increase CUDA memory allocation limit

# Reset CUDA_VISIBLE_DEVICES if it was previously set to force CPU mode
if 'CUDA_VISIBLE_DEVICES' in os.environ and os.environ['CUDA_VISIBLE_DEVICES'] == '':
    del os.environ['CUDA_VISIBLE_DEVICES']

# Set environment variables for Hugging Face to prevent unexpected downloads
os.environ['TRANSFORMERS_OFFLINE'] = '1'

# Import modular components
from .transcription.service import TranscriptionService as ModularTranscriptionService
from .transcription.utils import TranscriptionUtils
from app.models.job_context import JobContext
from app.models.job import Job

# Configure logger
logger = logging.getLogger(__name__)


class TranscriptionService(ModularTranscriptionService):
    """
    Service for transcribing audio files using WhisperX.
    This class extends the modular implementation while maintaining backward compatibility.
    """
    
    def __init__(self):
        """
        Initialize the transcription service with backward compatibility.
        We use the new modular implementation under the hood while maintaining
        the original interface for backward compatibility.
        """
        super().__init__()
        logger.info("TranscriptionService initialized (using modular implementation)")
        
    def transcribe(self, job_context_or_dir: Union[JobContext, str], audio_path: str, 
                  max_chars: int = 80, max_words: int = 15, progress_callback: Optional[callable] = None) -> str:
        """
        Transcribe an audio file using WhisperX.
        Supports both JobContext objects and job_dir strings for backward compatibility.
        
        Args:
            job_context_or_dir: Either a JobContext object or directory path for job output files
            audio_path: Path to the audio file to transcribe
            max_chars: Maximum characters per segment (for compatibility, unused)
            max_words: Maximum words per segment (for compatibility, unused)
            progress_callback: Optional callback function to report progress.
            
        Returns:
            Path to the transcription results file
        """
        logger.info(f"TranscriptionService.transcribe called with max_chars={max_chars}, max_words={max_words} (these are ignored in the new implementation)")
        
        # Handle both JobContext objects and string paths
        if isinstance(job_context_or_dir, JobContext):
            # Direct JobContext - use it directly
            context = job_context_or_dir
            logger.info(f"Using provided JobContext: {context}")
        elif isinstance(job_context_or_dir, str):
            # String path - extract job_id and user_id to create JobContext
            job_dir = job_context_or_dir
            logger.info(f"Converting job_dir to JobContext: {job_dir}")
            
            try:
                path_parts = job_dir.rstrip('/').split('/')
                if 'jobs' in path_parts:
                    jobs_index = path_parts.index('jobs')
                    if jobs_index + 1 < len(path_parts):
                        job_id = int(path_parts[jobs_index + 1])
                        if jobs_index >= 1 and 'users' in path_parts:
                            users_index = path_parts.index('users')
                            if users_index + 1 < len(path_parts):
                                user_id = int(path_parts[users_index + 1])
                            else:
                                # Fallback: try to get user_id from job
                                job = Job.get_by_id(job_id)
                                user_id = job.user_id if job else 1
                        else:
                            # Fallback: try to get user_id from job
                            job = Job.get_by_id(job_id)
                            user_id = job.user_id if job else 1
                    else:
                        raise ValueError("Invalid job_dir format: missing job_id")
                else:
                    raise ValueError("Invalid job_dir format: missing 'jobs' directory")
                    
                # Create JobContext
                context = JobContext(user_id=user_id, job_id=job_id)
                logger.info(f"Created JobContext from job_dir: {context}")
                
            except (ValueError, IndexError, AttributeError) as e:
                logger.error(f"Failed to extract job_id and user_id from job_dir '{job_dir}': {str(e)}")
                raise RuntimeError(f"Invalid job_dir format. Cannot extract job context: {str(e)}")
        else:
            raise TypeError(f"Expected JobContext or str, got {type(job_context_or_dir).__name__}")
        
        # Call the parent implementation with JobContext
        return super().transcribe(context, audio_path, progress_callback=progress_callback)
