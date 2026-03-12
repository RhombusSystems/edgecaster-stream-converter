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
- Automatic stream recovery on failure
- Persistent stream state across reboots
- Systemd-native deployment
- Local admin authentication

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
git clone https://github.com/RhombusSystems/edgecaster.git
cd edgecaster
sudo bash scripts/install.sh
```

### 2. Configure

Open `http://<device-ip>` in a browser:

1. Set an admin password
2. Enter your Rhombus Org API Key
3. Toggle cameras to start RTSP streams

### 3. Connect

Point your VMS/NVR to the RTSP streams:

```
rtsp://<device-ip>:8554/front_door
rtsp://<device-ip>:8554/warehouse
rtsp://<device-ip>:8554/parking_lot
```

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

## Production Deployment

The installer (`scripts/install.sh`) handles everything:

- Installs FFmpeg, Python, Node.js, Nginx, MediaMTX
- Creates `edgecaster` system user
- Sets up directories: `/etc/edgecaster`, `/var/lib/edgecaster`, `/var/log/edgecaster`
- Builds the frontend
- Installs and starts systemd services
- Configures Nginx reverse proxy on port 80

### Systemd Services

| Service | Purpose |
|---------|---------|
| `mediamtx.service` | RTSP server on port 8554 |
| `edgecaster.service` | Backend API on port 8000 (behind Nginx) |

```bash
# Check status
sudo systemctl status edgecaster
sudo systemctl status mediamtx

# View logs
journalctl -u edgecaster -f
journalctl -u mediamtx -f
```

### Update

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
| 8000 | Backend API (internal) |
| 8554 | RTSP streams |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/status` | Check auth/setup state |
| POST | `/api/auth/setup-password` | First-run password setup |
| POST | `/api/auth/login` | Authenticate |
| POST | `/api/auth/logout` | Sign out |
| GET | `/api/cameras` | List discovered cameras |
| GET | `/api/streams` | List active streams |
| POST | `/api/streams/{uuid}/enable` | Start RTSP stream |
| POST | `/api/streams/{uuid}/disable` | Stop RTSP stream |
| GET | `/api/settings` | Get app settings |
| POST | `/api/settings/api-key` | Set Rhombus API key |
| POST | `/api/settings/admin-password` | Change admin password |
| POST | `/api/settings/discovery/refresh` | Refresh camera list |
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
- Ensure the camera is online and on the same LAN

### RTSP URL not working
- Confirm the stream shows "running" in the UI
- Test with VLC: `vlc rtsp://<device-ip>:8554/<path>`
- Check port 8554 is not blocked by a firewall

## Limitations

- Maximum 10 concurrent streams (Pi CPU constraint)
- RTSP authentication is not enabled in v1 (can be added via MediaMTX config)
- Cameras must be accessible on the local network for raw stream URLs
- Secure Raw Stream tokens may expire; EdgeCaster auto-recreates them on failure

## Security Notes

- API keys are stored in `/etc/edgecaster/config.yaml` (root-owned)
- Admin password is bcrypt-hashed, never stored in plaintext
- Session tokens expire after 24 hours
- API keys are never logged or exposed in API responses
- The web UI should only be exposed on trusted networks

## Rhombus API

This project uses the [Rhombus API](https://apidocs.rhombussystems.com/) with an Organization API Key. Endpoints used:

- `POST /api/camera/getMinimalCameraStateList` — Camera discovery
- `POST /api/camera/createRawHttpStream` — Create Secure Raw Stream
- `POST /api/camera/deleteRawHttpStream` — Clean up stream
- `POST /api/location/getLocationLabelsForOrg` — Location name resolution

## License

Apache 2.0 — see [LICENSE](LICENSE)
