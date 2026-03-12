import { useEffect, useState } from "react";
import type { SetupState } from "./types";
import * as api from "./api";
import SetupForm from "./components/SetupForm";
import Dashboard from "./components/Dashboard";
import CameraList from "./components/CameraList";
import SettingsPanel from "./components/SettingsPanel";
import bannerImg from "./media/accelerate-banner 827x192.png";

type Page = "dashboard" | "cameras" | "settings";

export default function App() {
  const [setupState, setSetupState] = useState<SetupState>("needs_api_key");
  const [page, setPage] = useState<Page>("cameras");
  const [checking, setChecking] = useState(true);

  const checkSetup = async () => {
    try {
      const status = await api.getAuthStatus();
      setSetupState(status.setup_state);
    } catch {
      // Backend not reachable — stay on setup
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    checkSetup();
  }, []);

  if (checking) {
    return <div className="loading">Loading...</div>;
  }

  if (setupState !== "ready") {
    return (
      <SetupForm
        onSuccess={() => {
          setChecking(true);
          checkSetup();
        }}
      />
    );
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <img src={bannerImg} alt="EdgeCaster" className="sidebar-logo" />
        </div>
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
        {page === "settings" && <SettingsPanel />}
      </main>
    </div>
  );
}
