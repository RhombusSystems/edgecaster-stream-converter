# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EdgeCaster is a local edge gateway that converts Rhombus Secure Raw Streams (HTTPS H264) into RTSP streams via MediaMTX. It runs on a Raspberry Pi 5 with Ubuntu Server 24.04 and exposes a web UI for managing camera streams.

**Backend**: Python 3.11+ / FastAPI / Uvicorn | **Frontend**: React 18 / TypeScript / Vite | **RTSP**: MediaMTX (port 8554) | **Streams**: FFmpeg subprocesses (stream copy, no transcoding)

## Development Commands

### Backend
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend && npm install && npm run dev
```
Dev server at http://localhost:5173, proxies `/api` to backend port 8000.

### Tests
```bash
python -m pytest backend/tests/ -v              # all tests
python -m pytest backend/tests/test_slugify.py -v  # single file
python -m pytest backend/tests/test_slugify.py::test_basic_name -v  # single test
```
Tests require `pytest` and `pytest-asyncio`.

### Linting
```bash
ruff check backend/
cd frontend && npx tsc --noEmit
```

### Build frontend for production
```bash
cd frontend && npm run build   # outputs to frontend/dist/
```

## Architecture

### Import Paths
Python imports use fully-qualified paths from the repo root: `from backend.app.config import load_config`. The backend is **not** an installable package — it relies on running from the repo root directory.

### Dependency Injection (`backend/app/dependencies.py`)
Global singletons (config, state_store, stream_manager, discovery, rhombus_client) are initialized during FastAPI lifespan and accessed via `get_*()` functions used as FastAPI `Depends()`.

### Stream Manager (`backend/app/services/stream_manager.py`)
Core orchestrator managing FFmpeg subprocesses. Maintains in-memory map of `ManagedStream` objects.
- States: `starting` → `running` → `stopped` | `failed` → `restarting`
- Retry: 5s delay, max 10 attempts, then 5-minute backoff (infinite recovery)
- Health check loop every 60s detects dead processes
- Max 10 concurrent streams (configurable via `max_streams`)

### Rhombus API Client (`backend/app/services/rhombus_api.py`)
- Base URL: `https://api2.rhombussystems.com`
- Auth headers: `x-auth-scheme: api-token`, `x-auth-apikey: <key>`
- Key endpoints: `getMinimalCameraStateList`, `createRawHttpStream`, `deleteRawHttpStream`
- Appends `.v0` facet to camera UUIDs for raw stream calls

### State Persistence
Two separate stores:
- **Config** (YAML): API key, max_streams, mediamtx settings, auto-update schedule
- **State** (JSON): enabled camera UUIDs, slug_map (camera UUID → RTSP path)
- Dev paths: `backend/data/` | Prod paths: `/etc/edgecaster/`, `/var/lib/edgecaster/`

### Startup Lifecycle
1. Load config → setup logging → init StateStore
2. If API key present: create RhombusClient → discover cameras → restore enabled streams
3. Start background tasks: systemd watchdog ping, health check loop
4. Signal `READY=1` to systemd

### Authentication
No HTTP-level auth on API endpoints. Security relies on network isolation (trusted LAN). The only "auth" is the Rhombus Org API Key stored in plaintext in config.yaml.

## Important Notes

- `PRODUCT SUMMARY.md` and `Product Requirements Document - EdgeCaster.md` are historical generation prompts, not live specs. Trust the code.
- No RTSP authentication in v1. Can be added via MediaMTX config (`publishUser`/`readUser`).
- Slug generation (`utils/slugify.py`) normalizes camera names to URL-safe RTSP paths.
- Auto-update (`scripts/edgecaster-update.sh`) runs hourly via systemd timer, only during configured window (default 2-5 AM), git fast-forward only.
