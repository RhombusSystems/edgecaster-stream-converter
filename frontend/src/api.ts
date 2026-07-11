import type {
  AuthStatus,
  Camera,
  StreamInfo,
  SystemStatus,
  AppSettings,
  UpdateSchedule,
  AlertSettings,
  LogSource,
  PublicAccessStatus,
} from "./types";
import { captureException } from "./posthog";

const BASE = "";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const error = new Error(body.detail || `HTTP ${res.status}`);
    captureException(error, {
      api_path: path,
      status: res.status,
      method: options?.method || "GET",
    });
    throw error;
  }
  return res.json();
}

// Auth
export const getAuthStatus = () => request<AuthStatus>("/api/auth/status");

// Settings
export const getSettings = () => request<AppSettings>("/api/settings");

export const setApiKey = (api_key: string) =>
  request<{ ok: boolean }>("/api/settings/api-key", {
    method: "POST",
    body: JSON.stringify({ api_key }),
  });

export const setUpdateSchedule = (schedule: UpdateSchedule) =>
  request<{ ok: boolean }>("/api/settings/update-schedule", {
    method: "PUT",
    body: JSON.stringify(schedule),
  });

export const setAlertSettings = (alerts: AlertSettings) =>
  request<{ ok: boolean }>("/api/settings/alerts", {
    method: "PUT",
    body: JSON.stringify(alerts),
  });

export const testAlert = () =>
  request<{ ok: boolean }>("/api/settings/alerts/test", { method: "POST" });

export const refreshDiscovery = () =>
  request<{ ok: boolean; count: number }>("/api/settings/discovery/refresh", {
    method: "POST",
  });

// Cameras
export const getCameras = () => request<Camera[]>("/api/cameras");

// Streams
export const getStreams = () => request<StreamInfo[]>("/api/streams");

export const enableStream = (cameraUuid: string) =>
  request<StreamInfo>(`/api/streams/${cameraUuid}/enable`, { method: "POST" });

export const disableStream = (cameraUuid: string) =>
  request<{ ok: boolean }>(`/api/streams/${cameraUuid}/disable`, {
    method: "POST",
  });

// System
export const getSystemStatus = () =>
  request<SystemStatus>("/api/system/status");

// Live system metrics over Server-Sent Events. Returns the EventSource so the
// caller can close it on unmount. onStatus fires on each pushed snapshot.
export function subscribeSystemStatus(
  onStatus: (status: SystemStatus) => void,
  onError?: () => void
): EventSource {
  const es = new EventSource(`${BASE}/api/system/stream`, { withCredentials: true });
  es.onmessage = (evt) => {
    try {
      onStatus(JSON.parse(evt.data) as SystemStatus);
    } catch {
      /* ignore malformed frame */
    }
  };
  if (onError) es.onerror = onError;
  return es;
}

// Logs
export const getLogSources = () =>
  request<{ sources: LogSource[] }>("/api/logs/sources");

export const getLogs = (source: string, lines = 300) =>
  request<{ source: string; lines: string[] }>(
    `/api/logs?source=${encodeURIComponent(source)}&lines=${lines}`
  );

export function subscribeLogs(source: string, onLine: (line: string) => void): EventSource {
  const es = new EventSource(
    `${BASE}/api/logs/stream?source=${encodeURIComponent(source)}`,
    { withCredentials: true }
  );
  es.onmessage = (evt) => { if (evt.data) onLine(evt.data); };
  return es;
}

// Public access (Cloudflare tunnel)
export const getPublicAccess = () =>
  request<PublicAccessStatus>("/api/settings/public-access");

export const setPublicCredentials = (username: string, password: string) =>
  request<{ ok: boolean }>("/api/settings/public-access/credentials", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });

export const enablePublicAccess = () =>
  request<PublicAccessStatus>("/api/settings/public-access/enable", { method: "POST" });

export const disablePublicAccess = () =>
  request<PublicAccessStatus>("/api/settings/public-access/disable", { method: "POST" });
