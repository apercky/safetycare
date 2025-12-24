# SafetyCare Backend Dockerfile
# Python 3.12 with UV package manager

FROM python:3.12-slim AS builder

# Install system dependencies for OpenCV and MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Create virtual environment and install dependencies
RUN uv venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

# Install dependencies
RUN uv pip install -e .

# Production stage
FROM python:3.12-slim AS runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r safetycare && useradd -r -g safetycare safetycare

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

# Copy application code
COPY src/ ./src/

# Create data directories
RUN mkdir -p /data/auth /data/cameras /data/logs /data/models \
    && chown -R safetycare:safetycare /data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV SAFETYCARE_ENV=production
ENV SAFETYCARE_DATA_DIR=/data

# Download YOLOv8 model on build (optional, can be done at runtime)
# RUN python -c "from ultralytics import YOLO; YOLO('yolov8n-pose.pt')"

# Switch to non-root user
USER safetycare

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "safetycare.main:app", "--host", "0.0.0.0", "--port", "8000"]
