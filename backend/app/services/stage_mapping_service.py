"""
Stage Mapping Service for VideoLingo SaaS
Maps detailed backend processing stages to user-friendly frontend display stages
"""

from typing import Dict, List, Tuple, Optional
from enum import Enum
from app.services.processing_logger import ProcessingStage

class FrontendStage(str, Enum):
    """User-friendly frontend stage representation"""
    # Main processing phases
    UPLOADING = "UPLOADING"
    ANALYZING = "ANALYZING" 
    TRANSCRIBING = "TRANSCRIBING"
    TRANSLATING = "TRANSLATING"
    GENERATING = "GENERATING"
    FINALIZING = "FINALIZING"
    
    # Terminal states
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class StageGroup:
    """Represents a group of backend stages mapped to a single frontend stage"""
    
    def __init__(self, frontend_stage: FrontendStage, name: str, description: str, 
                 backend_stages: List[str], icon: str = "⏳"):
        self.frontend_stage = frontend_stage
        self.name = name
        self.description = description
        self.backend_stages = backend_stages
        self.icon = icon
        self.weight = len(backend_stages)  # Weight for progress calculation

class StageMappingService:
    """Service for mapping backend stages to frontend display stages"""
    
    # Define stage groups with their corresponding backend stages
    STAGE_GROUPS: List[StageGroup] = [
        StageGroup(
            frontend_stage=FrontendStage.UPLOADING,
            name="Uploading",
            description="Uploading and preparing your video",
            backend_stages=[
                ProcessingStage.INITIALIZED,
                ProcessingStage.VIDEO_DOWNLOAD,
                ProcessingStage.PREPROCESSING
            ],
            icon="📥"
        ),
        StageGroup(
            frontend_stage=FrontendStage.ANALYZING,
            name="Analyzing",
            description="Extracting audio and analyzing content",
            backend_stages=[
                ProcessingStage.AUDIO_EXTRACTION
            ],
            icon="🔍"
        ),
        StageGroup(
            frontend_stage=FrontendStage.TRANSCRIBING,
            name="Transcribing",
            description="Converting speech to text",
            backend_stages=[
                ProcessingStage.TRANSCRIPTION,
                ProcessingStage.TEXT_SEGMENTATION,
                ProcessingStage.TEXT_TAGGING,
                ProcessingStage.TEXT_REFINEMENT
            ],
            icon="🔤"
        ),
        StageGroup(
            frontend_stage=FrontendStage.TRANSLATING,
            name="Translating",
            description="Translating and optimizing text",
            backend_stages=[
                ProcessingStage.SEMANTIC_ANALYSIS,
                ProcessingStage.TERMINOLOGY_EXTRACTION,
                ProcessingStage.TRANSLATION
            ],
            icon="🌐"
        ),
        StageGroup(
            frontend_stage=FrontendStage.GENERATING,
            name="Generating",
            description="Creating subtitles and processing video",
            backend_stages=[
                ProcessingStage.SUBTITLE_GENERATION,
                ProcessingStage.DUBBING,  # Optional
                ProcessingStage.VIDEO_PROCESSING  # Optional
            ],
            icon="🎬"
        ),
        StageGroup(
            frontend_stage=FrontendStage.FINALIZING,
            name="Finalizing",
            description="Exporting files and cleanup",
            backend_stages=[
                ProcessingStage.FILE_EXPORT,
                ProcessingStage.CLEANUP
            ],
            icon="📁"
        )
    ]
    
    @classmethod
    def get_stage_groups(cls) -> List[StageGroup]:
        """Get all defined stage groups"""
        return cls.STAGE_GROUPS
    
    @classmethod
    def get_frontend_stage_for_backend_stage(cls, backend_stage: str) -> Optional[FrontendStage]:
        """Map a backend stage to its corresponding frontend stage"""
        for group in cls.STAGE_GROUPS:
            if backend_stage in group.backend_stages:
                return group.frontend_stage
        return None
    
    @classmethod
    def get_stage_group_for_backend_stage(cls, backend_stage: str) -> Optional[StageGroup]:
        """Get the stage group that contains a specific backend stage"""
        for group in cls.STAGE_GROUPS:
            if backend_stage in group.backend_stages:
                return group
        return None
    
    @classmethod
    def calculate_frontend_progress(cls, completed_backend_stages: List[str], 
                                   current_stage: Optional[str] = None, 
                                   current_stage_progress: float = 0.0) -> Dict[str, any]:
        """
        Calculate progress for each frontend stage based on completed backend stages
        
        Args:
            completed_backend_stages: List of completed backend stage names
            current_stage: Currently processing backend stage (optional)
            current_stage_progress: Progress of current stage (0-100)
            
        Returns:
            Dictionary with frontend stage progress information
        """
        result = {
            "overall_progress": 0.0,
            "stages": {},
            "current_frontend_stage": None,
            "current_stage_name": None
        }
        
        total_backend_stages = len(ProcessingStage.get_processing_stages())
        completed_count = len(completed_backend_stages)
        
        # Calculate overall progress
        if current_stage and current_stage in ProcessingStage.get_processing_stages():
            # Add partial progress from current stage
            current_stage_weight = current_stage_progress / 100.0
            result["overall_progress"] = ((completed_count + current_stage_weight) / total_backend_stages) * 100
        else:
            result["overall_progress"] = (completed_count / total_backend_stages) * 100
        
        # Calculate progress for each frontend stage group
        for group in cls.STAGE_GROUPS:
            # Count completed stages in this group
            group_completed = len([s for s in completed_backend_stages if s in group.backend_stages])
            group_total = len(group.backend_stages)
            
            # Check if current stage is in this group
            group_current_progress = 0.0
            is_current_group = current_stage in group.backend_stages if current_stage else False
            
            if is_current_group:
                # Add partial progress from current stage
                group_current_progress = current_stage_progress / group_total
            
            # Calculate group progress percentage
            if group_total > 0:
                base_progress = (group_completed / group_total) * 100
                group_progress = min(base_progress + group_current_progress, 100.0)
            else:
                group_progress = 0.0
            
            # Determine group status
            if group_progress >= 100.0:
                group_status = "completed"
            elif group_progress > 0.0 or is_current_group:
                group_status = "processing"
            else:
                group_status = "pending"
            
            result["stages"][group.frontend_stage] = {
                "name": group.name,
                "description": group.description,
                "progress": group_progress,
                "status": group_status,
                "icon": group.icon,
                "completed_substeps": group_completed,
                "total_substeps": group_total,
                "backend_stages": group.backend_stages
            }
            
            # Set current frontend stage
            if is_current_group:
                result["current_frontend_stage"] = group.frontend_stage
                result["current_stage_name"] = group.name
        
        return result
    
    @classmethod
    def get_user_friendly_status_message(cls, backend_stage: str, 
                                        backend_message: str = "") -> str:
        """Convert backend stage and message to user-friendly status message"""
        
        stage_messages = {
            ProcessingStage.INITIALIZED: "Initializing video processing...",
            ProcessingStage.VIDEO_DOWNLOAD: "Downloading your video...",
            ProcessingStage.PREPROCESSING: "Preparing video for processing...",
            ProcessingStage.AUDIO_EXTRACTION: "Extracting audio from video...",
            ProcessingStage.TRANSCRIPTION: "Converting speech to text...",
            ProcessingStage.TEXT_SEGMENTATION: "Analyzing text structure...",
            ProcessingStage.TEXT_TAGGING: "Organizing text segments...",
            ProcessingStage.TEXT_REFINEMENT: "Optimizing transcription quality...",
            ProcessingStage.SEMANTIC_ANALYSIS: "Understanding content context...",
            ProcessingStage.TERMINOLOGY_EXTRACTION: "Identifying key terms...",
            ProcessingStage.TRANSLATION: "Translating to target language...",
            ProcessingStage.SUBTITLE_GENERATION: "Creating subtitle files...",
            ProcessingStage.DUBBING: "Generating voice dubbing...",
            ProcessingStage.VIDEO_PROCESSING: "Adding subtitles to video...",
            ProcessingStage.FILE_EXPORT: "Preparing final files...",
            ProcessingStage.CLEANUP: "Finishing up...",
            ProcessingStage.COMPLETED: "Processing completed successfully!",
            ProcessingStage.FAILED: "Processing failed. Please try again."
        }
        
        user_message = stage_messages.get(backend_stage, f"Processing: {backend_stage}")
        
        # Include backend message if it provides additional context
        if backend_message and backend_message.strip() and backend_message != backend_stage:
            user_message += f" ({backend_message})"
            
        return user_message
    
    @classmethod
    def get_simplified_steps_for_frontend(cls) -> List[Dict[str, any]]:
        """Get simplified step configuration for frontend components"""
        steps = []
        
        for group in cls.STAGE_GROUPS:
            steps.append({
                "id": group.frontend_stage,
                "name": group.name,
                "description": group.description,
                "icon": group.icon,
                "status": "pending",
                "progress": 0,
                "backend_stages": group.backend_stages
            })
            
        return steps
    
    @classmethod 
    def create_progress_update_for_frontend(cls, job_id: int, backend_stages_completed: List[str],
                                          current_stage: Optional[str] = None,
                                          current_progress: float = 0.0,
                                          status_message: str = "") -> Dict[str, any]:
        """
        Create a complete progress update suitable for frontend consumption
        
        This method transforms detailed backend stage information into a simplified
        frontend-friendly format with grouped stages and user-friendly messages.
        """
        
        progress_data = cls.calculate_frontend_progress(
            completed_backend_stages=backend_stages_completed,
            current_stage=current_stage, 
            current_stage_progress=current_progress
        )
        
        # Generate user-friendly status message
        if current_stage:
            friendly_message = cls.get_user_friendly_status_message(current_stage, status_message)
        else:
            friendly_message = status_message or "Processing..."
        
        # Create step array for frontend components
        steps = []
        for group in cls.STAGE_GROUPS:
            stage_info = progress_data["stages"].get(group.frontend_stage, {})
            steps.append({
                "step_name": group.frontend_stage,
                "name": group.name,
                "status": stage_info.get("status", "pending"),
                "progress": stage_info.get("progress", 0),
                "details": stage_info.get("description", ""),
                "icon": group.icon
            })
        
        return {
            "job_id": job_id,
            "status": "PROCESSING" if progress_data["overall_progress"] < 100 else "COMPLETED",
            "progress": progress_data["overall_progress"],
            "message": friendly_message,
            "status_message": friendly_message,
            "current_stage": progress_data["current_frontend_stage"],
            "steps": steps,
            "detailed_progress": progress_data  # Include full details for advanced views
        }