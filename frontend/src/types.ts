export type SetupState = "needs_api_key" | "ready";

export type CameraStatus = "online" | "degraded" | "offline" | "unknown";

export type StreamState =
  | "starting"
  | "running"
  | "stopped"
  | "failed"
  | "restarting";

export interface Camera {
  uuid: string;
  name: string;
  location_name: string;
  status: CameraStatus;
  rtsp_enabled: boolean;
  rtsp_url: string;
  stream_state: StreamState | "";
}

export interface StreamInfo {
  camera_uuid: string;
  camera_name: string;
  rtsp_path: string;
  rtsp_url: string;
  state: StreamState;
  error_message: string;
}

export interface SystemStatus {
  hostname: string;
  local_ip: string;
  uptime_seconds: number;
  cpu_percent: number;
  memory_percent: number;
  total_cameras: number;
  active_streams: number;
  max_streams: number;
}

export interface AppSettings {
  hostname: string;
  local_ip: string;
  api_key_configured: boolean;
  setup_state: SetupState;
  max_streams: number;
  mediamtx_rtsp_port: number;
  auto_update_enabled: boolean;
  update_hour_start: number;
  update_hour_end: number;
}

export interface UpdateSchedule {
  auto_update_enabled: boolean;
  update_hour_start: number;
  update_hour_end: number;
}

export interface AuthStatus {
  setup_state: SetupState;
}
