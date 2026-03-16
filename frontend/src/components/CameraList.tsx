import { useEffect, useState, useCallback, useMemo } from "react";
import type { Camera, AppSettings } from "../types";
import * as api from "../api";
import StatusBadge from "./StatusBadge";

type StatusFilter = "all" | "online" | "offline" | "streaming";

const SearchIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8" />
    <line x1="21" y1="21" x2="16.65" y2="16.65" />
  </svg>
);

const CopyIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="9" width="13" height="13" rx="2" />
    <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
  </svg>
);

const CheckIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

export default function CameraList() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toggling, setToggling] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null);

  const maxStreams = settings?.max_streams ?? 10;

  const load = useCallback(async () => {
    try {
      const [cams, s] = await Promise.all([api.getCameras(), api.getSettings()]);
      setCameras(cams);
      setSettings(s);
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

  const handleCopy = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopiedUrl(url);
      setTimeout(() => setCopiedUrl(null), 2000);
    } catch {
      // Clipboard API may not be available over HTTP
    }
  };

  const activeCount = cameras.filter((c) => c.rtsp_enabled).length;
  const maxReached = activeCount >= maxStreams;

  // Counts for filter pills
  const counts = useMemo(() => {
    const searchLower = search.toLowerCase();
    const matchesSearch = (c: Camera) =>
      !search ||
      c.name.toLowerCase().includes(searchLower) ||
      c.location_name?.toLowerCase().includes(searchLower);

    const searched = cameras.filter(matchesSearch);
    return {
      all: searched.length,
      online: searched.filter((c) => c.status === "online").length,
      offline: searched.filter((c) => c.status === "offline" || c.status === "degraded").length,
      streaming: searched.filter((c) => c.rtsp_enabled).length,
    };
  }, [cameras, search]);

  const filtered = useMemo(() => {
    const searchLower = search.toLowerCase();
    return cameras.filter((cam) => {
      const matchesSearch =
        !search ||
        cam.name.toLowerCase().includes(searchLower) ||
        cam.location_name?.toLowerCase().includes(searchLower);
      if (!matchesSearch) return false;

      switch (filter) {
        case "online":
          return cam.status === "online";
        case "offline":
          return cam.status === "offline" || cam.status === "degraded";
        case "streaming":
          return cam.rtsp_enabled;
        default:
          return true;
      }
    });
  }, [cameras, search, filter]);

  if (loading && cameras.length === 0) {
    return <div className="loading">Loading cameras...</div>;
  }

  return (
    <div>
      <div className="toolbar">
        <h2>Cameras</h2>
        <div className="toolbar-right">
          <span className="toolbar-info">
            {activeCount}/{maxStreams} streams active
          </span>
          <button className="btn btn-secondary btn-sm" onClick={handleRefresh}>
            Refresh
          </button>
        </div>
      </div>

      {error && <div className="error-msg" style={{ marginBottom: 12 }}>{error}</div>}

      <div className="camera-toolbar">
        <div className="search-bar">
          <SearchIcon />
          <input
            type="text"
            placeholder="Search cameras..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="filter-pills">
          {(["all", "online", "offline", "streaming"] as StatusFilter[]).map((f) => (
            <button
              key={f}
              className={`filter-pill ${filter === f ? "active" : ""}`}
              onClick={() => setFilter(f)}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
              <span className="pill-count">{counts[f]}</span>
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M23 7l-7 5 7 5V7z" />
              <rect x="1" y="5" width="15" height="14" rx="2" />
            </svg>
            <p>
              {cameras.length === 0
                ? "No cameras discovered. Check your API key and click Refresh."
                : "No cameras match your search."}
            </p>
          </div>
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
              {filtered.map((cam) => (
                <tr key={cam.uuid}>
                  <td>
                    <strong>{cam.name}</strong>
                  </td>
                  <td>{cam.location_name || "\u2014"}</td>
                  <td>
                    <StatusBadge status={cam.status} />
                  </td>
                  <td>
                    {cam.stream_state ? (
                      <div>
                        <StatusBadge status={cam.stream_state} />
                        {cam.stream_state === "failed" && (
                          <div className="stream-error" title="Stream failed — check logs for details">
                            Check logs for error
                          </div>
                        )}
                      </div>
                    ) : (
                      "\u2014"
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
                      <span className="rtsp-url-container">
                        <code className="rtsp-url">{cam.rtsp_url}</code>
                        <button
                          className={`btn-icon ${copiedUrl === cam.rtsp_url ? "copied" : ""}`}
                          onClick={() => handleCopy(cam.rtsp_url)}
                          title="Copy RTSP URL"
                        >
                          {copiedUrl === cam.rtsp_url ? <CheckIcon /> : <CopyIcon />}
                        </button>
                      </span>
                    ) : (
                      "\u2014"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {maxReached && (
        <div className="info-msg" style={{ marginTop: 12 }}>
          Maximum of {maxStreams} concurrent streams reached. Disable a stream to enable another.
        </div>
      )}
    </div>
  );
}
