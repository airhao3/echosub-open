import os
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

def cleanup_temporary_files(temp_dirs=None, max_age_days=7, dry_run=False):
    """
    Cleans up temporary directories and files older than the specified age
    
    Args:
        temp_dirs: List of directories to clean up. If None, uses system-defined temp dirs
        max_age_days: Maximum age of files in days before deletion
        dry_run: If True, just logs what would be deleted without actual deletion
        
    Returns:
        Tuple of (deleted_count, freed_space_bytes)
    """
    if temp_dirs is None:
        # Get project root directory
        project_dir = Path(__file__).parents[2].absolute()
        
        # Default temporary directories to clean
        temp_dirs = [
            os.path.join(project_dir, "app", "temp"),
            os.path.join(project_dir, "temp"),
            os.path.join(project_dir, "tmp"),
        ]
    
    threshold_date = datetime.now() - timedelta(days=max_age_days)
    deleted_count = 0
    freed_space = 0
    
    for temp_dir in temp_dirs:
        if not os.path.exists(temp_dir) or not os.path.isdir(temp_dir):
            logger.debug(f"Skipping non-existent directory: {temp_dir}")
            continue
            
        logger.info(f"Cleaning temporary directory: {temp_dir} (files older than {threshold_date})")
        
        # Walk through the directory
        for dirpath, dirnames, filenames in os.walk(temp_dir, topdown=False):
            # Check files in current directory
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                try:
                    file_stats = os.stat(file_path)
                    file_mtime = datetime.fromtimestamp(file_stats.st_mtime)
                    
                    # Check if file is older than threshold
                    if file_mtime < threshold_date:
                        file_size = file_stats.st_size
                        logger.debug(f"Found old file: {file_path} (Last modified: {file_mtime})")
                        
                        if not dry_run:
                            os.unlink(file_path)
                            logger.info(f"Deleted file: {file_path} (Size: {file_size/1024/1024:.2f} MB)")
                            deleted_count += 1
                            freed_space += file_size
                        else:
                            logger.info(f"Would delete file: {file_path} (Size: {file_size/1024/1024:.2f} MB)")
                            deleted_count += 1
                            freed_space += file_size
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {str(e)}")
            
            # Check if current directory is empty and older than threshold
            try:
                if not os.listdir(dirpath) and dirpath != temp_dir:  # Don't delete the main temp dir
                    dir_stats = os.stat(dirpath)
                    dir_mtime = datetime.fromtimestamp(dir_stats.st_mtime)
                    
                    if dir_mtime < threshold_date:
                        logger.debug(f"Found empty old directory: {dirpath} (Last modified: {dir_mtime})")
                        
                        if not dry_run:
                            os.rmdir(dirpath)
                            logger.info(f"Deleted empty directory: {dirpath}")
                        else:
                            logger.info(f"Would delete empty directory: {dirpath}")
            except Exception as e:
                logger.error(f"Error processing directory {dirpath}: {str(e)}")
    
    if dry_run:
        logger.info(f"Dry run completed. Would have deleted {deleted_count} files/directories, freeing {freed_space/1024/1024:.2f} MB")
    else:
        logger.info(f"Cleanup completed. Deleted {deleted_count} files/directories, freed {freed_space/1024/1024:.2f} MB")
    
    return deleted_count, freed_space


def cleanup_old_jobs(job_dir, max_age_days=30, exclude_job_ids=None, dry_run=False):
    """
    Cleans up old completed job directories to free disk space
    
    Args:
        job_dir: Base job directory path
        max_age_days: Maximum age of completed jobs in days before deletion
        exclude_job_ids: List of job IDs to exclude from cleanup
        dry_run: If True, just logs what would be deleted without actual deletion
        
    Returns:
        Tuple of (deleted_count, freed_space_bytes)
    """
    if not os.path.exists(job_dir) or not os.path.isdir(job_dir):
        logger.warning(f"Job directory does not exist: {job_dir}")
        return 0, 0
    
    threshold_date = datetime.now() - timedelta(days=max_age_days)
    deleted_count = 0
    freed_space = 0
    exclude_job_ids = exclude_job_ids or []
    
    # Convert exclude_job_ids to strings for comparison
    exclude_job_ids = [str(job_id) for job_id in exclude_job_ids]
    
    logger.info(f"Cleaning up old jobs from {job_dir} (older than {threshold_date})")
    
    # Loop through direct subdirectories in job_dir which are job folders
    for job_folder in os.listdir(job_dir):
        job_path = os.path.join(job_dir, job_folder)
        
        # Skip if not a directory or in exclusion list
        if not os.path.isdir(job_path) or job_folder in exclude_job_ids:
            continue
        
        try:
            # Check job folder age using modification time
            job_stats = os.stat(job_path)
            job_mtime = datetime.fromtimestamp(job_stats.st_mtime)
            
            if job_mtime < threshold_date:
                # Calculate job folder size
                folder_size = calculate_folder_size(job_path)
                
                logger.debug(f"Found old job: {job_folder} from {job_mtime} ({folder_size/1024/1024:.2f} MB)")
                
                if not dry_run:
                    # Delete the entire job folder
                    shutil.rmtree(job_path)
                    logger.info(f"Deleted job folder: {job_folder} (Size: {folder_size/1024/1024:.2f} MB)")
                    deleted_count += 1
                    freed_space += folder_size
                else:
                    logger.info(f"Would delete job folder: {job_folder} (Size: {folder_size/1024/1024:.2f} MB)")
                    deleted_count += 1
                    freed_space += folder_size
        except Exception as e:
            logger.error(f"Error processing job folder {job_path}: {str(e)}")
    
    if dry_run:
        logger.info(f"Dry run completed. Would have deleted {deleted_count} job folders, freeing {freed_space/1024/1024:.2f} MB")
    else:
        logger.info(f"Cleanup completed. Deleted {deleted_count} job folders, freed {freed_space/1024/1024:.2f} MB")
    
    return deleted_count, freed_space


def calculate_folder_size(folder_path):
    """
    Calculate the total size of a folder and its contents
    
    Args:
        folder_path: Path to the folder
        
    Returns:
        Total size in bytes
    """
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            try:
                total_size += os.path.getsize(file_path)
            except (FileNotFoundError, PermissionError):
                # Skip files that can't be accessed
                pass
    return total_size
