import enum
from sqlalchemy import Column, Integer, String, DateTime, Float, Enum
from sqlalchemy.sql import func

from .base import Base

class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PREPARING = "PREPARING"
    DOWNLOADING = "DOWNLOADING"
    TRANSCRIBING = "TRANSCRIBING"
    ANALYZING_CONTENT = "ANALYZING_CONTENT"
    TRANSLATING = "TRANSLATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"

class TranslationJob(Base):
    __tablename__ = "translation_jobs"

    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(String, nullable=False, index=True)
    
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False)
    progress = Column(Float, default=0.0, nullable=False)
    status_message = Column(String, nullable=True)
    
    # File paths for job artifacts
    source_video_path = Column(String, nullable=True)
    transcript_path = Column(String, nullable=True)
    translated_video_path = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_onupdate=func.now())

class StepName(str, enum.Enum):
    UPLOAD = "UPLOAD"
    AUDIO_PROCESSING = "AUDIO_PROCESSING"
    TRANSCRIBING = "TRANSCRIBING"
    SEGMENTING = "SEGMENTING"
    ANALYZING = "ANALYZING"
    TRANSLATING = "TRANSLATING"
    INTEGRATING = "INTEGRATING"
    ALIGNING_TIMESTAMPS = "ALIGNING_TIMESTAMPS"
    ALIGNING_SUBTITLES = "ALIGNING_SUBTITLES"
    VIDEO_COMPRESSING = "VIDEO_COMPRESSING"

class StepStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

class JobStep(Base):
    __tablename__ = "job_steps"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, nullable=False, index=True) # Foreign key to TranslationJob
    step_name = Column(Enum(StepName), nullable=False)
    status = Column(String, default="pending", nullable=False) # pending, in_progress, completed, failed
    progress = Column(Float, default=0.0, nullable=False)
    details = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_onupdate=func.now())
