FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CELERY_BROKER_URL=redis://redis:6379/1
ENV CELERY_RESULT_BACKEND=redis://redis:6379/2
ENV DASHBOARD_URL=http://web:3000

WORKDIR /app

# Install system dependencies if any
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy the common packages
COPY packages/common /app/packages/common
COPY packages/contracts /app/packages/contracts

# Copy PDF worker dependencies
COPY apps/pdf_worker/pyproject.toml /app/apps/pdf_worker/

# Install dependencies using uv
WORKDIR /app/apps/pdf_worker
RUN uv pip install --system -e .

# Copy source code
COPY apps/pdf_worker /app/apps/pdf_worker

# Start celery worker
CMD ["celery", "-A", "pdf_worker.celery_app", "worker", "-Q", "pdf_generation", "-c", "1", "--loglevel=info"]
