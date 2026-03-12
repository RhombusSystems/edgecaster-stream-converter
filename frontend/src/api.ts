import type {
  AuthStatus,
  Camera,
  StreamInfo,
  SystemStatus,
  AppSettings,
} from "./types";

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
    throw new Error(body.detail || `HTTP ${res.status}`);
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
