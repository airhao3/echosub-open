"""
User Feedback and Training Data Models for Data Flywheel System
"""
from sqlalchemy import BigInteger, Column, Integer, String, Float, Boolean, TIMESTAMP, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base


class UserFeedback(Base):
    """
    Store user corrections and adjustments to AI-generated content.
    This is the core data collection point for the data flywheel.
    """
    __tablename__ = "user_feedback"
    
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Type of feedback: 'transcription', 'translation', 'timing', 'style'
    feedback_type = Column(String(50), nullable=False, index=True)
    
    # Original AI-generated data
    original_data = Column(JSONB, nullable=True)
    
    # User-corrected data
    corrected_data = Column(JSONB, nullable=True)
    
    # Additional metadata (audio features, context, etc.)
    metadata = Column(JSONB, nullable=True)
    
    # Automatically calculated quality score (0.0 - 1.0)
    quality_score = Column(Float, nullable=True, index=True)
    
    # Whether this feedback has been verified by experts/other users
    verified = Column(Boolean, default=False, nullable=False)
    
    # Points awarded to the contributor
    contributor_points = Column(Integer, default=0, nullable=False)
    
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False, index=True)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="feedback_contributions")
    job = relationship("Job", back_populates="user_feedback")
    training_data = relationship("TrainingData", back_populates="source_feedback")


class TrainingData(Base):
    """
    Processed and validated data ready for model training.
    """
    __tablename__ = "training_data"
    
    id = Column(BigInteger, primary_key=True, index=True)
    
    # Type of training data: 'transcription', 'translation', 'timing', 'style'
    data_type = Column(String(50), nullable=False, index=True)
    
    # Reference to the original user feedback
    source_feedback_id = Column(BigInteger, ForeignKey("user_feedback.id", ondelete="SET NULL"), nullable=True)
    
    # Processed input data for training
    input_data = Column(JSONB, nullable=True)
    
    # Expected output/target data
    target_data = Column(JSONB, nullable=True)
    
    # Quality metrics and validation scores
    quality_metrics = Column(JSONB, nullable=True)
    
    # Model version this data is intended for
    model_version = Column(String(50), nullable=True, index=True)
    
    # Whether this data has been used in training
    used_in_training = Column(Boolean, default=False, nullable=False, index=True)
    
    # Training batch identifier
    training_batch_id = Column(String(100), nullable=True, index=True)
    
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    
    # Relationships
    source_feedback = relationship("UserFeedback", back_populates="training_data")


class ModelPerformance(Base):
    """
    Track model performance metrics and training results.
    """
    __tablename__ = "model_performance"
    
    id = Column(BigInteger, primary_key=True, index=True)
    
    # Model type: 'transcription', 'translation', 'timing'
    model_type = Column(String(50), nullable=False, index=True)
    
    # Model version identifier
    model_version = Column(String(50), nullable=False, index=True)
    
    # Performance metrics (accuracy, BLEU score, WER, etc.)
    performance_metrics = Column(JSONB, nullable=True)
    
    # Number of training samples used
    training_data_count = Column(Integer, nullable=True)
    
    # Number of validation samples used
    validation_data_count = Column(Integer, nullable=True)
    
    # Test results and benchmarks
    test_results = Column(JSONB, nullable=True)
    
    # Deployment status: 'pending', 'testing', 'deployed', 'retired'
    deployment_status = Column(String(20), default="pending", nullable=False, index=True)
    
    evaluation_date = Column(TIMESTAMP, server_default=func.now(), nullable=False)


class UserContributionStats(Base):
    """
    Aggregate statistics for user contributions to track engagement and rewards.
    """
    __tablename__ = "user_contribution_stats"
    
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Total number of contributions
    total_contributions = Column(Integer, default=0, nullable=False)
    
    # Total points earned
    total_points = Column(Integer, default=0, nullable=False, index=True)
    
    # Average quality score of contributions
    quality_average = Column(Float, nullable=True, index=True)
    
    # Current contribution streak (consecutive days)
    contribution_streak = Column(Integer, default=0, nullable=False)
    
    # Last contribution date
    last_contribution_date = Column(TIMESTAMP, nullable=True)
    
    # Bonus credits earned through contributions
    bonus_credits_earned = Column(Integer, default=0, nullable=False)
    
    # User tier based on contributions: 'bronze', 'silver', 'gold', 'platinum'
    tier_level = Column(String(20), default="bronze", nullable=False, index=True)
    
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="contribution_stats")


# Add these to existing models for relationships

# In app/models/user.py, add:
# feedback_contributions = relationship("UserFeedback", back_populates="user")
# contribution_stats = relationship("UserContributionStats", back_populates="user", uselist=False)

# In app/models/job.py, add:
# user_feedback = relationship("UserFeedback", back_populates="job")