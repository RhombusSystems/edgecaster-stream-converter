import { useState } from "react";
import CameraList from "./CameraList";
import LogsViewer from "./LogsViewer";

type Sub = "cameras" | "logs";

export default function CamerasView() {
  const [sub, setSub] = useState<Sub>("cameras");

  return (
    <div>
      <div className="subtabs">
        <button className={`subtab ${sub === "cameras" ? "active" : ""}`} onClick={() => setSub("cameras")}>
          Cameras
        </button>
        <button className={`subtab ${sub === "logs" ? "active" : ""}`} onClick={() => setSub("logs")}>
          Logs
        </button>
      </div>
      {sub === "cameras" ? <CameraList /> : <LogsViewer />}
    </div>
  );
}
