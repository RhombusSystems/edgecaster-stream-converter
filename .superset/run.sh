#!/usr/bin/env bash
set -euo pipefail

# Start backend (port 8000) and frontend dev server (port 5173, proxies /api).
trap 'kill 0' EXIT INT TERM

# Run from repo root: the backend uses fully-qualified imports (backend.app.*)
venv/bin/uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000 &
(cd frontend && npm run dev) &
wait
