import { useEffect, useState } from "react";
import type { PublicAccessStatus } from "../types";
import * as api from "../api";

export default function PublicAccessCard() {
  const [status, setStatus] = useState<PublicAccessStatus | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [copied, setCopied] = useState(false);

  const refresh = async () => {
    try {
      const s = await api.getPublicAccess();
      setStatus(s);
      setUsername((u) => u || s.username);
    } catch { /* leave null */ }
  };

  useEffect(() => { refresh(); }, []);

  const msg = (fn: () => void) => { setError(""); setSuccess(""); fn(); };

  const handleEnable = async () => {
    msg(() => {});
    setBusy(true);
    try {
      if (username && password) {
        await api.setPublicCredentials(username, password);
        setPassword("");
      } else if (!status?.has_credentials) {
        setError("Set a username and password first.");
        setBusy(false);
        return;
      }
      const s = await api.enablePublicAccess();
      setStatus(s);
      setSuccess("Public access is on. Share the link below — it needs the username and password.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not enable public access");
      refresh();
    } finally {
      setBusy(false);
    }
  };

  const handleDisable = async () => {
    msg(() => {});
    setBusy(true);
    try {
      setStatus(await api.disablePublicAccess());
      setSuccess("Public access is off. The device is still reachable on your local network.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not disable public access");
    } finally {
      setBusy(false);
    }
  };

  const handleSaveCreds = async () => {
    msg(() => {});
    if (!username || !password) { setError("Enter both a username and password."); return; }
    setBusy(true);
    try {
      await api.setPublicCredentials(username, password);
      setPassword("");
      setSuccess("Login updated.");
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save login");
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    if (!status?.public_url) return;
    try { await navigator.clipboard.writeText(status.public_url); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { /* noop */ }
  };

  if (!status) return null;
  const on = status.enabled && status.running;

  return (
    <div className="card">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8, gap: 10, flexWrap: "wrap" }}>
        <h3 style={{ margin: 0 }}>Public Access</h3>
        <span className={`pa-status ${on ? "on" : ""}`}>
          <span className={`pulse-dot ${on ? "" : "paused"}`} style={{ animation: on ? undefined : "none", background: on ? undefined : "var(--faint)" }} />
          {on ? "On" : "Off"}
        </span>
      </div>

      <p className="info-msg" style={{ marginTop: 0, marginBottom: 14 }}>
        Reach this dashboard from anywhere over a secure Cloudflare link — no Cloudflare
        account or setup needed. On your local network you never need to log in; the public
        link always requires the username and password below.
      </p>

      {error && <div className="error-msg" style={{ marginBottom: 12 }}>{error}</div>}
      {success && <div className="success-msg" style={{ marginBottom: 12 }}>{success}</div>}

      {!status.installed && (
        <div className="warn-note">
          Public access needs the <code>cloudflared</code> helper, which isn’t installed on this
          device. Reinstall EdgeCaster (or install cloudflared) to turn this on.
        </div>
      )}

      {on ? (
        <>
          <div className="pa-url">
            <code>{status.public_url}</code>
            <button className={`btn-icon ${copied ? "copied" : ""}`} onClick={copy} title="Copy link">
              {copied ? "✓" : "Copy"}
            </button>
          </div>
          <p className="info-msg">Sign in as <strong>{status.username}</strong> with the password you set.</p>
          <div className="warn-note">
            Anyone with this link and login can view and control your cameras. Keep it private,
            use a strong password, and turn this off when you don’t need it. The link changes each
            time public access restarts.
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
            <button className="btn btn-danger" onClick={handleDisable} disabled={busy}>
              {busy ? "Working…" : "Turn off public access"}
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="form-group">
            <label>Username</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="e.g. admin" autoComplete="username" />
          </div>
          <div className="form-group">
            <label>Password{status.has_credentials ? " (leave blank to keep current)" : ""}</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" autoComplete="new-password" />
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button className="btn btn-primary" onClick={handleEnable} disabled={busy || !status.installed}>
              {busy ? "Turning on… (up to 30s)" : "Turn on public access"}
            </button>
            {status.has_credentials && (
              <button className="btn btn-secondary" onClick={handleSaveCreds} disabled={busy}>
                Update login
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
