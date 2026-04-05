from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Dict, Optional
from pydantic import BaseModel
import requests
import logging

from app.api import deps
from app.models.user import User
from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()
_settings = get_settings()

# Default processing preferences — populated from .env at startup
DEFAULT_PREFERENCES = {
    # Subtitle splitting
    "split_trigger_duration": 2.5,
    "split_trigger_words": 8,
    "pause_split_threshold": 0.3,
    "max_words_per_segment": 7,
    "split_on_comma": True,
    # LLM config
    "llm_base_url": _settings.OPENAI_BASE_URL,
    "llm_api_key": _settings.OPENAI_API_KEY,
    "llm_model": _settings.TRANSLATION_MODEL,
    "llm_temperature": _settings.TRANSLATION_TEMPERATURE,
    "llm_max_tokens": _settings.TRANSLATION_MAX_TOKENS,
    # Whisper config
    "whisper_api_url": "https://whisper.defaqman.com",
    "whisper_api_key": "",
    "whisper_model": "whisper-large-v3-turbo",
}


class ProcessingPreferences(BaseModel):
    # Subtitle splitting
    split_trigger_duration: Optional[float] = None
    split_trigger_words: Optional[int] = None
    pause_split_threshold: Optional[float] = None
    max_words_per_segment: Optional[int] = None
    split_on_comma: Optional[bool] = None
    # LLM config
    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = None
    llm_max_tokens: Optional[int] = None
    # Whisper config
    whisper_api_url: Optional[str] = None
    whisper_api_key: Optional[str] = None
    whisper_model: Optional[str] = None


@router.get("/status")
def get_account_status(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve current user's account status.
    Open-source version: no plan/subscription info.
    """
    return {
        "plan_name": "Open Source",
        "usage": {
            "video_minutes_used": current_user.video_minutes_used,
            "storage_used_mb": current_user.storage_used_mb,
            "projects_used": current_user.projects_used,
        }
    }


def _mask_key(key: str) -> str:
    """Mask API key for display: sk-abc...xyz"""
    if not key or len(key) < 8:
        return key or ""
    return key[:6] + "..." + key[-4:]


@router.get("/preferences")
def get_preferences(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get user's processing preferences."""
    prefs = {**DEFAULT_PREFERENCES, **(current_user.processing_preferences or {})}
    # Mask API key for display
    prefs["llm_api_key_display"] = _mask_key(prefs.get("llm_api_key", ""))
    return prefs


@router.put("/preferences")
def update_preferences(
    preferences: ProcessingPreferences,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update user's processing preferences."""
    # Re-fetch user within this session to ensure it's attached
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.processing_preferences = preferences.dict(exclude_none=True)
    db.commit()
    db.refresh(user)
    prefs = user.processing_preferences or {}
    return {**DEFAULT_PREFERENCES, **prefs}


class TestApiRequest(BaseModel):
    base_url: str
    api_key: Optional[str] = ""
    model: Optional[str] = ""
    type: str = "llm"  # "llm" or "whisper"


@router.post("/test-api")
def test_api_connection(req: TestApiRequest) -> Any:
    """Test API connectivity, key validity, and model availability."""
    base_url = req.base_url.rstrip('/')
    result = {"status": "error", "message": "", "models": []}

    try:
        if req.type == "llm":
            # Step 1: Test connection by listing models
            if base_url.endswith('/v1'):
                models_url = f"{base_url}/models"
            else:
                models_url = f"{base_url}/v1/models"

            headers = {}
            if req.api_key:
                headers["Authorization"] = f"Bearer {req.api_key}"

            resp = requests.get(models_url, headers=headers, timeout=10)

            if resp.status_code == 401:
                return {"status": "error", "message": "API 密钥无效", "models": []}
            if resp.status_code == 404:
                # Some APIs don't support /models — try a chat completion instead
                return _test_llm_chat(base_url, req.api_key, req.model)

            if resp.status_code == 200:
                data = resp.json()
                models = []
                if isinstance(data, dict) and 'data' in data:
                    models = [m.get('id', '') for m in data['data'] if m.get('id')]
                elif isinstance(data, list):
                    models = [m.get('id', '') for m in data if isinstance(m, dict) and m.get('id')]

                # Check if requested model is available
                model_ok = not req.model or req.model in models or len(models) == 0
                msg = "连接成功"
                if req.model and models and req.model not in models:
                    msg = f"连接成功，但模型 '{req.model}' 不在可用列表中"
                elif req.model and not models:
                    msg = "连接成功（API 未返回模型列表）"

                return {"status": "ok", "message": msg, "models": models[:20]}
            else:
                return {"status": "error", "message": f"API 返回 {resp.status_code}", "models": []}

        elif req.type == "whisper":
            # Test Whisper API — just check if endpoint is reachable
            test_url = f"{base_url}/api/v1/audio/transcriptions"
            resp = requests.post(test_url, data={"model": req.model or "whisper-1"}, timeout=10)
            # 400/500 with JSON error = API is working (just no file provided)
            if resp.status_code in [400, 500]:
                try:
                    err = resp.json()
                    return {"status": "ok", "message": "Whisper API 连接成功", "models": [req.model or "whisper-1"]}
                except Exception:
                    pass
            if resp.status_code == 200:
                return {"status": "ok", "message": "Whisper API 连接成功", "models": [req.model or "whisper-1"]}
            return {"status": "error", "message": f"Whisper API 返回 {resp.status_code}", "models": []}

    except requests.exceptions.Timeout:
        return {"status": "error", "message": "连接超时", "models": []}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "message": "无法连接到服务器", "models": []}
    except Exception as e:
        return {"status": "error", "message": str(e)[:100], "models": []}


def _test_llm_chat(base_url: str, api_key: str, model: str) -> dict:
    """Fallback: test LLM by sending a tiny chat completion."""
    try:
        if base_url.endswith('/v1'):
            url = f"{base_url}/chat/completions"
        else:
            url = f"{base_url}/v1/chat/completions"

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        data = {
            "model": model or "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 1,
        }
        resp = requests.post(url, json=data, headers=headers, timeout=15)

        if resp.status_code == 200:
            return {"status": "ok", "message": f"连接成功，模型 '{model}' 可用", "models": [model]}
        elif resp.status_code == 401:
            return {"status": "error", "message": "API 密钥无效", "models": []}
        elif resp.status_code == 404:
            return {"status": "error", "message": f"模型 '{model}' 不存在", "models": []}
        else:
            return {"status": "error", "message": f"API 返回 {resp.status_code}: {resp.text[:100]}", "models": []}
    except Exception as e:
        return {"status": "error", "message": str(e)[:100], "models": []}
