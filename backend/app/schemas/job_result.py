from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.job_result import ResultType

class JobResultBase(BaseModel):
    result_type: ResultType
    language: str
    file_url: str
    file_name: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    metadata: Optional[str] = None

class JobResultCreate(JobResultBase):
    job_id: int

class JobResultUpdate(BaseModel):
    result_type: Optional[ResultType] = None
    language: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    metadata: Optional[str] = None

class JobResultInDBBase(JobResultBase):
    id: int
    job_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class JobResult(JobResultInDBBase):
    pass

class JobResultResponse(JobResultInDBBase):
    pass

class JobResultInDB(JobResultInDBBase):
    pass
