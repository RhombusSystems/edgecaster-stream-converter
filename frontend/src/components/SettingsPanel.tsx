import { useEffect, useState } from "react";
import type { AppSettings } from "../types";
import * as api from "../api";

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, i) => {
  const suffix = i < 12 ? "AM" : "PM";
  const h = i === 0 ? 12 : i > 12 ? i - 12 : i;
  return { value: i, label: `${h}:00 ${suffix}` };
});

export default function SettingsPanel() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [autoUpdateEnabled, setAutoUpdateEnabled] = useState(true);
  const [updateStart, setUpdateStart] = useState(2);
  const [updateEnd, setUpdateEnd] = useState(5);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getSettings().then((s) => {
      setSettings(s);
      setAutoUpdateEnabled(s.auto_update_enabled);
      setUpdateStart(s.update_hour_start);
      setUpdateEnd(s.update_hour_end);
    }).catch(() => {});
  }, []);

  const handleSaveApiKey = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);
    try {
      await api.setApiKey(apiKey);
      setSuccess("API key updated and cameras refreshed.");
      setApiKey("");
      setSettings(await api.getSettings());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update API key");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveUpdateSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);
    try {
      await api.setUpdateSchedule({
        auto_update_enabled: autoUpdateEnabled,
        update_hour_start: updateStart,
        update_hour_end: updateEnd,
      });
      setSuccess("Update schedule saved.");
      setSettings(await api.getSettings());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save schedule");
    } finally {
      setLoading(false);
    }
  };

  if (!settings) return <div className="loading">Loading...</div>;

  return (
    <div>
      <h2>Settings</h2>

      {error && <div className="error-msg" style={{ marginBottom: 12 }}>{error}</div>}
      {success && <div className="info-msg" style={{ marginBottom: 12, color: "var(--success)" }}>{success}</div>}

      <div className="card">
        <h3 style={{ marginBottom: 12 }}>Device Info</h3>
        <p><strong>Hostname:</strong> {settings.hostname}</p>
        <p><strong>Local IP:</strong> {settings.local_ip}</p>
        <p><strong>RTSP Port:</strong> {settings.mediamtx_rtsp_port}</p>
        <p><strong>Max Streams:</strong> {settings.max_streams}</p>
      </div>

      <div className="card">
        <h3 style={{ marginBottom: 12 }}>Rhombus API Key</h3>
        <p className="info-msg" style={{ marginBottom: 12 }}>
          {settings.api_key_configured
            ? "API key is configured."
            : "No API key configured."}
        </p>
        <form onSubmit={handleSaveApiKey}>
          <div className="form-group">
            <label>{settings.api_key_configured ? "Update" : "Set"} API Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Paste your Rhombus Org API key"
              required
            />
          </div>
          <button className="btn btn-primary" disabled={loading}>
            {loading ? "Saving..." : "Save API Key"}
          </button>
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginBottom: 12 }}>Auto-Update</h3>
        <p className="info-msg" style={{ marginBottom: 16 }}>
          EdgeCaster checks for updates hourly during the configured window.
        </p>
        <form onSubmit={handleSaveUpdateSchedule}>
          <div className="form-group" style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <label className="toggle" style={{ marginBottom: 0 }}>
              <input
                type="checkbox"
                checked={autoUpdateEnabled}
                onChange={(e) => setAutoUpdateEnabled(e.target.checked)}
              />
              <span className="slider" />
            </label>
            <span style={{ fontSize: 14 }}>
              {autoUpdateEnabled ? "Auto-updates enabled" : "Auto-updates disabled"}
            </span>
          </div>

          {autoUpdateEnabled && (
            <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label>Start</label>
                <select
                  value={updateStart}
                  onChange={(e) => setUpdateStart(Number(e.target.value))}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius)",
                    fontFamily: "var(--font-body)",
                    fontSize: 14,
                  }}
                >
                  {HOUR_OPTIONS.map((h) => (
                    <option key={h.value} value={h.value}>{h.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-group" style={{ flex: 1 }}>
                <label>End</label>
                <select
                  value={updateEnd}
                  onChange={(e) => setUpdateEnd(Number(e.target.value))}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius)",
                    fontFamily: "var(--font-body)",
                    fontSize: 14,
                  }}
                >
                  {HOUR_OPTIONS.map((h) => (
                    <option key={h.value} value={h.value}>{h.label}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          <button className="btn btn-primary" disabled={loading}>
            {loading ? "Saving..." : "Save Schedule"}
          </button>
        </form>
      </div>
    </div>
  );
}
