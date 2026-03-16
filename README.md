# EdgeCaster

A lightweight edge gateway that converts **Rhombus Secure Raw Streams** into **RTSP streams** using **MediaMTX**.

EdgeCaster runs on a Raspberry Pi 5 and allows legacy VMS, NVR, and third-party AI/video systems that require RTSP to consume video from Rhombus cameras.

## Architecture

```
Rhombus Camera
     │
     │ Secure Raw Stream (HTTPS H264)
     ▼
EdgeCaster (FFmpeg pull)
     │
     ▼
MediaMTX (RTSP server)
     │
     ▼
External Systems (VMS / NVR / AI)
```

## Features

- Automatic camera discovery via Rhombus API
- Simple web UI for enabling/disabling RTSP streams
- Up to 10 concurrent streams (stream copy, no transcoding)
- Automatic stream recovery on failure with configurable retry logic
- Persistent stream state across reboots
- Systemd-native deployment with watchdog integration
- Automatic updates via configurable nightly window
- Raspberry Pi SD card image builder

## Hardware Requirements

| Component | Requirement |
|-----------|-------------|
| Device | Raspberry Pi 5 |
| RAM | 8GB recommended |
| Storage | 32GB SD minimum |
| Network | Gigabit Ethernet |
| OS | Ubuntu Server 24.04 |

## Quick Start

### 1. Install

```bash
git clone https://github.com/RhombusSystems/edgecaster-stream-converter.git
cd edgecaster-stream-converter
sudo bash scripts/install.sh
```

### 2. Configure

Open `http://<device-ip>` in a browser:

1. Enter your Rhombus Org API Key
2. Cameras are discovered automatically
3. Toggle cameras to start RTSP streams

### 3. Connect

Point your VMS/NVR to the RTSP streams:

```
rtsp://<device-ip>:8554/front_door
rtsp://<device-ip>:8554/warehouse
rtsp://<device-ip>:8554/parking_lot
```

## Raspberry Pi Image

You can build a ready-to-flash SD card image instead of installing manually:

```bash
# Cloud-init mode (smaller image, needs internet on first boot)
sudo bash image/build-image.sh

# Pre-baked mode (larger image, no internet needed on first boot)
sudo bash image/build-image.sh --prebaked
```

