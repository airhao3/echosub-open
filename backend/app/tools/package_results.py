#!/usr/bin/env python3
"""
Optimized package processing results by video hash.

This module provides functionality to organize all files related to a specific video
with improved performance through caching and optimized file operations.
"""

import os
import sys
import shutil
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

# Import optimized utilities
from app.utils.file_path_manager import get_file_path_manager, FileType
from app.utils.file_cache import (
    get_cached_path, batch_resolve_paths, log_warning_once,
    FileBatchProcessor, get_file_metadata, batch_copy_files
)

# Setup logging
logger = logging.getLogger("packaging")

_hash_cache: Dict[str, str] = {}

def calculate_file_hash(file_path: str, chunk_size: int = 65536) -> str:
    """
    Calculate a hash value for a file with caching.
    
    Args:
        file_path: The path to the file
        chunk_size: Size of chunks to read (default: 64KB)
        
    Returns:
        A hash string that uniquely identifies the file
    """
    abs_path = get_cached_path(file_path)
    
    # Return cached hash if available
    if abs_path in _hash_cache:
        return _hash_cache[abs_path]
    
    # Get file metadata first
    metadata = get_file_metadata(abs_path)
    if not metadata.get('exists'):
        log_warning_once(f"File not found for hashing: {file_path}")
        return ""
    
    # Use MD5 for speed, can be changed to SHA256 for more security
    hash_md5 = hashlib.md5()
    
    try:
        with open(abs_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hash_md5.update(chunk)
        
        # Cache the result
        _hash_cache[abs_path] = hash_md5.hexdigest()
        return _hash_cache[abs_path]
    except Exception as e:
        log_warning_once(f"Error hashing file {file_path}: {str(e)}")
        return ""

def create_package_dir(final_output_base_dir: str, video_path: str) -> str:
    """
    Create or clean a package directory for a specific video.
    
    Args:
        final_output_base_dir: Base directory for all final packaged outputs
        video_path: Path to the original video file
        
    Returns:
        Path to the created video-specific package directory
    """
    # Get video filename without extension safely
    video_name = Path(video_path).stem
    package_dir = Path(final_output_base_dir) / video_name
    
    # Remove existing directory if it exists
    if package_dir.exists():
        if logger.isEnabledFor(logging.INFO):
            logger.info(f"[Package] Removing existing package directory: {package_dir}")
        shutil.rmtree(package_dir, ignore_errors=True)
    
    # Create the package directory
    package_dir.mkdir(parents=True, exist_ok=True)
    
    if logger.isEnabledFor(logging.INFO):
        logger.info(f"[Package] Created package directory: {package_dir}")
    
    return str(package_dir)

def copy_video_file(video_path: str, package_dir: str) -> str:
    """
    Copy the video file to the package directory
    
    Args:
        video_path: Path to the video file
        package_dir: Path to the package directory
        
    Returns:
        Path to the copied video file
    """
    video_filename = os.path.basename(video_path)
    dest_path = os.path.join(package_dir, video_filename)
    
    logger.info(f"Copying video file: {video_path} -> {dest_path}")
    shutil.copy2(video_path, dest_path)
    
    return dest_path

def find_related_files(job_dir: str, video_hash: str) -> Dict[str, List[str]]:
    """
    DEPRECATED - This function is no longer needed with the new packaging approach that uses explicit file lists.
    This function is kept for backwards compatibility only.
    
    With the new approach, files are provided directly via the direct_files parameter to package_job_results,
    and no automatic file collection is performed.
    
    Args:
        job_dir: Job directory
        video_hash: Hash of the video file
        
    Returns:
        Empty dictionary of file categories (no files are collected)
    """
    logger.warning("find_related_files is deprecated - automatic file collection is disabled")
    
    # Return empty collections for all file categories
    # This ensures no automatic file collection occurs
    empty_files = {
        "subtitles": [],
        "audio": [],
        "translations": [],
        "output": [],
        "logs": [],
        "metadata": [],
        "subtitled": []
    }
    
    # Log empty result and return
    logger.info(f"No files collected for video hash '{video_hash}' - automatic collection disabled")
    return empty_files

def copy_related_files(
    related_files: Dict[str, List[str]],
    video_package_dir: str,
    processor: Optional[FileBatchProcessor] = None
) -> Dict[str, List[str]]:
    """
    Copy files to the package directory with optimized operations.
    
    Args:
        related_files: Dictionary mapping categories to file paths
        video_package_dir: Path to the package directory
        processor: Optional FileBatchProcessor instance
        
    Returns:
        Dictionary of successfully copied files by category
    """
    if processor is None:
        processor = FileBatchProcessor()
    
    # Prepare files for batch copying
    files_to_copy = {}
    for category, paths in related_files.items():
        if not paths:
            continue
            
        # Filter out non-existent files
        valid_paths = [p for p in paths if p and get_file_metadata(p).get('exists')]
        if valid_paths:
            files_to_copy[category] = valid_paths
    
    # Use batch copy for better performance
    return batch_copy_files(files_to_copy, video_package_dir)

def create_package_metadata(package_dir: str, video_path: str, copied_files: Dict[str, List[str]]) -> str:
    """
    Create metadata file for the package
    
    Args:
        package_dir: Path to the package directory
        video_path: Path to the video file
        copied_files: Dictionary of copied files
        
    Returns:
        Path to the created metadata file
    """
    video_hash = calculate_file_hash(video_path)
    video_filename = os.path.basename(video_path)
    video_name = os.path.splitext(video_filename)[0]
    
    metadata = {
        "package_created": datetime.now().isoformat(),
        "video_name": video_name,
        "video_hash": video_hash,
        "video_path": video_path,
        "file_counts": {
            category: len(files) for category, files in copied_files.items()
        },
        "total_files": sum(len(files) for files in copied_files.values()),
    }
    
    metadata_path = os.path.join(package_dir, "package_info.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Created package metadata at: {metadata_path}")
    
    # Also create a human-readable summary
    summary_path = os.path.join(package_dir, "README.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"VideoLingo Processing Results\n")
        f.write(f"=========================\n\n")
        f.write(f"Video: {video_name}\n")
        f.write(f"Hash: {video_hash}\n")
        f.write(f"Package created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write(f"Contents:\n")
        for category, files in copied_files.items():
            if files:
                f.write(f"- {category.capitalize()}: {len(files)} files\n")
                for file_path in files[:5]:  # List first 5 files
                    f.write(f"  - {os.path.basename(file_path)}\n")
                if len(files) > 5:
                    f.write(f"  - ... and {len(files) - 5} more\n")
        
        f.write("\nFor support, contact support@videolingo.ai\n")
    
    logger.info(f"Created package summary at: {summary_path}")
    
    return metadata_path

def package_job_results(job_dir: str, video_path: str, final_output_base_dir: str, direct_files: Dict[str, List[str]], job_id: int = None) -> str:
    """
    This function ensures that all important output files, especially subtitled videos,
    are properly included in the job results without creating unnecessary duplicate directories.
    Uses FilePathManager to find files when possible, falls back to traditional methods when necessary.
    
    Args:
        job_dir (str): Directory containing job temporary files and results
        video_path (str): Path to the original video file
        final_output_base_dir (str): Base directory for packages (not used for directory creation)
        direct_files (Dict[str, List[str]]): Dictionary of files to package
        job_id (int, optional): The ID of the job, to find videos in database

    Returns:
        str: The job directory path where all output files can be found
    """
    import glob
    import os
    import sys
    import importlib
    
    logger.info(f"[Package] Ensuring all output files are accessible from job directory: {job_dir}")
    logger.info(f"[Package] Original video path: {video_path}")
    
    all_subtitled_videos = []
    
    # Initialize FilePathManager if job_id is provided
    file_manager = None
    registry_loaded = False
    if job_id is not None:
        try:
            # Get base directory - which should be two levels up from job_dir
            base_dir = os.path.dirname(os.path.dirname(job_dir))
            file_manager = get_file_path_manager(base_dir)
            
            # Try to load the file registry for this job
            registry_path = file_manager.get_registry_path(job_id)
            if os.path.exists(registry_path):
                file_manager.load_registry(job_id)
                registry_loaded = True
                logger.info(f"[Package] Loaded file registry from {registry_path}")
        except Exception as e:
            logger.warning(f"[Package] Could not initialize FilePathManager: {str(e)}")
    
    # Method 0 (Preferred): Use FilePathManager to find subtitled videos
    if registry_loaded and file_manager:
        try:
            logger.info(f"[Package] Looking up subtitled videos using FilePathManager for job {job_id}")
            # Get all languages that have subtitled videos
            languages = file_manager.get_available_languages(job_id, FileType.SUBTITLED_VIDEO)
            
            for lang in languages:
                video_path = file_manager.get_file_path(job_id, FileType.SUBTITLED_VIDEO, lang)
                if video_path and os.path.exists(video_path):
                    all_subtitled_videos.append(video_path)
                    logger.info(f"[Package] Found subtitled video from FilePathManager: {video_path} (lang: {lang})")
                else:
                    logger.warning(f"[Package] FilePathManager subtitled video not found for language: {lang}")
        except Exception as e:
            logger.warning(f"[Package] Error using FilePathManager for subtitled videos: {str(e)}")
            
        # Also add other file types to direct_files using FilePathManager
        try:
            # Add subtitle files
            for lang in file_manager.get_available_languages(job_id, FileType.SUBTITLE_FILE):
                subtitle_path = file_manager.get_file_path(job_id, FileType.SUBTITLE_FILE, lang)
                if subtitle_path and os.path.exists(subtitle_path):
                    if 'subtitles' not in direct_files:
                        direct_files['subtitles'] = []
                    if subtitle_path not in direct_files['subtitles']:
                        direct_files['subtitles'].append(subtitle_path)
                        logger.info(f"[Package] Added subtitle file from FilePathManager: {subtitle_path}")
                        
            # Add transcript files
            for lang in file_manager.get_available_languages(job_id, FileType.TRANSCRIPT):
                transcript_path = file_manager.get_file_path(job_id, FileType.TRANSCRIPT, lang)
                if transcript_path and os.path.exists(transcript_path):
                    if 'transcripts' not in direct_files:
                        direct_files['transcripts'] = []
                    if transcript_path not in direct_files['transcripts']:
                        direct_files['transcripts'].append(transcript_path)
                        logger.info(f"[Package] Added transcript file from FilePathManager: {transcript_path}")
            
            # Add translation files
            for lang in file_manager.get_available_languages(job_id, FileType.TRANSLATION):
                translation_path = file_manager.get_file_path(job_id, FileType.TRANSLATION, lang)
                if translation_path and os.path.exists(translation_path):
                    if 'translations' not in direct_files:
                        direct_files['translations'] = []
                    if translation_path not in direct_files['translations']:
                        direct_files['translations'].append(translation_path)
                        logger.info(f"[Package] Added translation file from FilePathManager: {translation_path}")
        except Exception as e:
            logger.warning(f"[Package] Error adding files from FilePathManager: {str(e)}")
    else:
        logger.info("[Package] No file registry found, falling back to traditional methods")

    
    # Direct method 1: Use the database to find subtitled videos if job_id is provided
    if job_id is not None:
        try:
            # Dynamically import needed modules to avoid circular imports
            from sqlalchemy.orm import Session
            from app.core.database import SessionLocal
            from app.models.job_result import JobResult, ResultType
            
            # Get subtitled videos directly from the database
            logger.info(f"[Package] Looking up subtitled videos in database for job {job_id}")
            db = SessionLocal()
            try:
                # Query for both SUBTITLED_VIDEO type and OTHER type with metadata indicating subtitled videos
                subtitled_results = db.query(JobResult).filter(
                    JobResult.job_id == job_id,
                    JobResult.result_type == ResultType.SUBTITLED_VIDEO
                ).all()
                
                # Add file paths to the list
                for result in subtitled_results:
                    if result.file_url and os.path.exists(result.file_url):
                        all_subtitled_videos.append(result.file_url)
                        logger.info(f"[Package] Found subtitled video from database: {result.file_url}")
                    else:
                        logger.warning(f"[Package] Database subtitled video not found at: {result.file_url}")
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"[Package] Error accessing database for subtitled videos: {str(e)}")
    
    # We no longer use fallback search - rely only on FilePathManager and database
    logger.info("[Package] Using only FilePathManager and database for file access - no fallback search")
    
    # Add found subtitled videos to direct_files for downstream processing
    if all_subtitled_videos:
        if 'videos' not in direct_files:
            direct_files['videos'] = []
        for video in all_subtitled_videos:
            if video not in direct_files['videos']:
                direct_files['videos'].append(video)
                logger.info(f"[Package] Added subtitled video to output: {video}")
    else:
        video_base_name = os.path.splitext(os.path.basename(video_path))[0]
        logger.warning(f"[Package] No subtitled videos found for {video_base_name}")
    
    # Log all files that will be available in the output
    logger.info(f"[Package] Total files to be available: {sum(len(files) for files in direct_files.values())}")
    for category, files in direct_files.items():
        logger.info(f"[Package] Category {category}: {len(files)} files")
        for file in files:
            logger.debug(f"[Package] Will include: {file}")
    
    return job_dir

def main():
    parser = argparse.ArgumentParser(description="Package processing results by video hash")
    parser.add_argument("job_dir", help="Job directory containing results")
    parser.add_argument("video_path", help="Path to the video file")
    parser.add_argument("--output-dir", help="Output directory for the package")
    
    args = parser.parse_args()
    output_dir = args.output_dir or os.path.join(os.path.dirname(args.job_dir), "packages")
    
    try:
        # Create an empty direct_files dictionary for backwards compatibility
        direct_files = {
            "subtitles": [],
            "transcripts": [],
            "translations": [],
            "videos": [],
            "logs": [],
            "other": []
        }
        
        # Call package_job_results with the direct_files parameter
        package_dir = package_job_results(args.job_dir, args.video_path, output_dir, direct_files)
        print(f"Package created successfully at: {package_dir}")
    except Exception as e:
        logger.error(f"Error packaging job results: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
