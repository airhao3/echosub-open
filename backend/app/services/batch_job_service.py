"""
批量任务管理服务
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.job import Job, JobStatus
from app.models.user import User
from app.services.job_service import JobService

logger = logging.getLogger(__name__)


class BatchJobService:
    """批量任务管理服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.job_service = JobService(db)
    
    def get_batch_jobs_by_pattern(self, user_id: int, batch_pattern: str) -> List[Job]:
        """
        根据批次模式获取相关任务
        
        Args:
            user_id: 用户ID
            batch_pattern: 批次模式（如 "Batch 20241229_1030"）
            
        Returns:
            该批次的任务列表
        """
        return self.db.query(Job).filter(
            and_(
                Job.owner_id == user_id,
                Job.title.like(f"{batch_pattern}%")
            )
        ).order_by(Job.created_at).all()
    
    def get_batch_status_summary(self, user_id: int, batch_pattern: str) -> Dict[str, Any]:
        """
        获取批次任务状态汇总
        
        Args:
            user_id: 用户ID
            batch_pattern: 批次模式
            
        Returns:
            批次状态汇总信息
        """
        jobs = self.get_batch_jobs_by_pattern(user_id, batch_pattern)
        
        if not jobs:
            return {
                "batch_pattern": batch_pattern,
                "total_jobs": 0,
                "status_counts": {},
                "progress": {
                    "completed": 0,
                    "failed": 0,
                    "processing": 0,
                    "pending": 0
                },
                "estimated_completion": None
            }
        
        # 统计各状态任务数量
        status_counts = {}
        progress_counts = {"completed": 0, "failed": 0, "processing": 0, "pending": 0}
        total_duration = 0
        completed_jobs = []
        
        for job in jobs:
            status_str = job.status.value if hasattr(job.status, 'value') else str(job.status)
            status_counts[status_str] = status_counts.get(status_str, 0) + 1
            
            # 简化状态分类
            if job.status == JobStatus.COMPLETED:
                progress_counts["completed"] += 1
                completed_jobs.append(job)
            elif job.status == JobStatus.FAILED:
                progress_counts["failed"] += 1
            elif job.status == JobStatus.PROCESSING:
                progress_counts["processing"] += 1
            else:
                progress_counts["pending"] += 1
            
            # 累计视频时长
            if job.video_duration:
                total_duration += job.video_duration
        
        # 计算预计完成时间
        estimated_completion = self._estimate_batch_completion(jobs)
        
        # 计算平均处理时间
        avg_processing_time = None
        if completed_jobs:
            processing_times = []
            for job in completed_jobs:
                if job.completed_at and job.created_at:
                    processing_time = (job.completed_at - job.created_at).total_seconds()
                    processing_times.append(processing_time)
            
            if processing_times:
                avg_processing_time = sum(processing_times) / len(processing_times)
        
        return {
            "batch_pattern": batch_pattern,
            "total_jobs": len(jobs),
            "status_counts": status_counts,
            "progress": progress_counts,
            "total_duration_seconds": total_duration,
            "estimated_completion": estimated_completion,
            "average_processing_time_seconds": avg_processing_time,
            "completion_percentage": round((progress_counts["completed"] / len(jobs)) * 100, 1),
            "jobs": [
                {
                    "job_id": job.id,
                    "user_job_number": job.user_job_number,
                    "title": job.title,
                    "filename": job.video_filename,
                    "status": job.status.value if hasattr(job.status, 'value') else str(job.status),
                    "progress": job.progress,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    "error_message": job.error_message
                }
                for job in jobs
            ]
        }
    
    def _estimate_batch_completion(self, jobs: List[Job]) -> Optional[str]:
        """
        估算批次完成时间
        
        Args:
            jobs: 任务列表
            
        Returns:
            预计完成时间（ISO格式字符串）或None
        """
        try:
            pending_jobs = [job for job in jobs if job.status in [JobStatus.PENDING, JobStatus.PROCESSING]]
            completed_jobs = [job for job in jobs if job.status == JobStatus.COMPLETED]
            
            if not pending_jobs:
                return None  # 已经全部完成
            
            if not completed_jobs:
                # 没有完成的任务，无法估算
                return None
            
            # 计算平均处理时间
            total_processing_time = 0
            processing_count = 0
            
            for job in completed_jobs:
                if job.completed_at and job.created_at:
                    processing_time = (job.completed_at - job.created_at).total_seconds()
                    total_processing_time += processing_time
                    processing_count += 1
            
            if processing_count == 0:
                return None
            
            avg_processing_time = total_processing_time / processing_count
            
            # 估算剩余时间（考虑并发处理）
            # 假设系统可以并发处理多个任务，但这里简化为平均时间
            estimated_remaining_seconds = avg_processing_time * len(pending_jobs) / 4  # 假设4倍并发
            
            estimated_completion = datetime.now() + timedelta(seconds=estimated_remaining_seconds)
            return estimated_completion.isoformat()
            
        except Exception as e:
            logger.error(f"Error estimating batch completion: {e}")
            return None
    
    def retry_failed_batch_jobs(self, user_id: int, batch_pattern: str) -> Dict[str, Any]:
        """
        重试批次中的失败任务
        
        Args:
            user_id: 用户ID
            batch_pattern: 批次模式
            
        Returns:
            重试结果
        """
        failed_jobs = self.db.query(Job).filter(
            and_(
                Job.owner_id == user_id,
                Job.title.like(f"{batch_pattern}%"),
                Job.status == JobStatus.FAILED
            )
        ).all()
        
        retry_results = []
        from app.core.tasks import process_video_job
        
        for job in failed_jobs:
            try:
                # 重置任务状态
                job.status = JobStatus.PENDING
                job.error_message = None
                job.progress = 0
                self.db.commit()
                
                # 重新提交到队列
                process_video_job.delay(job.id)
                
                retry_results.append({
                    "job_id": job.id,
                    "user_job_number": job.user_job_number,
                    "title": job.title,
                    "status": "retried"
                })
                
                logger.info(f"Retried failed job {job.id} from batch {batch_pattern}")
                
            except Exception as e:
                logger.error(f"Failed to retry job {job.id}: {e}")
                retry_results.append({
                    "job_id": job.id,
                    "status": "retry_failed",
                    "error": str(e)
                })
        
        return {
            "batch_pattern": batch_pattern,
            "total_failed_jobs": len(failed_jobs),
            "retried_count": len([r for r in retry_results if r["status"] == "retried"]),
            "results": retry_results
        }
    
    def cancel_pending_batch_jobs(self, user_id: int, batch_pattern: str) -> Dict[str, Any]:
        """
        取消批次中的待处理任务
        
        Args:
            user_id: 用户ID
            batch_pattern: 批次模式
            
        Returns:
            取消结果
        """
        pending_jobs = self.db.query(Job).filter(
            and_(
                Job.owner_id == user_id,
                Job.title.like(f"{batch_pattern}%"),
                Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING])
            )
        ).all()
        
        cancelled_results = []
        
        for job in pending_jobs:
            try:
                old_status = job.status
                job.status = JobStatus.FAILED
                job.error_message = "Cancelled by user"
                self.db.commit()
                
                cancelled_results.append({
                    "job_id": job.id,
                    "user_job_number": job.user_job_number,
                    "title": job.title,
                    "old_status": old_status.value if hasattr(old_status, 'value') else str(old_status),
                    "status": "cancelled"
                })
                
                logger.info(f"Cancelled job {job.id} from batch {batch_pattern}")
                
            except Exception as e:
                logger.error(f"Failed to cancel job {job.id}: {e}")
                cancelled_results.append({
                    "job_id": job.id,
                    "status": "cancel_failed",
                    "error": str(e)
                })
        
        return {
            "batch_pattern": batch_pattern,
            "total_pending_jobs": len(pending_jobs),
            "cancelled_count": len([r for r in cancelled_results if r["status"] == "cancelled"]),
            "results": cancelled_results
        }
    
    def get_user_batch_history(self, user_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """
        获取用户的批量处理历史
        
        Args:
            user_id: 用户ID
            days: 查询天数
            
        Returns:
            批量处理历史列表
        """
        since_date = datetime.now() - timedelta(days=days)
        
        # 查询批量任务（根据title包含'Batch'来识别）
        batch_jobs = self.db.query(Job).filter(
            and_(
                Job.owner_id == user_id,
                Job.title.like("Batch %"),
                Job.created_at >= since_date
            )
        ).order_by(Job.created_at.desc()).all()
        
        # 按批次模式分组
        batch_groups = {}
        for job in batch_jobs:
            # 从title中提取批次标识（例如 "Batch 20241229_1030 - filename"）
            title_parts = job.title.split(' - ')
            if len(title_parts) >= 2:
                batch_key = title_parts[0]  # "Batch 20241229_1030"
                
                if batch_key not in batch_groups:
                    batch_groups[batch_key] = {
                        "batch_pattern": batch_key,
                        "jobs": [],
                        "first_created": job.created_at,
                        "last_updated": job.created_at
                    }
                
                batch_groups[batch_key]["jobs"].append(job)
                if job.created_at > batch_groups[batch_key]["last_updated"]:
                    batch_groups[batch_key]["last_updated"] = job.created_at
        
        # 生成批次汇总
        batch_summaries = []
        for batch_key, batch_data in batch_groups.items():
            jobs = batch_data["jobs"]
            
            status_counts = {}
            for job in jobs:
                status_str = job.status.value if hasattr(job.status, 'value') else str(job.status)
                status_counts[status_str] = status_counts.get(status_str, 0) + 1
            
            completed_count = len([j for j in jobs if j.status == JobStatus.COMPLETED])
            completion_rate = (completed_count / len(jobs)) * 100 if jobs else 0
            
            batch_summaries.append({
                "batch_pattern": batch_key,
                "total_jobs": len(jobs),
                "completion_rate": round(completion_rate, 1),
                "status_counts": status_counts,
                "first_created": batch_data["first_created"].isoformat(),
                "last_updated": batch_data["last_updated"].isoformat()
            })
        
        return sorted(batch_summaries, key=lambda x: x["last_updated"], reverse=True)