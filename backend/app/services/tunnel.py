"""Cloudflare quick-tunnel manager.

Uses ``cloudflared tunnel --url`` (TryCloudflare) to expose the local dashboard on
a public ``*.trycloudflare.com`` URL with NO Cloudflare account, token, or config.
The URL is ephemeral (changes on each restart) — that is the trade-off for the
zero-credential flow. Public traffic is authenticated by the app's Host/CF-header
middleware; LAN traffic is never challenged.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil

from backend.app.config import EdgeCasterConfig, save_config

logger = logging.getLogger("edgecaster.tunnel")

# cloudflared points at the app directly (uvicorn) so the auth middleware sees the
# Cloudflare edge headers without any intermediate proxy stripping them.
TUNNEL_ORIGIN = "http://127.0.0.1:8000"
_URL_RE = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
_RESTART_DELAY = 5


class TunnelManager:
    """Manages the cloudflared subprocess and the assigned public URL."""

    def __init__(self, config: EdgeCasterConfig) -> None:
        self._config = config
        self._process: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task | None = None
        self._monitor_task: asyncio.Task | None = None
        self._stopping = False
        self.public_url = ""
        self.running = False
        self.last_error = ""

    @staticmethod
    def is_installed() -> bool:
        return shutil.which("cloudflared") is not None

    async def start(self) -> None:
        if not self.is_installed():
            self.last_error = (
                "cloudflared is not installed on this device. Reinstall EdgeCaster "
                "or install cloudflared to enable public access."
            )
            raise RuntimeError(self.last_error)
        if self.running:
            return
        self._stopping = False
        self.last_error = ""
        await self._launch()

    async def _launch(self) -> None:
        cmd = ["cloudflared", "tunnel", "--url", TUNNEL_ORIGIN, "--no-autoupdate"]
        logger.info("Starting Cloudflare quick tunnel -> %s", TUNNEL_ORIGIN)
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self.running = True
        self._reader_task = asyncio.create_task(self._read_output(), name="tunnel-reader")
        self._monitor_task = asyncio.create_task(self._monitor(), name="tunnel-monitor")

    async def _read_output(self) -> None:
        proc = self._process
        if proc is None or proc.stdout is None:
            return
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode(errors="replace")
                match = _URL_RE.search(text)
                if match and self.public_url != match.group(0):
                    self.public_url = match.group(0)
                    self._config.public_hostname = self.public_url.split("://", 1)[1]
                    save_config(self._config)
                    logger.info("Cloudflare tunnel ready: %s", self.public_url)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.debug("tunnel reader ended: %s", e)

    async def _monitor(self) -> None:
        proc = self._process
        if proc is None:
            return
        rc = await proc.wait()
        self.running = False
        if self._stopping or not self._config.public_access_enabled:
            return
        logger.warning("cloudflared exited (code=%s); restarting in %ds", rc, _RESTART_DELAY)
        await asyncio.sleep(_RESTART_DELAY)
        if not self._stopping and self._config.public_access_enabled:
            await self._launch()

    async def wait_for_url(self, timeout: float = 25.0) -> str:
        """Wait until the tunnel reports its public URL (or timeout). Returns it or ''."""
        elapsed = 0.0
        while elapsed < timeout:
            if self.public_url:
                return self.public_url
            if not self.running:
                break
            await asyncio.sleep(0.5)
            elapsed += 0.5
        return self.public_url

    async def stop(self) -> None:
        self._stopping = True
        self.running = False
        for task in (self._reader_task, self._monitor_task):
            if task and not task.done():
                task.cancel()
        self._reader_task = self._monitor_task = None
        if self._process and self._process.returncode is None:
            try:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5)
                except TimeoutError:
                    self._process.kill()
            except ProcessLookupError:
                pass
        self._process = None
        self.public_url = ""
        self._config.public_hostname = ""
        save_config(self._config)

    def status(self) -> dict:
        return {
            "enabled": self._config.public_access_enabled,
            "running": self.running,
            "public_url": self.public_url or (
                f"https://{self._config.public_hostname}" if self._config.public_hostname else ""
            ),
            "installed": self.is_installed(),
            "has_credentials": bool(self._config.auth_username and self._config.auth_password_hash),
            "username": self._config.auth_username,
            "last_error": self.last_error,
        }
