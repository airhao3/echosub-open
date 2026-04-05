# --- Stage 1: Build dependencies ---
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies required for building some python packages
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Create a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements file and install dependencies into the venv
COPY requirements_lightweight.txt .
RUN pip install --no-cache-dir -r requirements_lightweight.txt

# Install additional runtime dependencies
RUN pip install --no-cache-dir email-validator python-multipart json-repair openai httpx

# --- Stage 2: Final application image ---
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies like ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy the application code
COPY . .

# Set the path to use the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
# Assumes the FastAPI app instance is named "app" in "app/main.py"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]