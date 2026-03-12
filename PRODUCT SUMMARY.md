You are a principal software engineer and systems architect. Generate a complete, production-oriented open-source project called **EdgeCaster**.

EdgeCaster runs on a **Raspberry Pi 5** with **Ubuntu Server 24.04** and converts **Rhombus Secure Raw Streams** into **RTSP streams** using **MediaMTX**.

I do not want a partial prototype. I want a coherent, end-to-end codebase with all major files generated in one pass.

Your task is to generate the **entire repository structure and source code** for a first working version of EdgeCaster, including backend, frontend, stream orchestration, configuration, install scripts, and systemd services.

Important constraints:
- This is an **open-source** project, not an internal Rhombus project.
- The device uses a **Rhombus Org API Key**
- Camera discovery must use the **Rhombus API camera list**
- The RTSP server must be **MediaMTX**
- The UI must be **simple** and focused on a **camera toggle list**
- The app must be **lightweight**
- The app must be **production-ready in architecture**, even if some API details are abstracted behind clean interfaces
- Prefer direct OS deployment over Docker to reduce overhead
- The target is **up to 10 concurrent streams**
- No transcoding unless absolutely required; use stream copy whenever possible
- The generated result should be organized as a real repository, with clear file paths and contents

Produce the output as a repository with file-by-file code blocks.

==================================================
PRODUCT SUMMARY
==================================================

Product name: EdgeCaster

Purpose:
EdgeCaster is a local edge gateway that:
1. Authenticates to Rhombus using an Org API key
2. Discovers cameras via Rhombus API
3. Lets the user select up to 10 cameras from a browser UI
4. Creates Secure Raw Streams for those cameras
5. Pulls those streams locally
6. Rebroadcasts them as RTSP via MediaMTX

Primary use case:
Allow legacy VMS, NVR, and third-party AI/video systems that require RTSP to consume Rhombus camera video streams.

==================================================
TECHNICAL DECISIONS
==================================================

Target hardware:
- Raspberry Pi 5
- Ubuntu Server 24.04
- 8 GB RAM recommended
- Gigabit Ethernet

Software stack:
- Backend: Python 3.12 + FastAPI
- Frontend: React + TypeScript + Vite
- RTSP server: MediaMTX
- Stream processing: FFmpeg subprocesses
- Config format: YAML
- Process supervision: systemd
- HTTP client: httpx
- Backend server: uvicorn
- State persistence: SQLite for local app state if useful, otherwise YAML/JSON storage is acceptable
- Styling: simple, clean CSS or lightweight component approach; do not overengineer UI

Architecture goals:
- Clean separation of backend API, Rhombus API client, stream manager, and frontend
- Easy to install and operate
- Minimal CPU/memory usage
- Recover cleanly on restart
- Robust logging
- Reasonable security practices
- Idempotent service startup
- Simple configuration management

==================================================
REQUIRED FUNCTIONALITY
==================================================

1. First-run setup
- Web UI accessible at:
  - http://edgecaster.local
  - or http://<device-ip>
- On first run, prompt for:
  - Rhombus Org API Key
- Persist the API key securely in a local config file
- After API key is saved, perform camera discovery

2. Camera discovery
- Use Rhombus API camera list to discover cameras
- Abstract the exact API behind a Rhombus client service
- Implement the discovery call using a backend service class
- Expected discovered metadata:
  - camera UUID
  - camera name
  - camera model
  - status
  - location name
- Include a manual refresh endpoint/button

3. Camera list UI
- Show a table/list of cameras with:
  - camera name
  - location
  - online/offline status
  - toggle for RTSP enable/disable
  - RTSP URL when enabled
- Limit total enabled streams to 10
- UI should show clear error if limit is exceeded

4. Stream startup
- When user enables a camera:
  - backend requests a Secure Raw Stream URL from Rhombus API
  - backend starts an FFmpeg process for that camera
  - FFmpeg pulls the HTTPS H264 Secure Raw Stream
  - FFmpeg republishes it into MediaMTX as RTSP
- Use a stream copy approach whenever possible:
  - -c copy
- Ensure each camera has a deterministic RTSP path slug
- Example output:
  - rtsp://<device-ip>:8554/front_door

5. Stream shutdown
- When user disables a camera:
  - stop the associated FFmpeg process
  - remove it from active state
  - keep discovered camera data intact

6. Stream persistence
- If a stream was enabled before reboot, it should automatically restart on boot
- On service startup:
  - load config/state
  - validate API key exists
  - rediscover cameras
  - restart enabled streams if possible

7. Stream monitoring
- Monitor each FFmpeg process
- Detect exit/failure
- Retry after 5 seconds
- If the Secure Raw Stream token expires, recreate the stream via Rhombus API before restart
- Expose stream health/state in API and UI
- Track:
  - starting
  - running
  - stopped
  - failed
  - restarting

8. Dashboard
- Show:
  - total discovered cameras
  - active streams count
  - CPU usage
  - memory usage
  - uptime
- Keep it simple

9. Settings
- Show:
  - current hostname
  - whether API key is configured
