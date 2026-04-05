#!/usr/bin/env python3
"""
File Path Manager (Refactored)

A utility module that standardizes file paths and naming conventions for the video processing system.
This module implements a user_id/job_id based hierarchical file organization structure to ensure proper
security isolation and consistent file management across the application.

This version uses a data-driven approach to eliminate large conditional blocks,
making it easier to extend and maintain.

Directory Structure:
/base_dir/
└── users/
    └── <user_id>/
        └── jobs/
            └── <job_id>/
                ├── source/
                │   └── original_video.mp4      # Uploaded original file
                ├── audio/
                │   ├── raw_audio.wav           # Extracted full audio track
                │   └── compressed_audio.mp3    # Compressed audio for ASR
                ├── transcription/
                │   ├── transcription.json      # ASR original output
                │   └── refined_transcript.txt  # After optimization and segmentation
                ├── translation/
                │   ├── translation_all.json    # Raw translation results for all languages
                │   └── segmented_fr.txt        # Segmented text for a specific language (e.g., French)
                ├── subtitles/
                │   ├── en.srt                  # Final generated English SRT
                │   └── fr.vtt                  # Final generated French VTT
                └── logs/
                    └── workflow.log            # Job-specific log
"""

import json
import os
import logging
from enum import Enum
from typing import Optional, List, Dict, NamedTuple, Any, BinaryIO

logger = logging.getLogger(__name__)

# Import JobContext for type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.job_context import JobContext


class FileType(str, Enum):
    """
    Enum of file types that can be managed by FilePathManager.
    The string value corresponds to the stage directory.
    """
    # Source Files
    SOURCE_VIDEO = "source"  # The original uploaded video file

    # Working files - temporary files used during processing
    WORKING_VIDEO = "working_video"

    # Audio Processing
    RAW_AUDIO = "raw_audio"
    COMPRESSED_AUDIO = "compressed_audio"

    # Transcription
    TRANSCRIPTION_JSON = "transcription_json"
    TRANSCRIPTION_TXT = "transcription_txt"
    LABELED_TRANSCRIPT = "labeled_transcript"
    SEGMENTED_TRANSCRIPT = "segmented_transcript"
    SEGMENTED_TRANSCRIPT_JSON = "segmented_transcript_json"
    REFINED_TRANSCRIPT = "refined_transcription"
    LABELED_SEGMENTED_TRANSCRIPT = "transcription"

    # Translation
    TRANSLATION_OUTPUT_JSON = "translation"
    TRANSLATION_TXT = "translation"  # Raw translation output (first stage)
    TRANSLATION_SEGMENTED_TXT = "translation"
    TRANSLATION_SORTED_TXT = "translation"  # Sorted and cleaned translation text

    # Subtitles
    SUBTITLE_SRT = "subtitles"
    SUBTITLE_VTT = "subtitles_vtt"

    # Logging
    JOB_LOG = "logs"

    # Directories
    JOB_DIRECTORY = "jobs"  # Represents the root directory for a job

    # Configuration files
    CUSTOM_TERMS_XLSX = "config"
    
    # Analysis and Summary
    SUMMARY_JSON = "summary"
    
    # Terminology
    TERMINOLOGY_JSON = "terminology"

    # Content Analysis (Step 2 - Post-transcription understanding)
    GLOBAL_ANALYSIS_JSON = "analysis"      # Global content scan result
    SCENE_DIGESTS_JSON = "analysis"        # Chained scene digests
    CORRECTED_TRANSCRIPT = "analysis"      # Scene-corrected transcript
    
    # Debug files
    DEBUG_FILE = "debug"  # For debug-related files
    ALIGNED_CHUNKS_XLSX = "debug" # For aligned chunks (legacy)
    ALIGNED_CHUNKS_JSON = "debug" # For aligned chunks JSON (replaces xlsx)
    CLEANED_CHUNKS_XLSX = "logs" # For cleaned chunks Excel file
    CLEANED_CHUNKS_TXT = "logs" # For cleaned chunks TXT file
    
    
    # Thumbnails
    THUMBNAIL = "thumbnails"  # Video thumbnail images
    
    
    # Package management
    PACKAGE_DIR = "packages"  # Package directory
    PACKAGE_MANIFEST = "packages"  # Package manifest file
    
    # Subtitle versioning  
    
    MODIFIED_SUBTITLE = "modified_subtitles"  # Modified subtitle file
    SUBTITLE_LANG_JSON = "subtitles_json"  # Language-specific subtitle JSON file
    SUBTITLE_SRC_JSON = "subtitles_src"  # Source subtitle JSON file
    VERSION_FILE = "versions"  # Version-specific file
    
    # Preferences
    PREFERENCES_FILE = "preferences"  # User preference files
    
    # Temporary and uploaded files
    TEMP_FILE = "temp"  # Temporary files
    UPLOADED_FILE = "uploads"  # Uploaded files


