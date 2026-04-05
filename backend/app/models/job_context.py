#!/usr/bin/env python3
"""
Job Context Model

A centralized data structure that holds all necessary context information for a job's file operations.
This ensures that required parameters like user_id and job_id are consistently available throughout
the processing pipeline, eliminating parameter-passing errors and improving code reliability.
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class JobContext(BaseModel):
    """
    Context object that encapsulates all job-related information needed for file operations.
    
    This object is created once at the beginning of job processing and passed to all
    services that need to perform file operations. It ensures that critical parameters
    like user_id and job_id are always available and correctly passed.
    
    Attributes:
        user_id: The ID of the user who owns this job
        job_id: The unique identifier for this job
        source_language: Optional source language code (e.g., 'en', 'zh')
        target_languages: Optional list of target language codes for translation
    """
    
    user_id: int = Field(..., description="The ID of the user who owns this job")
    job_id: int = Field(..., description="The unique identifier for this job")
    source_language: Optional[str] = Field(None, description="Source language code (e.g., 'en', 'zh')")
    target_languages: Optional[List[str]] = Field(default_factory=list, description="List of target language codes")
    
    class Config:
        """Pydantic configuration"""
        # Allow arbitrary types for flexibility
        arbitrary_types_allowed = True
        # Validate assignment to catch errors early
        validate_assignment = True
        # Use enum values instead of names for serialization
        use_enum_values = True
        
    def __str__(self) -> str:
        """String representation for logging and debugging"""
        return f"JobContext(user_id={self.user_id}, job_id={self.job_id}, source_lang={self.source_language})"
    
    def __repr__(self) -> str:
        """Detailed representation for debugging"""
        return (f"JobContext(user_id={self.user_id}, job_id={self.job_id}, "
                f"source_language='{self.source_language}', target_languages={self.target_languages})")
