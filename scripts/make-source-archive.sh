#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-/workspace/keitaro-wrapper-liveqa-source-sanitized.tar.gz}"
cd "$ROOT"
# Sanitized source only: no secrets, QA journal/DB, venv, git, node_modules, build caches.
tar czf "$OUT"   --exclude='./.git'   --exclude='./.venv'   --exclude='./backend/.venv'   --exclude='./qa-private'   --exclude='./node_modules'   --exclude='./frontend/node_modules'   --exclude='./frontend/dist'   --exclude='./backend/data'   --exclude='./.env'   --exclude='./backend/.env'   --exclude='**/__pycache__'   --exclude='**/.pytest_cache'   --exclude='**/*.pyc'   --exclude='**/*.db'   --exclude='**/.DS_Store'   --exclude='./.cursor'   .
echo "Wrote $OUT ($(du -h "$OUT" | cut -f1))"
