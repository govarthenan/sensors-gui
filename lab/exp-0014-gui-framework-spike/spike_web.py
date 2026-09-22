"""Spike: one live value from the real sampler, in a local web window.

This is throw-away code. It exists to prove the stack of ADR 0012 before the
application is built on it, and to give the idle cost a number.

    uv run python lab/exp-0014-gui-framework-spike/spike_web.py --hz 10

Options:
    --hz N        the sample rate, 0.25 to 10
    --all         stream every channel, not one
    --no-window   do not open the browser window (the server alone)
    --port N      the port on 127.0.0.1

Nothing is written to hardware. The server listens on 127.0.0.1 only.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import subprocess
import time
from collections.abc import AsyncIterator
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from sensors_gui import naming
from sensors_gui.collectors.hwmon import HwmonCollector
from sensors_gui.collectors.nvidia import NvidiaCollector
from sensors_gui.collectors.power_supply import PowerSupplyCollector
from sensors_gui.collectors.privileged import PrivilegedCollector
from sensors_gui.collectors.system import SystemCollector
from sensors_gui.model import Sample, SensorSpec
from sensors_gui.registry import Registry
from sensors_gui.sampler import Sampler

logger = logging.getLogger("spike")

HOST = "127.0.0.1"
DEFAULT_PORT = 8712
SPIKE_LABEL = "Tctl"

PAGE = (Path(__file__).parent / "spike_web.html").read_text()


class SpikeState:
    """Everything the spike holds while it runs."""

    def __init__(self, hz: float, stream_all: bool) -> None:
        """Create the state.

        Args:
            hz: The sample rate.
            stream_all: Stream every channel, instead of one.
        """
        self.hz = hz
        self.stream_all = stream_all
        self.registry = Registry(
            [
                HwmonCollector(),
                NvidiaCollector(),
                PowerSupplyCollector(),
                PrivilegedCollector(),
                SystemCollector(),
            ]
        )
        self.sampler = Sampler(self.registry)
        self.specs: list[SensorSpec] = []
        self.pass_ms = 0.0
        self.clients: set[WebSocket] = set()
        self.frames_sent = 0

    def discover(self) -> None:
        """Find every sensor and choose the ones the spike streams."""
        self.registry.discover()
        decorated = [naming.friendly(raw) for raw in self.registry.specs()]
        if self.stream_all:
            self.specs = decorated
        else:
            self.specs = [spec for spec in decorated if spec.label == SPIKE_LABEL] or decorated[:1]

    def catalogue(self) -> list[dict[str, object]]:
        """Return the static description of every streamed channel."""
        return [
            {
                "key": spec.id.key,
                "label": spec.label,
                "group": str(spec.group),
                "unit": spec.unit.symbol,
                "low": spec.low,
                "high": spec.high,
                "origin": spec.origin,
            }
            for spec in self.specs
        ]

    def frame(self, sample: Sample) -> str:
        """Return one sample as a compact JSON frame, aligned to the catalogue order."""
        by_id = sample.by_id()
        values: list[float | None] = []
        for spec in self.specs:
            reading = by_id.get(spec.id)
            values.append(None if reading is None else reading.value)
        return json.dumps({"t": sample.timestamp, "ms": round(self.pass_ms, 3), "v": values})


def build_app(state: SpikeState) -> FastAPI:
    """Build the spike's web application.

    Args:
        state: The shared state.

    Returns:
        The application.
    """

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Start the sampler loop, and stop it and the collectors at the end."""
        task = asyncio.create_task(sample_loop(state))
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            state.registry.close()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        """Serve the one page of the spike."""
        return PAGE

    @app.get("/api/catalogue")
    async def catalogue() -> dict[str, object]:
        """Serve the static description of every streamed channel."""
        return {"hz": state.hz, "channels": state.catalogue()}

    @app.websocket("/ws")
    async def stream(socket: WebSocket) -> None:
        """Push one frame for every sample, until the client goes away."""
        await socket.accept()
        state.clients.add(socket)
        try:
            while True:
                await socket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            state.clients.discard(socket)

    return app


async def sample_loop(state: SpikeState) -> None:
    """Sample at the chosen rate and push every frame to every client."""
    period = 1.0 / state.hz
    start = time.monotonic()
    passes = 0
    while True:
        started = time.perf_counter()
        sample = state.sampler.sample()
        state.pass_ms = (time.perf_counter() - started) * 1000
        if state.clients:
            payload = state.frame(sample)
            for socket in list(state.clients):
                try:
                    await socket.send_text(payload)
                    state.frames_sent += 1
                except Exception:  # noqa: BLE001 - a dead client must not stop the loop
                    state.clients.discard(socket)
        passes += 1
        delay = start + passes * period - time.monotonic()
        await asyncio.sleep(max(delay, 0.0))


def open_window(url: str, profile: Path) -> subprocess.Popen[bytes]:
    """Open the page in a dedicated Chrome application window.

    A separate profile directory keeps the window out of Gova's own browser, so
    that the measurement counts this window alone and no extension runs in it.

    Args:
        url: The address to open.
        profile: The profile directory to use.

    Returns:
        The browser process.
    """
    profile.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        [
            "google-chrome",
            f"--app={url}",
            f"--user-data-dir={profile}",
            "--window-size=2560,1440",
            "--window-position=0,0",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=Translate,MediaRouter",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> None:
    """Run the spike."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hz", type=float, default=2.0)
    parser.add_argument("--all", action="store_true", dest="stream_all")
    parser.add_argument("--no-window", action="store_true")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--profile", type=Path, default=Path.home() / ".local/state/sensors-gui/spike-profile")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    state = SpikeState(hz=args.hz, stream_all=args.stream_all)
    state.discover()
    print(f"spike: {len(state.specs)} channel(s) at {args.hz} Hz on http://{HOST}:{args.port}")

    browser: subprocess.Popen[bytes] | None = None
    if not args.no_window:
        browser = open_window(f"http://{HOST}:{args.port}/", args.profile)

    try:
        uvicorn.run(build_app(state), host=HOST, port=args.port, log_level="warning")
    finally:
        if browser is not None:
            browser.terminate()


if __name__ == "__main__":
    main()
