import os
import shutil
import logging
import tempfile
import subprocess
import json
import re
from pathlib import Path
from typing import Optional, Tuple, Dict, List, Any, Union

import cv2

from .utils import check_ffmpeg
from app.core.config import settings

logger = logging.getLogger(__name__)

import json

def _process_subtitle_style(style_dict: Optional[Union[Dict[str, Any], str]], video_height: Optional[int] = None) -> str:
    """
    Convert a subtitle style dictionary from the frontend into a FFmpeg-compatible ASS style string.

    - Converts snake_case keys (e.g., 'font_size') to PascalCase ('Fontsize').
    - Converts color strings (hex or rgba) to ASS format (&HAABBGGRR).
    - Maps position strings ('top', 'middle', 'bottom') to ASS alignment codes.
    - Handles preset style values: 'default', 'outline', 'box'
    - If a custom ASS format string is provided, it's used directly.

    Args:
        style_dict: A dictionary containing subtitle style properties from the frontend,
                   or a string representing a preset style or ASS format string.

    Returns:
        A comma-separated string of ASS style overrides for FFmpeg.
    """
    default_font_size = 48
    if video_height:
        # Set font size to be ~7% of video height, with a reasonable minimum.
        default_font_size = max(20, int(video_height * 0.07))

    if not style_dict:
        return f"Fontsize={default_font_size}"

    if isinstance(style_dict, str):
        # First, try to parse it as a JSON string (for custom styles from frontend)
        try:
            style_dict = json.loads(style_dict)
            if not isinstance(style_dict, dict):
                raise json.JSONDecodeError("Not a dict", style_dict, 0)
        except json.JSONDecodeError:
            # If it's not a valid JSON string, treat it as a preset name
            if style_dict == "default":
                return f"Fontname='Helvetica Neue',Fontsize={default_font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2.5,Shadow=0,Alignment=2" # Netflix-style default
            elif style_dict == "outline":
                return f"Fontsize={default_font_size},PrimaryColour=&H00FFFFFF,Alignment=2,BorderStyle=1,Outline=2" # White with black outline
            elif style_dict == "box":
                return f"Fontsize={default_font_size},PrimaryColour=&H0000FFFF,Alignment=2,BorderStyle=3" # Yellow with black box
            
            # If not a recognized preset, assume it's a raw ASS string and return it
            return style_dict

    def _parse_color_to_ass(color_str: str) -> Optional[str]:
        """Converts CSS-style color strings (hex, rgba) to FFmpeg ASS format (&HAABBGGRR)."""
        if not isinstance(color_str, str):
            return None

        color_str = color_str.lower().strip()

        # Handle hex format (#RRGGBB or #RGB)
        if color_str.startswith('#'):
            hex_color = color_str[1:]
            if len(hex_color) == 3:
                hex_color = "".join([c*2 for c in hex_color])
            if len(hex_color) == 6:
                r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
                # ASS format is &HAABBGGRR, with 00 being opaque.
                return f"&H00{b:02X}{g:02X}{r:02X}"

        # Handle rgba format (e.g., "rgba(0,0,0,0.5)")
        match = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", color_str)
        if match:
            r, g, b, a = map(float, match.groups())
            r, g, b = int(r), int(g), int(b)
            # ASS alpha is inverted (00=opaque, FF=transparent)
            ass_alpha = f"{int((1 - a) * 255):02X}"
            return f"&H{ass_alpha}{b:02X}{g:02X}{r:02X}"

        logger.warning(f"Unsupported color format: {color_str}")
        return None

    # Maps frontend snake_case keys to FFmpeg/ASS PascalCase keys
    style_map = {
        "font_size": "Fontsize",
        "font_color": "PrimaryColour",
        "background_color": "BackColour",
        "position": "Alignment",
        "outline_color": "OutlineColour",
        "outline": "Outline",
        "shadow": "Shadow",
        "border_style": "BorderStyle"
    }

    # Maps frontend position names to ASS alignment codes
    # 2=bottom-center, 5=middle-center, 8=top-center
    alignment_map = {
        'bottom': 2,
        'middle': 5,
        'top': 8,
    }

    style_params = []
    has_user_fontsize = 'font_size' in style_dict if isinstance(style_dict, dict) else False

    for key, value in style_dict.items():
        if key not in style_map or value is None:
            continue

        ass_key = style_map[key]

        if "Colour" in ass_key:
            ass_color = _parse_color_to_ass(str(value))
            if ass_color:
                style_params.append(f"{ass_key}={ass_color}")
        elif ass_key == "Alignment" and isinstance(value, str):
            if value.lower() in alignment_map:
                style_params.append(f"{ass_key}={alignment_map[value.lower()]}")
        else:
            style_params.append(f"{ass_key}={value}")

    if not has_user_fontsize and video_height:
        style_params.append(f"Fontsize={default_font_size}")

    return ",".join(style_params)

