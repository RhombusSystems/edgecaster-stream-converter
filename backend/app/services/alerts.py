"""LAN alerting via a generic outbound webhook.

Fires JSON POSTs to a configured webhook URL (Slack incoming webhook, Make.com,
or any custom LAN listener). Includes per-type cooldown and clear-on-recovery so
a flapping condition does not spam. Active alerts are also surfaced to the
dashboard via the system-status SSE stream.
"""

from __future__ import annotations

import logging
import time

import httpx

from backend.app.config import EdgeCasterConfig
from backend.app.models.settings import Alert, SystemStatus
from backend.app.services.posthog_service import get_device_id
from backend.app.utils.network import get_hostname, get_local_ip

logger = logging.getLogger("edgecaster.alerts")

# Re-send a still-active alert at most this often.
COOLDOWN_SECONDS = 300
# Require this many consecutive breaching samples before raising a load/CPU alert.
SUSTAIN_SAMPLES = 3
_POST_TIMEOUT = 5.0

SEVERITY_CRITICAL = "critical"
SEVERITY_WARNING = "warning"


class AlertManager:
    """Tracks active alert conditions and delivers them to a webhook."""

    def __init__(self, config: EdgeCasterConfig) -> None:
        self._config = config
        self._active: dict[str, Alert] = {}
        self._last_sent: dict[str, float] = {}
        self._breach_counts: dict[str, int] = {}

    # ---- public API ---------------------------------------------------

    def get_active(self) -> list[Alert]:
        return list(self._active.values())

    async def raise_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        """Mark a condition active and deliver it (subject to cooldown)."""
        now = time.time()
        existing = self._active.get(alert_type)
        if existing is None:
            alert = Alert(
                type=alert_type,
                severity=severity,
                title=title,
                message=message,
                since=now,
            )
            self._active[alert_type] = alert
            logger.warning("ALERT raised [%s] %s: %s", severity, title, message)
        else:
            alert = existing
            alert.severity = severity
            alert.message = message

        # Cooldown gate on delivery (not on tracking).
        last = self._last_sent.get(alert_type, 0)
        if now - last < COOLDOWN_SECONDS:
            return
        self._last_sent[alert_type] = now
        await self._deliver("alert", alert, details or {})

    async def clear_alert(self, alert_type: str) -> None:
        """Clear a previously-active condition and notify recovery."""
        alert = self._active.pop(alert_type, None)
        self._breach_counts.pop(alert_type, None)
        self._last_sent.pop(alert_type, None)
        if alert is None:
            return
        logger.info("ALERT cleared: %s", alert.title or alert_type)
        recovered = Alert(
            type=alert_type,
            severity="info",
            title=f"Recovered: {alert.title}",
            message="Condition has cleared.",
            since=time.time(),
        )
        await self._deliver("recovery", recovered, {})

    async def send_test(self) -> bool:
        """Fire a test alert regardless of enabled thresholds. Returns success."""
        test = Alert(
            type="test",
            severity=SEVERITY_WARNING,
            title="EdgeCaster test alert",
            message="This is a test alert from EdgeCaster. Webhook is working.",
            since=time.time(),
        )
        return await self._deliver("test", test, {}, force=True)

    async def evaluate_system(self, status: SystemStatus) -> None:
        """Evaluate power/thermal/CPU/load conditions against configured thresholds."""
        if not self._config.alerts_enabled:
            return

        # Power / under-voltage — critical, immediate.
        if status.under_voltage_now:
            await self.raise_alert(
                "under_voltage",
                SEVERITY_CRITICAL,
                "Under-voltage detected",
                "The Pi is power constrained (under-voltage now). Check the power supply/cabling.",
                {"throttle_status": status.throttle_status},
            )
        else:
            await self.clear_alert("under_voltage")

        # Thermal throttling — warning, immediate.
        temp_over = (
            self._config.temp_alert_threshold_c > 0
            and status.temperature_c >= self._config.temp_alert_threshold_c
        )
        if status.throttled_now or status.freq_capped_now or temp_over:
            await self.raise_alert(
                "thermal",
                SEVERITY_WARNING,
                "Thermal throttling / high temperature",
                f"Temperature {status.temperature_c}°C, throttle status {status.throttle_status}.",
                {"temperature_c": status.temperature_c},
            )
        else:
            await self.clear_alert("thermal")

        # High sustained CPU — warning, with hysteresis.
        await self._sustained(
            "high_cpu",
            breaching=self._config.cpu_alert_threshold > 0
            and status.cpu_percent >= self._config.cpu_alert_threshold,
            severity=SEVERITY_WARNING,
            title="High sustained CPU",
            message=f"CPU at {status.cpu_percent:.0f}% "
            f"(threshold {self._config.cpu_alert_threshold}%).",
            details={"cpu_percent": status.cpu_percent},
        )

        # High sustained load average — warning, with hysteresis.
        await self._sustained(
            "high_load",
            breaching=self._config.load_alert_threshold > 0
            and status.load_avg_1m >= self._config.load_alert_threshold,
            severity=SEVERITY_WARNING,
            title="High system load",
            message=f"1-min load {status.load_avg_1m} "
            f"(threshold {self._config.load_alert_threshold}).",
            details={"load_avg_1m": status.load_avg_1m},
        )

    # ---- internals ----------------------------------------------------

    async def _sustained(
        self,
        alert_type: str,
        *,
        breaching: bool,
        severity: str,
        title: str,
        message: str,
        details: dict,
    ) -> None:
        """Raise only after SUSTAIN_SAMPLES consecutive breaches; clear immediately."""
        if breaching:
            count = self._breach_counts.get(alert_type, 0) + 1
            self._breach_counts[alert_type] = count
            if count >= SUSTAIN_SAMPLES:
                await self.raise_alert(alert_type, severity, title, message, details)
        else:
            if self._breach_counts.get(alert_type):
                self._breach_counts[alert_type] = 0
            await self.clear_alert(alert_type)

    async def _deliver(
        self, kind: str, alert: Alert, details: dict, force: bool = False
    ) -> bool:
        config = self._config
        if not force and not config.alerts_enabled:
            return False
        url = config.alert_webhook_url.strip()
        if not url:
            if force:
                logger.warning("Test alert requested but no webhook URL configured")
            return False

        payload = {
            "device": get_device_id(),
            "hostname": get_hostname(),
            "local_ip": get_local_ip(),
            "kind": kind,  # "alert" | "recovery" | "test"
            "severity": alert.severity,
            "type": alert.type,
            "title": alert.title,
            # Slack incoming webhooks render the "text" field; include both.
            "text": f"[{alert.severity.upper()}] {alert.title} — {alert.message}",
            "message": alert.message,
            "timestamp": alert.since,
            "details": details,
        }
        try:
            async with httpx.AsyncClient(timeout=_POST_TIMEOUT) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
            return True
        except Exception as e:  # noqa: BLE001 - alerting must never crash the app
            logger.error("Failed to deliver %s webhook: %s", kind, e)
            return False
