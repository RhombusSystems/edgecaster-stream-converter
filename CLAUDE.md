# EdgeCaster - Claude Code Guide

## Project Overview

EdgeCaster is a local edge gateway that converts Rhombus Secure Raw Streams (HTTPS H264) into RTSP streams via MediaMTX. It runs on a Raspberry Pi 5 with Ubuntu Server 24.04 and exposes a web UI for managing camera streams.

## Tech Stack

- **Backend**: Python 3.11+ / FastAPI / Uvicorn
- **Frontend**: React 18 / TypeScript / Vite
- **RTSP Server**: MediaMTX (port 8554)
- **Stream Processing**: FFmpeg subprocesses (stream copy, no transcoding)
- **Reverse Proxy**: Nginx (port 80)
- **Process Management**: systemd
- **Config**: YAML (`/etc/edgecaster/config.yaml`)
- **State**: JSON (`/var/lib/edgecaster/state.json`)

## Repository Structure

```
backend/app/           # FastAPI application
  main.py              # App entrypoint, lifespan, router registration
  config.py            # YAML config loader/saver
  dependencies.py      # Dependency injection (global singletons)
  logging_setup.py     # File + console logging setup
  models/              # Pydantic models (camera, stream, settings)
  routers/             # API route handlers (auth, cameras, streams, settings, system)
  services/            # Domain logic (stream_manager, rhombus_api, state_store, discovery, watchdog)
  utils/               # Helpers (slugify, network, security)
backend/tests/         # pytest tests (slugify, state_store, stream_manager)
frontend/src/          # React SPA
  App.tsx              # Root component, setup flow, page routing
  api.ts               # Fetch-based API client
  types.ts             # TypeScript interfaces
  components/          # UI components (Dashboard, CameraList, SettingsPanel, SetupForm, StatusBadge)
scripts/               # install.sh, uninstall.sh, edgecaster-update.sh, first-boot.sh
packaging/             # systemd units, nginx config, mediamtx.yml, default config, logrotate
image/                 # Raspberry Pi .img build pipeline (build-image.sh, cloud-init configs)
```

## Development

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
Dev server runs on http://localhost:5173 and proxies `/api` to backend on port 8000.

### Tests
```bash
pip install pytest pytest-asyncio
python -m pytest backend/tests/ -v
```

### Linting
```bash
ruff check backend/
cd frontend && npx tsc --noEmit
```

## Key Architecture Details

### Authentication
There is **no HTTP-level authentication** on API endpoints. The app relies on network isolation (trusted LAN). The only "auth" is configuring the Rhombus Org API Key, which authenticates EdgeCaster to Rhombus cloud APIs.

### Stream Manager (`backend/app/services/stream_manager.py`)
- Core orchestrator managing FFmpeg subprocesses
- Maintains in-memory map of `ManagedStream` objects
- States: `starting`, `running`, `stopped`, `failed`, `restarting`
- Retry: 5s delay, max 10 attempts, then 5-minute backoff (infinite recovery)
- Health check loop every 60 seconds detects dead processes
- Max 10 concurrent streams (configurable via `max_streams`)

### Rhombus API Client (`backend/app/services/rhombus_api.py`)
- Base URL: `https://api2.rhombussystems.com`
- Auth headers: `x-auth-scheme: api-token`, `x-auth-apikey: <key>`
- Key endpoints: `getMinimalCameraStateList`, `createRawHttpStream`, `deleteRawHttpStream`
- Appends `.v0` facet to camera UUIDs for raw stream calls

### State Persistence
- **Config** (YAML): API key, max_streams, mediamtx settings, auto-update schedule
- **State** (JSON): enabled camera UUIDs, slug_map (camera UUID -> RTSP path)
- Dev paths: `backend/data/` ; Prod paths: `/etc/edgecaster/`, `/var/lib/edgecaster/`

### Startup Lifecycle
1. Load config -> setup logging -> init StateStore
2. If API key present: create RhombusClient -> discover cameras -> restore enabled streams
3. Start background tasks: systemd watchdog ping, health check loop
4. Signal `READY=1` to systemd

### Auto-Update System
- `edgecaster-update.sh` runs hourly via systemd timer
- Only updates during configured window (default 2-5 AM)
- Git-based: fetches origin/main, fast-forward only
- Rebuilds frontend, updates pip deps, restarts services

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/status` | Setup state (`needs_api_key` or `ready`) |
| GET | `/api/settings` | App settings (no secrets) |
| POST | `/api/settings/api-key` | Set Rhombus API key |
| PUT | `/api/settings/update-schedule` | Configure auto-update window |
| POST | `/api/settings/discovery/refresh` | Refresh camera list |
| GET | `/api/cameras` | List discovered cameras with stream state |
| GET | `/api/streams` | List active streams |
| POST | `/api/streams/{uuid}/enable` | Start RTSP stream |
| POST | `/api/streams/{uuid}/disable` | Stop RTSP stream |
| GET | `/api/system/status` | System health metrics |

## Important Notes

- The `PRODUCT SUMMARY.md` and `Product Requirements Document - EdgeCaster.md` are historical generation prompts, not live specs. Trust the code.
- Admin password auth was removed in favor of API-key-only setup (see commit history).
- API key is stored in plaintext in config.yaml. Security relies on file permissions and network isolation.
- No RTSP authentication in v1. Can be added via MediaMTX config (`publishUser`/`readUser`).
- Slug generation (`utils/slugify.py`) normalizes camera names to URL-safe RTSP paths.
