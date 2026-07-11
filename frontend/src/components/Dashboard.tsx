import { useEffect, useRef, useState } from "react";
import type { SystemStatus, StreamInfo } from "../types";
import * as api from "../api";
import StatusBadge from "./StatusBadge";

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function pctClass(pct: number): string {
  if (pct >= 80) return "danger";
  if (pct >= 60) return "warn";
  return "";
}

function statCardClass(pct: number): string {
  if (pct >= 80) return "stat-danger";
  if (pct >= 60) return "stat-warning";
  return "";
}

function tempClass(c: number): string {
  if (c >= 80) return "danger";
  if (c >= 70) return "warn";
  return "";
}

function throttleBadge(status: SystemStatus): { label: string; cls: string } {
  if (status.under_voltage_now) return { label: "Under-voltage", cls: "stat-danger" };
  if (status.throttled_now || status.freq_capped_now) return { label: "Throttled", cls: "stat-warning" };
  if (status.throttle_status === "unknown") return { label: "N/A", cls: "" };
  return { label: "OK", cls: "" };
}

function formatThroughput(kbps: number): string {
  if (!kbps) return "—";
  if (kbps >= 1000) return `${(kbps / 1000).toFixed(1)} Mbps`;
  return `${Math.round(kbps)} kbps`;
}

const CopyIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="9" width="13" height="13" rx="2" />
    <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
  </svg>
);

const CheckIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

