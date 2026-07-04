#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/operation-drake

echo "=== D.R.A.K.E. Deploy ==="
cd "$APP_DIR"

echo "--- Pulling latest code ---"
git pull

echo "--- Building images ---"
docker compose build

echo "--- Starting containers ---"
docker compose up -d

echo ""
echo "--- Container status ---"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo ""
echo "--- Health check ---"
sleep 5
curl -sf http://localhost:8000/health && echo "" || echo "WARN: health endpoint not yet ready"
echo "=== Deploy complete ==="