def detect_video_dimensions(video_path: str) -> Tuple[int, int]:
    """
    Detect video dimensions using FFprobe (more reliable than OpenCV for some formats)
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Tuple of (width, height)
    """
    try:
        cmd = [
            "ffprobe", 
            "-v", "error", 
            "-select_streams", "v:0", 
            "-show_entries", "stream=width,height", 
            "-of", "csv=p=0", 
            video_path
        ]
        
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            check=False
        )
        
        if result.returncode == 0:
            dimensions = result.stdout.strip().split(',')
            if len(dimensions) == 2:
                return (int(dimensions[0]), int(dimensions[1]))
        
        # Fallback to OpenCV if FFprobe fails
        logger.warning("FFprobe failed, falling back to OpenCV")
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Could not open video file: {video_path}")
            return (0, 0)
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        
        return (width, height)
    except Exception as e:
        logger.error(f"Error detecting video dimensions: {str(e)}")
        return (0, 0)


def embed_subtitle(video_path: str, subtitle_path: str, output_path: str = None,
                   font_size: int = 10, font_color: str = "white",
                   position: str = "bottom", burn_in: bool = True,
                   video_format: Optional[str] = None,
                   resolution: Optional[str] = None,
                   subtitle_style: Optional[Union[Dict[str, Any], str]] = None,
                   video_height: Optional[int] = None) -> str:
    logger.info(f"embed_subtitle received video_height: {video_height}")
    """
    Embed subtitles into a video file using FFmpeg with proper encoding support
    
    Args:
        video_path: Path to the input video file
        subtitle_path: Path to the subtitle file (SRT)
        output_path: Path for the output video file (generated if None)
        font_size: Font size for the subtitles (deprecated, use subtitle_style)
        font_color: Font color for the subtitles (deprecated, use subtitle_style)
        position: Position of the subtitles (deprecated, use subtitle_style)
        burn_in: Whether to burn subtitles into the video (hardcoded)
        video_format: Optional video format for output
        resolution: Optional resolution for output
        subtitle_style: Optional custom style for subtitles (dict or JSON string)
        video_height: Optional video height for dynamic font sizing
        
    Returns:
        Path to the output video file
    """
    if not check_ffmpeg():
        logger.error("FFmpeg is not installed or not in PATH")
        raise RuntimeError("FFmpeg is required for embedding subtitles but was not found")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not os.path.exists(subtitle_path):
        raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")

    # Generate output path
    if not output_path:
        video_dir = os.path.dirname(video_path)
        base_name, _ = os.path.splitext(os.path.basename(video_path))
        output_ext = f".{video_format.lower()}" if video_format else os.path.splitext(video_path)[1]
        output_path = os.path.join(video_dir, f"{base_name}_subtitled{output_ext}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    vf_options = []
    if resolution and resolution.endswith('p'):
        try:
            height = int(resolution[:-1])
            vf_options.append(f"scale=-2:{height}")
        except ValueError:
            logger.warning(f"Invalid resolution format: {resolution}. Ignoring.")

    # Prepare subtitle file by ensuring it's UTF-8
    temp_subtitle_path = None
    try:
        # Create a temporary file to store the UTF-8 encoded subtitle
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.srt', encoding='utf-8', errors='replace') as temp_sub_file:
            with open(subtitle_path, 'r', encoding='utf-8', errors='ignore') as f:
                temp_sub_file.write(f.read())
            temp_subtitle_path = temp_sub_file.name
        
        # Process the subtitle style
        style_str = _process_subtitle_style(subtitle_style, video_height=video_height)
        
        # FFmpeg's filter syntax for filenames can be tricky. The safest way is to pass the absolute path.
        # No manual escaping is needed here if we pass the arguments as a list.
        subtitle_filter = f"subtitles={os.path.abspath(temp_subtitle_path)}:force_style='{style_str}'"
        vf_options.append(subtitle_filter)

        # Prepare FFmpeg command with proper video compression settings
        # Using NVENC for hardware acceleration and level 5.1 for 4K support
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-vf', ",".join(vf_options),
            '-c:v', 'h264_nvenc',  # Use NVIDIA GPU encoder
            '-preset', 'p6',  # Slightly slower but better quality than p4
            '-profile:v', 'high',
            '-level', '5.1',  # Support for 4K resolution
            '-b:v', '10M',  # Target bitrate, adjust as needed
            '-maxrate', '15M',  # Maximum bitrate
            '-bufsize', '20M',  # Bitrate buffer
            '-c:a', 'aac',  # Use AAC audio codec
            '-b:a', '192k',  # Audio bitrate
            '-ar', '48000',  # Standard audio sample rate
            '-movflags', '+faststart',  # For web streaming
            output_path
        ]
        logger.info(f"Executing FFmpeg command: {' '.join(cmd)}")

        # Create environment with UTF-8 encoding
        env = os.environ.copy()
        env['LANG'] = 'en_US.UTF-8'
        env['LC_ALL'] = 'en_US.UTF-8'
        env['PYTHONIOENCODING'] = 'utf-8'
        
        # Run FFmpeg with explicit encoding
        try:
            result = subprocess.run(
                cmd, 
                check=True, 
                capture_output=True, 
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            logger.info(f"Successfully compressed and embedded subtitles into: {output_path}")
            logger.debug(f"FFmpeg output: {result.stdout}")
            
            # Verify output file was created and has content
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise RuntimeError("Output file was not created or is empty")
                
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg command failed with return code {e.returncode}")
            logger.error(f"FFmpeg stderr: {e.stderr}")
            logger.error(f"FFmpeg stdout: {e.stdout}")
            raise RuntimeError(f"Failed to process video: {e.stderr}")
        except Exception as e:
            logger.error(f"Error during video processing: {str(e)}")
            raise

    except Exception as e:
        logger.error(f"Failed during subtitle embedding: {e}")
        if isinstance(e, subprocess.CalledProcessError):
            logger.error(f"FFmpeg stderr: {e.stderr}")
        # Fallback: copy original video if subtitle processing fails
        logger.info(f"Fallback: copying original video to {output_path}")
        shutil.copy2(video_path, output_path)
    finally:
        if temp_subtitle_path and os.path.exists(temp_subtitle_path):
            os.unlink(temp_subtitle_path)

    return output_path


def embed_dual_subtitles(video_path: str, src_subtitle_path: str, trans_subtitle_path: str, 
                        output_path: str = None,
                        video_format: Optional[str] = None,
                        resolution: Optional[str] = None,
                        subtitle_style: Optional[Dict[str, Any]] = None,
                        video_height: Optional[int] = None) -> str:
    """
    Embed both source and translation subtitles into video with different positions
    """
    check_ffmpeg()

    if not all(os.path.exists(p) for p in [video_path, src_subtitle_path, trans_subtitle_path]):
        logger.error("One or more input files not found for dual subtitle embedding")
        return video_path

    if not output_path:
        video_dir, video_filename = os.path.split(video_path)
        video_name, _ = os.path.splitext(video_filename)
        output_path = os.path.join(video_dir, f"{video_name}_dual_sub.mp4")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    base_style_str = _process_subtitle_style(subtitle_style, video_height=video_height)
    style_parts = [p for p in base_style_str.split(',') if p and not p.lower().strip().startswith('alignment=')]
    clean_base_style = ','.join(style_parts)

    # Alignment=8 is top-center, Alignment=2 is bottom-center
    trans_style_str = f"Alignment=8,{clean_base_style}".strip(',')
    src_style_str = f"Alignment=2,{clean_base_style}".strip(',')

    temp_src_sub_path = None
    temp_trans_sub_path = None
    try:
        with (
            tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_src.srt', encoding='utf-8') as temp_src,
            open(src_subtitle_path, 'r', encoding='utf-8', errors='replace') as f_src,
            tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_trans.srt', encoding='utf-8') as temp_trans,
            open(trans_subtitle_path, 'r', encoding='utf-8', errors='replace') as f_trans_in
        ):
            shutil.copyfileobj(f_src, temp_src)
            temp_src.flush()
            temp_src_sub_path = temp_src.name

            shutil.copyfileobj(f_trans_in, temp_trans)
            temp_trans.flush()
            temp_trans_sub_path = temp_trans.name

            # All ffmpeg logic must be inside the with block to access temp files
            abs_src_path = os.path.abspath(temp_src_sub_path).replace('\\', '/').replace("'", "'\'").replace(':', '\\:')
            abs_trans_path = os.path.abspath(temp_trans_sub_path).replace('\\', '/').replace("'", "'\'").replace(':', '\\:')

            video_filters = [
                f"subtitles='{abs_trans_path}':force_style='{trans_style_str}'",
                f"subtitles='{abs_src_path}':force_style='{src_style_str}'"
            ]

            if resolution:
                video_filters.append(f"scale={resolution}")

            # Prepare FFmpeg command with proper video compression settings
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', ",".join(video_filters),
                '-c:v', 'libx264',  # Use H.264 codec for video
                '-preset', 'medium',  # Good balance between speed and compression
                '-crf', '23',  # Quality level (18-28 is good, lower is better quality)
                '-c:a', 'aac',  # Use AAC audio codec
                '-b:a', '192k',  # Audio bitrate
                '-movflags', '+faststart'  # For web streaming
            ]
            
            if video_format:
                cmd.extend(['-f', video_format])
            cmd.append(output_path)

            logger.info(f"Running FFmpeg command for dual subtitles: {' '.join(cmd)}")
            
            # Create environment with UTF-8 encoding
            env = os.environ.copy()
            env['LANG'] = 'en_US.UTF-8'
            env['LC_ALL'] = 'en_US.UTF-8'
            env['PYTHONIOENCODING'] = 'utf-8'
            
            try:
                result = subprocess.run(
                    cmd, 
                    check=True, 
                    capture_output=True, 
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    env=env
                )
                
                # Verify output file was created and has content
                if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                    raise RuntimeError("Output file was not created or is empty")
                    
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg command failed with return code {e.returncode}")
                logger.error(f"FFmpeg stderr: {e.stderr}")
                logger.error(f"FFmpeg stdout: {e.stdout}")
                raise RuntimeError(f"Failed to process video: {e.stderr}")
            except Exception as e:
                logger.error(f"Error during dual subtitle video processing: {str(e)}")
                raise
                
            if result.returncode != 0:
                logger.error(f"FFmpeg failed with exit code {result.returncode}\nstderr: {result.stderr}")
                return video_path  # Failure, return original path

    except Exception as e:
        logger.error(f"An unexpected error occurred during dual subtitle embedding: {e}")
        return video_path
    finally:
        # Clean up temporary files
        if temp_src_sub_path and os.path.exists(temp_src_sub_path):
            os.unlink(temp_src_sub_path)
        if temp_trans_sub_path and os.path.exists(temp_trans_sub_path):
            os.unlink(temp_trans_sub_path)

    # This part is reached only on success
    logger.info(f"Successfully embedded dual subtitles into {output_path}")
    return output_path


