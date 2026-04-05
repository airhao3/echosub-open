import logging
import os
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from app.api.endpoints import (
    health, auth, users, jobs, uploads, downloads,
    file_registry, preview, thumbnails, subtitles,
    user_jobs, languages, account
)
from app.core.config import get_settings
from app.core.logging import setup_logging

# Get settings
settings = get_settings()

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="EchoSub API",
    version="0.2.0",
    description="Open-source video subtitle generation and translation"
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Open source: allow all origins by default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "Content-Range", "Content-Length", "Content-Type",
        "Range", "Content-Disposition", "Accept-Ranges", "Content-Encoding"
    ],
    max_age=86400
)

# Setup request logging middleware
from app.middleware.request_logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)

# Mount static files
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
os.makedirs(os.path.join(static_dir, "avatars"), exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include routers — core functionality only
app.include_router(health.router, prefix=f"{settings.API_V1_STR}/health", tags=["Health"])
app.include_router(languages.router, prefix=f"{settings.API_V1_STR}/languages", tags=["Languages"])
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["Users"])
app.include_router(jobs.router, prefix=f"{settings.API_V1_STR}/jobs", tags=["Jobs"])
app.include_router(user_jobs.router, prefix=f"{settings.API_V1_STR}/my/jobs", tags=["User Jobs"])
app.include_router(uploads.router, prefix=f"{settings.API_V1_STR}/uploads", tags=["Uploads"])
app.include_router(downloads.router, prefix=f"{settings.API_V1_STR}/downloads", tags=["Downloads"])
app.include_router(preview.router, prefix=f"{settings.API_V1_STR}/preview", tags=["Preview"])
app.include_router(file_registry.router, prefix=f"{settings.API_V1_STR}", tags=["File Registry"])
app.include_router(thumbnails.router, prefix=f"{settings.API_V1_STR}/thumbnails", tags=["Thumbnails"])
app.include_router(subtitles.router, prefix=f"{settings.API_V1_STR}/subtitles", tags=["Subtitles"])
app.include_router(account.router, prefix=f"{settings.API_V1_STR}/account", tags=["Account"])


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


@app.on_event("startup")
async def startup_event():
    logger.info("Starting EchoSub API")

    # Initialize database
    try:
        from app.core.database import engine
        from app.models.base import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables ready.")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")

    # Create storage directories
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.JOB_DIR, exist_ok=True)

    # Auto-create admin user for single-user mode
    try:
        from app.core.database import SessionLocal
        from app.models.user import User
        from app.core.security import get_password_hash
        db = SessionLocal()
        admin = db.query(User).filter(User.is_superuser == True).first()
        if not admin:
            admin = User(
                email="admin@echosub.local",
                username="admin",
                full_name="Admin",
                hashed_password=get_password_hash("admin"),
                is_active=True,
                is_superuser=True,
            )
            db.add(admin)
            db.commit()
            logger.info("Created default admin user (admin / admin). Please change the password after first login.")
        db.close()
    except Exception as e:
        logger.error(f"Failed to create default admin user: {e}")

    # Start scheduled maintenance tasks
    try:
        from app.core.scheduled_tasks import start_scheduled_tasks
        start_scheduled_tasks()
    except Exception as e:
        logger.warning(f"Scheduled tasks not started: {str(e)}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down EchoSub API")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