The output is a compressed `.img.xz` file. Flash it to an SD card with [Raspberry Pi Imager](https://www.raspberrypi.com/software/) or `dd`.

On first boot the device will:
- Set hostname to `edgecaster`
- Create the `edgecaster` user (default password: `edgecaster` — change immediately)
- Install all dependencies and start services
- Be accessible at `http://edgecaster.local` or `http://<device-ip>`

## Local Development

### Backend

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run backend (dev mode)
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs on `http://localhost:5173` and proxies `/api` to the backend.

### Run Tests

```bash
pip install pytest pytest-asyncio
python -m pytest backend/tests/ -v
```

### Linting

```bash
ruff check backend/
cd frontend && npx tsc --noEmit
```

## Production Deployment

The installer (`scripts/install.sh`) handles everything:

- Installs FFmpeg, Python, Node.js, Nginx, MediaMTX
- Creates `edgecaster` system user
- Sets up directories: `/etc/edgecaster`, `/var/lib/edgecaster`, `/var/log/edgecaster`
- Builds the frontend
- Installs and starts systemd services
- Configures Nginx reverse proxy on port 80
- Sets up log rotation and auto-update timer

### Systemd Services

| Service | Purpose |
|---------|---------|
| `mediamtx.service` | RTSP server on port 8554 |
| `edgecaster.service` | Backend API on port 8000 (behind Nginx) |
| `edgecaster-update.timer` | Hourly update check |

```bash
# Check status
sudo systemctl status edgecaster
sudo systemctl status mediamtx

# View logs
journalctl -u edgecaster -f
journalctl -u mediamtx -f
```

### Auto-Updates

EdgeCaster checks for updates hourly via a systemd timer. Updates only apply during a configurable window (default: 2:00–5:00 AM) and use git fast-forward pulls.

The update window can be configured through the Settings page in the web UI, or directly in `/etc/edgecaster/config.yaml`:

```yaml
auto_update_enabled: true
update_hour_start: 2
update_hour_end: 5
```

### Manual Update

```bash
sudo bash scripts/edgecaster-update.sh
```

### Uninstall

```bash
sudo bash scripts/uninstall.sh
```

## Configuration

### Paths

| Path | Purpose |
|------|---------|
| `/etc/edgecaster/config.yaml` | Main configuration |
| `/etc/edgecaster/mediamtx.yml` | MediaMTX configuration |
| `/var/lib/edgecaster/state.json` | Persistent stream state |
| `/var/log/edgecaster/` | Application logs |

### Network Ports

| Port | Purpose |
|------|---------|
| 80 | Web UI (Nginx) |
| 8000 | Backend API (internal, localhost only) |
| 8554 | RTSP streams |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/status` | Check setup state |
| GET | `/api/settings` | Get app settings |
| POST | `/api/settings/api-key` | Set Rhombus API key |
| PUT | `/api/settings/update-schedule` | Configure auto-update window |
| POST | `/api/settings/discovery/refresh` | Refresh camera list |
| GET | `/api/cameras` | List discovered cameras |
| GET | `/api/streams` | List active streams |
| POST | `/api/streams/{uuid}/enable` | Start RTSP stream |
| POST | `/api/streams/{uuid}/disable` | Stop RTSP stream |
| GET | `/api/system/status` | System health metrics |

## Troubleshooting

### No cameras found
- Verify your Rhombus Org API Key is valid
- Check the device has network access to `api2.rhombussystems.com`
- Try refreshing discovery from the Settings page

### Stream not starting
- Check FFmpeg is installed: `ffmpeg -version`
- Check MediaMTX is running: `systemctl status mediamtx`
- Check logs: `journalctl -u edgecaster -f`
- Ensure the camera is online and accessible on the local network

### RTSP URL not working
- Confirm the stream shows "running" in the UI
- Test with VLC: `vlc rtsp://<device-ip>:8554/<path>`
- Check port 8554 is not blocked by a firewall

### Auto-update not running
- Check timer status: `systemctl status edgecaster-update.timer`
- Check update logs: `cat /var/log/edgecaster/update.log`
- Verify the installation directory contains a `.git` folder
- Confirm the current hour falls within the update window

## Limitations

- Maximum 10 concurrent streams (Pi CPU constraint, configurable via `max_streams`)
- RTSP authentication is not enabled in v1 (can be added via MediaMTX config)
- Cameras must be accessible on the local network for raw stream URLs
- Secure Raw Stream tokens may expire; EdgeCaster auto-recreates them on failure
- No HTTP-level authentication on the web UI — deploy on a trusted network only
- Auto-updates require a git-based installation (not standalone packages)

## Security Notes

- The API key is stored in `/etc/edgecaster/config.yaml` (owned by `edgecaster` user, not world-readable)
- API keys are never logged or exposed in API responses
- The web UI has no built-in authentication — it should only be exposed on trusted networks
- The systemd service runs with hardened security options (NoNewPrivileges, ProtectSystem=strict, ProtectHome, PrivateTmp)
- RTSP streams are unauthenticated in v1; restrict access via network controls

## Rhombus API

This project uses the [Rhombus API](https://apidocs.rhombussystems.com/) with an Organization API Key. Endpoints used:

- `POST /api/camera/getMinimalCameraStateList` — Camera discovery
- `POST /api/camera/createRawHttpStream` — Create Secure Raw Stream
- `POST /api/camera/deleteRawHttpStream` — Clean up stream
- `POST /api/camera/getRawHttpStreams` — List existing raw streams
- `POST /api/location/getLocationLabelsForOrg` — Location name resolution

## License

Apache 2.0 — see [LICENSE](LICENSE)
