import { useState } from "react";
import * as api from "../api";
import iconImg from "../media/developer-icon-512.png";

interface SetupFormProps {
  onSuccess: () => void;
}

export default function SetupForm({ onSuccess }: SetupFormProps) {
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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

  return (
    <div className="setup-container">
      <div className="setup-box">
        <img src={iconImg} alt="EdgeCaster" className="setup-icon" />
        <h1>EdgeCaster Setup</h1>
        <p>Enter your Rhombus Organization API Key to get started.</p>
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
