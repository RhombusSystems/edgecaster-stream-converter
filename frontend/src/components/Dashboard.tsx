import { useEffect, useState } from "react";
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

function cpuClass(pct: number): string {
  if (pct >= 80) return "danger";
  if (pct >= 60) return "warn";
  return "";
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

  const load = async () => {
    try {
      const [s, st] = await Promise.all([
        api.getSystemStatus(),
        api.getStreams(),
      ]);
      setStatus(s);
      setStreams(st);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load status");
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleCopy = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopiedUrl(url);
      setTimeout(() => setCopiedUrl(null), 2000);
    } catch { /* noop */ }
  };

  if (error) return <div className="error-msg">{error}</div>;
  if (!status) return <div className="loading">Loading...</div>;

  const failedStreams = streams.filter((s) => s.state === "failed");

  return (
    <div>
      <h2>Dashboard</h2>

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
        <div className={`stat-card ${status.cpu_percent >= 80 ? "stat-danger" : status.cpu_percent >= 60 ? "stat-warning" : ""}`}>
          <div className="value">{status.cpu_percent.toFixed(1)}%</div>
          <div className="label">CPU Usage</div>
          <div className="progress-bar-container">
            <div
              className={`progress-bar ${cpuClass(status.cpu_percent)}`}
              style={{ width: `${Math.min(status.cpu_percent, 100)}%` }}
            />
          </div>
        </div>
        <div className={`stat-card ${status.memory_percent >= 80 ? "stat-danger" : status.memory_percent >= 60 ? "stat-warning" : ""}`}>
          <div className="value">{status.memory_percent.toFixed(1)}%</div>
          <div className="label">Memory Usage</div>
          <div className="progress-bar-container">
            <div
              className={`progress-bar ${cpuClass(status.memory_percent)}`}
              style={{ width: `${Math.min(status.memory_percent, 100)}%` }}
            />
          </div>
        </div>
        <div className="stat-card">
          <div className="value">{formatUptime(status.uptime_seconds)}</div>
          <div className="label">Uptime</div>
        </div>
        <div className="stat-card">
          <div className="value">{status.active_streams}/{status.max_streams}</div>
          <div className="label">Stream Capacity</div>
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
