#!/usr/bin/env bash
# Start Expert AI Docker backend stack in WSL2
# Usage: bash scripts/start-expert-ai-docker.sh [--build] [--no-wait]
set -euo pipefail

cd "$(dirname "$0")/.."
COMPOSE_FILE="docker-compose.expert-ai.yml"
BUILD_FLAG="${1:+--build}"

echo "=== GW2 Expert AI — Docker Backend ==="
echo "Services: $(docker compose -f "$COMPOSE_FILE" config --services | tr '\n' ' ')"

# Check for port conflicts with existing containers
if docker ps --format '{{.Names}} {{.Ports}}' | grep -q ':5432->'; then
  echo "⚠ Port 5432 (Postgres) already in use — expert-ai will use 5433 within compose network"
fi

docker compose -f "$COMPOSE_FILE" up -d $BUILD_FLAG

if [ "${2:-}" != "--no-wait" ]; then
  echo "Waiting for health checks..."
  for i in $(seq 1 30); do
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "gw2-progression-app-1" 2>/dev/null || echo "starting")
    if [ "$HEALTH" = "healthy" ]; then
      echo "✓ All services healthy"
      break
    fi
    sleep 2
  done
fi

echo "=== Stack Status ==="
docker compose -f "$COMPOSE_FILE" ps
