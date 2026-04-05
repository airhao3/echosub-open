from sqlalchemy import Column, Integer, String, Text, Enum, DateTime, ForeignKey, Boolean, Index, Float
from sqlalchemy.sql import func
from datetime import datetime
from sqlalchemy.orm import relationship, object_session
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.dialects.postgresql import ARRAY, JSON as JSONType
from enum import Enum as PyEnum
import json
import logging
from typing import Optional, Union, List, Dict, Any, TYPE_CHECKING

from app.db.types import FlexibleJSON
from app.models.base import Base

logger = logging.getLogger(__name__)

from .base import Base
from ..core.config import settings

if TYPE_CHECKING:
    from .user import User

class JobStatus(str, PyEnum):
    """Enum for job status"""
    PENDING = "pending"  # Job submitted but not yet started
    PROCESSING = "processing"  # Job is currently being processed
    COMPLETED = "completed"  # Job completed successfully
    FAILED = "failed"  # Job failed during processing
    CANCELLED = "cancelled"  # Job was cancelled by the user

class ResultType(str, PyEnum):
    """Enum for job result types"""
    TRANSCRIPT_TXT = "transcript_txt"
    TRANSCRIPT_JSON = "transcript_json"
    SUBTITLE_SRT = "subtitle_srt"
    SUBTITLE_VTT = "subtitle_vtt"
    SUBTITLE_ASS = "subtitle_ass"
    TRANSCRIPTION_SRT = "transcription_srt"
    TRANSLATED_SUBTITLE_SRT = "translated_subtitle_srt"
    TRANSLATED_SUBTITLE_VTT = "translated_subtitle_vtt"
    DUBBED_AUDIO_MP3 = "dubbed_audio_mp3"
    DUBBED_AUDIO_WAV = "dubbed_audio_wav"
    DUBBED_VIDEO_MP4 = "dubbed_video_mp4"
    SOURCE_VIDEO_INFO = "source_video_info"
    LOG_FILE = "log_file"
    
    # Video preview types
    ORIGINAL_VIDEO = "original_video"
    SUBTITLED_VIDEO = "subtitled_video"
    
    # Text processing types
    SEGMENTED_TEXT = "segmented_text"
    TRANSCRIPTION_REFINED = "transcription_refined"  # Refined transcription text
    LABELED_TEXT = "labeled_text"  # Text with timing labels
    ALIGNED_CHUNKS = "aligned_chunks"  # Aligned text chunks for debugging
    SUMMARY_JSON = "summary_json"  # JSON summary of the transcription
    TERMINOLOGY_JSON = "terminology_json"  # JSON of extracted terminology
    TRANSLATION_TXT = "translation_txt"  # Translated text files

    # Thumbnail types
    THUMBNAIL_SMALL = "thumbnail_small"
    THUMBNAIL_MEDIUM = "thumbnail_medium"
    THUMBNAIL_LARGE = "thumbnail_large"
    THUMBNAIL_POSTER = "thumbnail_poster"

class Job(Base):
    """Job model for video processing tasks"""
    
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_job_number = Column(Integer, nullable=False, index=True)  # User-specific job number (1, 2, 3, ...)
    title = Column(String(255), nullable=True)  # User-defined title for the job
    description = Column(Text, nullable=True)  # Optional description
    
    # Video processing settings
    source_language = Column(String, nullable=False)  # Original video language
    target_languages = Column(String, nullable=False)  # Comma-separated list of target languages
    source_video_url = Column(String(512), nullable=True)  # URL to the source video file in storage
    output_directory = Column(String, nullable=True)  # Directory where job outputs are stored
    video_filename = Column(String(255), nullable=True)  # Filename in the central upload directory
    content_hash = Column(String(64), nullable=True, index=True)  # Content hash for file organization and deduplication
    
    # Video information
    video_duration = Column(Float, nullable=True, index=True)  # Duration in seconds
    status_message = Column(String(500), nullable=True)  # Status message for the job
    
    # Processing options
    generate_subtitles = Column(Boolean, default=True)
    generate_dubbing = Column(Boolean, default=True)
    video_format = Column(String(10), default='mp4')
    resolution = Column(String(10), default='1080p')
    # Simplified subtitle style storage - store as JSON only
    subtitle_style = Column(JSONType, default=None, nullable=True)
    
    def get_subtitle_style_dict(self) -> Optional[Dict[str, Any]]:
        """Get subtitle style as a dictionary. Returns None for presets or invalid data."""
        if not self.subtitle_style:
            return None
            
        # If it's already a dict, return it
        if isinstance(self.subtitle_style, dict):
            return self.subtitle_style
            
        # If it's a preset string, return None (services handle presets)
        if isinstance(self.subtitle_style, str) and self.subtitle_style.lower() in ['default', 'outline', 'box']:
            return None
            
        # Log warning for invalid formats and return None
        logger.warning(f"Invalid subtitle_style format in job {getattr(self, 'id', 'unknown')}: {self.subtitle_style}")
        return None
    
    # We'll handle subtitle_languages in code since we don't have migrations
    # subtitle_languages = Column(JSON, default=list)  # List of selected subtitle languages
    
    # Result metadata (e.g., upload mode, audio file path)
    result_metadata = Column(JSONType, default=None, nullable=True)

    # Status tracking
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False)
    progress = Column(Integer, default=0, nullable=False)  # Progress percentage (0-100)
    error_message = Column(Text, nullable=True)  # Error details if job failed
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    started_at = Column(DateTime(timezone=True), nullable=True)  # When job began processing
    completed_at = Column(DateTime(timezone=True), nullable=True)  # When job finished (success or fail)
    
    # Relationships
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="jobs")
    # The JobResult class will be defined below, this relationship links to it.
    results = relationship("JobResult", back_populates="job", cascade="all, delete-orphan")
    
    # Subtitle editing relationships
    subtitle_edits = relationship("SubtitleEdit", back_populates="job", cascade="all, delete-orphan")
    subtitle_versions = relationship("SubtitleVersion", back_populates="job", cascade="all, delete-orphan")
    
    # Table constraints
    __table_args__ = (
        Index('idx_jobs_user_sequence', 'owner_id', 'user_job_number', unique=True),
    )

class JobResult(Base):
    """Model for storing individual results of a job (e.g., subtitle files, audio files)"""
    __tablename__ = "job_results"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    result_type = Column(Enum(ResultType), nullable=False)
    language = Column(String(10), nullable=True)  # e.g., 'en', 'es', 'fr-CA'
    file_path = Column(String(1024), nullable=False)  # Path to the result file within job's output directory or a full URL
    metadata_ = Column("metadata", JSONType, nullable=True)  # Using metadata_ to avoid conflict with SQLAlchemy internal 'metadata'
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    job = relationship("Job", back_populates="results")

    __table_args__ = (Index('ix_job_results_job_id_result_type_language', 'job_id', 'result_type', 'language', unique=True),)
