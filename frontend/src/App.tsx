import { useEffect, useState } from "react";
import type { SetupState } from "./types";
import * as api from "./api";
import SetupForm from "./components/SetupForm";
import Dashboard from "./components/Dashboard";
import CameraList from "./components/CameraList";
import SettingsPanel from "./components/SettingsPanel";
import bannerImg from "./media/accelerate-banner 827x192.png";
import iconImg from "./media/developer-icon-512.png";

type Page = "dashboard" | "cameras" | "settings";

const NAV_ITEMS: { page: Page; label: string; icon: JSX.Element }[] = [
  {
    page: "dashboard",
    label: "Dashboard",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  {
    page: "cameras",
    label: "Cameras",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M23 7l-7 5 7 5V7z" />
        <rect x="1" y="5" width="15" height="14" rx="2" />
      </svg>
    ),
  },
  {
    page: "settings",
    label: "Settings",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
      </svg>
    ),
  },
];

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
      <header className="top-banner">
        <img src={bannerImg} alt="" className="top-banner-img" />
      </header>
      <div className="app-body">
        <aside className="sidebar">
          <div className="sidebar-brand">
            <img src={iconImg} alt="" className="sidebar-icon" />
            <div className="sidebar-brand-text">
              <span className="sidebar-title">EdgeCaster</span>
              <span className="sidebar-subtitle">Stream Converter</span>
            </div>
          </div>
          <nav>
            {NAV_ITEMS.map((item) => (
              <a
                key={item.page}
                href="#"
                className={page === item.page ? "active" : ""}
                onClick={(e) => {
                  e.preventDefault();
                  setPage(item.page);
                }}
              >
                {item.icon}
                {item.label}
              </a>
            ))}
          </nav>
          <div className="sidebar-footer">
            Made by Rhombus Developers with &#10084;&#65039; in Sacramento
          </div>
        </aside>
        <main className="main-content">
          {page === "dashboard" && <Dashboard />}
          {page === "cameras" && <CameraList />}
          {page === "settings" && <SettingsPanel />}
        </main>
      </div>
    </div>
  );
}
