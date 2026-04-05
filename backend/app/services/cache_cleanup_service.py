import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.job import Job, JobStatus
from app.utils.file_path_manager import get_file_path_manager

logger = logging.getLogger(__name__)


class CacheCleanupService:
    """
    Service for managing local cache cleanup after S3 synchronization.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.file_manager = get_file_path_manager()
    
    def cleanup_completed_job(self, job_id: int, user_id: int, force: bool = False) -> Dict:
        """
        Clean up local cache for a completed job.
        
        Args:
            job_id: Job ID to clean up
            user_id: User ID who owns the job
            force: If True, skip safety checks and clean immediately
            
        Returns:
            Dictionary with cleanup statistics
        """
        logger.info(f"Starting cache cleanup for job {job_id}")
        
        if not self.settings.AUTO_CLEANUP_LOCAL_CACHE and not force:
            logger.info(f"Auto cleanup disabled for job {job_id}")
            return {"status": "skipped", "reason": "auto_cleanup_disabled"}
        
        # For safety, only clean up jobs that are completed and old enough
        delay_hours = 0 if force else self.settings.CLEANUP_DELAY_HOURS
        
        try:
            stats = self.file_manager.cleanup_job_cache(
                user_id=user_id,
                job_id=job_id,
                older_than_hours=delay_hours
            )
            
            stats["status"] = "completed"
            stats["job_id"] = job_id
            stats["cleanup_time"] = datetime.now().isoformat()
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup job {job_id}: {e}")
            return {
                "status": "failed",
                "job_id": job_id,
                "error": str(e),
                "cleanup_time": datetime.now().isoformat()
            }
    
    def cleanup_old_jobs(self, db: Session, max_jobs: int = 50) -> List[Dict]:
        """
        Clean up local cache for old completed jobs.
        
        Args:
            db: Database session
            max_jobs: Maximum number of jobs to process in one run
            
        Returns:
            List of cleanup results
        """
        if not self.settings.AUTO_CLEANUP_LOCAL_CACHE:
            logger.info("Auto cleanup is disabled")
            return []
        
        # Find completed jobs older than the cleanup delay
        cutoff_time = datetime.now() - timedelta(hours=self.settings.CLEANUP_DELAY_HOURS)
        
        completed_jobs = db.query(Job).filter(
            Job.status == JobStatus.COMPLETED,
            Job.updated_at < cutoff_time
        ).limit(max_jobs).all()
        
        logger.info(f"Found {len(completed_jobs)} jobs eligible for cleanup")
        
        results = []
        for job in completed_jobs:
            try:
                result = self.cleanup_completed_job(
                    job_id=job.id,
                    user_id=job.owner_id,
                    force=False
                )
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error cleaning up job {job.id}: {e}")
                results.append({
                    "status": "error",
                    "job_id": job.id,
                    "error": str(e)
                })
        
        return results
    
    def sync_and_cleanup_file(self, file_path: str, cleanup_after_sync: bool = True) -> Dict:
        """
        Sync a file to S3 and optionally clean up local copy.
        
        Args:
            file_path: Path to the file to sync
            cleanup_after_sync: Whether to clean up local file after successful sync
            
        Returns:
            Dictionary with operation results
        """
        result = {
            "file_path": file_path,
            "sync_success": False,
            "cleanup_success": False,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # First, sync to remote storage
            if self.file_manager.sync_to_remote(file_path):
                result["sync_success"] = True
                logger.info(f"Successfully synced file to S3: {file_path}")
                
                # If sync successful and cleanup requested, clean up local file
                if cleanup_after_sync and self.settings.AUTO_CLEANUP_LOCAL_CACHE:
                    if self.file_manager.cleanup_local_file(file_path):
                        result["cleanup_success"] = True
                        logger.info(f"Successfully cleaned up local file: {file_path}")
                    else:
                        logger.warning(f"Failed to cleanup local file: {file_path}")
            else:
                logger.error(f"Failed to sync file to S3: {file_path}")
                
        except Exception as e:
            logger.error(f"Error in sync_and_cleanup_file for {file_path}: {e}")
            result["error"] = str(e)
        
        return result
    
    def get_cache_usage_stats(self) -> Dict:
        """
        Get statistics about local cache usage.
        
        Returns:
            Dictionary with cache usage statistics
        """
        stats = {
            "total_size_bytes": 0,
            "total_files": 0,
            "directories": {},
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            base_dir = self.file_manager.base_dir
            
            if not os.path.exists(base_dir):
                return stats
            
            for root, dirs, files in os.walk(base_dir):
                dir_size = 0
                dir_files = 0
                
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_size = os.path.getsize(file_path)
                        dir_size += file_size
                        dir_files += 1
                        stats["total_size_bytes"] += file_size
                        stats["total_files"] += 1
                    except OSError:
                        continue
                
                if dir_files > 0:
                    rel_dir = os.path.relpath(root, base_dir)
                    stats["directories"][rel_dir] = {
                        "size_bytes": dir_size,
                        "files": dir_files,
                        "size_mb": round(dir_size / (1024 * 1024), 2)
                    }
            
            stats["total_size_mb"] = round(stats["total_size_bytes"] / (1024 * 1024), 2)
            stats["total_size_gb"] = round(stats["total_size_bytes"] / (1024 * 1024 * 1024), 2)
            
        except Exception as e:
            logger.error(f"Error calculating cache usage stats: {e}")
            stats["error"] = str(e)
        
        return stats


# Global instance
cache_cleanup_service = CacheCleanupService()
