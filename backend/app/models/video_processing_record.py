from sqlalchemy import Boolean, Column, Integer, String, Float, Text, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
import datetime
from .base import Base


class VideoProcessingRecord(Base):
    """
    Model to track video processing history using content hash
    This allows identifying already processed videos and their processing history
    """
    
    __tablename__ = "video_processing_records"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Video identification
    content_hash = Column(String, nullable=False, index=True)  # Hash of video content for identification
    original_filename = Column(String, nullable=True)  # Original filename for reference
    
    # Processing details
    language = Column(String, nullable=False)  # Language the video was processed for
    process_type = Column(String, nullable=False)  # Type of processing (subtitles, dubbing, etc.)
    
    # Processing metrics
    process_count = Column(Integer, default=1)  # Number of times this video was processed
    last_processed_at = Column(DateTime, default=func.now())  # When the video was last processed
    first_processed_at = Column(DateTime, default=func.now())  # When the video was first processed
    
    # Related job tracking
    job_ids = Column(JSON, default=lambda: [], nullable=False)  # List of job IDs that processed this video
    
    # Result information
    result_path = Column(String, nullable=True)  # Path to the processed result
    
    # Status information
    is_processing = Column(Boolean, default=False)  # Whether the video is currently being processed
    
    def __repr__(self):
        return f"<VideoProcessingRecord(content_hash='{self.content_hash}', language='{self.language}', process_count={self.process_count})>"
    
    def update_processing(self, job_id=None):
        """
        Update when a video is processed again
        """
        self.process_count += 1
        self.last_processed_at = func.now()
        
        # Ensure job_ids is a list
        if self.job_ids is None:
            self.job_ids = []
            
        if job_id and job_id not in self.job_ids:
            self.job_ids.append(job_id)
            
        self.is_processing = True
    
    def mark_completed(self, result_path=None):
        """
        Mark processing as completed
        """
        if result_path:
            self.result_path = result_path
        self.is_processing = False
