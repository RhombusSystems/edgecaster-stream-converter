import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { LogSource } from "../types";
import * as api from "../api";

const MAX_LINES = 2000;

const SOURCE_LABELS: Record<string, string> = {
  streams: "Streams",
  application: "Application",
  rhombus: "Rhombus API",
};

function lineClass(line: string): string {
  if (/\bERROR\b|\[ERROR\]/.test(line)) return "log-line error";
  if (/\bWARN(ING)?\b|\[WARNING\]/.test(line)) return "log-line warning";
  if (/\[INFO\]|\bINFO\b/.test(line)) return "log-line info";
  return "log-line";
}

export default function LogsViewer() {
  const [sources, setSources] = useState<LogSource[]>([]);
  const [source, setSource] = useState("streams");
  const [lines, setLines] = useState<string[]>([]);
  const [live, setLive] = useState(true);
  const [error, setError] = useState("");
  const consoleRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);

  useEffect(() => {
    api.getLogSources().then((r) => setSources(r.sources)).catch(() => {});
  }, []);

  // Load snapshot + open live tail whenever source changes or live toggles on.
  useEffect(() => {
    let es: EventSource | null = null;
    let cancelled = false;

    (async () => {
      try {
        const snap = await api.getLogs(source, 300);
        if (cancelled) return;
        setLines(snap.lines);
        setError("");
        stickRef.current = true;
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load logs");
      }
      if (cancelled || !live) return;
      es = api.subscribeLogs(source, (line) => {
        setLines((prev) => {
          const next = prev.length >= MAX_LINES ? prev.slice(-MAX_LINES + 1) : prev;
          return [...next, line];
        });
      });
    })();

    return () => { cancelled = true; if (es) es.close(); };
  }, [source, live]);

  // Keep pinned to the bottom unless the user scrolled up.
  useLayoutEffect(() => {
    const el = consoleRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [lines]);

  const onScroll = () => {
    const el = consoleRef.current;
    if (!el) return;
    stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  };

  return (
    <div>
      <div className="logs-toolbar">
        <div className="filter-pills">
          {sources.map((s) => (
            <button
              key={s.name}
              className={`filter-pill ${source === s.name ? "active" : ""}`}
              onClick={() => setSource(s.name)}
              disabled={!s.exists}
              title={s.exists ? "" : "No log file yet"}
            >
              {SOURCE_LABELS[s.name] ?? s.name}
            </button>
          ))}
        </div>
        <div className="toolbar-spacer" style={{ flex: 1 }} />
        <span className="logs-status">
          <span className={`live-dot ${live ? "" : "paused"}`} />
          {live ? "Live" : "Paused"} · {lines.length} lines
        </span>
        <button className="btn btn-secondary btn-sm" onClick={() => setLive((v) => !v)}>
          {live ? "Pause" : "Resume"}
        </button>
        <button className="btn btn-secondary btn-sm" onClick={() => { setLines([]); stickRef.current = true; }}>
          Clear
        </button>
      </div>

      {error && <div className="error-msg" style={{ marginBottom: 10 }}>{error}</div>}

      <div className="logs-console" ref={consoleRef} onScroll={onScroll}>
        {lines.length === 0 ? (
          <div className="log-empty">No log lines yet. New activity will appear here live.</div>
        ) : (
          lines.map((ln, i) => (
            <div key={i} className={lineClass(ln)}>{ln || " "}</div>
          ))
        )}
      </div>
    </div>
  );
}
