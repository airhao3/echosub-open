"""
Video Thumbnail Generation Service

This service generates thumbnails from video files using FFmpeg.
Supports different sizes and formats for various use cases.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple, List
import tempfile

logger = logging.getLogger(__name__)

class ThumbnailService:
    """Service for generating video thumbnails"""
    
    # Standard thumbnail sizes
    THUMBNAIL_SIZES = {
        'small': (160, 90),      # For grid view
        'medium': (320, 180),    # For list view
        'large': (640, 360),     # For detailed view
        'poster': (1280, 720)    # For hero sections
    }
    
    def __init__(self):
        self.ffmpeg_path = self._find_ffmpeg()
        
    def _find_ffmpeg(self) -> str:
        """Find FFmpeg executable path"""
        import shutil
        ffmpeg_path = shutil.which('ffmpeg')
        if not ffmpeg_path:
            raise RuntimeError("FFmpeg not found in system PATH. Please install FFmpeg and ensure it's in your system's PATH.")
        return ffmpeg_path
    
    def generate_thumbnail(self, 
                         video_path: str, 
                         output_path: str,
                         size: str = 'medium',
                         timestamp: str = '00:00:05',
                         quality: int = 2) -> bool:
        """
        Generate a single thumbnail from video
        
        Args:
            video_path: Path to input video file
            output_path: Path for output thumbnail
            size: Thumbnail size key ('small', 'medium', 'large', 'poster')
            timestamp: Time position to extract frame (format: HH:MM:SS)
            quality: JPEG quality (1-31, lower is better quality)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Validate input
            if not os.path.exists(video_path):
                logger.error(f"Video file not found: {video_path}")
                return False
                
            if size not in self.THUMBNAIL_SIZES:
                logger.error(f"Invalid size: {size}. Must be one of {list(self.THUMBNAIL_SIZES.keys())}")
                return False
            
            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Get dimensions for the requested size
            width, height = self.THUMBNAIL_SIZES[size]
            
            # Build FFmpeg command
            cmd = [
                self.ffmpeg_path,
                '-i', video_path,
                '-ss', timestamp,
                '-vframes', '1',
                '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black',
                '-q:v', str(quality),
                '-y',  # Overwrite output file
                output_path
            ]
            
            logger.debug(f"Executing FFmpeg command: {' '.join(cmd)}")
            
            # Execute FFmpeg command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            if result.returncode == 0:
                # Verify output file was created and has content
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f"Successfully generated thumbnail: {output_path}")
                    return True
                else:
                    logger.error(f"Thumbnail file was not created or is empty: {output_path}")
                    return False
            else:
                logger.error(f"FFmpeg failed with return code {result.returncode}")
                logger.error(f"FFmpeg stderr: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"FFmpeg timeout while generating thumbnail for {video_path}")
            return False
        except Exception as e:
            logger.error(f"Error generating thumbnail: {str(e)}")
            return False
    
    def generate_multiple_thumbnails(self,
                                   video_path: str,
                                   output_dir: str,
                                   base_name: str,
                                   sizes: List[str] = None,
                                   timestamps: List[str] = None) -> dict:
        """
        Generate multiple thumbnails at different sizes and timestamps
        
        Args:
            video_path: Path to input video file
            output_dir: Directory for output thumbnails
            base_name: Base name for thumbnail files (without extension)
            sizes: List of size keys to generate
            timestamps: List of timestamps to extract frames from
            
        Returns:
            dict: Dictionary with size/timestamp keys and file paths as values
        """
        if sizes is None:
            sizes = ['small', 'medium', 'large']
            
        if timestamps is None:
            timestamps = ['00:00:05']  # Default to 5 seconds
            
        results = {}
        
        try:
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            for size in sizes:
                for i, timestamp in enumerate(timestamps):
                    # Create filename
                    if len(timestamps) > 1:
                        filename = f"{base_name}_{size}_{i+1}.jpg"
                        key = f"{size}_{i+1}"
                    else:
                        filename = f"{base_name}_{size}.jpg"
                        key = size
                    
                    output_path = os.path.join(output_dir, filename)
                    
                    # Generate thumbnail
                    if self.generate_thumbnail(video_path, output_path, size, timestamp):
                        results[key] = output_path
                        logger.info(f"Generated {size} thumbnail: {output_path}")
                    else:
                        logger.warning(f"Failed to generate {size} thumbnail")
            
            return results
            
        except Exception as e:
            logger.error(f"Error generating multiple thumbnails: {str(e)}")
            return results
    
    def generate_animated_preview(self,
                                video_path: str,
                                output_path: str,
                                duration: int = 3,
                                fps: int = 10,
                                size: str = 'medium') -> bool:
        """
        Generate an animated GIF preview from video
        
        Args:
            video_path: Path to input video file
            output_path: Path for output GIF
            duration: Duration of GIF in seconds
            fps: Frames per second for GIF
            size: Size key for dimensions
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not os.path.exists(video_path):
                logger.error(f"Video file not found: {video_path}")
                return False
            
            if size not in self.THUMBNAIL_SIZES:
                logger.error(f"Invalid size: {size}")
                return False
            
            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Get dimensions
            width, height = self.THUMBNAIL_SIZES[size]
            
            # Build FFmpeg command for animated GIF
            cmd = [
                self.ffmpeg_path,
                '-i', video_path,
                '-t', str(duration),
                '-vf', f'fps={fps},scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black',
                '-y',
                output_path
            ]
            
            logger.debug(f"Executing FFmpeg command for GIF: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout for GIF
            )
            
            if result.returncode == 0:
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f"Successfully generated animated preview: {output_path}")
                    return True
            
            logger.error(f"Failed to generate animated preview: {result.stderr}")
            return False
            
        except Exception as e:
            logger.error(f"Error generating animated preview: {str(e)}")
            return False
    
    def get_video_duration(self, video_path: str) -> Optional[float]:
        """
        Get video duration in seconds
        
        Args:
            video_path: Path to video file
            
        Returns:
            float: Duration in seconds, or None if failed
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                duration = float(data['format']['duration'])
                return duration
            else:
                logger.error(f"Failed to get video duration: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting video duration: {str(e)}")
            return None
    
    def get_optimal_timestamp(self, video_path: str) -> str:
        """
        Get optimal timestamp for thumbnail extraction - at 10% of video duration
        
        Args:
            video_path: Path to video file
            
        Returns:
            str: Timestamp in HH:MM:SS format
        """
        duration = self.get_video_duration(video_path)
        if duration is None or duration < 1:
            logger.warning(f"Could not get video duration or duration is too short for {video_path}. Using default timestamp 00:00:01.")
            return "00:00:01"
        
        # Calculate timestamp at 10% of duration, but not less than 1 second
        # and not more than (duration - 1) second to avoid issues with end of video
        target_seconds = max(1, min(int(duration * 0.1), int(duration - 1)))
        
        # Convert seconds to HH:MM:SS format
        hours = target_seconds // 3600
        minutes = (target_seconds % 3600) // 60
        seconds = target_seconds % 60
        
        timestamp_str = f"{hours:02}:{minutes:02}:{seconds:02}"
        logger.debug(f"Calculated optimal timestamp for {video_path}: {timestamp_str} (from duration {duration}s)")
        return timestamp_str
    