def embed_subtitles(video_path: str, subtitles: Dict[str, str], output_path: str = None) -> str:
    """
    Embed subtitles into a video file with robust error handling
    
    Args:
        video_path: Path to the input video file
        subtitles: Dictionary of subtitle files (keys: 'src', 'trans', etc.)
        output_path: Path for output video (generated if None)
        
    Returns:
        Path to the output video, or original video if process fails
    """
    try:
        if not check_ffmpeg():
            logger.error("FFmpeg is not available")
            return video_path
            
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return video_path
            
        # Validate subtitles
        valid_subtitles = {}
        for key, sub_path in subtitles.items():
            if not os.path.exists(sub_path):
                logger.warning(f"Subtitle file not found: {sub_path}")
                continue
            if os.path.getsize(sub_path) == 0:
                logger.warning(f"Subtitle file is empty: {sub_path}")
                continue
            valid_subtitles[key] = sub_path
            
        if not valid_subtitles:
            logger.error("No valid subtitle files provided")
            return video_path
            
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_video = os.path.join(temp_dir, os.path.basename(video_path))
            shutil.copy2(video_path, temp_video)
            
            # Generate output path if not provided
            if not output_path:
                base, ext = os.path.splitext(video_path)
                output_path = f"{base}_subtitled{ext}"
                
            # Detect if video is vertical
            width, height = detect_video_dimensions(video_path)
            is_vertical = height > width if width > 0 and height > 0 else False
            
            # Embed subtitles
            if embed_with_ffmpeg(temp_dir, os.path.basename(temp_video), valid_subtitles, 
                              output_path, is_vertical=is_vertical):
                logger.info(f"Successfully embedded subtitles to: {output_path}")
                return output_path
                
    except Exception as e:
        logger.error(f"Error embedding subtitles: {str(e)}", exc_info=True)
        
    return video_path


