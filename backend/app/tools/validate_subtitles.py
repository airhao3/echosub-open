#!/usr/bin/env python3

import os
import sys
import json
import logging
import argparse
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("subtitle-validator")


def check_ffmpeg() -> bool:
    """Check if FFmpeg is available"""
    try:
        subprocess.run(["ffmpeg", "-version"], 
                     stdout=subprocess.PIPE, 
                     stderr=subprocess.PIPE, 
                     check=False)
        return True
    except FileNotFoundError:
        return False


def validate_video_file(file_path: str) -> dict:
    """Validate a video file using FFprobe"""
    result = {
        "exists": os.path.exists(file_path),
        "size_mb": 0,
        "duration": 0,
        "width": 0,
        "height": 0,
        "valid": False,
        "message": ""
    }
    
    if not result["exists"]:
        result["message"] = f"File does not exist: {file_path}"
        return result
    
    # Get file size
    try:
        result["size_mb"] = os.path.getsize(file_path) / (1024 * 1024)
    except Exception as e:
        result["message"] = f"Error getting file size: {str(e)}"
        return result
    
    # Validate video using FFprobe
    try:
        cmd = [
            "ffprobe", 
            "-v", "error", 
            "-select_streams", "v:0", 
            "-show_entries", "stream=width,height,duration", 
            "-of", "json", 
            file_path
        ]
        
        proc = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            check=False
        )
        
        if proc.returncode != 0:
            result["message"] = f"FFprobe failed: {proc.stderr}"
            return result
        
        data = json.loads(proc.stdout)
        if "streams" in data and len(data["streams"]) > 0:
            stream = data["streams"][0]
            result["width"] = stream.get("width", 0)
            result["height"] = stream.get("height", 0)
            result["duration"] = float(stream.get("duration", 0))
            result["valid"] = True
        else:
            result["message"] = "No valid video streams found"
            
    except Exception as e:
        result["message"] = f"Error validating video: {str(e)}"
    
    return result


def validate_subtitle_file(file_path: str) -> dict:
    """Validate an SRT subtitle file"""
    result = {
        "exists": os.path.exists(file_path),
        "size_kb": 0,
        "entry_count": 0,
        "valid": False,
        "message": ""
    }
    
    if not result["exists"]:
        result["message"] = f"File does not exist: {file_path}"
        return result
    
    # Get file size
    try:
        result["size_kb"] = os.path.getsize(file_path) / 1024
    except Exception as e:
        result["message"] = f"Error getting file size: {str(e)}"
        return result
    
    # Count subtitle entries
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Simple validation - SRT files have numeric entries
        lines = content.split('\n')
        entry_count = 0
        
        for line in lines:
            if line.strip().isdigit():
                entry_count += 1
        
        result["entry_count"] = entry_count
        result["valid"] = entry_count > 0
        
        if entry_count == 0:
            result["message"] = "No subtitle entries found"
    
    except Exception as e:
        result["message"] = f"Error reading subtitle file: {str(e)}"
    
    return result


def scan_job_directory(job_dir: str) -> dict:
    """Scan a job directory for video and subtitle files"""
    result = {
        "job_dir": job_dir,
        "exists": os.path.exists(job_dir),
        "video_files": [],
        "subtitle_files": [],
        "issues": []
    }
    
    if not result["exists"]:
        result["issues"].append(f"Job directory does not exist: {job_dir}")
        return result
    
    # Look for video files
    video_extensions = (".mp4", ".avi", ".mov", ".mkv")
    
    # Look for subtitle directories
    subtitle_dirs = ["subtitles", "srt", "output", ""]
    
    # Walk through directory
    for root, dirs, files in os.walk(job_dir):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, job_dir)
            
            # Check for video files
            if any(file.endswith(ext) for ext in video_extensions):
                video_info = validate_video_file(file_path)
                video_info["path"] = file_path
                video_info["rel_path"] = rel_path
                result["video_files"].append(video_info)
            
            # Check for subtitle files
            if file.endswith(".srt"):
                subtitle_info = validate_subtitle_file(file_path)
                subtitle_info["path"] = file_path
                subtitle_info["rel_path"] = rel_path
                subtitle_info["name"] = os.path.basename(file_path)
                result["subtitle_files"].append(subtitle_info)
    
    # Add issues
    if not result["video_files"]:
        result["issues"].append("No video files found in job directory")
    
    if not result["subtitle_files"]:
        result["issues"].append("No subtitle files found in job directory")
    
    # Check for standard subtitle files
    std_subtitles = {"src.srt", "trans.srt"}
    found_std = {s["name"] for s in result["subtitle_files"] if s["name"] in std_subtitles}
    missing_std = std_subtitles - found_std
    
    if missing_std:
        result["issues"].append(f"Missing standard subtitle files: {', '.join(missing_std)}")
    
    return result


