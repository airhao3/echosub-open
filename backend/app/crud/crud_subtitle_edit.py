from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, or_

from app.crud.base import CRUDBase
from app.models.subtitle_edit import SubtitleEdit, SubtitleVersion, EditType
from app.schemas.subtitle_edit import (
    SubtitleEditCreate, SubtitleEditUpdate,
    SubtitleVersionCreate
)


class CRUDSubtitleEdit(CRUDBase[SubtitleEdit, SubtitleEditCreate, SubtitleEditUpdate]):
    def create_edit(
        self, 
        db: Session, 
        *, 
        edit_data: SubtitleEditCreate,
        user_id: int
    ) -> SubtitleEdit:
        """创建字幕编辑记录"""
        edit_obj = SubtitleEdit(
            **edit_data.dict(),
            user_id=user_id
        )
        db.add(edit_obj)
        db.commit()
        db.refresh(edit_obj)
        return edit_obj
    
    def get_edit_history(
        self,
        db: Session,
        *,
        job_id: int,
        language: Optional[str] = None,
        limit: int = 100
    ) -> List[SubtitleEdit]:
        """获取字幕编辑历史"""
        query = db.query(SubtitleEdit).filter(SubtitleEdit.job_id == job_id)
        
        if language:
            query = query.filter(SubtitleEdit.language == language)
        
        return query.order_by(desc(SubtitleEdit.created_at)).limit(limit).all()
    
    def get_edits_by_subtitle(
        self,
        db: Session,
        *,
        job_id: int,
        language: str,
        subtitle_id: str
    ) -> List[SubtitleEdit]:
        """获取特定字幕的编辑历史"""
        return db.query(SubtitleEdit).filter(
            and_(
                SubtitleEdit.job_id == job_id,
                SubtitleEdit.language == language,
                SubtitleEdit.subtitle_id == subtitle_id
            )
        ).order_by(desc(SubtitleEdit.created_at)).all()
    
    def batch_create_edits(
        self,
        db: Session,
        *,
        edits_data: List[SubtitleEditCreate],
        user_id: int
    ) -> List[SubtitleEdit]:
        """批量创建编辑记录"""
        edits = []
        for edit_data in edits_data:
            edit_obj = SubtitleEdit(
                **edit_data.dict(),
                user_id=user_id
            )
            db.add(edit_obj)
            edits.append(edit_obj)
        
        db.commit()
        for edit in edits:
            db.refresh(edit)
        return edits


class CRUDSubtitleVersion(CRUDBase[SubtitleVersion, SubtitleVersionCreate, Dict[str, Any]]):
    def create_version(
        self,
        db: Session,
        *,
        version_data: SubtitleVersionCreate
    ) -> SubtitleVersion:
        """创建字幕版本记录"""
        # 如果设置为当前版本，先将其他版本设为非当前
        if version_data.is_current == "true":
            db.query(SubtitleVersion).filter(
                and_(
                    SubtitleVersion.job_id == version_data.job_id,
                    SubtitleVersion.language == version_data.language
                )
            ).update({"is_current": "false"})
        
        version_obj = SubtitleVersion(**version_data.dict())
        db.add(version_obj)
        db.commit()
        db.refresh(version_obj)
        return version_obj
    
    def get_current_version(
        self,
        db: Session,
        *,
        job_id: int,
        language: str
    ) -> Optional[SubtitleVersion]:
        """获取当前版本"""
        return db.query(SubtitleVersion).filter(
            and_(
                SubtitleVersion.job_id == job_id,
                SubtitleVersion.language == language,
                SubtitleVersion.is_current == "true"
            )
        ).first()
    
    def get_versions(
        self,
        db: Session,
        *,
        job_id: int,
        language: str
    ) -> List[SubtitleVersion]:
        """获取所有版本"""
        return db.query(SubtitleVersion).filter(
            and_(
                SubtitleVersion.job_id == job_id,
                SubtitleVersion.language == language
            )
        ).order_by(desc(SubtitleVersion.version_number)).all()
    
    def get_next_version_number(
        self,
        db: Session,
        *,
        job_id: int,
        language: str
    ) -> int:
        """获取下一个版本号"""
        latest = db.query(SubtitleVersion).filter(
            and_(
                SubtitleVersion.job_id == job_id,
                SubtitleVersion.language == language
            )
        ).order_by(desc(SubtitleVersion.version_number)).first()
        
        if latest:
            return latest.version_number + 1
        return 1
    
    def get_version_by_type(
        self,
        db: Session,
        job_id: int,
        language: str,
        version_type: str
    ) -> Optional[SubtitleVersion]:
        """根据版本类型获取版本（source=源文件, modified=修改版本）"""
        if version_type == "source":
            version_number = 1
        elif version_type == "modified":
            version_number = 2
        else:
            return None
            
        return db.query(SubtitleVersion).filter(
            and_(
                SubtitleVersion.job_id == job_id,
                SubtitleVersion.language == language,
                SubtitleVersion.version_number == version_number
            )
        ).first()
    
    def get_expired_versions(
        self,
        db: Session,
        *,
        cutoff_date: datetime
    ) -> List[SubtitleVersion]:
        """获取过期版本"""
        return db.query(SubtitleVersion).filter(
            and_(
                SubtitleVersion.created_at < cutoff_date,
                SubtitleVersion.is_current != "true"
            )
        ).all()
    
    def get_auto_save_versions(
        self,
        db: Session,
        *,
        job_id: Optional[int] = None,
        cutoff_date: Optional[datetime] = None
    ) -> List[SubtitleVersion]:
        """获取自动保存版本"""
        query = db.query(SubtitleVersion)
        
        # 通过描述判断是否为自动保存
        query = query.filter(
            or_(
                SubtitleVersion.description.contains("自动保存"),
                SubtitleVersion.description.contains("auto"),
                SubtitleVersion.description.contains("Auto")
            )
        )
        
        if job_id:
            query = query.filter(SubtitleVersion.job_id == job_id)
        
        if cutoff_date:
            query = query.filter(SubtitleVersion.created_at < cutoff_date)
        
        return query.order_by(desc(SubtitleVersion.created_at)).all()
    
    def get_versions_by_job(
        self,
        db: Session,
        *,
        job_id: int
    ) -> List[SubtitleVersion]:
        """获取指定作业的所有版本"""
        return db.query(SubtitleVersion).filter(
            SubtitleVersion.job_id == job_id
        ).order_by(desc(SubtitleVersion.created_at)).all()
    
    def get_all_versions(
        self,
        db: Session
    ) -> List[SubtitleVersion]:
        """获取所有版本"""
        return db.query(SubtitleVersion).order_by(desc(SubtitleVersion.created_at)).all()


# 创建CRUD实例
subtitle_edit = CRUDSubtitleEdit(SubtitleEdit)
subtitle_version = CRUDSubtitleVersion(SubtitleVersion)