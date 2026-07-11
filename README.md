# EdgeCaster

**Turn your Rhombus cameras into standard RTSP streams** that any VMS, NVR, or AI/video system can use — with sub-second latency.

EdgeCaster is a small box (a Raspberry Pi, mini-PC, or Linux VM) that pulls video from your Rhombus cameras and re-broadcasts it as RTSP on your local network. Set it up once from a simple web page; it then runs 24/7 and heals itself if a stream drops.

```
Rhombus Cameras  →  EdgeCaster  →  RTSP streams  →  Your VMS / NVR / AI system
```

---

## Install it

Pick whichever is easier for you.

### Option A — Ready-to-use Raspberry Pi (easiest, no typing)

1. Ask Rhombus for the EdgeCaster SD-card image, or [build one](#build-a-raspberry-pi-image).
2. Flash it to an SD card with the free [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
3. Put the card in a **Raspberry Pi 5**, connect it to your network with an Ethernet cable, and power it on.
4. Wait a few minutes, then open **http://edgecaster.local** in a web browser.

### Option B — One command on any Linux machine

On a machine running **Ubuntu or Debian** (Raspberry Pi, mini-PC, or virtual machine), open a terminal and paste this single line:

```bash
curl -fsSL https://raw.githubusercontent.com/RhombusSystems/edgecaster-stream-converter/main/scripts/bootstrap.sh | sudo bash
```

It downloads and installs everything, then tells you the web address to open.

---

## Set it up (2 minutes)

1. Open EdgeCaster in a web browser (**http://edgecaster.local** or `http://<device-ip>`).
2. Paste your **Rhombus Org API Key**. Your cameras appear automatically.
3. Flip the switch next to any camera to start streaming.
4. Copy that camera's **RTSP link** and paste it into your VMS, NVR, or AI system. Done.

An RTSP link looks like: `rtsp://<device-ip>:8554/front_door`

The dashboard shows live health — active streams, CPU, temperature, and power status — and can **alert you** (via a webhook such as Slack) if a stream drops or the device is under strain. Turn that on under **Settings → Alerts**.

---

## Need help?

**Email [support@rhombus.com](mailto:support@rhombus.com)** and we'll help you get set up. It helps to include what you were doing and anything shown on the dashboard.

---

<details>
<summary><b>Advanced & developer notes</b> (click to expand)</summary>

### What you need
- A **Raspberry Pi 5** (8 GB RAM recommended) or any Ubuntu/Debian machine (arm64 or x86-64)
- Wired Gigabit network
- A Rhombus **Org API Key**

### How it works
Rhombus cameras expose a Secure Raw Stream (H264 over HTTPS). EdgeCaster pulls each one with FFmpeg (stream copy — no transcoding, so it's light and low-latency) and publishes it to a built-in [MediaMTX](https://github.com/bluenviron/mediamtx) RTSP server on port 8554. There's no fixed stream limit — the device runs as many as its network and CPU allow.

For sub-second latency it strips buffering at every hop, and a per-stream watchdog detects a frozen feed and automatically re-fetches it, so it keeps running 24/7.

### Common commands (on the device)
```bash
# Service status and live logs
sudo systemctl status edgecaster mediamtx
journalctl -u edgecaster -f

# Update now (also runs nightly on its own)
sudo bash /opt/edgecaster/scripts/edgecaster-update.sh

# Uninstall
sudo bash /opt/edgecaster/scripts/uninstall.sh
```

### Key locations & ports
| What | Where |
|------|-------|
| Configuration | `/etc/edgecaster/config.yaml` |
| Saved state | `/var/lib/edgecaster/state.json` |
| Logs | `/var/log/edgecaster/` |
| Web UI | port 80 · RTSP | port 8554 |

### Install from a git checkout
```bash
git clone https://github.com/RhombusSystems/edgecaster-stream-converter.git
cd edgecaster-stream-converter
sudo bash scripts/install.sh
```

### Build a Raspberry Pi image
```bash
sudo bash image/build-image.sh              # smaller, needs internet on first boot
sudo bash image/build-image.sh --prebaked   # larger, no internet needed on first boot
```
Output is a flashable `.img.xz`. First boot sets the hostname to `edgecaster`, creates the `edgecaster` user (default password `edgecaster` — change it), and starts all services.

### Local development
```bash
# Backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (dev server on :5173, proxies /api to :8000)
cd frontend && npm install && npm run dev

# Tests & linting
python -m pytest backend/tests/ -v
ruff check backend/ && (cd frontend && npx tsc --noEmit)
```

### Notes
- The web UI has **no built-in login** — run EdgeCaster on a trusted network. RTSP streams are unauthenticated in v1 (can be restricted via MediaMTX config).
- The API key is stored in `/etc/edgecaster/config.yaml` (not world-readable) and is never logged.
- Auto-updates use git fast-forward pulls during a configurable nightly window (default 2–5 AM), set under Settings or in `config.yaml`.

</details>

## License
Apache 2.0 — see [LICENSE](LICENSE)