- Allow:
  - save/update API key
  - refresh discovery
- Do not overbuild advanced settings

10. Logging
- Store logs under /var/log/edgecaster
- Separate logical logger domains if reasonable:
  - app
  - stream_manager
  - rhombus_api
- Also support local dev logging to console

11. Security
- Do not log API keys
- Mask secrets in responses/logs
- Include basic local UI authentication mechanism
- Keep it simple:
  - a local admin password set on first run is acceptable
- Session auth can be cookie-based or token-based
- This is a local appliance, so keep auth lightweight but real

==================================================
RHOMBUS API ASSUMPTIONS
==================================================

Use these assumptions and isolate them behind interfaces/constants so they can be adjusted later.

Base URL:
https://api2.rhombussystems.com

Authentication headers:
- x-auth-scheme: api-token
- x-auth-apikey: <ORG_API_KEY>

Implement a Rhombus API client module with methods like:
- get_cameras()
- create_secure_raw_stream(camera_id)
- optionally revoke_secure_raw_stream(camera_id) if needed

Use these endpoint assumptions:
- camera discovery endpoint:
  /camera/getMinimalCameraStateList
- secure raw stream creation:
  you may stub or create a clearly isolated placeholder method if the exact endpoint contract is unknown

Important:
If any Rhombus API contract is uncertain, do not stop. Instead:
- implement a clean abstraction
- clearly mark the assumptions in code comments
- make the unknown pieces easy to replace
- ensure the rest of the codebase remains runnable

==================================================
NON-FUNCTIONAL REQUIREMENTS
==================================================

- Lightweight enough for Raspberry Pi 5
- No Docker required for default deployment
- Systemd-native deployment
- Code should be readable and maintainable
- Good naming and project organization
- Type hints for Python
- Pydantic models for API contracts where appropriate
- Proper error handling
- Minimal but real tests for critical backend pieces
- Linting/formatting config
- .env.example if useful, but actual runtime config should live in YAML under /etc/edgecaster
- Idempotent installer script
- Friendly README with setup instructions

==================================================
PREFERRED REPOSITORY STRUCTURE
==================================================

Use something close to this unless you have a better, cleaner structure:

edgecaster/
  README.md
  LICENSE
  .gitignore
  pyproject.toml
  requirements.txt
  Makefile
  scripts/
    install.sh
    uninstall.sh
    edgecaster-update.sh
  packaging/
    mediamtx.yml
    edgecaster.default.yaml
    edgecaster.service
    mediamtx.service
    nginx.example.conf
  backend/
    app/
      __init__.py
      main.py
      config.py
      auth.py
      dependencies.py
      logging_setup.py
      models/
        __init__.py
        camera.py
        stream.py
        settings.py
      routers/
        __init__.py
        auth.py
        cameras.py
        streams.py
        settings.py
        system.py
      services/
        __init__.py
        rhombus_api.py
        discovery.py
        stream_manager.py
        mediamtx.py
        health.py
        state_store.py
      utils/
        __init__.py
        network.py
        slugify.py
        security.py
    tests/
      test_slugify.py
      test_state_store.py
      test_stream_manager.py
  frontend/
    package.json
    tsconfig.json
    vite.config.ts
    index.html
    src/
      main.tsx
      App.tsx
      api.ts
      types.ts
      styles.css
      components/
        LoginForm.tsx
        Dashboard.tsx
        CameraList.tsx
        SettingsPanel.tsx
        StatusBadge.tsx

You may adjust this structure if needed, but keep it professional and coherent.

==================================================
BACKEND REQUIREMENTS
==================================================

Implement a FastAPI backend with these routes, or a very similar set:

Auth:
- POST /api/auth/login
- POST /api/auth/logout
- GET /api/auth/status

Settings:
- GET /api/settings
- POST /api/settings/api-key
- POST /api/settings/admin-password
- POST /api/settings/discovery/refresh

Cameras:
- GET /api/cameras

Streams:
- GET /api/streams
- POST /api/streams/{camera_id}/enable
- POST /api/streams/{camera_id}/disable

System:
- GET /api/system/status

Behavior:
- Require auth for all non-login endpoints
- Return structured JSON
- Expose clear error messages
- Use background startup hooks to initialize services
- Use a central stream manager singleton/service

Implement:
- a config loader
- a persistent state store
- a stream manager that tracks subprocesses
- a Rhombus API client abstraction
- health/status reporting
- hostname and local IP discovery helpers

==================================================
STREAM MANAGER DESIGN
==================================================

Implement the stream manager carefully.

Responsibilities:
- start stream for a camera
- stop stream for a camera
- restart failed stream
- keep in-memory map of active FFmpeg processes
- keep persistent enabled/disabled stream state
- generate deterministic RTSP path slug
- limit active streams to 10
- provide status snapshot
- handle graceful shutdown

Use asyncio where useful, but keep it understandable.
Subprocesses may be launched via asyncio.create_subprocess_exec or subprocess.Popen.
Prefer a design that is reliable on Linux and easy to debug.

