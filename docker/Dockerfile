# GW2 Data Factory v1 — Dockerfile
# Multi-stage build for all factory services.

FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose API port
EXPOSE 8000

# Default command (overridden in docker-compose)
CMD ["uvicorn", "src.gw2_progression.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
