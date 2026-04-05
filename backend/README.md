# EchoSub Backend

Video translation and subtitle generation API backend. Supports multi-language subtitle generation using any OpenAI-compatible LLM API.

## Quick Start

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and edit environment config
cp ../.env.example ../.env

# Initialize database
python manage.py initdb

# Run everything (API server + Celery worker)
python manage.py runall
```

API docs available at http://localhost:8000/docs after starting.

## Environment Variables

See `../.env.example` for all available options. Key settings:

- `OPENAI_API_KEY` - API key for your LLM provider
- `OPENAI_BASE_URL` - Base URL (any OpenAI-compatible endpoint)
- `TRANSLATION_MODEL` - Model name for translation
- `WHISPER_MODE` - `api` (external API) or `local` (requires GPU)

## Project Structure

```
app/
  api/endpoints/   # FastAPI route handlers
  core/            # Config, security, database, Celery tasks
  models/          # SQLAlchemy models
  schemas/         # Pydantic validation schemas
  services/        # Business logic (transcription, translation, subtitles)
  utils/           # Helpers and utilities
alembic/           # Database migrations
manage.py          # CLI management tool
```

## Management Commands

```bash
python manage.py runall          # Start API + Celery worker
python manage.py runserver       # API server only
python manage.py worker          # Celery worker only
python manage.py initdb          # Initialize/migrate database
python manage.py makemigrations  # Create new migration
```

## Tech Stack

FastAPI, SQLAlchemy, Celery + Redis, SQLite (default), FFmpeg