export default function Dashboard() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [streams, setStreams] = useState<StreamInfo[]>([]);
  const [error, setError] = useState("");
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null);
  const lastPushRef = useRef<number>(0);

  // Live system metrics via SSE, with a polling safety net if SSE goes quiet.
  useEffect(() => {
    let es: EventSource | null = null;

    const applyStatus = (s: SystemStatus) => {
      setStatus(s);
      setError("");
      lastPushRef.current = Date.now();
    };

    const pollOnce = async () => {
      try {
        applyStatus(await api.getSystemStatus());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load status");
      }
    };

    // Immediate populate so the UI isn't blank until the first SSE frame.
    pollOnce();

    try {
      es = api.subscribeSystemStatus(applyStatus);
    } catch {
      /* EventSource unsupported — polling fallback below covers it */
    }

    // If no SSE frame has arrived in >5s, fall back to a poll.
    const watchdog = window.setInterval(() => {
      if (Date.now() - lastPushRef.current > 5000) pollOnce();
    }, 3000);

    return () => {
      if (es) es.close();
      window.clearInterval(watchdog);
    };
  }, []);

  // Stream list + throughput polled separately (not part of the SSE payload).
  useEffect(() => {
    const loadStreams = async () => {
      try {
        setStreams(await api.getStreams());
      } catch {
        /* handled by system-status error surface */
      }
    };
    loadStreams();
    const interval = window.setInterval(loadStreams, 5000);
    return () => window.clearInterval(interval);
  }, []);

  const handleCopy = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopiedUrl(url);
      setTimeout(() => setCopiedUrl(null), 2000);
    } catch { /* noop */ }
  };

  if (error && !status) return <div className="error-msg">{error}</div>;
  if (!status) return <div className="loading">Loading...</div>;

  const failedStreams = streams.filter((s) => s.state === "failed");
  const unlimited = status.max_streams === 0;
  const badge = throttleBadge(status);
  const loadOver = status.cpu_count > 0 && status.load_avg_1m > status.cpu_count;

  return (
    <div>
      {/* Active Alerts */}
      {status.alerts.length > 0 && (
        <div className="dashboard-section">
          <h3>Active Alerts</h3>
          {status.alerts.map((a) => (
            <div key={a.type} className={`alert-banner ${a.severity === "critical" ? "" : "warn"}`}>
              <div>
                <div className="alert-title">{a.title}</div>
                <div className="alert-msg">{a.message}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Overview Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="value">{status.active_streams}</div>
          <div className="label">Active Streams</div>
        </div>
        <div className="stat-card">
          <div className="value">{status.total_cameras}</div>
          <div className="label">Cameras Found</div>
        </div>
        <div className={`stat-card ${statCardClass(status.cpu_percent)}`}>
          <div className="value">{status.cpu_percent.toFixed(1)}%</div>
          <div className="label">CPU Usage</div>
          <div className="progress-bar-container">
            <div
              className={`progress-bar ${pctClass(status.cpu_percent)}`}
              style={{ width: `${Math.min(status.cpu_percent, 100)}%` }}
            />
          </div>
        </div>
        <div className={`stat-card ${statCardClass(status.memory_percent)}`}>
          <div className="value">{status.memory_percent.toFixed(1)}%</div>
          <div className="label">Memory Usage</div>
          <div className="progress-bar-container">
            <div
              className={`progress-bar ${pctClass(status.memory_percent)}`}
              style={{ width: `${Math.min(status.memory_percent, 100)}%` }}
            />
          </div>
        </div>
        <div className={`stat-card ${status.temperature_c ? statCardClass(status.temperature_c >= 80 ? 80 : status.temperature_c >= 70 ? 60 : 0) : ""}`}>
          <div className="value">
            {status.temperature_c ? `${status.temperature_c.toFixed(1)}°C` : "—"}
          </div>
          <div className="label">Temperature</div>
          {status.temperature_c > 0 && (
            <div className="progress-bar-container">
              <div
                className={`progress-bar ${tempClass(status.temperature_c)}`}
                style={{ width: `${Math.min((status.temperature_c / 90) * 100, 100)}%` }}
              />
            </div>
          )}
        </div>
        <div className={`stat-card ${badge.cls}`}>
          <div className="value" style={{ fontSize: 20 }}>{badge.label}</div>
          <div className="label">Power / Throttle</div>
          {(status.under_voltage_occurred || status.throttled_occurred) && (
            <div style={{ fontSize: 11, color: "var(--warning)", marginTop: 4 }}>
              {status.under_voltage_occurred ? "Under-voltage" : "Throttling"} occurred since boot
            </div>
          )}
        </div>
        <div className={`stat-card ${loadOver ? "stat-warning" : ""}`}>
          <div className="value">{status.load_avg_1m.toFixed(2)}</div>
          <div className="label">
            Load (1m){status.cpu_count ? ` / ${status.cpu_count} cores` : ""}
          </div>
        </div>
        <div className="stat-card">
          <div className="value">{formatUptime(status.uptime_seconds)}</div>
          <div className="label">Uptime</div>
        </div>
        <div className="stat-card">
          <div className="value">
            {unlimited ? status.active_streams : `${status.active_streams}/${status.max_streams}`}
          </div>
          <div className="label">{unlimited ? "Streams (unlimited)" : "Stream Capacity"}</div>
        </div>
      </div>

      {/* Failed Streams Alert */}
      {failedStreams.length > 0 && (
        <div className="dashboard-section">
          <h3>Failed Streams</h3>
          <div className="card" style={{ borderLeft: "3px solid var(--danger)" }}>
            <table className="stream-detail-table">
              <thead>
                <tr>
                  <th>Camera</th>
                  <th>RTSP Path</th>
                  <th>Status</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {failedStreams.map((s) => (
                  <tr key={s.camera_uuid}>
                    <td><strong>{s.camera_name}</strong></td>
                    <td><code className="rtsp-url">{s.rtsp_path}</code></td>
                    <td><StatusBadge status={s.state} /></td>
                    <td style={{ color: "var(--danger)", fontSize: 12 }}>
                      {s.error_message || "Unknown error"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Active Streams */}
      <div className="dashboard-section">
        <h3>Active Streams</h3>
        {streams.length === 0 ? (
          <div className="card">
            <div className="empty-state">
              <p>No streams enabled. Go to Cameras to start streaming.</p>
            </div>
          </div>
        ) : (
          <div className="card">
            <table className="stream-detail-table">
              <thead>
                <tr>
                  <th>Camera</th>
                  <th>RTSP URL</th>
                  <th>Status</th>
                  <th>Throughput</th>
                  <th>Readers</th>
                </tr>
              </thead>
              <tbody>
                {streams.map((s) => (
                  <tr key={s.camera_uuid}>
                    <td><strong>{s.camera_name}</strong></td>
                    <td>
                      <span className="rtsp-url-container">
                        <code className="rtsp-url">{s.rtsp_url}</code>
                        <button
                          className={`btn-icon ${copiedUrl === s.rtsp_url ? "copied" : ""}`}
                          onClick={() => handleCopy(s.rtsp_url)}
                          title="Copy RTSP URL"
                        >
                          {copiedUrl === s.rtsp_url ? <CheckIcon /> : <CopyIcon />}
                        </button>
                      </span>
                    </td>
                    <td><StatusBadge status={s.state} /></td>
                    <td style={{ fontSize: 13 }}>{formatThroughput(s.throughput_kbps)}</td>
                    <td style={{ fontSize: 13 }}>{s.readers ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Device Info */}
      <div className="dashboard-section">
        <h3>Device Info</h3>
        <div className="card">
          <div className="device-info-grid">
            <div className="device-info-item">
              <span className="info-label">Hostname</span>
              <span className="info-value">{status.hostname}</span>
            </div>
            <div className="device-info-item">
              <span className="info-label">Local IP</span>
              <span className="info-value">{status.local_ip}</span>
            </div>
            <div className="device-info-item">
              <span className="info-label">RTSP Base</span>
              <span className="info-value">
                <code className="rtsp-url">rtsp://{status.local_ip}:8554/</code>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
