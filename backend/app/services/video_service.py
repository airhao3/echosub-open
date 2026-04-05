import os
import shutil
import logging
import json
import subprocess
import re
import tempfile
import hashlib
import tempfile
import unicodedata
import urllib.parse
from typing import Optional, Tuple, Dict, Any, List, Union

# Import FilePathManager and FileType
from app.utils.file_path_manager import FilePathManager, FileType
from app.models.job_context import JobContext

# 将来这些路径会通过配置进行管理
TEMP_DIR = "/tmp/videolingo_uploads"

logger = logging.getLogger(__name__)

class VideoService:
    """
    轻量级视频服务 - 仅支持音频提取，不进行视频压制
    适用于低资源云服务器
    """
    
    # 支持的视频格式
    SUPPORTED_VIDEO_EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv", ".webm"]
    
    def __init__(self, file_manager: Optional[FilePathManager] = None):
        """
        Initialize VideoService with optional FilePathManager
        
        Args:
            file_manager: Optional FilePathManager instance for file path management
        """
        from app.utils.file_path_manager import get_file_path_manager
        self.file_manager = file_manager or get_file_path_manager()
    
    @staticmethod
    def sanitize_filename(filename: str, max_length: int = 200) -> str:
        """
        Sanitize a filename while preserving Unicode characters, spaces, and emojis.
        Only removes characters that could cause filesystem or security issues.
        
        Args:
            filename: The original filename to sanitize
            max_length: Maximum length of the resulting filename
            
        Returns:
            Sanitized filename with safe characters
        """
        if not filename:
            return "unnamed_file"
            
        # Normalize Unicode characters for consistent handling
        filename = unicodedata.normalize('NFC', filename)
        
        # Replace only dangerous control characters and filesystem-unsafe characters
        # Keep Unicode letters, numbers, spaces, dots, hyphens, underscores, and emojis
        # Only remove: control chars (0x00-0x1F), DEL (0x7F), and filesystem unsafe chars
        unsafe_chars = r'[\x00-\x1f\x7f\/\\:\*\?"<>|]'
        filename = re.sub(unsafe_chars, '_', filename)
        
        # Remove leading/trailing whitespace and dots (but keep internal ones)
        filename = filename.strip(' .')
        
        # If the filename is empty after sanitization, use a default name
        if not filename:
            return "unnamed_file"
            
        # Truncate if too long, preserving extension
        if len(filename) > max_length:
            name, ext = os.path.splitext(filename)
            if ext:
                # Keep the extension
                max_name_length = max(max_length - len(ext), 1)  # Ensure at least 1 character for name
                name = name[:max_name_length]
                filename = name + ext
            else:
                filename = filename[:max_length]
        
        return filename

    @staticmethod
    def generate_unique_id() -> str:
        """Generate a unique ID for a file"""
        import uuid
        return uuid.uuid4().hex[:12]
    
    @staticmethod
    def validate_file_path(file_path: str) -> str:
        """
        Validate and normalize file path for FFmpeg operations.
        Ensures the path exists and is accessible.
        
        Args:
            file_path: Path to validate
            
        Returns:
            Normalized absolute path
            
        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file isn't accessible
        """
        if not file_path:
            raise ValueError("File path cannot be empty")
            
        # Convert to absolute path and normalize
        abs_path = os.path.abspath(file_path)
        
        # Check if file exists
        if not os.path.isfile(abs_path):
            # Try unquoting in case it's URL-encoded
            try:
                unquoted_path = urllib.parse.unquote(abs_path)
                if os.path.isfile(unquoted_path):
                    abs_path = unquoted_path
                else:
                    raise FileNotFoundError(f"File not found: {abs_path}")
            except Exception:
                raise FileNotFoundError(f"File not found: {abs_path}")
        
        # Check if file is readable
        if not os.access(abs_path, os.R_OK):
            raise PermissionError(f"Cannot read file: {abs_path}")
            
        return abs_path
        
    def calculate_file_hash_with_manager(self, file_path: str) -> str:
        """
        Calculate the SHA-256 hash of a file using file manager for path resolution
        """
        local_path = self.file_manager.get_local_path(file_path)
        if not os.path.exists(local_path):
            logger.error(f"File not found for hashing: {local_path} (original: {file_path})")
            return ""
        return self._calculate_hash_from_local_path(local_path)
    
    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """
        Calculate the SHA-256 hash of a file to identify duplicates
        Uses chunks to efficiently handle large files (static method for backward compatibility)
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found for hashing: {file_path}")
            return ""
        return VideoService._calculate_hash_from_local_path(file_path)
    
    @staticmethod
    def _calculate_hash_from_local_path(local_path: str) -> str:
        """Calculate hash from local file path"""
        import hashlib
        sha256_hash = hashlib.sha256()
        
        try:
            with open(local_path, "rb") as f:
                # Read and update hash in chunks of 4K for memory efficiency
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating file hash: {str(e)}")
            return ""
            
    @staticmethod
    def find_jobs_by_video_filename(db, video_filename: str) -> List:
        """
        Find jobs with the same video filename
        This is a fallback method when file_hash isn't available in the database schema
        Returns jobs sorted by creation date (newest first)
        """
        from app.models.job import Job, JobStatus
        from sqlalchemy import desc
        
        try:
            # Check for completed jobs with same filename first
            completed_jobs = db.query(Job).filter(
                Job.video_filename == video_filename,
                Job.status == JobStatus.COMPLETED
            ).order_by(desc(Job.created_at)).all()
            
            if completed_jobs:
                return completed_jobs
                
            # If no completed jobs, check for in-progress ones
            in_progress_jobs = db.query(Job).filter(
                Job.video_filename == video_filename,
                Job.status.in_([JobStatus.PROCESSING, JobStatus.PENDING])
            ).order_by(desc(Job.created_at)).all()
            
            return in_progress_jobs
        except Exception as e:
            logger.error(f"Error finding jobs by file info: {str(e)}")
            return []
    
    @staticmethod
    def is_valid_video_extension(filename: str) -> bool:
        """Check if a file has a valid video extension"""
        if not filename:
            return False
        
        ext = os.path.splitext(filename.lower())[1]
        return ext in VideoService.SUPPORTED_VIDEO_EXTENSIONS
    
    @staticmethod
    def get_supported_video_formats() -> list:
        """Get a list of supported video formats"""
        return [ext[1:] for ext in VideoService.SUPPORTED_VIDEO_EXTENSIONS]  # Remove leading dot
    
    @staticmethod
    def ensure_temp_dir():
        """Ensure temporary directory exists"""
        os.makedirs(TEMP_DIR, exist_ok=True)
    
    @staticmethod
    def save_uploaded_video(file_content: bytes, filename: str) -> str:
        """
        Save an uploaded video file to temporary storage
        
        Warning: This method uses hardcoded paths and is deprecated.
        Use save_uploaded_video_to_job() with file_path_manager instead.
        """
        logger.warning("save_uploaded_video() is deprecated. Use save_uploaded_video_to_job() instead.")
        VideoService.ensure_temp_dir()
        file_path = os.path.join(TEMP_DIR, filename)
        
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        return file_path
    
    def save_uploaded_video_to_job(self, file_content: bytes, filename: str, context: JobContext) -> str:
        """
        Save an uploaded video file to job-specific storage using file_path_manager
        
        Args:
            file_content: Binary content of the video file
            filename: Original filename of the video
            context: JobContext containing user_id and job_id
            
        Returns:
            Path to the saved video file
        """
        try:
            # Use file_path_manager to get the proper path for uploaded video
            file_path = self.file_manager.get_file_path(
                context, FileType.UPLOADED_FILE, filename=filename
            )
            
            # Write the file content
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            logger.info(f"Saved uploaded video to: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving uploaded video: {str(e)}")
            raise
    
    def copy_video_to_source(self, video_path: str, context: JobContext, target_filename: str) -> str:
        """
        Copy video file to job's source directory using file_path_manager
        
        Args:
            video_path: Path to the source video file
            context: JobContext containing user_id and job_id  
            target_filename: Target filename for the copied video
            
        Returns:
            Path to the copied video file
        """
        try:
            # Use file_path_manager to get proper source video path
            destination_path = self.file_manager.get_file_path(
                context, FileType.SOURCE_VIDEO, filename=target_filename
            )
            
            # Copy the video file
            shutil.copy2(video_path, destination_path)
            logger.info(f"Copied video to source directory: {destination_path}")
            
            # Calculate file hash for verification
            file_hash = VideoService.calculate_file_hash(destination_path)
            logger.info(f"Calculated file hash: {file_hash}")
            
            return destination_path
            
        except Exception as e:
            logger.error(f"Error copying video to source: {str(e)}")
            raise
    
    def convert_video_to_audio_with_manager(self, video_path: str, output_path: str, progress_callback: Optional[callable] = None) -> str:
        """
        Convert video file to audio using file manager for path resolution
        """
        local_video_path = self.file_manager.get_local_path(video_path)
        local_output_path = self.file_manager.get_local_path(output_path)
        return self._convert_audio_from_local_paths(local_video_path, local_output_path, progress_callback)
    
    @staticmethod
    def convert_video_to_audio(video_path: str, output_path: str, progress_callback: Optional[callable] = None) -> str:
        """
        Convert video file to audio for transcription
        轻量级版本 - 仅提取音频，不进行复杂处理
        
        Args:
            video_path: Path to the input video file
            output_path: Path where the output audio file should be saved
                        
        Returns:
            Path to the converted audio file
        """
        try:
            # Validate input video path
            video_path = VideoService.validate_file_path(video_path)
            return VideoService._convert_audio_from_local_paths(video_path, output_path, progress_callback)
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Error converting video to audio: {e.stderr if e.stderr else e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        except Exception as e:
            logger.error(f"Unexpected error in convert_video_to_audio: {str(e)}")
            raise
    
    @staticmethod
    def _convert_audio_from_local_paths(video_path: str, output_path: str, progress_callback: Optional[callable] = None) -> str:
        """
        Core audio conversion logic using local file paths
        """
        # Ensure the parent directory for the output file exists
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)

        # Set environment variables for proper UTF-8 encoding
        env = os.environ.copy()
        env['LC_ALL'] = 'C.UTF-8'
        env['LANG'] = 'C.UTF-8'
        env['PYTHONIOENCODING'] = 'utf-8'

        # Use ffmpeg to extract audio - optimized for Whisper API
        # 16kHz mono 64kbps is sufficient: Whisper internally downsamples to 16kHz anyway
        # This produces ~0.5MB/min vs ~1.5MB/min at 44100Hz/stereo/192kbps
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-vn',              # No video
            '-acodec', 'libmp3lame',
            '-ar', '16000',     # 16kHz (Whisper's native sample rate)
            '-ac', '1',         # Mono (speech recognition doesn't need stereo)
            '-b:a', '64k',      # 64kbps (adequate for speech)
            output_path
        ]
        
        if progress_callback:
            progress_callback(0, "Starting audio conversion")

        logger.info(f"Converting video to audio: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
            
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError(f"Output file was not created or is empty: {output_path}")

        if progress_callback:
            progress_callback(100, "Audio conversion complete")
            
        logger.info(f"Successfully converted video to audio: {output_path} ({os.path.getsize(output_path)/1024/1024:.2f} MB)")
        return output_path
    
    @staticmethod
    def copy_video_to_job_dir(video_path: str, job_dir: str) -> str:
        """
        Copy the video file to the job directory
        
        Warning: This method uses hardcoded paths and is deprecated.
        Use copy_video_to_source() with file_path_manager instead.
        """
        logger.warning("copy_video_to_job_dir() is deprecated. Use copy_video_to_source() instead.")
        os.makedirs(job_dir, exist_ok=True)
        video_filename = os.path.basename(video_path)
        destination = os.path.join(job_dir, video_filename)
        
        shutil.copy2(video_path, destination)
        logger.info(f"Copied video to job directory: {destination}")
        
        # Calculate file hash after copying to ensure the file is accessible
        file_hash = VideoService.calculate_file_hash(destination)
        logger.info(f"Calculated file hash: {file_hash}")
        
        return destination
    
    @staticmethod
    def compress_audio(audio_path: str, output_path: str) -> str:
        """
        Compress audio file for faster processing
        Based on original VideoLingo's compress_audio function
        """
        try:
            # Set environment variables for proper UTF-8 encoding
            env = os.environ.copy()
            env['LC_ALL'] = 'C.UTF-8'
            env['LANG'] = 'C.UTF-8'
            env['PYTHONIOENCODING'] = 'utf-8'
            env['LANGUAGE'] = 'en'
            
            cmd = [
                'ffmpeg', '-y',
                '-i', audio_path,
                '-b:a', '64k',
                '-ac', '1',
                '-ar', '16000',
                output_path
            ]
            
            subprocess.run(cmd, check=True, capture_output=True, env=env)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Error compressing audio: {e.stderr.decode('utf-8', errors='replace')}")
            raise
    
    @staticmethod
    def check_video_file(file_path: str) -> bool:
        """
        Check if a file is a valid video
        """
        try:
            # Set environment variables for proper UTF-8 encoding
            env = os.environ.copy()
            env['LC_ALL'] = 'C.UTF-8'
            env['LANG'] = 'C.UTF-8'
            env['PYTHONIOENCODING'] = 'utf-8'
            env['LANGUAGE'] = 'en'
            
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_type',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                file_path
            ]
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
            return result.stdout.strip() == 'video'
        except Exception as e:
            logger.error(f"Error checking video file: {str(e)}")
            return False
    
    def get_video_metadata_with_manager(self, video_path: str) -> Dict[str, Any]:
        """
        Get basic video metadata using file manager for path resolution
        """
        # Use file manager to get local path
        local_path = self.file_manager.get_local_path(video_path)
        if not os.path.exists(local_path):
            logger.error(f"Video file does not exist: {local_path} (original: {video_path})")
            return {}
        return self._get_metadata_from_local_path(local_path)
    
    @staticmethod
    def get_video_metadata(video_path: str) -> Dict[str, Any]:
        """
        Get basic video metadata - simplified version (static method for backward compatibility)
        """
        if not os.path.exists(video_path):
            logger.error(f"Video file does not exist: {video_path}")
            return {}
        return VideoService._get_metadata_from_local_path(video_path)
    
    @staticmethod
    def _get_metadata_from_local_path(local_path: str) -> Dict[str, Any]:
        """
        Extract metadata from a local file path
        """
        try:
            # Set environment variables for FFmpeg
            env = os.environ.copy()
            env['LC_ALL'] = 'en_US.UTF-8'
            env['LANG'] = 'en_US.UTF-8'
            env['LANGUAGE'] = 'en'
            
            # Get basic video info
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                local_path
            ]
            
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                env=env,
                text=False  # Get binary output
            )
            
            # Decode with error handling
            try:
                output = result.stdout.decode('utf-8', errors='replace')
                data = json.loads(output)
            except UnicodeDecodeError:
                # Try with UTF-8-sig if UTF-8 fails
                output = result.stdout.decode('utf-8-sig', errors='replace')
                data = json.loads(output)
            
            # Extract basic information
            metadata = {}
            
            # Find video stream
            video_stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
            
            if video_stream:
                metadata['width'] = int(video_stream.get('width', 0))
                metadata['height'] = int(video_stream.get('height', 0))
                metadata['codec'] = video_stream.get('codec_name', 'unknown')
                
                # Calculate fps
                if 'r_frame_rate' in video_stream:
                    fps_parts = video_stream['r_frame_rate'].split('/')
                    if len(fps_parts) == 2 and int(fps_parts[1]) != 0:
                        metadata['fps'] = round(int(fps_parts[0]) / int(fps_parts[1]), 2)
                    else:
                        metadata['fps'] = video_stream['r_frame_rate']
            
            # Format information (duration, etc)
            if 'format' in data:
                if 'duration' in data['format']:
                    metadata['duration'] = float(data['format']['duration'])
                if 'size' in data['format']:
                    metadata['size'] = int(data['format']['size'])  # Size in bytes
            
            return metadata
        
        except Exception as e:
            logger.error(f"Error getting video metadata: {str(e)}")
            return {}
    
    def get_audio_metadata_with_manager(self, audio_path: str) -> Dict[str, Any]:
        """
        Get basic audio metadata using file manager for path resolution
        """
        local_path = self.file_manager.get_local_path(audio_path)
        if not os.path.exists(local_path):
            logger.error(f"Audio file not found: {local_path} (original: {audio_path})")
            return {}
        return self._get_audio_metadata_from_local_path(local_path)
    
    @staticmethod
    def get_audio_metadata(audio_path: str) -> Dict[str, Any]:
        """
        Get basic audio metadata - simplified version (static method for backward compatibility)
        """
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            return {}
        return VideoService._get_audio_metadata_from_local_path(audio_path)
    
    @staticmethod
    def _get_audio_metadata_from_local_path(local_path: str) -> Dict[str, Any]:
        """Extract audio metadata from local file path"""
        try:
            # Set environment variables for encoding
            env = os.environ.copy()
            env['LC_ALL'] = 'C.UTF-8'
            env['LANG'] = 'C.UTF-8'
            env['LANGUAGE'] = 'en'
            
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                local_path
            ]
            
            result = subprocess.run(
                cmd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=False
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='replace')
                logger.error(f"ffprobe failed with error: {error_msg}")
                return {}
            
            # Decode output
            output = result.stdout.decode('utf-8', errors='replace')
            data = json.loads(output)
            
            # Extract relevant information
            metadata = {}
            
            # Find audio stream
            audio_stream = next((s for s in data.get('streams', []) 
                              if s.get('codec_type') == 'audio'), None)
            
            if audio_stream:
                metadata['codec'] = audio_stream.get('codec_name', 'unknown')
                metadata['sample_rate'] = int(audio_stream.get('sample_rate', 0))
                metadata['channels'] = int(audio_stream.get('channels', 0))
                
                if 'bit_rate' in audio_stream and audio_stream['bit_rate']:
                    metadata['bitrate'] = int(audio_stream['bit_rate']) // 1000  # Convert to kbps
            
            # Format information (duration, etc)
            if 'format' in data:
                fmt = data['format']
                if 'duration' in fmt and fmt['duration']:
                    metadata['duration'] = float(fmt['duration'])
                if 'size' in fmt and fmt['size']:
                    metadata['size'] = int(fmt['size'])  # Size in bytes
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting audio metadata: {str(e)}", exc_info=True)
            return {}