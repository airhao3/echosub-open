from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class EditType(str, Enum):
    TEXT = "TEXT"
    TIMING = "TIMING"
    SPLIT = "SPLIT"
    MERGE = "MERGE"
    CREATE = "CREATE"
    DELETE = "DELETE"


class SubtitleEditBase(BaseModel):
    job_id: int
    language: str
    subtitle_id: str
    edit_type: EditType
    old_text: Optional[str] = None
    old_start_time: Optional[float] = None
    old_end_time: Optional[float] = None
    new_text: Optional[str] = None
    new_start_time: Optional[float] = None
    new_end_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class SubtitleEditCreate(SubtitleEditBase):
    pass


class SubtitleEditUpdate(BaseModel):
    old_text: Optional[str] = None
    old_start_time: Optional[float] = None
    old_end_time: Optional[float] = None
    new_text: Optional[str] = None
    new_start_time: Optional[float] = None
    new_end_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class SubtitleEdit(SubtitleEditBase):
    id: int
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class SubtitleBatchEditCreate(BaseModel):
    job_id: int
    language: str
    edits: List[SubtitleEditCreate]


class SubtitleEditResponse(BaseModel):
    success: bool
    message: str
    subtitle: Optional[Dict[str, Any]] = None
    subtitles: Optional[List[Dict[str, Any]]] = None
    errors: Optional[List[str]] = None


class SubtitleVersionBase(BaseModel):
    job_id: int
    language: str
    version_number: int = 1
    file_path: str
    file_format: str = "srt"
    file_size: Optional[int] = None
    description: Optional[str] = None
    is_current: str = "true"


class SubtitleVersionCreate(SubtitleVersionBase):
    pass


class SubtitleVersion(SubtitleVersionBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True