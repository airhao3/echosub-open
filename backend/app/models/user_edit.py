"""
Simple User Edit Model for Data Collection
"""
from sqlalchemy import BigInteger, Column, Integer, String, Float, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base


class UserEdit(Base):
    """
    Simple model to track user edits for data flywheel.
    Captures all types of user adjustments in a single table.
    """
    __tablename__ = "user_edits"
    
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Allow anonymous
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Type of edit: 'subtitle_edit', 'timing_adjustment', 'translation_choice', 'style_change'
    edit_type = Column(String(50), nullable=False, index=True)
    
    # Original AI-generated data
    original_data = Column(JSONB, nullable=True)
    
    # User-modified data
    user_data = Column(JSONB, nullable=True)
    
    # Additional metadata (language, confidence, etc.)
    metadata = Column(JSONB, nullable=True)
    
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False, index=True)
    
    # Whether this edit has been used for training
    processed = Column(Boolean, default=False, nullable=False, index=True)
    
    # Simple quality score (0.0 - 1.0), calculated automatically
    quality_score = Column(Float, nullable=True, index=True)
    
    # Relationships
    user = relationship("User", back_populates="edits")
    job = relationship("Job", back_populates="user_edits")


# Add this to existing models for relationships:

# In app/models/user.py, add:
# edits = relationship("UserEdit", back_populates="user")

# In app/models/job.py, add:
# user_edits = relationship("UserEdit", back_populates="job")