from typing import List
from fastapi import APIRouter

from app.schemas.language import Language
from app.core.languages import SOURCE_LANGUAGES, TARGET_LANGUAGES

router = APIRouter()


@router.get("/source", response_model=List[Language])
def get_source_languages():
    """
    Retrieve the list of supported source languages for transcription (based on Whisper).
    """
    return SOURCE_LANGUAGES


@router.get("/target", response_model=List[Language])
def get_target_languages():
    """
    Retrieve the list of supported target languages for translation (based on Gemini).
    """
    return TARGET_LANGUAGES
