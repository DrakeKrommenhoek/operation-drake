#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/operation-drake
BACKUP_DIR="$APP_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_${TIMESTAMP}.tar.gz"

echo "=== D.R.A.K.E. Backup ==="
mkdir -p "$BACKUP_DIR"

echo "--- Creating backup: backup_${TIMESTAMP}.tar.gz ---"
tar -czf "$BACKUP_FILE" \
    -C "$APP_DIR" \
    data/database \
    data/artifacts

BACKUP_SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
BACKUP_COUNT=$(ls "$BACKUP_DIR"/*.tar.gz 2>/dev/null | wc -l)

echo "Backup created: $BACKUP_FILE ($BACKUP_SIZE)"
echo "Total backups stored: $BACKUP_COUNT"
echo ""
echo "--- Recent backups ---"
ls -lah "$BACKUP_DIR"/*.tar.gz 2>/dev/null | tail -5 || echo "No backups found"
echo "=== Backup complete ==="
