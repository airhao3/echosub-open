from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api import deps
from app.models import User
from app.schemas.subtitle_edit import (
    SubtitleEditCreate, SubtitleBatchEditCreate, SubtitleEditResponse,
    SubtitleEdit as SubtitleEditSchema
)
from app.services.subtitle_edit_service import subtitle_edit_service
from app.services.subtitle_version_service import subtitle_version_service
from app.services.subtitle_cleanup_service import subtitle_cleanup_service
from app.crud.crud_subtitle_edit import subtitle_edit
from app.core.database import get_db

router = APIRouter()


@router.post("/edit", response_model=SubtitleEditResponse)
def edit_subtitle(
    *,
    db: Session = Depends(get_db),
    edit_data: SubtitleEditCreate,
    current_user: User = Depends(deps.get_current_active_user)
) -> SubtitleEditResponse:
    """
    编辑单个字幕
    """
    try:
        result = subtitle_edit_service.process_edit(
            db=db,
            edit_data=edit_data,
            user_id=current_user.id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-edit", response_model=SubtitleEditResponse)
def batch_edit_subtitles(
    *,
    db: Session = Depends(get_db),
    batch_data: SubtitleBatchEditCreate,
    current_user: User = Depends(deps.get_current_active_user)
) -> SubtitleEditResponse:
    """
    批量编辑字幕
    """
    try:
        result = subtitle_edit_service.process_batch_edit(
            db=db,
            batch_data=batch_data,
            user_id=current_user.id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/edit-history/{job_id}")
def get_edit_history(
    job_id: int,
    language: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    获取字幕编辑历史
    """
    try:
        history = subtitle_edit_service.get_edit_history(
            db=db,
            job_id=job_id,
            language=language
        )
        return {"edits": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/undo-edit/{edit_id}", response_model=SubtitleEditResponse)
def undo_edit(
    edit_id: int,
    job_id: int,
    language: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> SubtitleEditResponse:
    """
    撤销编辑操作
    """
    try:
        # 获取编辑记录
        edit_record = subtitle_edit.get(db=db, id=edit_id)
        if not edit_record:
            raise HTTPException(status_code=404, detail="Edit record not found")
        
        # 创建撤销编辑操作
        undo_edit_data = SubtitleEditCreate(
            job_id=job_id,
            language=language,
            subtitle_id=edit_record.subtitle_id,
            edit_type=edit_record.edit_type,
            # 反向操作：新内容变成旧内容，旧内容变成新内容
            old_text=edit_record.new_text,
            new_text=edit_record.old_text,
            old_start_time=edit_record.new_start_time,
            new_start_time=edit_record.old_start_time,
            old_end_time=edit_record.new_end_time,
            new_end_time=edit_record.old_end_time,
            metadata={"undo_edit_id": edit_id}
        )
        
        result = subtitle_edit_service.process_edit(
            db=db,
            edit_data=undo_edit_data,
            user_id=current_user.id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/{job_id}")
def export_subtitles(
    job_id: int,
    language: str,
    format: str = "srt",
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    导出编辑后的字幕文件
    """
    try:
        content = subtitle_edit_service.export_subtitles(
            job_id=job_id,
            language=language,
            user_id=current_user.id,
            format=format
        )
        
        # 设置合适的Content-Type和文件名
        if format.lower() == "srt":
            media_type = "text/plain"
            filename = f"subtitle_{language}.srt"
        elif format.lower() == "vtt":
            media_type = "text/vtt"
            filename = f"subtitle_{language}.vtt"
        elif format.lower() == "ass":
            media_type = "text/plain"
            filename = f"subtitle_{language}.ass"
        else:
            media_type = "text/plain"
            filename = f"subtitle_{language}.txt"
        
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/{job_id}")
def get_subtitle_versions(
    job_id: int,
    language: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    获取字幕版本历史
    """
    try:
        from app.crud.crud_subtitle_edit import subtitle_version
        
        versions = subtitle_version.get_versions(
            db=db,
            job_id=job_id,
            language=language
        )
        
        return {
            "versions": [
                {
                    "id": v.id,
                    "version_number": v.version_number,
                    "file_path": v.file_path,
                    "file_format": v.file_format,
                    "description": v.description,
                    "is_current": v.is_current,
                    "created_at": v.created_at.isoformat()
                }
                for v in versions
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/version-history/{job_id}")
def get_version_history(
    job_id: int,
    language: str,
    include_auto_saves: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    获取字幕版本历史（包含详细信息）
    """
    try:
        history = subtitle_version_service.get_version_history(
            db=db,
            job_id=job_id,
            language=language,
            include_auto_saves=include_auto_saves
        )
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save-version/{job_id}")
def save_working_version(
    job_id: int,
    language: str,
    subtitles: List[dict],
    description: str = "工作版本",
    auto_save: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    保存工作版本
    """
    try:
        version_id = subtitle_version_service.save_working_version(
            db=db,
            job_id=job_id,
            language=language,
            subtitles=subtitles,
            description=description,
            auto_save=auto_save,
            user_id=current_user.id
        )
        return {"success": True, "version_id": version_id, "message": "Version saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/publish-version/{job_id}")
def publish_version(
    job_id: int,
    language: str,
    version_id: Optional[str] = None,
    description: str = "发布版本",
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    发布版本
    """
    try:
        published_version = subtitle_version_service.publish_version(
            db=db,
            job_id=job_id,
            language=language,
            version_id=version_id,
            description=description
        )
        return {
            "success": True,
            "published_version": {
                "id": published_version.id,
                "version_number": published_version.version_number,
                "description": published_version.description,
                "created_at": published_version.created_at.isoformat()
            },
            "message": "Version published successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restore-version/{job_id}")
def restore_version(
    job_id: int,
    language: str,
    version_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    恢复到指定版本
    """
    try:
        subtitles = subtitle_version_service.restore_version(
            db=db,
            job_id=job_id,
            language=language,
            version_id=version_id,
            user_id=current_user.id
        )
        return {
            "success": True,
            "subtitles": subtitles,
            "message": "Version restored successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compare-versions")
def compare_versions(
    version_id_1: str,
    version_id_2: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    比较两个版本的差异
    """
    try:
        comparison = subtitle_version_service.compare_versions(
            db=db,
            version_id_1=version_id_1,
            version_id_2=version_id_2
        )
        return {"comparison": comparison}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cleanup-versions/{job_id}")
def cleanup_old_versions(
    job_id: int,
    language: str,
    keep_count: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    清理旧版本
    """
    try:
        deleted_count = subtitle_version_service.cleanup_old_versions(
            db=db,
            job_id=job_id,
            language=language,
            keep_count=keep_count
        )
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Cleaned up {deleted_count} old versions"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/storage-stats")
def get_storage_statistics(
    job_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    获取存储统计信息
    """
    try:
        stats = subtitle_cleanup_service.get_storage_statistics(
            db=db,
            job_id=job_id
        )
        return {"stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup-storage")
def cleanup_storage(
    job_id: Optional[int] = None,
    cleanup_type: str = "auto_save",  # "auto_save", "old_versions", "optimize", "full"
    days_threshold: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    清理存储空间
    """
    try:
        if cleanup_type == "auto_save":
            result = subtitle_cleanup_service.cleanup_auto_save_versions(
                db=db,
                job_id=job_id
            )
        elif cleanup_type == "old_versions":
            result = subtitle_cleanup_service.cleanup_old_versions(
                db=db,
                days_threshold=days_threshold
            )
        elif cleanup_type == "optimize" and job_id:
            result = subtitle_cleanup_service.optimize_version_storage(
                db=db,
                job_id=job_id
            )
        elif cleanup_type == "full":
            result = subtitle_cleanup_service.scheduled_cleanup(db=db)
        else:
            raise HTTPException(status_code=400, detail="Invalid cleanup type or missing job_id for optimization")
        
        return {
            "success": True,
            "cleanup_type": cleanup_type,
            "result": result,
            "message": f"Storage cleanup completed successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto-save/{job_id}")
def auto_save_subtitle(
    job_id: int,
    language: str,
    subtitles: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    自动保存字幕（用于前端自动保存功能）
    """
    try:
        from datetime import datetime
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"[Auto Save] 接收到字幕数据 - Job: {job_id}, Language: {language}, Count: {len(subtitles)}")
        for i, subtitle in enumerate(subtitles[:3]):  # 只打印前3个
            logger.info(f"[Auto Save] 字幕 {i+1}: ID={subtitle.get('id')}, Text='{subtitle.get('text', '')[:50]}...'")
        
        # 首先更新主工作文件（这样前端刷新就能看到最新修改）
        subtitle_version_service._save_current_working_files(
            job_id=job_id,
            language=language,
            subtitles=subtitles,
            user_id=current_user.id
        )
        
        # 然后创建自动保存版本（用于版本历史）
        version_id = subtitle_version_service.save_working_version(
            db=db,
            job_id=job_id,
            language=language,
            subtitles=subtitles,
            description="自动保存",
            auto_save=True,
            user_id=current_user.id
        )
        return {
            "success": True,
            "version_id": version_id,
            "message": "Auto-save completed",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        # 自动保存失败不应该影响用户操作，只返回警告
        from datetime import datetime
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Auto-save failed for job {job_id}, language {language}: {str(e)}")
        return {
            "success": False,
            "message": "Auto-save failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }