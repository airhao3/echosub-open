"""
Pydantic schemas for user feedback and data flywheel system
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, validator


class UserFeedbackBase(BaseModel):
    """Base schema for user feedback"""
    job_id: int
    feedback_type: str = Field(..., regex="^(transcription|translation|timing|style)$")
    original_data: Optional[Dict[str, Any]] = None
    corrected_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class UserFeedbackCreate(UserFeedbackBase):
    """Schema for creating user feedback"""
    pass
    
    @validator('feedback_type')
    def validate_feedback_type(cls, v):
        allowed_types = ['transcription', 'translation', 'timing', 'style']
        if v not in allowed_types:
            raise ValueError(f'feedback_type must be one of {allowed_types}')
        return v
    
    @validator('corrected_data')
    def validate_corrected_data(cls, v, values):
        if not v and not values.get('original_data'):
            raise ValueError('Either corrected_data or original_data must be provided')
        return v


class UserFeedbackUpdate(BaseModel):
    """Schema for updating user feedback"""
    corrected_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class UserFeedbackResponse(UserFeedbackBase):
    """Schema for user feedback response"""
    id: int
    user_id: int
    quality_score: Optional[float] = None
    verified: bool = False
    contributor_points: int = 0
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FeedbackQualityAssessment(BaseModel):
    """Schema for peer feedback quality assessment"""
    quality_score: float = Field(..., ge=0.0, le=1.0)
    assessment_notes: Optional[str] = None
    helpful: bool = True


class ContributionStatsResponse(BaseModel):
    """Schema for user contribution statistics"""
    user_id: int
    total_contributions: int = 0
    total_points: int = 0
    quality_average: Optional[float] = None
    contribution_streak: int = 0
    last_contribution_date: Optional[datetime] = None
    bonus_credits_earned: int = 0
    tier_level: str = "bronze"
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TrainingDataBase(BaseModel):
    """Base schema for training data"""
    data_type: str = Field(..., regex="^(transcription|translation|timing|style)$")
    input_data: Optional[Dict[str, Any]] = None
    target_data: Optional[Dict[str, Any]] = None
    quality_metrics: Optional[Dict[str, Any]] = None
    model_version: Optional[str] = None


class TrainingDataCreate(TrainingDataBase):
    """Schema for creating training data"""
    source_feedback_id: Optional[int] = None


class TrainingDataResponse(TrainingDataBase):
    """Schema for training data response"""
    id: int
    source_feedback_id: Optional[int] = None
    used_in_training: bool = False
    training_batch_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ModelPerformanceBase(BaseModel):
    """Base schema for model performance"""
    model_type: str = Field(..., regex="^(transcription|translation|timing)$")
    model_version: str
    performance_metrics: Optional[Dict[str, Any]] = None
    training_data_count: Optional[int] = None
    validation_data_count: Optional[int] = None
    test_results: Optional[Dict[str, Any]] = None


class ModelPerformanceCreate(ModelPerformanceBase):
    """Schema for creating model performance record"""
    pass


class ModelPerformanceResponse(ModelPerformanceBase):
    """Schema for model performance response"""
    id: int
    deployment_status: str = "pending"
    evaluation_date: datetime
    
    class Config:
        from_attributes = True


class QualityTrendPoint(BaseModel):
    """Schema for quality trend data point"""
    date: datetime
    average_quality: float
    feedback_count: int
    feedback_type: Optional[str] = None


class QualityTrendsResponse(BaseModel):
    """Schema for quality trends response"""
    period_days: int
    trends: List[QualityTrendPoint]
    overall_average: float
    total_feedback_count: int


class BatchFeedbackResult(BaseModel):
    """Schema for batch feedback submission result"""
    feedback_id: Optional[int] = None
    job_id: Optional[int] = None
    status: str  # 'success' or 'error'
    message: Optional[str] = None
    points_earned: Optional[int] = None


class BatchFeedbackResponse(BaseModel):
    """Schema for batch feedback response"""
    results: List[BatchFeedbackResult]
    total_submitted: int
    successful: int
    total_points_earned: int


# Specific feedback type schemas for better validation

class TranscriptionFeedbackData(BaseModel):
    """Schema for transcription feedback data"""
    original_text: str
    corrected_text: str
    start_time: float
    end_time: float
    confidence_score: Optional[float] = None
    speaker_id: Optional[str] = None
    correction_type: List[str] = Field(default_factory=list)  # ['text', 'timing', 'speaker']


class TranslationFeedbackData(BaseModel):
    """Schema for translation feedback data"""
    source_text: str
    ai_translation: str
    user_translation: str
    source_language: str
    target_language: str
    context: Optional[str] = None
    domain: Optional[str] = None
    difficulty_level: Optional[str] = None


class TimingFeedbackData(BaseModel):
    """Schema for timing adjustment feedback"""
    original_start: float
    original_end: float
    adjusted_start: float
    adjusted_end: float
    subtitle_text: str
    adjustment_reason: Optional[str] = None
    video_metadata: Optional[Dict[str, Any]] = None


class StyleFeedbackData(BaseModel):
    """Schema for style preference feedback"""
    original_style: Dict[str, Any]
    preferred_style: Dict[str, Any]
    video_type: Optional[str] = None
    device_type: Optional[str] = None
    user_preferences: Optional[Dict[str, Any]] = None


class FeedbackAnalytics(BaseModel):
    """Schema for feedback analytics"""
    total_feedback: int
    quality_distribution: Dict[str, int]  # quality score ranges
    type_distribution: Dict[str, int]     # feedback types
    user_participation: Dict[str, int]    # user tier participation
    improvement_metrics: Dict[str, float] # model improvement metrics


class UserRewards(BaseModel):
    """Schema for user rewards calculation"""
    current_points: int
    points_to_next_tier: int
    current_tier: str
    next_tier: Optional[str] = None
    bonus_credits: int
    weekly_goal: int
    weekly_progress: int