FFmpeg command should look conceptually like:
ffmpeg -hide_banner -loglevel warning -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -i <secure_raw_stream_url> -c copy -f rtsp rtsp://127.0.0.1:8554/<path>

Make the exact command configurable.

If MediaMTX requires a different ingest pattern, adapt accordingly.
Include the MediaMTX config file needed for this to work.

==================================================
MEDIAMTX REQUIREMENTS
==================================================

Use MediaMTX as the RTSP server.

Provide:
- a sample mediamtx.yml
- sensible defaults for a local appliance
- RTSP listen on :8554
- low-friction setup
- enough configuration so FFmpeg can publish streams to named paths

If authentication for RTSP is not included in v1, note that clearly in README and structure the config so it can be added later.

==================================================
FRONTEND REQUIREMENTS
==================================================

Build a simple React + TypeScript frontend.

Pages/sections:
- Login screen
- Dashboard
- Cameras list
- Settings panel

Requirements:
- clean and minimal layout
- responsive enough for desktop/tablet
- no heavy UI frameworks required
- use fetch or a tiny wrapper for API calls
- show loading/error states
- show stream state badges
- optimistic updates are optional; correctness is more important

UI behavior:
- login required
- if not configured, guide user through first-run setup
- show camera list with toggles
- disable toggles when 10 active streams are already enabled
- show RTSP URL inline for enabled streams
- include refresh discovery action

==================================================
AUTH DESIGN
==================================================

Implement local auth for the UI.

Simple acceptable approach:
- local admin password stored as a secure password hash
- login creates a signed session cookie
- FastAPI validates session on protected endpoints

Requirements:
- never store plaintext password
- use a strong password hash library
- provide first-run behavior for password creation
- if no password exists yet, backend should expose first-run state

==================================================
CONFIG AND STATE
==================================================

Use:
- /etc/edgecaster/config.yaml for configuration
- /var/lib/edgecaster/state.json or sqlite db for stream state and app state

Persist at least:
- API key present/value
- admin password hash
- enabled camera IDs
- RTSP path mappings if needed

Use sane defaults for local dev so the app can run without system paths.

==================================================
INSTALLATION AND OPERATIONS
==================================================

Provide:
1. install.sh
2. uninstall.sh
3. edgecaster-update.sh
4. systemd service unit for EdgeCaster backend
5. installation steps in README
6. MediaMTX installation or bundled setup instructions

install.sh should:
- install system packages
- install FFmpeg
- install MediaMTX if missing
- create edgecaster system user if appropriate
- create required directories:
  - /etc/edgecaster
  - /var/lib/edgecaster
  - /var/log/edgecaster
- install backend Python dependencies
- build frontend
- install/copy systemd units
- install default config if missing
- enable and start services

uninstall.sh should:
- stop/disable services
- remove installed files cautiously
- avoid destructive removal of config unless clearly intentional

edgecaster-update.sh should:
- pull latest code or install latest release asset in a simple way
- restart services safely

==================================================
README REQUIREMENTS
==================================================

Write a strong README that includes:
- project overview
- architecture summary
- features
- installation on Raspberry Pi 5
- local development instructions
- production deployment instructions
- configuration paths
- troubleshooting
- limitations
- security notes
- future enhancements

Also include:
- example RTSP URLs
- explanation that this project relies on Rhombus APIs and assumes valid Org API key access
- note that exact Secure Raw Stream API details may need adjustment depending on API contract

==================================================
TESTING REQUIREMENTS
==================================================

Include a minimal but useful test suite for:
- slug generation
- state persistence
- stream limit logic

If mocking is needed for Rhombus API and subprocesses, do so cleanly.

==================================================
CODING QUALITY
==================================================

Write code that is:
- production-oriented
- explicit
- typed
- readable
- commented only where helpful
- not bloated
- not toy-level

Do not hand-wave with placeholders like "implement this later" unless the external API contract is genuinely unknown. In those cases, still provide a working abstraction and clear TODO markers.

==================================================
OUTPUT FORMAT
==================================================

Return the complete repository in this format:

1. First, print the repository tree
2. Then print each file one by one
3. For each file use:
   FILE: path/to/file
   ```language
   ...contents...
Do not skip major files.
Do not summarize instead of writing code.
Do not provide only stubs.
Generate the actual contents.

If you need to make an assumption, make it and proceed.
The priority is a coherent first working codebase in one pass.
After Claude generates the repo, the next prompt to use is:

```text
Now review everything you just generated and do a second pass focused only on production hardening.

Tasks:
1. Find broken imports, missing files, inconsistent names, or mismatched API shapes
2. Fix startup/runtime issues across backend, frontend, scripts, and systemd units
3. Strengthen error handling and logging
4. Improve the installer so it is idempotent
5. Tighten security around secrets, sessions, and password setup
6. Verify MediaMTX and FFmpeg integration is internally consistent
7. Ensure stream restart logic and persistence are correct
8. Improve README accuracy
9. Fill any weak spots with real code, not TODOs
10. Return only the changed files in full

Be aggressive and critical. Treat the prior output like a code review for a real open-source release candidate.