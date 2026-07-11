import { useEffect, useState } from "react";
import type { AppSettings } from "../types";
import * as api from "../api";
import PublicAccessCard from "./PublicAccessCard";

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

  // Alerting
  const [alertsEnabled, setAlertsEnabled] = useState(false);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [cpuThreshold, setCpuThreshold] = useState(85);
  const [tempThreshold, setTempThreshold] = useState(80);
  const [loadThreshold, setLoadThreshold] = useState(0);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    api.getSettings().then((s) => {
      setSettings(s);
      setAutoUpdateEnabled(s.auto_update_enabled);
      setUpdateStart(s.update_hour_start);
      setUpdateEnd(s.update_hour_end);
      setAlertsEnabled(s.alerts_enabled);
      setWebhookUrl(s.alert_webhook_url);
      setCpuThreshold(s.cpu_alert_threshold);
      setTempThreshold(s.temp_alert_threshold_c);
      setLoadThreshold(s.load_alert_threshold);
    }).catch(() => {});
  }, []);

  const clearMessages = () => { setError(""); setSuccess(""); };

  const handleSaveApiKey = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
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
    clearMessages();
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

  const handleSaveAlerts = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
    setLoading(true);
    try {
      await api.setAlertSettings({
        alerts_enabled: alertsEnabled,
        alert_webhook_url: webhookUrl,
        cpu_alert_threshold: cpuThreshold,
        temp_alert_threshold_c: tempThreshold,
        load_alert_threshold: loadThreshold,
      });
      setSuccess("Alert settings saved.");
      setSettings(await api.getSettings());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save alert settings");
    } finally {
      setLoading(false);
    }
  };

  const handleTestAlert = async () => {
    clearMessages();
    setTesting(true);
    try {
      await api.testAlert();
      setSuccess("Test alert sent to the webhook.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send test alert");
    } finally {
      setTesting(false);
    }
  };

  if (!settings) return <div className="loading">Loading...</div>;

  return (
    <div>
      {error && <div className="error-msg" style={{ marginBottom: 12 }}>{error}</div>}
      {success && <div className="success-msg" style={{ marginBottom: 12 }}>{success}</div>}

      <div className="card">
        <h3>Device Info</h3>
        <div className="device-info-grid">
          <div className="device-info-item">
            <span className="info-label">Hostname</span>
            <span className="info-value">{settings.hostname}</span>
          </div>
          <div className="device-info-item">
            <span className="info-label">Local IP</span>
            <span className="info-value">{settings.local_ip}</span>
          </div>
          <div className="device-info-item">
            <span className="info-label">RTSP Port</span>
            <span className="info-value">{settings.mediamtx_rtsp_port}</span>
          </div>
          <div className="device-info-item">
            <span className="info-label">Max Streams</span>
            <span className="info-value">
              {settings.max_streams === 0 ? "Unlimited" : settings.max_streams}
            </span>
          </div>
        </div>
      </div>

      <div className="card">
        <h3>Rhombus API Key</h3>
        <p className="info-msg" style={{ marginBottom: 12, marginTop: 0 }}>
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

      <PublicAccessCard />

      <div className="card">
        <h3>Auto-Update</h3>
        <p className="info-msg" style={{ marginBottom: 16, marginTop: 0 }}>
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

      <div className="card">
        <h3>Alerts</h3>
        <p className="info-msg" style={{ marginBottom: 16, marginTop: 0 }}>
          Send a LAN alert to a webhook (Slack incoming webhook, Make.com, or any
          HTTP listener) when a stream drops, the Pi is power/thermally constrained,
          or CPU/load stays high.
        </p>
        <form onSubmit={handleSaveAlerts}>
          <div className="form-group" style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <label className="toggle" style={{ marginBottom: 0 }}>
              <input
                type="checkbox"
                checked={alertsEnabled}
                onChange={(e) => setAlertsEnabled(e.target.checked)}
              />
              <span className="slider" />
            </label>
            <span style={{ fontSize: 14 }}>
              {alertsEnabled ? "Alerts enabled" : "Alerts disabled"}
            </span>
          </div>

          <div className="form-group">
            <label>Webhook URL</label>
            <input
              type="text"
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              placeholder="https://hooks.slack.com/services/..."
            />
          </div>

          <div style={{ display: "flex", gap: 16 }}>
            <div className="form-group" style={{ flex: 1 }}>
              <label>CPU alert (%)</label>
              <input
                type="number"
                min={0}
                max={100}
                value={cpuThreshold}
                onChange={(e) => setCpuThreshold(Number(e.target.value))}
              />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label>Temp alert (°C)</label>
              <input
                type="number"
                min={0}
                max={120}
                value={tempThreshold}
                onChange={(e) => setTempThreshold(Number(e.target.value))}
              />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label>Load alert (0=off)</label>
              <input
                type="number"
                min={0}
                step={0.5}
                value={loadThreshold}
                onChange={(e) => setLoadThreshold(Number(e.target.value))}
              />
            </div>
          </div>

          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn btn-primary" disabled={loading}>
              {loading ? "Saving..." : "Save Alerts"}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={testing || !webhookUrl}
              onClick={handleTestAlert}
            >
              {testing ? "Sending..." : "Send test alert"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