# --- Data-Driven Configuration ---

class FileSpec(NamedTuple):
    """Defines the specification for a file type."""
    filename_template: str          # e.g., "{language}.srt" or "raw_audio.wav"
    required_params: List[str] = [] # List of required kwargs, e.g., ["language"]

# This map replaces the entire if/elif block
FILE_SPEC_MAP: Dict[FileType, FileSpec] = {
    FileType.SOURCE_VIDEO: FileSpec(filename_template="{filename}", required_params=["filename"]),
    FileType.WORKING_VIDEO: FileSpec(filename_template="{filename}", required_params=["filename"]),
    FileType.RAW_AUDIO: FileSpec(filename_template="raw_audio.wav"),
    FileType.COMPRESSED_AUDIO: FileSpec(filename_template="{filename}", required_params=["filename"]),
    FileType.TRANSCRIPTION_JSON: FileSpec(filename_template="transcription.json"),
    FileType.TRANSCRIPTION_TXT: FileSpec(filename_template="transcription.txt"),
    FileType.LABELED_TRANSCRIPT: FileSpec(filename_template="transcript_labeled.txt"),
    FileType.SEGMENTED_TRANSCRIPT: FileSpec(filename_template="transcript_segmented.txt"),
    FileType.SEGMENTED_TRANSCRIPT_JSON: FileSpec(filename_template="transcript_segmented.json"),
    FileType.LABELED_SEGMENTED_TRANSCRIPT: FileSpec(filename_template="labeled_segmented_transcript.txt"),
    FileType.REFINED_TRANSCRIPT: FileSpec(filename_template="refined_transcript.txt"),
    FileType.TRANSLATION_OUTPUT_JSON: FileSpec(filename_template="translations_all.json"),
    FileType.TRANSLATION_TXT: FileSpec(filename_template="translated_{language}.txt", required_params=["language"]),
    FileType.TRANSLATION_SEGMENTED_TXT: FileSpec(filename_template="segmented_{language}.txt", required_params=["language"]),
    FileType.SUBTITLE_SRT: FileSpec(filename_template="{language}.srt", required_params=["language"]),
    FileType.SUBTITLE_VTT: FileSpec(filename_template="{language}.vtt", required_params=["language"]),
    FileType.JOB_LOG: FileSpec(filename_template="workflow.log"),
    FileType.CUSTOM_TERMS_XLSX: FileSpec(filename_template="custom_terms.xlsx"),
    FileType.SUMMARY_JSON: FileSpec(filename_template="summary.json"),
    FileType.TERMINOLOGY_JSON: FileSpec(filename_template="terminology.json"),
    FileType.GLOBAL_ANALYSIS_JSON: FileSpec(filename_template="global_analysis.json"),
    FileType.SCENE_DIGESTS_JSON: FileSpec(filename_template="scene_digests.json"),
    FileType.CORRECTED_TRANSCRIPT: FileSpec(filename_template="transcript_corrected.txt"),
    FileType.TRANSLATION_SORTED_TXT: FileSpec(filename_template="sorted_{language}.txt", required_params=["language"]),
    FileType.DEBUG_FILE: FileSpec(filename_template="{filename}", required_params=["filename"]),
    FileType.ALIGNED_CHUNKS_XLSX: FileSpec(filename_template="aligned_chunks.xlsx"),
    FileType.ALIGNED_CHUNKS_JSON: FileSpec(filename_template="aligned_chunks.json"),
    FileType.CLEANED_CHUNKS_XLSX: FileSpec(filename_template="cleaned_chunks.xlsx"),
    FileType.CLEANED_CHUNKS_TXT: FileSpec(filename_template="cleaned_chunks.txt"),
    FileType.THUMBNAIL: FileSpec(filename_template="thumbnail_{size}.jpg", required_params=["size"]),
    FileType.PACKAGE_MANIFEST: FileSpec(filename_template="package_{job_id}_manifest.json", required_params=["job_id"]),
    FileType.MODIFIED_SUBTITLE: FileSpec(filename_template="{language}/modified.json", required_params=["language"]),
    FileType.SUBTITLE_LANG_JSON: FileSpec(filename_template="subtitle_{language}.json", required_params=["language"]),
    FileType.SUBTITLE_SRC_JSON: FileSpec(filename_template="subtitle_src.json"),
    FileType.VERSION_FILE: FileSpec(filename_template="{language}/{filename}", required_params=["language", "filename"]),
    FileType.PREFERENCES_FILE: FileSpec(filename_template="{filename}", required_params=["filename"]),
    FileType.TEMP_FILE: FileSpec(filename_template="{filename}", required_params=["filename"]),
    FileType.UPLOADED_FILE: FileSpec(filename_template="{filename}", required_params=["filename"]),
    # JOB_DIRECTORY is a special case handled directly in the get_file_path method
}


