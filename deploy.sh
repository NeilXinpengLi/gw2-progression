#!/usr/bin/env bash
# Production deployment script for GW2 Progression
set -euo pipefail

echo "=== GW2 Progression Production Deployment ==="

# Check for .env
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    echo "No .env file found. Copying from .env.example..."
    cp .env.example .env
    echo "Please edit .env with your configuration before deploying."
    exit 1
  fi
fi

# Build and start
echo "Building images..."
docker compose -f docker-compose.prod.yml build

echo "Starting services..."
docker compose -f docker-compose.prod.yml up -d

echo "Waiting for health check..."
sleep 5
docker compose -f docker-compose.prod.yml ps

echo "=== Deployment complete ==="
echo "The app is now running at http://localhost"
echo "To view logs: docker compose -f docker-compose.prod.yml logs -f"
