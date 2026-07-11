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
  throughput_kbps: number;
  readers: number;
}

export type AlertSeverity = "critical" | "warning" | "info";

export interface Alert {
  type: string;
  severity: AlertSeverity;
  title: string;
  message: string;
  since: number;
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
  temperature_c: number;
  throttle_status: "ok" | "under_voltage" | "throttled" | "unknown";
  under_voltage_now: boolean;
  under_voltage_occurred: boolean;
  throttled_now: boolean;
  throttled_occurred: boolean;
  freq_capped_now: boolean;
  load_avg_1m: number;
  load_avg_5m: number;
  load_avg_15m: number;
  cpu_count: number;
  cpu_freq_mhz: number;
  alerts: Alert[];
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
  alerts_enabled: boolean;
  alert_webhook_url: string;
  cpu_alert_threshold: number;
  temp_alert_threshold_c: number;
  load_alert_threshold: number;
}

export interface UpdateSchedule {
  auto_update_enabled: boolean;
  update_hour_start: number;
  update_hour_end: number;
}

export interface AlertSettings {
  alerts_enabled: boolean;
  alert_webhook_url: string;
  cpu_alert_threshold: number;
  temp_alert_threshold_c: number;
  load_alert_threshold: number;
}

export interface AuthStatus {
  setup_state: SetupState;
}
