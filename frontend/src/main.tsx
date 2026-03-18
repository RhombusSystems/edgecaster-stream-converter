import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { captureException } from "./posthog";
import "./styles.css";

// Capture uncaught errors globally
window.addEventListener("error", (event) => {
  if (event.error) captureException(event.error, { source: "window.onerror" });
});
window.addEventListener("unhandledrejection", (event) => {
  captureException(event.reason, { source: "unhandledrejection" });
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
