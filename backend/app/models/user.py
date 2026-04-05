from sqlalchemy import Boolean, Column, Integer, String, DateTime, Float, text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy import JSON
from .base import Base
from enum import Enum as PyEnum


class OAuthProvider(str, PyEnum):
    GITHUB = "github"
    GOOGLE = "google"


class User(Base):
    """User model for authentication"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)

    # Profile fields
    bio = Column(String, nullable=True)
    location = Column(String, nullable=True)
    website = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)

    # Processing preferences (JSON: subtitle splitting, LLM params, etc.)
    processing_preferences = Column(JSON, nullable=True, default=None)

    # Usage counters
    video_minutes_used = Column(Float, default=0, nullable=False)
    storage_used_mb = Column(Float, default=0, nullable=False)
    projects_used = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'), onupdate=text('CURRENT_TIMESTAMP'))

    # Relationships
    jobs = relationship("Job", back_populates="owner")
    subtitle_edits = relationship("SubtitleEdit", back_populates="user", cascade="all, delete-orphan")
