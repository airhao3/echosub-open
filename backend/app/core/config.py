from pydantic import validator
from typing import Union
from pydantic_settings import BaseSettings
from functools import lru_cache
import os
import logging
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    PROJECT_NAME: str = "EchoSub"
    API_V1_STR: str = "/api/v1"

    # Database — defaults to SQLite for easy open-source setup
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/echosub.db")

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return self.DATABASE_URL

    # JWT Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Celery configuration
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

    # File storage configuration
    STORAGE_BASE_DIR: str = os.getenv(
        "STORAGE_BASE_DIR",
        os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..", "files"))
    )
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", os.path.join(STORAGE_BASE_DIR, "uploads"))
    JOB_DIR: str = os.getenv("JOB_DIR", os.path.join(STORAGE_BASE_DIR, "jobs"))

    # ---- Translation API (OpenAI-compatible) ----
    # Supports OpenAI, DeepSeek, local LLMs, or any OpenAI-compatible endpoint
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    TRANSLATION_MODEL: str = os.getenv("TRANSLATION_MODEL", "gemini-2.5-flash")
    TRANSLATION_TEMPERATURE: float = float(os.getenv("TRANSLATION_TEMPERATURE", "0.7"))
    TRANSLATION_MAX_TOKENS: int = int(os.getenv("TRANSLATION_MAX_TOKENS", "8000"))
    TRANSLATION_TIMEOUT: int = int(os.getenv("TRANSLATION_TIMEOUT", "180"))

    # Legacy aliases — map old YUNWU_* / TRANSLATOR_* env vars for backward compatibility
    @property
    def YUNWU_API_KEY(self) -> str:
        return os.getenv("YUNWU_API_KEY", self.OPENAI_API_KEY)

    @property
    def YUNWU_BASE_URL(self) -> str:
        return os.getenv("YUNWU_BASE_URL", self.OPENAI_BASE_URL)

    @property
    def YUNWU_MODEL(self) -> str:
        return os.getenv("YUNWU_MODEL", self.TRANSLATION_MODEL)

    @property
    def YUNWU_TEMPERATURE(self) -> float:
        return float(os.getenv("YUNWU_TEMPERATURE", str(self.TRANSLATION_TEMPERATURE)))

    @property
    def YUNWU_MAX_TOKENS(self) -> int:
        return int(os.getenv("YUNWU_MAX_TOKENS", str(self.TRANSLATION_MAX_TOKENS)))

    @property
    def YUNWU_TIMEOUT(self) -> int:
        return int(os.getenv("YUNWU_TIMEOUT", str(self.TRANSLATION_TIMEOUT)))

    YUNWU_API_VERSION: str = os.getenv("YUNWU_API_VERSION", "2023-05-15")
    YUNWU_ORGANIZATION: str = os.getenv("YUNWU_ORGANIZATION", "")

    @property
    def TRANSLATOR_API_KEY(self) -> str:
        return os.getenv("TRANSLATOR_API_KEY", self.OPENAI_API_KEY)

    @property
    def TRANSLATOR_BASE_URL(self) -> str:
        return os.getenv("TRANSLATOR_BASE_URL", self.OPENAI_BASE_URL)

    @property
    def TRANSLATOR_MODEL(self) -> str:
        return os.getenv("TRANSLATOR_MODEL", self.TRANSLATION_MODEL)

    @property
    def TRANSLATOR_TEMPERATURE(self) -> float:
        return float(os.getenv("TRANSLATOR_TEMPERATURE", str(self.TRANSLATION_TEMPERATURE)))

    @property
    def TRANSLATOR_MAX_TOKENS(self) -> int:
        return int(os.getenv("TRANSLATOR_MAX_TOKENS", str(self.TRANSLATION_MAX_TOKENS)))

    @property
    def TRANSLATOR_TIMEOUT(self) -> int:
        return int(os.getenv("TRANSLATOR_TIMEOUT", str(self.TRANSLATION_TIMEOUT)))

    # Processing configuration
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "large-v2")
    TRANSLATION_PROVIDER: str = os.getenv("TRANSLATION_PROVIDER", "yunwu")
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "5"))
    MAX_SPLIT_LENGTH: int = int(os.getenv("MAX_SPLIT_LENGTH", "30"))
    SPLIT_TOLERANCE: int = int(os.getenv("SPLIT_TOLERANCE", "20"))
    TRANSLATION_WORKERS: int = int(os.getenv("TRANSLATION_WORKERS", "5"))
    ENABLE_TAG_REALIGNMENT: bool = os.getenv("ENABLE_TAG_REALIGNMENT", "true").lower() == "true"

    # Debug mode
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Frontend configuration
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:8080")

    # Redis configuration
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # Subtitle text limits
    SUBTITLE_CHINESE_HORIZONTAL_MAX: int = int(os.getenv("SUBTITLE_CHINESE_HORIZONTAL_MAX", "20"))
    SUBTITLE_CHINESE_VERTICAL_MAX: int = int(os.getenv("SUBTITLE_CHINESE_VERTICAL_MAX", "15"))
    SUBTITLE_ENGLISH_HORIZONTAL_MAX: int = int(os.getenv("SUBTITLE_ENGLISH_HORIZONTAL_MAX", "42"))
    SUBTITLE_ENGLISH_VERTICAL_MAX: int = int(os.getenv("SUBTITLE_ENGLISH_VERTICAL_MAX", "25"))
    SUBTITLE_MIN_CHUNK_CHARS: int = int(os.getenv("SUBTITLE_MIN_CHUNK_CHARS", "5"))

    # Storage backend — default to local for open-source
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "")
    S3_REGION: str = os.getenv("S3_REGION", "us-west-2")
    S3_ACCESS_KEY_ID: str = os.getenv("S3_ACCESS_KEY_ID", "")
    S3_SECRET_ACCESS_KEY: str = os.getenv("S3_SECRET_ACCESS_KEY", "")
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "")
    ENABLE_LOCAL_CACHE: bool = os.getenv("ENABLE_LOCAL_CACHE", "true").lower() == "true"
    CACHE_ONLY_MODE: bool = os.getenv("CACHE_ONLY_MODE", "true").lower() == "true"
    S3_DIRECT_ACCESS: bool = os.getenv("S3_DIRECT_ACCESS", "false").lower() == "true"
    PREFER_S3_STORAGE: bool = os.getenv("PREFER_S3_STORAGE", "false").lower() == "true"
    S3_PRESIGNED_URL_EXPIRY: int = int(os.getenv("S3_PRESIGNED_URL_EXPIRY", "3600"))
    AUTO_CLEANUP_LOCAL_CACHE: bool = os.getenv("AUTO_CLEANUP_LOCAL_CACHE", "false").lower() == "true"
    CLEANUP_DELAY_HOURS: int = int(os.getenv("CLEANUP_DELAY_HOURS", "24"))
    KEEP_RECENT_FILES_HOURS: int = int(os.getenv("KEEP_RECENT_FILES_HOURS", "72"))

    # CORS — open source defaults to allow all origins
    CORS_ALLOW_ALL_ORIGINS: bool = os.getenv("CORS_ALLOW_ALL_ORIGINS", "true").lower() in ("true", "1", "t")

    _default_cors_origins = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
    ]

    BACKEND_CORS_ORIGINS: Union[str, list[str]] = os.getenv("BACKEND_CORS_ORIGINS", ",".join(_default_cors_origins))

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, list[str]]) -> Union[list[str], str]:
        if isinstance(v, str) and not v.startswith('['):
            return [i.strip() for i in v.split(',')]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]
    CORS_EXPOSE_HEADERS: list[str] = [
        "Content-Range", "Content-Length", "Content-Disposition",
        "Accept-Ranges", "Content-Encoding"
    ]

    # Demucs settings for audio source separation
    ENABLE_DEMUCS: bool = os.getenv("ENABLE_DEMUCS", "true").lower() == "true"
    DEMUCS_MODEL_NAME: str = os.getenv("DEMUCS_MODEL_NAME", "htdemucs")
    DEMUCS_OUTPUT_BITRATE: int = int(os.getenv("DEMUCS_OUTPUT_BITRATE", "128"))
    DEMUCS_SHIFTS: int = int(os.getenv("DEMUCS_SHIFTS", "1"))
    DEMUCS_OVERLAP: float = float(os.getenv("DEMUCS_OVERLAP", "0.25"))

    # Subtitle styling
    SUBTITLE_FONT_SIZE: int = int(os.getenv("SUBTITLE_FONT_SIZE", "18"))
    SUBTITLE_FONT_SIZE_VERTICAL: int = int(os.getenv("SUBTITLE_FONT_SIZE_VERTICAL", "10"))
    SUBTITLE_FONT_SIZE_HORIZONTAL: int = int(os.getenv("SUBTITLE_FONT_SIZE_HORIZONTAL", "18"))
    SUBTITLE_MARGIN_VERTICAL: int = int(os.getenv("SUBTITLE_MARGIN_VERTICAL", "5"))
    SUBTITLE_MARGIN_HORIZONTAL: int = int(os.getenv("SUBTITLE_MARGIN_HORIZONTAL", "10"))
    SUBTITLE_FONT_COLOR: str = os.getenv("SUBTITLE_FONT_COLOR", "FFFFFF")
    SUBTITLE_BACKGROUND_COLOR: str = os.getenv("SUBTITLE_BACKGROUND_COLOR", "00FFFF")
    SUBTITLE_OUTLINE_COLOR: str = os.getenv("SUBTITLE_OUTLINE_COLOR", "FFFFFF")
    SUBTITLE_OUTLINE: int = int(os.getenv("SUBTITLE_OUTLINE", "1"))
    SUBTITLE_SHADOW: float = float(os.getenv("SUBTITLE_SHADOW", "0.5"))
    SUBTITLE_BORDER_STYLE: int = int(os.getenv("SUBTITLE_BORDER_STYLE", "4"))
    SUBTITLE_POSITION: str = os.getenv("SUBTITLE_POSITION", "bottom").lower()

    _subtitle_pos = os.getenv("SUBTITLE_POSITION", "bottom").lower()
    _default_alignment = "2" if _subtitle_pos == "bottom" else ("10" if _subtitle_pos == "top" else "5")
    SUBTITLE_ALIGNMENT: int = int(os.getenv("SUBTITLE_ALIGNMENT", _default_alignment))

    model_config = {
        "case_sensitive": True,
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        os.makedirs(self.STORAGE_BASE_DIR, exist_ok=True)
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)
        os.makedirs(self.JOB_DIR, exist_ok=True)


# Create settings instance
settings = Settings()

logger.info(f"EchoSub config loaded — DB: {settings.DATABASE_URL[:30]}..., Storage: {settings.STORAGE_BACKEND}")


@lru_cache()
def get_settings() -> Settings:
    return settings
