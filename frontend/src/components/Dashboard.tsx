import { useEffect, useState } from "react";
import type { SystemStatus } from "../types";
import * as api from "../api";

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export default function Dashboard() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState("");

  const load = async () => {
    try {
      setStatus(await api.getSystemStatus());
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

  if (error) return <div className="error-msg">{error}</div>;
  if (!status) return <div className="loading">Loading...</div>;

  return (
    <div>
      <h2>Dashboard</h2>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="value">{status.active_streams}</div>
          <div className="label">Active Streams</div>
        </div>
        <div className="stat-card">
          <div className="value">{status.total_cameras}</div>
          <div className="label">Cameras Found</div>
        </div>
        <div className="stat-card">
          <div className="value">{status.cpu_percent.toFixed(1)}%</div>
          <div className="label">CPU Usage</div>
        </div>
        <div className="stat-card">
          <div className="value">{status.memory_percent.toFixed(1)}%</div>
          <div className="label">Memory Usage</div>
        </div>
        <div className="stat-card">
          <div className="value">{formatUptime(status.uptime_seconds)}</div>
          <div className="label">Uptime</div>
        </div>
        <div className="stat-card">
          <div className="value">{status.max_streams}</div>
          <div className="label">Max Streams</div>
        </div>
      </div>
      <div className="card">
        <p>
          <strong>Hostname:</strong> {status.hostname}
        </p>
        <p>
          <strong>Local IP:</strong> {status.local_ip}
        </p>
        <p>
          <strong>RTSP Base:</strong>{" "}
          <code className="rtsp-url">rtsp://{status.local_ip}:8554/</code>
        </p>
      </div>
    </div>
  );
}
