#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/operation-drake
PASS=0
FAIL=0

echo "=== D.R.A.K.E. Smoke Test ==="

# Container status
echo "--- Container status ---"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

# Health endpoint
echo ""
echo "--- Health endpoint ---"
if HEALTH=$(curl -sf http://localhost:8000/health 2>/dev/null); then
    echo "PASS: $HEALTH"
    PASS=$((PASS + 1))
else
    echo "FAIL: health endpoint not responding"
    FAIL=$((FAIL + 1))
fi

# Production diagnostic
echo ""
echo "--- Production diagnostic ---"
cd "$APP_DIR"
if docker compose exec api python -m operation_drake.main --check; then
    PASS=$((PASS + 1))
else
    echo "FAIL: diagnostic failed"
    FAIL=$((FAIL + 1))
fi

# Data directories
echo ""
echo "--- Persistent data directories ---"
for dir in data/database data/artifacts data/inbox backups; do
    if [ -d "$APP_DIR/$dir" ]; then
        echo "PASS: $dir exists"
        PASS=$((PASS + 1))
    else
        echo "FAIL: $dir missing"
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
