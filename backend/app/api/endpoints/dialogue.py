"""
API endpoints for dialogue translation with context awareness.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.services.workflow_service import WorkflowService
from app.services.job_service import JobService

router = APIRouter()

class DialogueSegment(BaseModel):
    """Represents a single dialogue segment for translation."""
    text: str = Field(..., description="The text content of the segment")
    id: Optional[str] = Field(None, description="Optional identifier for the segment")

class DialogueTranslationRequest(BaseModel):
    """Request model for dialogue translation."""
    segments: List[DialogueSegment] = Field(..., description="List of dialogue segments to translate")
    source_lang: str = Field(..., description="Source language code (e.g., 'en')")
    target_lang: str = Field(..., description="Target language code (e.g., 'zh')")
    job_id: Optional[int] = Field(None, description="Optional job ID for tracking")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

@router.post("/translate")
async def translate_dialogue(
    request: DialogueTranslationRequest,
    db=Depends(get_db)
) -> Dict[str, Any]:
    """
    Translate dialogue segments with context awareness.
    
    This endpoint takes a list of dialogue segments and translates them while maintaining
    context between segments for better translation quality.
    """
    workflow_service = WorkflowService(db)
    
    # Convert segments to list of dicts for service layer
    segments = [
        {"text": seg.text, "id": seg.id or str(i)}
        for i, seg in enumerate(request.segments)
    ]
    
    # Call the workflow service
    result = workflow_service.translate_dialogue_segments(
        segments=segments,
        source_lang=request.source_lang,
        target_lang=request.target_lang,
        job_id=request.job_id,
        metadata=request.metadata
    )
    
    if result['status'] == 'error':
        raise HTTPException(status_code=400, detail=result['error'])
    
    return result
