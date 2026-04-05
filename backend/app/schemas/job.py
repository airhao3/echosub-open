from pydantic import BaseModel, Field, validator, HttpUrl
from typing import Optional, List, Dict, Union, Any, Literal
from datetime import datetime
import json
import re
from app.models.job import JobStatus

# Subtitle style model with all available parameters
def convert_color_format(color: str) -> str:
    """Convert #RRGGBB to &H00RRGGBB or validate &HAABBGGRR format"""
    if not color:
        return "&H00FFFFFF"
        
    # If already in &HAABBGGRR format
    if color.startswith('&H') and len(color) == 10:
        if not all(c.upper() in '0123456789ABCDEF' for c in color[2:]):
            raise ValueError(f"Invalid hex color: {color}")
        return color.upper()
    
    # If in #RRGGBB format
    if color.startswith('#') and len(color) == 7:
        try:
            # Convert #RRGGBB to &H00RRGGBB
            r, g, b = color[1:3], color[3:5], color[5:7]
            return f"&H00{r.upper()}{g.upper()}{b.upper()}"
        except (ValueError, IndexError):
            raise ValueError(f"Invalid hex color: {color}")
    
    raise ValueError(f"Color must be in #RRGGBB or &HAABBGGRR format, got {color}")

class SubtitleStyle(BaseModel):
    # Basic controls
    font_size: int = Field(12, ge=8, le=72, description="Font size in pixels (8-72)")
    font_color: str = Field(
        "&H00FFFFFF", 
        description="Text color in #RRGGBB or &HAABBGGRR format (AABBGGRR), e.g., #FFFFFF or &H00FFFFFF for white"
    )
    back_color: str = Field(
        "&H99000000", 
        description="Background color in #RRGGBB or &HAABBGGRR format (AABBGGRR), e.g., #00000080 or &H80000000 for semi-transparent black"
    )
    
    @validator('font_color', 'back_color')
    def validate_color_format(cls, v):
        return convert_color_format(v)
    position: Union[Literal['top', 'middle', 'bottom'], int] = Field(
        'bottom',
        description="Vertical position of subtitles ('top', 'middle', 'bottom' or FFmpeg alignment number)"
    )
    
    @validator('position')
    def validate_position(cls, v):
        if isinstance(v, int):
            # Convert FFmpeg alignment number to position string
            position_map = {8: 'top', 5: 'middle', 2: 'bottom'}
            if v in position_map:
                return position_map[v]
            return 'bottom'  # Default to bottom for unknown numbers
        return v
    
    # Advanced controls
    font_name: str = Field(
        "Arial, Microsoft YaHei, Noto Sans CJK SC, Noto Sans SC, SimHei, sans-serif",
        description="Comma-separated list of font families in order of preference"
    )
    bold: bool = Field(False, description="Use bold text")
    italic: bool = Field(False, description="Use italic text")
    border_style: Literal[1, 3] = Field(
        3, 
        description="1=Outline, 3=Opaque box"
    )
    outline_width: int = Field(0, ge=0, le=10, description="Outline width in pixels")
    shadow: float = Field(0.7, ge=0, le=1, description="Shadow opacity (0-1)")
    margin_v: int = Field(30, ge=0, le=200, description="Vertical margin in pixels")
    alignment: int = Field(2, ge=1, le=9, description="Numeric keypad position (1-9, 5=center)")
    scale_x: int = Field(100, ge=50, le=200, description="Horizontal scaling (50-200%)")
    scale_y: int = Field(100, ge=50, le=200, description="Vertical scaling (50-200%)")
    
    @validator('position')
    def set_alignment_based_on_position(cls, v, values):
        """Set alignment based on position if not explicitly set"""
        if 'alignment' not in values:
            return {'top': 8, 'middle': 5, 'bottom': 2}.get(v, 2)
        return values.get('alignment')
    
    class Config:
        json_schema_extra = {
            "example": {
                "font_size": 12,
                "font_color": "&H00FFFFFF",
                "back_color": "&H99000000",
                "position": "bottom",
                "font_name": "Arial, Microsoft YaHei, sans-serif",
                "bold": False,
                "italic": False,
                "border_style": 3,
                "outline_width": 0,
                "shadow": 0.7,
                "margin_v": 30,
                "alignment": 2,
                "scale_x": 100,
                "scale_y": 100
            }
        }

class JobBase(BaseModel):
    video_duration: Optional[float] = None
    title: str
    description: Optional[str] = None
    source_language: str
    target_languages: str  # Comma-separated list of languages
    generate_subtitles: bool = True
    generate_dubbing: bool = True
    
    @validator('generate_subtitles', 'generate_dubbing', pre=True)
    def ensure_boolean_values(cls, v):
        """Ensure boolean fields are not None"""
        if v is None:
            return True
        return v
    subtitle_languages: Optional[List[str]] = Field(default_factory=list)  # List of language codes for subtitles

    # Output settings
    video_format: Optional[str] = Field('mp4', description="Output video format (mp4, mov, etc.)")
    resolution: Optional[str] = Field('1080p', description="Output video resolution")
    subtitle_style: Optional[Union[SubtitleStyle, Dict[str, Any]]] = Field(
        default_factory=SubtitleStyle,
        description="Subtitle styling parameters"
    )
    
    @validator('subtitle_style', pre=True)
    def parse_subtitle_style(cls, v):
        if v is None or v == 'default':
            return SubtitleStyle()
        if isinstance(v, str):
            try:
                v = json.loads(v) if v.startswith('{') else {}
            except json.JSONDecodeError:
                v = {}
        if isinstance(v, dict):
            return SubtitleStyle(**v)
        return v

class JobCreate(JobBase):
    source_video_url: str
    content_hash: str = Field(..., description="SHA-256 hash of the video file content for deduplication")

class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_languages: Optional[str] = None
    generate_subtitles: Optional[bool] = None
    generate_dubbing: Optional[bool] = None
    status: Optional[JobStatus] = None

class JobInDBBase(JobBase):
    id: int
    user_job_number: int
    owner_id: int
    source_video_url: Optional[str] = None
    output_directory: Optional[str] = None
    status: JobStatus
    progress: int = 0
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Job(JobInDBBase):
    pass

class JobInDB(JobInDBBase):
    pass

class JobResponse(JobInDBBase):
    """Job model for API responses."""
    thumbnails: Optional[Dict[str, str]] = Field(default_factory=dict, description="URLs for different thumbnail sizes")

    
    @validator('subtitle_style', pre=True)
    def ensure_subtitle_style_dict(cls, v):
        if v is None:
            return {}
        if isinstance(v, str):
            try:
                return json.loads(v) if v.startswith('{') else {}
            except json.JSONDecodeError:
                return {}
        if hasattr(v, 'dict'):  # If it's a Pydantic model
            return v.dict(exclude_unset=True, exclude_none=True)
        return v
    
    class Config:
        from_attributes = True
        json_encoders = {
            'dict': lambda v: v,  # Ensure dicts are passed through as-is
            'SubtitleStyle': lambda v: v.dict(exclude_unset=True, exclude_none=True)
        }

class JobBulkDelete(BaseModel):
    job_ids: List[int]
