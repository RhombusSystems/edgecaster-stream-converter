import { useEffect, useState } from "react";
import type { AppSettings } from "../types";
import * as api from "../api";

export default function SettingsPanel() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getSettings().then(setSettings).catch(() => {});
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
    </div>
  );
}
