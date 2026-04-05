import logging
import time
import threading
from datetime import datetime, timedelta
from app.utils.cleanup_utils import cleanup_temporary_files, cleanup_old_jobs
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def start_scheduled_tasks():
    """
    Start background threads for scheduled maintenance tasks
    """
    logger.info("Starting scheduled maintenance tasks")
    
    # Start temp file cleanup thread
    temp_cleanup_thread = threading.Thread(target=temp_file_cleanup_task, daemon=True)
    temp_cleanup_thread.start()
    
    # Start old job cleanup thread
    job_cleanup_thread = threading.Thread(target=old_job_cleanup_task, daemon=True)
    job_cleanup_thread.start()
    
    logger.info("Scheduled maintenance tasks started")


def temp_file_cleanup_task():
    """
    Periodically run temporary file cleanup task
    """
    # Wait 5 minutes after startup before first cleanup
    time.sleep(300)
    
    while True:
        try:
            logger.info("Running scheduled temporary file cleanup")
            count, space = cleanup_temporary_files(max_age_days=3)  # Clean files older than 3 days
            logger.info(f"Scheduled cleanup removed {count} files, freed {space/1024/1024:.2f} MB")
        except Exception as e:
            logger.error(f"Error in temporary file cleanup task: {str(e)}")
        
        # Run every 24 hours
        time.sleep(86400)  # 24 hours in seconds


def old_job_cleanup_task():
    """
    Periodically run old job cleanup task
    """
    # Wait 15 minutes after startup before first cleanup
    time.sleep(900)
    
    while True:
        try:
            logger.info("Running scheduled old job cleanup")
            count, space = cleanup_old_jobs(settings.JOB_DIR, max_age_days=30)  # Clean jobs older than 30 days
            logger.info(f"Scheduled job cleanup removed {count} jobs, freed {space/1024/1024:.2f} MB")
        except Exception as e:
            logger.error(f"Error in old job cleanup task: {str(e)}")
        
        # Run every 3 days
        time.sleep(259200)  # 3 days in seconds