def test_embedding(job_dir: str, video_path: str = None, output_path: str = None, language: str = None) -> dict:
    """Test the subtitle embedding process"""
    result = {
        "success": False,
        "message": "",
        "output_path": "",
        "output_valid": False,
        "command_output": ""
    }
    
    # Import our reliable embedding function
    try:
        logger.info("Importing reliable subtitle embedding implementation")
        from app.services.subtitle_deprecated.temp_fix.embed_subtitles import embed_subtitles_from_job
    except ImportError as e:
        result["message"] = f"Failed to import subtitle embedding module: {str(e)}"
        return result
    
    # Auto-detect video if not specified
    if not video_path:
        scan_result = scan_job_directory(job_dir)
        valid_videos = [v for v in scan_result["video_files"] if v["valid"]]
        
        if valid_videos:
            video_path = valid_videos[0]["path"]
            logger.info(f"Auto-detected video: {video_path}")
        else:
            result["message"] = "No valid video files found in job directory"
            return result
    
    # Generate output path if not provided
    if not output_path:
        video_dir = os.path.dirname(video_path)
        video_filename = os.path.basename(video_path)
        base_name, extension = os.path.splitext(video_filename)
        output_path = os.path.join(job_dir, f"{base_name}_subtitled{extension}")
        logger.info(f"Auto-generated output path: {output_path}")
    
    # Test embedding process
    try:
        logger.info(f"Starting subtitle embedding with:\n"
                  f"  Job dir: {job_dir}\n"
                  f"  Video: {video_path}\n"
                  f"  Output: {output_path}\n"
                  f"  Language: {language}")
        
        # Call the embedding function
        embed_result = embed_subtitles_from_job(
            job_dir=job_dir,
            video_path=video_path,
            output_path=output_path,
            language=language
        )
        
        # Verify result
        if embed_result and os.path.exists(embed_result):
            result["success"] = True
            result["output_path"] = embed_result
            
            # Validate output video
            output_validation = validate_video_file(embed_result)
            result["output_valid"] = output_validation["valid"]
            
            if output_validation["valid"]:
                size_mb = output_validation["size_mb"]
                duration = output_validation["duration"]
                dimensions = f"{output_validation['width']}x{output_validation['height']}"
                result["message"] = f"Successfully generated video with subtitles: {embed_result} ({size_mb:.2f} MB, {duration:.1f}s, {dimensions})"
            else:
                result["message"] = f"Output file exists but may be invalid: {output_validation['message']}"
        else:
            result["message"] = "Embedding function did not return a valid output path"
            
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        result["message"] = f"Error during subtitle embedding: {str(e)}"
        result["command_output"] = error_trace
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Validate subtitle files and test embedding")
    parser.add_argument("--job-dir", type=str, help="Path to job directory", required=True)
    parser.add_argument("--video-path", type=str, help="Path to specific video file (optional)")
    parser.add_argument("--output-path", type=str, help="Path for output video (optional)")
    parser.add_argument("--language", type=str, help="Language code for subtitle (optional)")
    parser.add_argument("--scan-only", action="store_true", help="Only scan directory, don't test embedding")
    args = parser.parse_args()
    
    # Check for FFmpeg
    if not check_ffmpeg():
        logger.error("FFmpeg is not installed or not found in PATH")
        return 1
    
    # Scan job directory
    logger.info(f"Scanning job directory: {args.job_dir}")
    scan_result = scan_job_directory(args.job_dir)
    
    # Print scan results
    logger.info(f"Found {len(scan_result['video_files'])} video files")
    for video in scan_result["video_files"]:
        status = "✅" if video["valid"] else "❌"
        logger.info(f"  {status} {video['rel_path']} ({video['size_mb']:.2f} MB, {video['width']}x{video['height']})")
    
    logger.info(f"Found {len(scan_result['subtitle_files'])} subtitle files")
    for subtitle in scan_result["subtitle_files"]:
        status = "✅" if subtitle["valid"] else "❌"
        logger.info(f"  {status} {subtitle['rel_path']} ({subtitle['size_kb']:.1f} KB, {subtitle['entry_count']} entries)")
    
    if scan_result["issues"]:
        logger.warning("Issues found:")
        for issue in scan_result["issues"]:
            logger.warning(f"  ⚠️ {issue}")
    
    # Exit if scan-only
    if args.scan_only:
        return 0
    
    # Test embedding if requested
    if scan_result["video_files"] and scan_result["subtitle_files"]:
        logger.info("Testing subtitle embedding process...")
        
        # Choose video path if not specified
        video_path = args.video_path
        if not video_path:
            valid_videos = [v for v in scan_result["video_files"] if v["valid"]]
            if valid_videos:
                video_path = valid_videos[0]["path"]
                logger.info(f"Selected video: {video_path}")
            else:
                logger.error("No valid video files found for embedding test")
                return 1
        
        # Run the test
        test_result = test_embedding(
            job_dir=args.job_dir,
            video_path=video_path,
            output_path=args.output_path,
            language=args.language
        )
        
        # Print test results
        if test_result["success"]:
            logger.info(f"✅ {test_result['message']}")
            return 0
        else:
            logger.error(f"❌ {test_result['message']}")
            if test_result["command_output"]:
                logger.error(f"Detailed error:\n{test_result['command_output']}")
            return 1
    else:
        logger.error("Cannot test embedding: missing video or subtitle files")
        return 1


if __name__ == "__main__":
    sys.exit(main())
