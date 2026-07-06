FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CELERY_BROKER_URL=redis://redis:6379/1
ENV CELERY_RESULT_BACKEND=redis://redis:6379/2

WORKDIR /app

# Install system dependencies if any
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install uv

# Copy the common package
COPY packages/common /app/packages/common
COPY packages/contracts /app/packages/contracts

# Copy bot worker dependencies
COPY apps/bot_worker/pyproject.toml /app/apps/bot_worker/

# Install dependencies using uv
WORKDIR /app/apps/bot_worker
RUN uv pip install --system -e .

# Copy source code
COPY apps/bot_worker /app/apps/bot_worker

# Start celery worker
CMD ["celery", "-A", "bot_worker.celery_app", "worker", "-Q", "bot", "-c", "1", "--loglevel=info"]