class FilePathManager:
    """
    FilePathManager provides a centralized, data-driven mechanism for managing file paths.
    It enforces a hierarchical directory structure based on user_id and job_id
    to ensure proper security isolation between users and jobs.
    """
    # Added a comment to force reload

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initializes the FilePathManager.
        Args:
            base_dir: Optional base directory override. If not provided, uses STORAGE_BASE_DIR from settings.
        """
        from app.core.config import get_settings
        settings = get_settings()
        
        self.base_dir = base_dir or settings.STORAGE_BASE_DIR
        self.users_dir = os.path.join(self.base_dir, "users")
        self._path_cache: Dict[str, str] = {}
        
        # Local-only storage (S3/R2 removed for open-source version)
        from app.utils.storage_backend import create_storage_backend
        self.storage = create_storage_backend('local', base_dir=self.base_dir)
        self.local_cache = self.storage
        
        # Create base directory for local storage/cache
        # Always create local directories since we use local cache even in S3 mode
        os.makedirs(self.users_dir, exist_ok=True)
        
        logger.info(f"FilePathManager initialized with local storage backend: {self.base_dir}")

    def _get_job_dir(self, user_id: int, job_id: int) -> str:
        """Returns the path to a specific job's directory, creating it if necessary."""
        user_dir = os.path.join(self.users_dir, str(user_id))
        job_dir = os.path.join(user_dir, "jobs", str(job_id))
        os.makedirs(job_dir, exist_ok=True)
        return job_dir

    def _get_stage_dir(self, user_id: int, job_id: int, stage: str) -> str:
        """Returns the path to a specific stage directory within a job, creating it if necessary."""
        job_dir = self._get_job_dir(user_id, job_id)
        stage_dir = os.path.join(job_dir, stage)
        os.makedirs(stage_dir, exist_ok=True)
        return stage_dir

    def get_file_path(self, context: "JobContext", file_type: FileType, **kwargs: Any) -> str:
        """
        Gets the standardized, secure file path for a given file type using a data-driven approach.
        
        Args:
            context: JobContext containing user_id, job_id.
            file_type: The type of file to get the path for.
            **kwargs: Dynamic arguments required by the file type, e.g., language="fr", filename="video.mp4".
            
        Returns:
            The full, absolute path to the requested file.
            
        Raises:
            ValueError: If a required parameter for a file type is not provided.
            KeyError: If the file_type is not defined in the configuration map.
        """
        # Generate a stable cache key from kwargs
        kwargs_tuple = tuple(sorted(kwargs.items()))
        cache_key = f"u{context.user_id}_j{context.job_id}_{file_type.name}_{kwargs_tuple}"
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]

        # Handle special cases that don't map to a file, but a directory
        if file_type == FileType.JOB_DIRECTORY:
            return self._get_job_dir(context.user_id, context.job_id)
        
        # Handle package directory - packages are stored at base level, not per job
        if file_type == FileType.PACKAGE_DIR:
            packages_dir = os.path.join(self.base_dir, "packages")
            os.makedirs(packages_dir, exist_ok=True)
            # Create package subdirectory for this specific job
            package_dir = os.path.join(packages_dir, f"package_{context.job_id}")
            os.makedirs(package_dir, exist_ok=True)
            return package_dir

        # Look up the file specification from the map
        spec = FILE_SPEC_MAP.get(file_type)
        if not spec:
            raise KeyError(f"No file specification found for file type: {file_type}")

        # Validate that all required parameters are provided in kwargs
        for param in spec.required_params:
            if param not in kwargs:
                raise ValueError(f"Missing required parameter '{param}' for file type {file_type}")

        # Generate filename from the template and provided kwargs
        try:
            # Note: Using .format(**kwargs) allows templates to use any provided kwarg
            final_filename = spec.filename_template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Template for {file_type} requires parameter '{e.args[0]}', but it was not provided.") from e


        # Get the stage directory and combine with filename
        stage = file_type.value
        stage_dir = self._get_stage_dir(context.user_id, context.job_id, stage)
        file_path = os.path.join(stage_dir, final_filename)
        
        self._path_cache[cache_key] = file_path
        return file_path
    
    def get_directory_path(self, context: "JobContext", dir_type: FileType) -> str:
        """
        Get the directory path for a specific directory type.
        
        Args:
            context: JobContext containing user_id, job_id
            dir_type: FileType representing the directory
            
        Returns:
            str: Full path to the directory
        """
        if dir_type == FileType.JOB_DIRECTORY:
            return self._get_job_dir(context.user_id, context.job_id)
        
        # For other directory types, use the file type value as the stage
        stage = dir_type.value
        return self._get_stage_dir(context.user_id, context.job_id, stage)
        
    def read_file(self, file_path: str, use_cache: bool = True) -> bytes:
        """Read file contents as bytes."""
        from app.core.config import get_settings
        settings = get_settings()
        
        # If S3 priority is enabled, try S3 first
        if settings.PREFER_S3_STORAGE and hasattr(self, 'storage') and self.local_cache != self.storage:
            try:
                return self.storage.read_file(file_path)
            except Exception as e:
                logger.warning(f"Failed to read from S3, falling back to local cache: {e}")
        
        # Try local cache first if available and requested (default behavior)
        if use_cache and hasattr(self, 'local_cache') and self.local_cache != self.storage:
            if self.local_cache.exists(file_path):
                return self.local_cache.read_file(file_path)
        
        # Fallback to storage (S3 or local)
        return self.storage.read_file(file_path)
    
    def write_file(self, file_path: str, data: bytes, cache_only: bool = None) -> None:
        """Write bytes to file."""
        from app.core.config import get_settings
        settings = get_settings()
        
        # Use cache_only from settings if not explicitly provided
        if cache_only is None:
            cache_only = settings.CACHE_ONLY_MODE
            
        # Write to local cache if available
        if hasattr(self, 'local_cache'):
            self.local_cache.write_file(file_path, data)
            
        # Also write to remote storage unless cache_only is True
        if not cache_only and self.local_cache != self.storage:
            self.storage.write_file(file_path, data)
        elif self.local_cache == self.storage:
            # For local-only mode, storage and cache are the same
            pass
    
    def read_text(self, file_path: str, encoding: str = 'utf-8', use_cache: bool = True) -> str:
        """Read file contents as text."""
        from app.core.config import get_settings
        settings = get_settings()
        
        # If S3 priority is enabled, try S3 first
        if settings.PREFER_S3_STORAGE and hasattr(self, 'storage') and self.local_cache != self.storage:
            try:
                return self.storage.read_text(file_path, encoding)
            except Exception as e:
                logger.warning(f"Failed to read text from S3, falling back to local cache: {e}")
        
        # Try local cache first if available and requested (default behavior)
        if use_cache and hasattr(self, 'local_cache') and self.local_cache != self.storage:
            if self.local_cache.exists(file_path):
                return self.local_cache.read_text(file_path, encoding)
        
        # Fallback to storage (S3 or local)
        return self.storage.read_text(file_path, encoding)
    
    def write_text(self, file_path: str, text: str, encoding: str = 'utf-8', cache_only: bool = None) -> None:
        """Write text to file."""
        from app.core.config import get_settings
        settings = get_settings()
        
        # Use cache_only from settings if not explicitly provided
        if cache_only is None:
            cache_only = settings.CACHE_ONLY_MODE
            
        # Write to local cache if available
        if hasattr(self, 'local_cache'):
            self.local_cache.write_text(file_path, text, encoding)
            
        # Also write to remote storage unless cache_only is True
        if not cache_only and self.local_cache != self.storage:
            self.storage.write_text(file_path, text, encoding)
        elif self.local_cache == self.storage:
            # For local-only mode, storage and cache are the same
            pass
    
    def read_json(self, file_path: str) -> Any:
        """Read JSON file, checking storage priority."""
        from app.core.config import get_settings
        settings = get_settings()
        
        # If S3 priority is enabled, try S3 first
        if settings.PREFER_S3_STORAGE and hasattr(self, 'storage') and self.local_cache != self.storage:
            try:
                return self.storage.read_json(file_path)
            except Exception as e:
                logger.warning(f"Failed to read JSON from S3, falling back to local cache: {e}")
        
        # Try local cache first if available (default behavior)
        if hasattr(self, 'local_cache') and self.local_cache != self.storage:
            if self.local_cache.exists(file_path):
                return self.local_cache.read_json(file_path)
        
        # Fallback to remote storage
        return self.storage.read_json(file_path)
    
    def write_json(self, file_path: str, data: Any, indent: int = 2, ensure_ascii: bool = False, cache_only: bool = None) -> None:
        """Write data to JSON file."""
        from app.core.config import get_settings
        settings = get_settings()
        
        # Use cache_only from settings if not explicitly provided
        if cache_only is None:
            cache_only = settings.CACHE_ONLY_MODE
            
        # Always write to local cache if available
        if hasattr(self, 'local_cache'):
            self.local_cache.write_json(file_path, data, indent, ensure_ascii)
            logger.debug(f"JSON data written to local cache: {file_path}")
            
        # Also write to remote storage unless cache_only is True
        if not cache_only and self.local_cache != self.storage:
            self.storage.write_json(file_path, data, indent, ensure_ascii)
            logger.debug(f"JSON data written to remote storage: {file_path}")
        elif self.local_cache == self.storage:
            # For local-only mode, storage and cache are the same
            pass
    
    def exists(self, file_path: str, check_cache_first: bool = True) -> bool:
        """Check if file exists."""
        from app.core.config import get_settings
        settings = get_settings()
        
        # If S3 priority is enabled, check S3 first
        if settings.PREFER_S3_STORAGE and hasattr(self, 'storage') and self.local_cache != self.storage:
            try:
                if self.storage.exists(file_path):
                    return True
            except Exception as e:
                logger.warning(f"Failed to check S3 existence, checking local cache: {e}")
        
        # Check local cache first if available and requested (default behavior)
        if check_cache_first and hasattr(self, 'local_cache') and self.local_cache != self.storage:
            if self.local_cache.exists(file_path):
                return True
        
        # Check remote storage (fallback or primary for non-S3-priority mode)
        return self.storage.exists(file_path)
    
    def remove(self, file_path: str) -> None:
        """Remove file."""
        self.storage.remove(file_path)
    
    def copy(self, src_path: str, dst_path: str) -> None:
        """Copy file from src to dst."""
        self.storage.copy(src_path, dst_path)
    
    def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes."""
        # Try local cache first if available
        if hasattr(self, 'local_cache') and self.local_cache != self.storage:
            if self.local_cache.exists(file_path):
                return self.local_cache.get_file_size(file_path)
        # Fallback to remote storage
        return self.storage.get_file_size(file_path)
    
    def get_local_path(self, file_path: str) -> str:
        """
        Get the actual local file system path for a given file path.
        This is useful for operations that require direct file system access.
        """
        if hasattr(self, 'local_cache') and self.local_cache != self.storage:
            # For S3 with local cache, check if path is already local
            if file_path.startswith(self.base_dir):
                # Path is already a local path, return as-is
                return file_path
            elif file_path.startswith('/'):
                # Absolute path, convert to local cache path
                return os.path.join(self.base_dir, file_path.lstrip('/'))
            else:
                # Relative path, join with base_dir
                return os.path.join(self.base_dir, file_path)
        else:
            # For local storage, return as-is
            return file_path
    
    def makedirs(self, dir_path: str, exist_ok: bool = True) -> None:
        """Create directory."""
        self.storage.makedirs(dir_path, exist_ok)
    
    def generate_presigned_url(self, file_path: str, expiry_seconds: int = 3600) -> Optional[str]:
        """No-op in local-only mode."""
        return None
    
    def sync_to_remote(self, file_path: str) -> bool:
        """
        Sync a file from local cache to remote S3 storage.
        Returns True if successful, False otherwise.
        """
        from app.core.config import get_settings
        settings = get_settings()
        
        # Only sync if we have both local cache and remote storage
        if not hasattr(self, 'local_cache') or self.local_cache == self.storage:
            return False
            
        try:
            # Convert absolute path to relative path if needed
            relative_path = file_path
            if file_path.startswith(self.base_dir):
                relative_path = os.path.relpath(file_path, self.base_dir)
            
            logger.debug(f"Syncing file: original_path={file_path}, relative_path={relative_path}")
            
            # Check if file exists in local cache
            if not self.local_cache.exists(relative_path):
                logger.warning(f"File not found in local cache for sync: {relative_path}")
                return False
                
            # Read from local cache and write to remote storage
            file_data = self.local_cache.read_file(relative_path)
            self.storage.write_file(relative_path, file_data)
            
            logger.info(f"Successfully synced file to remote storage: {relative_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync file to remote storage {file_path}: {e}")
            logger.error(f"Exception type: {type(e)}, Exception args: {e.args}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False
    
    def cleanup_local_file(self, file_path: str, force: bool = False) -> bool:
        """
        Clean up a local cached file after confirming it exists in remote storage.
        
        Args:
            file_path: Path to the file to clean up
            force: If True, delete without checking remote storage
            
        Returns:
            True if file was cleaned up, False otherwise
        """
        from app.core.config import get_settings
        settings = get_settings()
        
        # Only cleanup if auto cleanup is enabled or force is True
        if not settings.AUTO_CLEANUP_LOCAL_CACHE and not force:
            return False
            
        # Only cleanup if we have both local cache and remote storage
        if not hasattr(self, 'local_cache') or self.local_cache == self.storage:
            return False
            
        try:
            # Check if file exists in local cache
            if not self.local_cache.exists(file_path):
                return True  # Already cleaned up
                
            # Unless forced, verify file exists in remote storage before cleanup
            if not force and not self.storage.exists(file_path):
                logger.warning(f"File not found in remote storage, skipping cleanup: {file_path}")
                return False
                
            # Get local path and remove the file
            local_path = self.get_local_path(file_path)
            if os.path.exists(local_path):
                os.remove(local_path)
                logger.info(f"Cleaned up local cached file: {local_path}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to cleanup local file {file_path}: {e}")
            return False
            
        return False
    
    def cleanup_job_cache(self, user_id: int, job_id: int, older_than_hours: int = None) -> dict:
        """
        Clean up local cache for a specific job.
        
        Args:
            user_id: User ID
            job_id: Job ID
            older_than_hours: Only clean files older than this many hours
            
        Returns:
            Dictionary with cleanup statistics
        """
        from app.core.config import get_settings
        settings = get_settings()
        
        if older_than_hours is None:
            older_than_hours = settings.CLEANUP_DELAY_HOURS
            
        stats = {
            "files_checked": 0,
            "files_cleaned": 0,
            "files_failed": 0,
            "bytes_freed": 0
        }
        
        try:
            # Get job directory
            job_dir = self._get_job_dir(user_id, job_id)
            local_job_dir = self.get_local_path(job_dir)
            
            if not os.path.exists(local_job_dir):
                return stats
                
            import time
            cutoff_time = time.time() - (older_than_hours * 3600)
            
            # Walk through all files in job directory
            for root, dirs, files in os.walk(local_job_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    stats["files_checked"] += 1
                    
                    try:
                        # Check file age
                        if os.path.getmtime(file_path) > cutoff_time:
                            continue  # File is too recent
                            
                        # Get relative path for remote storage check
                        rel_path = os.path.relpath(file_path, self.base_dir)
                        
                        # Get file size before deletion
                        file_size = os.path.getsize(file_path)
                        
                        # Clean up the file
                        if self.cleanup_local_file(rel_path):
                            stats["files_cleaned"] += 1
                            stats["bytes_freed"] += file_size
                        else:
                            stats["files_failed"] += 1
                            
                    except Exception as e:
                        logger.error(f"Error processing file {file_path}: {e}")
                        stats["files_failed"] += 1
                        
            logger.info(f"Job {job_id} cache cleanup completed: {stats}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup job cache for job {job_id}: {e}")
            
        return stats
    
    def copy_fileobj(self, src_fileobj: BinaryIO, dst_path: str, cache_only: bool = None) -> None:
        """Copy file object to destination path."""
        from app.core.config import get_settings
        settings = get_settings()
        
        # Use cache_only from settings if not explicitly provided
        if cache_only is None:
            cache_only = settings.CACHE_ONLY_MODE
            
        # Always write to local cache if available
        if hasattr(self, 'local_cache'):
            self.local_cache.copy_fileobj(src_fileobj, dst_path)
            logger.debug(f"File copied to local cache: {dst_path}")
            
        # Also write to remote storage unless cache_only is True
        if not cache_only and self.local_cache != self.storage:
            # Reset file pointer for second copy operation
            src_fileobj.seek(0)
            self.storage.copy_fileobj(src_fileobj, dst_path)
            logger.debug(f"File copied to remote storage: {dst_path}")
        elif self.local_cache == self.storage:
            # For local-only mode, storage and cache are the same
            pass
    
    def read_excel(self, file_path: str, **kwargs):
        """Read Excel file using pandas. Returns DataFrame."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas required for Excel operations")
        
        # For S3 storage, we need to read the file data and use BytesIO
        if hasattr(self.storage, 'bucket_name'):  # S3 backend
            import io
            data = self.storage.read_file(file_path)
            return pd.read_excel(io.BytesIO(data), **kwargs)
        else:
            # For local storage, use file path directly
            return pd.read_excel(file_path, **kwargs)
    
    def write_excel(self, file_path: str, df, **kwargs) -> None:
        """Write DataFrame to Excel file."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas required for Excel operations")
        
        # For S3 storage, write to BytesIO then upload
        if hasattr(self.storage, 'bucket_name'):  # S3 backend
            import io
            buffer = io.BytesIO()
            df.to_excel(buffer, **kwargs)
            self.storage.write_file(file_path, buffer.getvalue())
        else:
            # For local storage, write directly
            df.to_excel(file_path, **kwargs)

    def sync_job_to_remote(self, job_context: "JobContext", file_types: Optional[List[FileType]] = None) -> bool:
        """
        Manually sync local cached files to remote S3 storage.
        
        Args:
            job_context: Job context containing user_id and job_id
            file_types: Optional list of specific file types to sync. If None, sync all files.
            
        Returns:
            bool: True if sync successful, False otherwise
        """
        if not hasattr(self, 'local_cache') or self.local_cache == self.storage:
            logger.info("No local cache or already using local storage, no sync needed")
            return True
            
        try:
            job_dir = self._get_job_dir(job_context.user_id, job_context.job_id)
            
            # If specific file types provided, sync only those
            if file_types:
                for file_type in file_types:
                    local_path = self.get_file_path(job_context, file_type)
                    if self.local_cache.exists(local_path):
                        # Read from local cache
                        data = self.local_cache.read_file(local_path)
                        # Write to remote storage
                        self.storage.write_file(local_path, data)
                        logger.info(f"Synced {file_type.value} to remote storage")
            else:
                # Sync entire job directory
                import glob
                local_job_path = os.path.join(self.base_dir, job_dir)
                if os.path.exists(local_job_path):
                    for root, dirs, files in os.walk(local_job_path):
                        for file in files:
                            local_file_path = os.path.join(root, file)
                            # Convert to relative path for storage
                            rel_path = os.path.relpath(local_file_path, self.base_dir)
                            rel_path = rel_path.replace(os.sep, '/')  # Normalize for S3
                            
                            # Read from local and write to remote
                            data = self.local_cache.read_file(rel_path)
                            self.storage.write_file(rel_path, data)
                            logger.info(f"Synced {rel_path} to remote storage")
                            
            logger.info(f"Successfully synced job {job_context.job_id} files to remote storage")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync files to remote storage: {e}")
            return False

    def cleanup_local_cache(self, job_context: "JobContext", keep_final_results: bool = True) -> bool:
        """
        Clean up local cached files after successful sync to remote.
        
        Args:
            job_context: Job context containing user_id and job_id
            keep_final_results: If True, keep final result files (subtitles, videos)
            
        Returns:
            bool: True if cleanup successful, False otherwise
        """
        if not hasattr(self, 'local_cache') or self.local_cache == self.storage:
            logger.info("No local cache to clean up")
            return True
            
        try:
            job_dir = self._get_job_dir(job_context.user_id, job_context.job_id)
            local_job_path = os.path.join(self.base_dir, job_dir)
            
            if not os.path.exists(local_job_path):
                logger.info(f"Local cache directory {local_job_path} does not exist")
                return True
                
            if keep_final_results:
                # Only remove intermediate files, keep final results
                temp_dirs = ['audio', 'transcription', 'translation', 'logs']
                for temp_dir in temp_dirs:
                    temp_path = os.path.join(local_job_path, temp_dir)
                    if os.path.exists(temp_path):
                        import shutil
                        shutil.rmtree(temp_path)
                        logger.info(f"Cleaned up temporary directory: {temp_dir}")
            else:
                # Remove entire job directory
                import shutil
                shutil.rmtree(local_job_path)
                logger.info(f"Cleaned up entire local cache for job {job_context.job_id}")
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup local cache: {e}")
            return False

    def auto_sync_file_to_remote(self, file_path: str, logger_func=None) -> bool:
        """
        Automatically sync a file to remote storage if S3 backend is configured.
        This is a convenience method for services to use after creating result files.
        
        Args:
            file_path: Path to the file to sync
            logger_func: Optional logging function to use for messages
            
        Returns:
            bool: True if sync was successful or not needed, False if sync failed
        """
        from app.core.config import get_settings
        settings = get_settings()
        
        # Only sync if using S3 backend
        if settings.STORAGE_BACKEND.lower() != 's3':
            return True  # No sync needed for local storage
            
        try:
            if logger_func:
                logger_func(f"Auto-syncing file to remote storage: {file_path}")
            
            success = self.sync_to_remote(file_path)
            
            if success:
                if logger_func:
                    logger_func(f"Successfully synced to remote storage: {file_path}")
            else:
                if logger_func:
                    logger_func(f"Failed to sync to remote storage: {file_path}")
                logger.warning(f"Failed to auto-sync file to remote storage: {file_path}")
                
            return success
            
        except Exception as e:
            if logger_func:
                logger_func(f"Error syncing file to remote storage: {file_path} - {str(e)}")
            logger.error(f"Error in auto_sync_file_to_remote for {file_path}: {e}")
            return False


# Global singleton instance
_file_path_manager_instance = None

def get_file_path_manager() -> "FilePathManager":
    """
    Get a singleton instance of the FilePathManager.
    """
    global _file_path_manager_instance
    if _file_path_manager_instance is None:
        _file_path_manager_instance = FilePathManager()
    return _file_path_manager_instance