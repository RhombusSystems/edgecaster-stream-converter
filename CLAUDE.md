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
- **Streams are uncapped by default** (`max_streams=0`). A positive `max_streams` is an optional hard ceiling.
- Low-latency FFmpeg (`_build_ffmpeg_cmd`): stream copy with buffering stripped at every hop (`-fflags nobuffer+flush_packets`, `-flags low_delay`, tuned `-probesize`/`-analyzeduration`, `-muxdelay/-muxpreload/-max_delay 0`, `-progress pipe:1`).
- Per-stream tasks: stdout `-progress` drain (liveness via `last_progress_ts`), stderr drain (bounded tail), and exit monitor. Draining also prevents pipe deadlock.
- **Stall watchdog** (`health_check_loop`, ~2s): detects frozen-but-alive feeds (no progress past `stall_threshold_seconds`, default 6) and dead processes.
- **Unified `_recover(stream, observed_generation, reason)`**: single guarded entry for ALL failure triggers. The `restart_generation` guard + `recovery_lock` guarantee exactly one relaunch (no double-launch race). Exit failures use the 5s×10 → 5-min-backoff ladder; stalls use a light backoff and refetch a fresh Rhombus URL.

### Alerts, Metrics & MediaMTX API (added subsystems)
- `services/alerts.py` — `AlertManager` POSTs JSON to a configured webhook (Slack/Make/custom) with cooldown + hysteresis + clear-on-recovery. Triggers: stream-down/retries-exhausted (from stream manager), under-voltage/thermal/high-CPU/load (from metrics loop).
- `services/health.py` — `MetricsCollector` samples non-blocking CPU, memory, Pi temperature (scans all `/sys/class/thermal/thermal_zone*` + hwmon + `vcgencmd` fallback), throttle bitmask (`vcgencmd get_throttled`), and load average. A background `metrics_loop` (main.py, ~2s) samples, polls the MediaMTX API, and evaluates alerts. **Note:** temperature/throttle/cpu-freq require the Pi kernel (`linux-raspi`); the Ubuntu `-generic`/`virtual` kernel exposes no sensors, so those read 0/"unknown" (handled gracefully; `install.sh` warns about it).
- `services/mediamtx.py` — besides URL builders, `get_path_stats()` queries the MediaMTX control API (`127.0.0.1:9997/v3/paths/list`) for per-path liveness/throughput; also enabled in `packaging/mediamtx.yml`.
- SSE: `GET /api/system/stream` pushes `SystemStatus` (+ active alerts) ~1s; frontend Dashboard subscribes via `EventSource`.

### Rhombus API Client (`backend/app/services/rhombus_api.py`)
- Base URL: `https://api2.rhombussystems.com`
- Auth headers: `x-auth-scheme: api-token`, `x-auth-apikey: <key>`
- Key endpoints: `getMinimalCameraStateList`, `createRawHttpStream`, `deleteRawHttpStream`
- Appends `.v0` facet to camera UUIDs for raw stream calls

### State Persistence
Two separate stores:
- **Config** (YAML): API key, max_streams, mediamtx (rtsp + api) settings, ffmpeg tunables, `stall_threshold_seconds`, auto-update schedule, alert settings (`alerts_enabled`, `alert_webhook_url`, thresholds)
- **State** (JSON): enabled camera UUIDs, slug_map (camera UUID → RTSP path)
- Dev paths: `backend/data/` | Prod paths: `/etc/edgecaster/`, `/var/lib/edgecaster/`

### Startup Lifecycle
1. Load config → setup logging → init StateStore, AlertManager, MetricsCollector
2. If API key present: create RhombusClient → discover cameras → restore enabled streams
3. Start background tasks: systemd watchdog ping, stall watchdog (`health_check_loop`), `metrics_loop` (metrics + MediaMTX poll + alert eval)
4. Signal `READY=1` to systemd

### Authentication
No HTTP-level auth on API endpoints. Security relies on network isolation (trusted LAN). The only "auth" is the Rhombus Org API Key stored in plaintext in config.yaml.

## Important Notes

- `PRODUCT SUMMARY.md` and `Product Requirements Document - EdgeCaster.md` are historical generation prompts, not live specs. Trust the code.
- No RTSP authentication in v1. Can be added via MediaMTX config (`publishUser`/`readUser`).
- Slug generation (`utils/slugify.py`) normalizes camera names to URL-safe RTSP paths.
- Auto-update (`scripts/edgecaster-update.sh`) runs hourly via systemd timer, only during configured window (default 2-5 AM), git fast-forward only. Requires `/opt/edgecaster` to be a git repo — `scripts/install.sh` now includes `.git` in its rsync so manual installs auto-update too (previously only the Pi image did).
- Install paths: one-line `scripts/bootstrap.sh` (curl | sudo bash, clones + installs), manual `scripts/install.sh` (apt-based; Debian/Ubuntu, arm64/amd64/armv7), or the Pi SD image (`image/build-image.sh`).
- End-user support contact is **support@rhombus.com** (referenced in README + bootstrap output).
