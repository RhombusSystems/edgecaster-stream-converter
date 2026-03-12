import { useEffect, useState, useCallback } from "react";
import type { Camera } from "../types";
import * as api from "../api";
import StatusBadge from "./StatusBadge";

export default function CameraList() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toggling, setToggling] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    try {
      setCameras(await api.getCameras());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cameras");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [load]);

  const handleToggle = async (cam: Camera) => {
    setToggling((prev) => new Set(prev).add(cam.uuid));
    try {
      if (cam.rtsp_enabled) {
        await api.disableStream(cam.uuid);
      } else {
        await api.enableStream(cam.uuid);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Toggle failed");
    } finally {
      setToggling((prev) => {
        const next = new Set(prev);
        next.delete(cam.uuid);
        return next;
      });
    }
  };

  const handleRefresh = async () => {
    setLoading(true);
    try {
      await api.refreshDiscovery();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setLoading(false);
    }
  };

  const activeCount = cameras.filter((c) => c.rtsp_enabled).length;
  const maxReached = activeCount >= 10;

  if (loading && cameras.length === 0) {
    return <div className="loading">Loading cameras...</div>;
  }

  return (
    <div>
      <div className="toolbar">
        <h2>Cameras</h2>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span className="toolbar-info">
            {activeCount}/10 streams active
          </span>
          <button className="btn btn-secondary btn-sm" onClick={handleRefresh}>
            Refresh
          </button>
        </div>
      </div>

      {error && <div className="error-msg" style={{ marginBottom: 12 }}>{error}</div>}

      {cameras.length === 0 ? (
        <div className="card">
          <p>No cameras discovered. Check your API key and click Refresh.</p>
        </div>
      ) : (
        <div className="card table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Camera</th>
                <th>Location</th>
                <th>Status</th>
                <th>Stream</th>
                <th>RTSP</th>
                <th>RTSP URL</th>
              </tr>
            </thead>
            <tbody>
              {cameras.map((cam) => (
                <tr key={cam.uuid}>
                  <td>
                    <strong>{cam.name}</strong>
                  </td>
                  <td>{cam.location_name || "-"}</td>
                  <td>
                    <StatusBadge status={cam.status} />
                  </td>
                  <td>
                    {cam.stream_state ? (
                      <StatusBadge status={cam.stream_state} />
                    ) : (
                      "-"
                    )}
                  </td>
                  <td>
                    <label className="toggle">
                      <input
                        type="checkbox"
                        checked={cam.rtsp_enabled}
                        disabled={
                          toggling.has(cam.uuid) ||
                          (!cam.rtsp_enabled && maxReached)
                        }
                        onChange={() => handleToggle(cam)}
                      />
                      <span className="slider" />
                    </label>
                  </td>
                  <td>
                    {cam.rtsp_enabled && cam.rtsp_url ? (
                      <code className="rtsp-url">{cam.rtsp_url}</code>
                    ) : (
                      "-"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {maxReached && (
        <div className="info-msg">
          Maximum of 10 concurrent streams reached. Disable a stream to enable another.
        </div>
      )}
    </div>
  );
}
