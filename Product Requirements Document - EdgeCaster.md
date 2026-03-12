Product Requirements Document

Product: Rhombus EdgeCaster

Version: 1.1
Project Type: Open Source
License (recommended): Apache 2.0 or MIT
Target Platform: Raspberry Pi 5 (Ubuntu Server)

⸻

1. Product Overview

EdgeCaster is a lightweight edge gateway that converts Rhombus Secure Raw Streams (SRS) into RTSP streams.

The device runs locally on a Raspberry Pi 5, automatically discovers cameras using the Rhombus API, and exposes a simple UI where users can enable RTSP streams for selected cameras.

EdgeCaster does not modify camera firmware or Rhombus infrastructure. It simply acts as a local protocol bridge.

Primary Use Case

Allow third-party VMS, NVRs, and AI systems that require RTSP to consume video from Rhombus cameras.

⸻

2. Key Design Principles

EdgeCaster must be:

• Plug-and-play
• Lightweight
• Transparent in operation
• Reliable for long-running deployments
• Secure (no credential exposure)

⸻

3. System Architecture

Rhombus Camera
     │
     │ Secure Raw Stream (HTTPS H264)
     ▼
EdgeCaster
     │
     │ FFmpeg Pull
     ▼
MediaMTX
     │
     │ RTSP
     ▼
External Systems
(VMS / NVR / AI Analytics)


⸻

4. Hardware Target

Component	Requirement
Device	Raspberry Pi 5
CPU	ARM Cortex-A76
RAM	8GB recommended
Storage	32GB SD minimum
Network	Gigabit Ethernet
OS	Ubuntu Server 24.04


⸻

5. Software Stack

Layer	Technology
Backend API	FastAPI (Python)
Stream Conversion	FFmpeg
RTSP Server	MediaMTX
UI	React
Process Control	systemd
Configuration	YAML

The application should run directly on the OS rather than requiring Docker to keep resource usage low.

⸻

6. Authentication

EdgeCaster uses a Rhombus Organization API Key.

The API key allows:

• Camera discovery
• Secure Raw Stream creation

API Authentication Headers

x-auth-scheme: api-token
x-auth-apikey: <ORG_API_KEY>

Base API endpoint:

https://api2.rhombussystems.com


⸻

7. Camera Discovery

EdgeCaster will discover cameras using the Rhombus API camera list.

API Endpoint

/camera/getMinimalCameraStateList

Returned metadata should include:

• Camera UUID
• Camera name
• Camera model
• Camera status
• Location name

The UI will display cameras based on this data.

Discovery occurs:

• During first setup
• On manual refresh
• On service restart

⸻

8. Secure Raw Stream Creation

When a user enables RTSP for a camera:
	1.	EdgeCaster requests a Secure Raw Stream.
	2.	The API returns a stream URL.
	3.	EdgeCaster pulls that stream.

Example SRS URL:

https://<camera-lan-address>:8000/<token>/h264

This stream contains:

• H264 video
• Encrypted transport
• LAN access only

⸻

9. Stream Conversion Pipeline

Each enabled camera runs a dedicated pipeline.

Secure Raw Stream
       │
       ▼
FFmpeg pull
       │
       ▼
MediaMTX RTSP publish
       │
       ▼
RTSP endpoint exposed

Example FFmpeg process:

ffmpeg -rtsp_transport tcp \
-i https://camera_stream_url \
-c copy \
-f rtsp rtsp://localhost:8554/<camera_name>

No transcoding occurs.

Video is stream copied to minimize CPU usage.

⸻

10. RTSP Server

EdgeCaster will use MediaMTX.

Reasons:

• Very lightweight
• Stable
• Actively maintained
• Excellent RTSP compatibility

MediaMTX listens on:

rtsp://<device-ip>:8554

Example stream URLs:

rtsp://edgecaster.local:8554/front_door
rtsp://edgecaster.local:8554/warehouse


⸻

11. Stream Limits

Maximum concurrent streams:

10

This protects Raspberry Pi CPU resources.

Approximate usage:

Streams	CPU
5	~30%
10	~60%


⸻

12. User Interface

UI should remain intentionally simple.

Accessible via:

http://edgecaster.local

or

http://<device-ip>


⸻

UI Layout

Dashboard

Displays:

• Device status
• Active streams
• CPU usage
• System uptime

⸻

Cameras Page

Primary interface.

Table view:

Camera	Location	Status	Enable RTSP


Toggle switch:

ON → Start stream
OFF → Stop stream

When enabled, display RTSP URL.

⸻

Settings Page

Minimal settings:

• Rhombus Org API Key
• Hostname
• Refresh cameras button

⸻

13. Boot Behavior

On system startup:
	1.	Start MediaMTX
	2.	Start EdgeCaster service
	3.	Load configuration
	4.	Validate API key
	5.	Discover cameras
	6.	Restart previously enabled streams

⸻

14. Configuration

Configuration stored in:

/etc/edgecaster/config.yaml

Example:

api_key: "RHOMBUS_API_KEY"
max_streams: 10

streams:
  front_door: enabled
  warehouse: disabled


⸻

15. Logging

Logs stored in:

/var/log/edgecaster

Files:

system.log
stream_manager.log
api.log


⸻

16. Failure Handling

If a stream fails:

retry after 5 seconds

Failure cases:

• Camera offline
• Network interruption
• Expired SRS token

EdgeCaster will automatically recreate the SRS.

⸻

17. Network Ports

Port	Purpose
80	Web UI
8554	RTSP
443	optional UI TLS

Outbound access required:

api2.rhombussystems.com


⸻

18. Installation Flow

First Boot Setup
	1.	User connects to device
	2.	Opens browser
	3.	Enters Org API Key
	4.	Cameras discovered
	5.	User toggles desired streams

Total setup time target:

< 3 minutes


⸻

19. Update Mechanism

EdgeCaster should support simple upgrades.

Example command:

edgecaster update

Recommended method:

GitHub release installer


⸻

20. Repository Layout

edgecaster/
 ├── api/
 │   ├── cameras.py
 │   ├── streams.py
 │   └── auth.py
 ├── services/
 │   ├── discovery.py
 │   ├── stream_manager.py
 │   └── rhombus_api.py
 ├── ui/
 │   ├── components/
 │   ├── pages/
 │   └── api/
 ├── config/
 ├── scripts/
 └── systemd/


⸻

21. Performance Targets

Metric	Target
Boot time	<30s
Discovery	<5s
Stream startup	<3s
Max streams	10


⸻

22. Security

EdgeCaster must ensure:

• API key stored securely
• UI protected with password
• No credentials logged
• No cloud dependencies

⸻

23. Open Source Distribution

Recommended repository:

github.com/<org>/edgecaster

Recommended license:

Apache 2.0

Documentation should include:

• Install guide
• Raspberry Pi flashing guide
• Troubleshooting guide

⸻

24. Success Criteria

EdgeCaster is successful when:

• Installs easily on Raspberry Pi
• Streams run reliably for weeks
• Compatible with major VMS platforms
• Requires minimal configuration

⸻