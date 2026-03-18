import posthog from "posthog-js";

let initialized = false;

/**
 * Initialize PostHog from backend config.
 * Fetches the PostHog API key and host from the backend so config
 * lives in one place (config.yaml).
 */
export async function initPostHog(): Promise<void> {
  if (initialized) return;

  try {
    const res = await fetch("/api/system/posthog-config");
    if (!res.ok) return;

    const config: { api_key: string; host: string; device_id: string } =
      await res.json();

    if (!config.api_key) return;

    posthog.init(config.api_key, {
      api_host: config.host,
      // Use the same device_id as the backend for unified identity
      bootstrap: { distinctID: config.device_id },
      autocapture: false, // Edge device UI, no need for autocapture
      capture_pageview: false,
      capture_pageleave: false,
      enable_recording_console_log: false,
      persistence: "memory", // No cookies needed on local device UI
    });

    initialized = true;
  } catch {
    // PostHog init is best-effort — don't break the app
  }
}

/**
 * Capture an exception to PostHog error tracking.
 */
export function captureException(
  error: unknown,
  context?: Record<string, unknown>
): void {
  if (!initialized) return;
  const err = error instanceof Error ? error : new Error(String(error));
  posthog.captureException(err, context);
}

/**
 * Capture a custom event.
 */
export function captureEvent(
  event: string,
  properties?: Record<string, unknown>
): void {
  if (!initialized) return;
  posthog.capture(event, properties);
}