def embed_subtitles_from_job(job_dir: str, video_path: str, output_path: str = None, 
                              dual: bool = True, language: str = None,
                              video_format: Optional[str] = None,
                              resolution: Optional[str] = None,
                              subtitle_style: Optional[Dict[str, Any]] = None) -> str:
    """
    Embed subtitles from a job directory into a video with robust error handling
    
    Args:
        job_dir: Path to the job directory containing subtitles
        video_path: Path to the video file
        output_path: Path for the output video file (generated if None)
        dual: Whether to embed both source and translation subtitles
        language: Language code for translation subtitles (if specified)
        
    Returns:
        Path to the output video with embedded subtitles, or original video on failure
    """
    
    # Verify the video file exists
    if not os.path.exists(video_path):
        logger.warning(f"Video file not found at specified path: {video_path}")
        
        # Try to find the video in the job directory
        job_video_path = os.path.join(job_dir, os.path.basename(video_path))
        if os.path.exists(job_video_path):
            logger.info(f"Found video file in job directory: {job_video_path}")
            video_path = job_video_path
        else:
            # Look for any video file in the job directory
            video_files = [f for f in os.listdir(job_dir) 
                          if os.path.isfile(os.path.join(job_dir, f)) and
                          f.endswith(('.mp4', '.avi', '.mov', '.mkv'))]
            
            if video_files:
                job_video_path = os.path.join(job_dir, video_files[0])
                logger.info(f"Using alternative video file found in job directory: {job_video_path}")
                video_path = job_video_path
            else:
                logger.error(f"No video files found in job directory: {job_dir}")
                # Create a dummy log file and raise a more informative error
                error_log = os.path.join(job_dir, "video_not_found.log")
                with open(error_log, 'w') as f:
                    f.write(f"Error: Video file not found at {video_path}\n")
                    f.write(f"Job directory contents: {os.listdir(job_dir)}\n")
                raise FileNotFoundError(f"Video file not found in job directory: {job_dir}")
    
    logger.info(f"Using video file: {video_path} (exists: {os.path.exists(video_path)})")

    # Look for subtitle files in the job directory
    srt_dir = os.path.join(job_dir, "subtitles")
    if not os.path.exists(srt_dir):
        # Create subtitles directory if it doesn't exist
        os.makedirs(srt_dir, exist_ok=True)
        logger.info(f"Created subtitle directory: {srt_dir}")
        
        # Look for subtitle files in fallback directories
        fallback_dirs = ["srt", "output", ""]
        found_subtitles = False
        
        for fallback in fallback_dirs:
            test_dir = os.path.join(job_dir, fallback)
            if os.path.exists(test_dir) and any(f.endswith(".srt") for f in os.listdir(test_dir)):
                # Copy SRT files to the standard subtitles directory
                for srt_file in [f for f in os.listdir(test_dir) if f.endswith(".srt")]:
                    src_path = os.path.join(test_dir, srt_file)
                    dest_path = os.path.join(srt_dir, srt_file)
                    import shutil
                    shutil.copy2(src_path, dest_path)
                    logger.info(f"Copied subtitle file from {src_path} to {dest_path}")
                found_subtitles = True
                break
                
        if not found_subtitles:
            logger.warning(f"No subtitle files found in any directory for job: {job_dir}")
            # We'll continue and may create subtitles from other sources
    
    # Find source subtitles
    src_srt = os.path.join(srt_dir, "src.srt")
    
    # Find translation subtitles (either by language or default)
    if language:
        trans_srt = os.path.join(srt_dir, f"{language}.srt")
    else:
        # Try both "trans.srt" and any language code SRT files
        trans_srt = os.path.join(srt_dir, "trans.srt")
        
        # If trans.srt doesn't exist, look for any language-specific SRT files
        if not os.path.exists(trans_srt):
            lang_srt_files = [f for f in os.listdir(srt_dir) if len(os.path.splitext(f)[0]) == 2 and f.endswith(".srt")]
            if lang_srt_files:
                trans_srt = os.path.join(srt_dir, lang_srt_files[0])  # Use the first language file
                logger.info(f"Using language subtitle file: {trans_srt}")
    
    # Combined source+translation subtitle file
    src_trans_srt = os.path.join(srt_dir, "src_trans.srt")
    
    # Generate output path if not provided
    if not output_path:
        # Use a standardized output path in the job directory
        output_path = os.path.join(job_dir, "output_sub.mp4")
        logger.info(f"Using standard output path for subtitled video: {output_path}")
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # Check if subtitle files exist
    src_exists = os.path.exists(src_srt)
    trans_exists = os.path.exists(trans_srt)
    src_trans_exists = os.path.exists(src_trans_srt)
    
    # Log found subtitle files
    logger.info(f"Subtitle files status: Source={src_exists}, Translation={trans_exists}, Combined={src_trans_exists}")
    
    # Try to use any available subtitle files
    # Detect video dimensions for dynamic font sizing
    try:
        width, height = detect_video_dimensions(video_path)
        logger.info(f"Detected video dimensions: {width}x{height}")
    except Exception as e:
        logger.error(f"Could not detect video dimensions for {video_path}, using fallback. Error: {e}")
        height = None # Fallback to default font size

    # Determine target height for dynamic font size
    target_height = height
    if resolution:
        try:
            if 'x' in resolution:
                target_height = int(resolution.split('x')[1])
            elif resolution.lower().endswith('p'):
                target_height = int(resolution[:-1])
        except (ValueError, IndexError):
            logger.warning(f"Could not parse height from resolution: '{resolution}'. Using original height.")

    if dual and src_exists and trans_exists:
        # Use dual subtitles if both source and translation exist
        logger.info("Using dual subtitles (source + translation)")
        return embed_dual_subtitles(
            video_path=video_path,
            src_subtitle_path=src_srt,
            trans_subtitle_path=trans_srt,
            output_path=output_path,
            video_format=video_format,
            resolution=resolution,
            subtitle_style=subtitle_style,
            video_height=target_height
        )
    elif src_trans_exists:
        # Use combined source+translation if available
        logger.info("Using combined source+translation subtitles")
        return embed_subtitle(
            video_path=video_path,
            subtitle_path=src_trans_srt,
            output_path=output_path,
            video_format=video_format,
            resolution=resolution,
            subtitle_style=subtitle_style,
            video_height=height
        )
    elif src_exists:
        # Fallback to source only
        logger.info("Using source-only subtitles")
        return embed_subtitle(
            video_path=video_path,
            subtitle_path=src_srt,
            output_path=output_path,
            video_format=video_format,
            resolution=resolution,
            subtitle_style=subtitle_style,
            video_height=height
        )
    else:
        # No subtitles found, copy the video as-is
        logger.warning(f"No subtitle files found, creating a copy of the video as the output")
        import shutil
        shutil.copy2(video_path, output_path)
        logger.info(f"Copied original video to output path: {output_path}")
        return output_path
