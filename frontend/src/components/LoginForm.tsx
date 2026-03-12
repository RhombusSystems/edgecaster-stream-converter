import { useState } from "react";
import type { SetupState } from "../types";
import * as api from "../api";

interface LoginFormProps {
  setupState: SetupState;
  onSuccess: () => void;
}

export default function LoginForm({ setupState, onSuccess }: LoginFormProps) {
  const [password, setPassword] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSetupPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.setupPassword(password);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Setup failed");
    } finally {
      setLoading(false);
    }
  };

  const handleSetApiKey = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.setApiKey(apiKey);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to set API key");
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.login(password);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  if (setupState === "needs_password") {
    return (
      <div className="login-container">
        <div className="login-box">
          <h1>EdgeCaster Setup</h1>
          <p>Create an admin password to get started.</p>
          <form onSubmit={handleSetupPassword}>
            <div className="form-group">
              <label>Admin Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min 8 characters"
                minLength={8}
                required
                autoFocus
              />
            </div>
            <button className="btn btn-primary" style={{ width: "100%" }} disabled={loading}>
              {loading ? "Setting up..." : "Set Password"}
            </button>
            {error && <div className="error-msg">{error}</div>}
          </form>
        </div>
      </div>
    );
  }

  if (setupState === "needs_api_key") {
    return (
      <div className="login-container">
        <div className="login-box">
          <h1>EdgeCaster Setup</h1>
          <p>Enter your Rhombus Organization API Key.</p>
          <form onSubmit={handleSetApiKey}>
            <div className="form-group">
              <label>Rhombus Org API Key</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Paste your API key"
                required
                autoFocus
              />
            </div>
            <button className="btn btn-primary" style={{ width: "100%" }} disabled={loading}>
              {loading ? "Validating..." : "Save API Key"}
            </button>
            {error && <div className="error-msg">{error}</div>}
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>EdgeCaster</h1>
        <p>Sign in to manage your streams.</p>
        <form onSubmit={handleLogin}>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Admin password"
              required
              autoFocus
            />
          </div>
          <button className="btn btn-primary" style={{ width: "100%" }} disabled={loading}>
            {loading ? "Signing in..." : "Sign In"}
          </button>
          {error && <div className="error-msg">{error}</div>}
        </form>
      </div>
    </div>
  );
}
