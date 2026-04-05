from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON, Enum as SqlEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from .base import Base


class EditType(str, enum.Enum):
    TEXT = "TEXT"
    TIMING = "TIMING"
    SPLIT = "SPLIT"
    MERGE = "MERGE"
    CREATE = "CREATE"
    DELETE = "DELETE"


class SubtitleEdit(Base):
    """字幕编辑历史记录"""
    __tablename__ = "subtitle_edits"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    language = Column(String(10), nullable=False, index=True)
    subtitle_id = Column(String(100), nullable=False, index=True)
    
    # 编辑类型
    edit_type = Column(SqlEnum(EditType, name="edittype"), nullable=False, index=True)
    
    # 原始内容
    old_text = Column(Text, nullable=True)
    old_start_time = Column(Float, nullable=True)
    old_end_time = Column(Float, nullable=True)
    
    # 新内容
    new_text = Column(Text, nullable=True)
    new_start_time = Column(Float, nullable=True)
    new_end_time = Column(Float, nullable=True)
    
    # 元数据 (用于存储分割合并等操作的额外信息)
    metadata_ = Column("metadata", JSON, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 关联关系
    job = relationship("Job", back_populates="subtitle_edits")
    user = relationship("User", back_populates="subtitle_edits")
    
    def __repr__(self):
        return f"<SubtitleEdit(id={self.id}, job_id={self.job_id}, type={self.edit_type}, subtitle_id={self.subtitle_id})>"


class SubtitleVersion(Base):
    """字幕版本记录 - 用于保存字幕文件的不同版本"""
    __tablename__ = "subtitle_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    language = Column(String(10), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)
    
    # 文件信息
    file_path = Column(String(500), nullable=False)
    file_format = Column(String(10), nullable=False, default="srt")  # srt, vtt, ass
    file_size = Column(Integer, nullable=True)
    
    # 版本描述
    description = Column(String(500), nullable=True)
    is_current = Column(String(5), nullable=False, default="true")  # "true" or "false"
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 关联关系
    job = relationship("Job", back_populates="subtitle_versions")
    
    def __repr__(self):
        return f"<SubtitleVersion(id={self.id}, job_id={self.job_id}, language={self.language}, version={self.version_number})>"