"""
Language Slots management endpoints
"""
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.services.language_slots_service import LanguageSlotsService

router = APIRouter()

@router.get("/report", response_model=Dict[str, Any])
def get_language_usage_report(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get a detailed language usage report for the current user.
    """
    report = LanguageSlotsService.get_language_usage_report(db, current_user.id)
    return report

@router.post("/check-quota", response_model=Dict[str, Any])
def check_language_quota(
    target_languages: str,
    calculation_method: str = "cumulative",
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Check if user can create a job with specified target languages.
    
    Args:
        target_languages: Comma-separated language codes (e.g., "es,fr,de")
        calculation_method: How to calculate usage ("cumulative", "concurrent", "additive")
    """
    allowed, message, details = LanguageSlotsService.check_language_slots_quota(
        db, current_user.id, target_languages, calculation_method
    )
    
    language_slots_needed = LanguageSlotsService.calculate_language_slots_from_string(target_languages)
    
    return {
        "allowed": allowed,
        "message": message,
        "language_slots_needed": language_slots_needed,
        "target_languages": target_languages.split(',') if target_languages else [],
        "calculation_method": calculation_method,
        "quota_details": details
    }

@router.post("/update-usage", response_model=Dict[str, Any])
def update_language_usage(
    calculation_method: str = "cumulative",
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Manually update user's language slots usage based on actual job data.
    
    Args:
        calculation_method: How to calculate usage ("cumulative", "concurrent", "additive")
    """
    try:
        new_usage = LanguageSlotsService.update_user_language_slots_usage(
            db, current_user.id, calculation_method
        )
        
        return {
            "success": True,
            "new_usage": new_usage,
            "calculation_method": calculation_method,
            "message": f"Language slots usage updated to {new_usage} using {calculation_method} method"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update language usage: {str(e)}"
        )