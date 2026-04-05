"""
批量视频上传处理端点
支持多文件同时上传和处理
"""
import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.models.job import Job, JobStatus
from app.services.job_service import JobService
from app.services.video_service import VideoService
from app.services.usage_tracker_service import UsageTrackerService
from app.utils.file_path_manager import get_file_path_manager, FileType
from app.utils.file_utils import ensure_directory_exists
from app.core.tasks import process_video_job
from app.core.config import settings
from app.models.job_context import JobContext

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def batch_upload_videos(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    files: List[UploadFile] = File(..., description="Multiple video files to upload"),
    source_language: str = Form("auto", description="Source language for all videos"),
    target_languages: str = Form("zh", description="Target languages (comma-separated)"),
    generate_subtitles: bool = Form(True),
    generate_dubbing: bool = Form(False),
    video_format: str = Form("mp4"),
    resolution: str = Form("1080p"),
    batch_title: Optional[str] = Form(None, description="Optional batch title prefix")
) -> Dict[str, Any]:
    """
    批量上传多个视频文件进行处理
    
    Args:
        files: 视频文件列表（最多20个文件）
        source_language: 源语言
        target_languages: 目标语言（逗号分隔）
        batch_title: 批次标题前缀
        
    Returns:
        Dict包含批量上传结果和job信息
    """
    
    # 限制批量上传数量
    if len(files) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Maximum 20 files per batch upload"
        )
    
    if len(files) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one file is required"
        )
    
    logger.info(f"[USER:{current_user.id}] Starting batch upload of {len(files)} files")
    
    # 验证所有文件格式
    invalid_files = []
    for file in files:
        if not file.filename or not VideoService.is_valid_video_extension(file.filename):
            invalid_files.append(file.filename)
    
    if invalid_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid video file formats: {', '.join(invalid_files)}"
        )
    
    job_service = JobService(db, data_dir=settings.STORAGE_BASE_DIR)
    video_service = VideoService()
    usage_tracker_service = UsageTrackerService(db)
    file_manager = get_file_path_manager()
    
    successful_jobs = []
    failed_jobs = []
    total_duration = 0
    total_size = 0
    
    # 批量处理每个文件
    for i, file in enumerate(files):
        job = None
        final_file_path = None
        
        try:
            # 生成任务标题
            base_filename = os.path.splitext(file.filename)[0]
            if batch_title:
                job_title = f"{batch_title} - {base_filename}"
            else:
                job_title = f"Batch {datetime.now().strftime('%Y%m%d_%H%M')} - {base_filename}"
            
            logger.info(f"[USER:{current_user.id}] Processing file {i+1}/{len(files)}: {file.filename}")
            
            # 1. 创建job记录
            job_data = {
                "title": job_title,
                "description": f"Batch upload file {i+1}/{len(files)}",
                "status": JobStatus.PENDING,
                "source_language": source_language,
                "target_languages": target_languages,
                "video_filename": file.filename,
                "subtitle_style": "default"
            }
            
            job = job_service.create_job(
                user_id=current_user.id,
                job_data=job_data
            )
            
            # 2. 保存文件
            context = JobContext(
                user_id=current_user.id,
                job_id=job.id,
                source_language=source_language,
                target_languages=target_languages.split(',') if target_languages else []
            )
            
            final_file_path = file_manager.get_file_path(
                context=context,
                file_type=FileType.SOURCE_VIDEO,
                filename=file.filename
            )
            ensure_directory_exists(os.path.dirname(final_file_path))
            
            # 保存文件
            with open(final_file_path, "wb") as f:
                file.file.seek(0)  # 确保从头开始读取
                content = await file.read()
                f.write(content)
            
            # 3. 获取视频元数据
            metadata = video_service.get_video_metadata(final_file_path)
            video_duration = metadata.get('duration')
            file_size_bytes = os.path.getsize(final_file_path)
            
            if video_duration:
                try:
                    duration_seconds = float(video_duration)
                    job.video_duration = duration_seconds
                    total_duration += duration_seconds
                except (ValueError, TypeError):
                    logger.warning(f"[JOB:{job.id}] Could not parse duration: {video_duration}")
            
            total_size += file_size_bytes
            
            # 4. 更新job信息
            job.file_path = final_file_path
            job.source_video_url = final_file_path
            job.file_size = file_size_bytes
            db.commit()
            
            # 5. 加入成功列表
            successful_jobs.append({
                "job_id": job.id,
                "user_job_number": job.user_job_number,
                "filename": file.filename,
                "title": job_title,
                "file_size": file_size_bytes,
                "duration": video_duration,
                "status": job.status.value
            })
            
            logger.info(f"[JOB:{job.id}] Successfully created job for {file.filename}")
            
        except Exception as e:
            error_message = f"Failed to process {file.filename}: {str(e)}"
            logger.error(f"[USER:{current_user.id}] {error_message}", exc_info=True)
            
            failed_jobs.append({
                "filename": file.filename,
                "error": error_message
            })
            
            # 清理失败的job
            if job:
                try:
                    job.status = JobStatus.FAILED
                    job.error_message = error_message
                    db.commit()
                except:
                    pass
            
            # 清理文件
            if final_file_path and os.path.exists(final_file_path):
                try:
                    os.remove(final_file_path)
                except:
                    pass
    
    # 检查用户配额
    if successful_jobs:
        try:
            # 检查视频时长配额
            if total_duration > 0:
                minutes_to_add = int((total_duration + 59) // 60)
                usage_tracker_service.check_and_update_video_minutes(
                    user_id=current_user.id, 
                    minutes_to_add=minutes_to_add
                )
            
            # 检查存储配额
            if total_size > 0:
                storage_mb = total_size / (1024 * 1024)
                usage_tracker_service.check_and_update_storage_mb(
                    user_id=current_user.id,
                    mb_to_add=storage_mb
                )
            
            logger.info(f"[USER:{current_user.id}] Usage updated: {minutes_to_add} minutes, {storage_mb:.2f} MB")
            
        except Exception as e:
            logger.error(f"[USER:{current_user.id}] Failed to update usage: {e}", exc_info=True)
    
    # 批量提交任务到队列
    queued_jobs = []
    for job_info in successful_jobs:
        try:
            process_video_job.delay(job_info["job_id"])
            queued_jobs.append(job_info["job_id"])
            logger.info(f"[JOB:{job_info['job_id']}] Queued for processing")
        except Exception as e:
            logger.error(f"[JOB:{job_info['job_id']}] Failed to queue: {e}")
    
    # 返回批量处理结果
    result = {
        "batch_id": f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "total_files": len(files),
        "successful_jobs": len(successful_jobs),
        "failed_jobs": len(failed_jobs),
        "queued_jobs": len(queued_jobs),
        "total_duration_seconds": total_duration,
        "total_size_bytes": total_size,
        "jobs": successful_jobs,
        "failures": failed_jobs,
        "message": f"Batch upload completed: {len(successful_jobs)}/{len(files)} files processed successfully"
    }
    
    logger.info(f"[USER:{current_user.id}] Batch upload completed: {result['message']}")
    return result

@router.get("/batch/{batch_pattern}/status")
async def get_batch_status(
    batch_pattern: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    获取批量任务的整体状态
    """
    from app.services.batch_job_service import BatchJobService
    
    batch_service = BatchJobService(db)
    return batch_service.get_batch_status_summary(current_user.id, batch_pattern)

@router.get("/batch/history")
async def get_batch_history(
    days: int = 30,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> List[Dict[str, Any]]:
    """
    获取用户的批量处理历史
    """
    from app.services.batch_job_service import BatchJobService
    
    batch_service = BatchJobService(db)
    return batch_service.get_user_batch_history(current_user.id, days)

@router.post("/batch/{batch_pattern}/retry")
async def retry_batch_failed_jobs(
    batch_pattern: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    重试批次中的失败任务
    """
    from app.services.batch_job_service import BatchJobService
    
    batch_service = BatchJobService(db)
    return batch_service.retry_failed_batch_jobs(current_user.id, batch_pattern)

@router.post("/batch/{batch_pattern}/cancel")
async def cancel_batch_pending_jobs(
    batch_pattern: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    取消批次中的待处理任务
    """
    from app.services.batch_job_service import BatchJobService
    
    batch_service = BatchJobService(db)
    return batch_service.cancel_pending_batch_jobs(current_user.id, batch_pattern)

@router.post("/batch/retry")
async def retry_failed_batch_jobs(
    job_ids: List[int],
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    重试批量上传中失败的任务
    """
    job_service = JobService(db, data_dir=settings.STORAGE_BASE_DIR)
    
    retry_results = []
    for job_id in job_ids:
        try:
            job = job_service.get_job_by_id(job_id)
            if job and job.owner_id == current_user.id and job.status == JobStatus.FAILED:
                # 重置状态并重新提交
                job.status = JobStatus.PENDING
                job.error_message = None
                db.commit()
                
                process_video_job.delay(job_id)
                retry_results.append({"job_id": job_id, "status": "retried"})
            else:
                retry_results.append({"job_id": job_id, "status": "not_eligible"})
        except Exception as e:
            retry_results.append({"job_id": job_id, "status": "error", "error": str(e)})
    
    return {
        "retried_jobs": len([r for r in retry_results if r["status"] == "retried"]),
        "results": retry_results
    }