from fastapi import APIRouter

from app.api.endpoints import (
    health, auth, jobs, users, uploads, batch_uploads, downloads, preview, progress,
    video_compatibility, reprocess, results, direct_download, dialogue, account,
    video_effects, thumbnails, subtitles, user_jobs, language_slots, cache_management, languages
)

api_router = APIRouter()

# Health check endpoint (no auth required)
api_router.include_router(health.router, prefix="/health", tags=["health"])

# Language list endpoints (no auth required)
api_router.include_router(languages.router, prefix="/languages", tags=["languages"])

# Authentication endpoints (no auth required)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# User management endpoints (auth required)
api_router.include_router(users.router, prefix="/users", tags=["users"])

# Job management endpoints (auth required)
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])

# User-specific job endpoints with user job numbers (auth required)
api_router.include_router(user_jobs.router, prefix="/my/jobs", tags=["user-jobs"])

# Language slots management endpoints (auth required)
api_router.include_router(language_slots.router, prefix="/language-slots", tags=["language-slots"])

# Account status endpoint (auth required)
api_router.include_router(account.router, prefix="/account", tags=["account"])

# Upload endpoints (auth required)
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])

# Batch upload endpoints (auth required)
api_router.include_router(batch_uploads.router, prefix="/uploads", tags=["batch-uploads"])

# Download endpoints (auth required)
api_router.include_router(downloads.router, prefix="/downloads", tags=["downloads"])

# Preview endpoints (auth required)
api_router.include_router(preview.router, prefix="/preview", tags=["preview"])
api_router.include_router(reprocess.router, prefix="/reprocess", tags=["reprocess"])

# Progress tracking endpoints (auth required)
api_router.include_router(progress.router, tags=["progress"])

# Video compatibility endpoints (auth required)
api_router.include_router(video_compatibility.router, prefix="/compatibility", tags=["compatibility"])

# Results endpoints (auth required)
api_router.include_router(results.router, prefix="/results", tags=["results"])

# Direct download endpoints for frontend compatibility
api_router.include_router(direct_download.router, prefix="/downloads", tags=["downloads"])

# Dialogue translation endpoints (auth required)
api_router.include_router(dialogue.router, prefix="/dialogue", tags=["dialogue"])

# Video effects endpoints (auth required)
api_router.include_router(video_effects.router, prefix="/video-effects", tags=["video-effects"])

# Thumbnail endpoints (auth required)
api_router.include_router(thumbnails.router, prefix="/thumbnails", tags=["thumbnails"])

# Subtitle editing endpoints (auth required)
api_router.include_router(subtitles.router, prefix="/subtitles", tags=["subtitles"])

# Cache management endpoints (admin only)
api_router.include_router(cache_management.router, prefix="/cache", tags=["cache-management"])
