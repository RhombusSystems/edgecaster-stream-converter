import { useEffect, useState } from "react";
import type { SetupState } from "./types";
import * as api from "./api";
import LoginForm from "./components/LoginForm";
import Dashboard from "./components/Dashboard";
import CameraList from "./components/CameraList";
import SettingsPanel from "./components/SettingsPanel";

type Page = "dashboard" | "cameras" | "settings";

export default function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [setupState, setSetupState] = useState<SetupState>("needs_password");
  const [page, setPage] = useState<Page>("cameras");
  const [checking, setChecking] = useState(true);

  const checkAuth = async () => {
    try {
      const status = await api.getAuthStatus();
      setSetupState(status.setup_state);

      if (status.setup_state === "ready") {
        // Try loading settings to verify session is valid
        try {
          await api.getSettings();
          setAuthenticated(true);
        } catch {
          setAuthenticated(false);
        }
      } else {
        setAuthenticated(false);
      }
    } catch {
      setAuthenticated(false);
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  if (checking) {
    return <div className="loading">Loading...</div>;
  }

  if (!authenticated || setupState !== "ready") {
    return (
      <LoginForm
        setupState={setupState}
        onSuccess={() => {
          setChecking(true);
          checkAuth();
        }}
      />
    );
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>EdgeCaster</h1>
        <nav>
          <a
            href="#"
            className={page === "dashboard" ? "active" : ""}
            onClick={(e) => { e.preventDefault(); setPage("dashboard"); }}
          >
            Dashboard
          </a>
          <a
            href="#"
            className={page === "cameras" ? "active" : ""}
            onClick={(e) => { e.preventDefault(); setPage("cameras"); }}
          >
            Cameras
          </a>
          <a
            href="#"
            className={page === "settings" ? "active" : ""}
            onClick={(e) => { e.preventDefault(); setPage("settings"); }}
          >
            Settings
          </a>
        </nav>
      </aside>
      <main className="main-content">
        {page === "dashboard" && <Dashboard />}
        {page === "cameras" && <CameraList />}
        {page === "settings" && (
          <SettingsPanel
            onLogout={() => {
              setAuthenticated(false);
              setSetupState("ready");
            }}
          />
        )}
      </main>
    </div>
  );
}
