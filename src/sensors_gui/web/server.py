"""The web server: the catalogue, the frame stream and the static files.

It listens on `127.0.0.1` only. No route writes to hardware, now or ever;
ADR 0007 and ADR 0012. The only things a client can change are the sample
rate, the pause state and a re-scan, and none of those touches the machine.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sensors_gui.web.service import MAX_HZ, MIN_HZ, SensorService

logger = logging.getLogger(__name__)

STATIC = Path(__file__).parent / "static"
HOST = "127.0.0.1"


# The browser must check a page again before it uses a cached copy. Without it
# a new status bar met an old `index.html`, and every frame raised an error.
REVALIDATE = {"Cache-Control": "no-cache"}


class RevalidatedFiles(StaticFiles):
    """Static files the browser must check again before it uses a cached copy.

    Without this, Chrome kept serving an old `widgets.js` after a change, by
    its own heuristic, and a reload showed the old page. `no-cache` still lets
    it keep the file: it asks with the ETag and gets a 304 when nothing moved.
    """

    def file_response(self, *args: object, **kwargs: object) -> Response:
        """Return the file with a header that says to revalidate it."""
        response = super().file_response(*args, **kwargs)  # type: ignore[arg-type]
        response.headers.update(REVALIDATE)
        return response


class RateRequest(BaseModel):
    """The body of a request to change the sample rate."""

    hz: float = Field(ge=MIN_HZ, le=MAX_HZ, description="Passes per second, from 0.25 to 10.")


class PauseRequest(BaseModel):
    """The body of a request to pause or resume sampling."""

    paused: bool = Field(description="True stops sampling; False starts it again.")


class FrameHub:
    """Carries each frame from the worker thread to every open WebSocket.

    The worker calls `publish` on its own thread. The frame is handed to the
    event loop with `call_soon_threadsafe` and put on a queue of one for each
    client. A slow client loses the older frame instead of holding the worker
    up: a sensor screen wants the newest value, never a backlog.
    """

    def __init__(self) -> None:
        """Create an empty hub."""
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queues: set[asyncio.Queue[str]] = set()

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        """Remember the event loop the frames must be delivered on."""
        self._loop = loop

    def register(self) -> asyncio.Queue[str]:
        """Open a queue for one client and return it."""
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        self._queues.add(queue)
        return queue

    def forget(self, queue: asyncio.Queue[str]) -> None:
        """Close one client's queue."""
        self._queues.discard(queue)

    def publish(self, frame: dict[str, object]) -> None:
        """Hand one frame to every client. Called on the worker thread."""
        loop = self._loop
        if loop is None or not self._queues:
            return
        payload = json.dumps(frame, separators=(",", ":"))
        loop.call_soon_threadsafe(self._deliver, payload)

    def _deliver(self, payload: str) -> None:
        """Put the frame on every queue, dropping whatever a full one still holds."""
        for queue in self._queues:
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(payload)


def build_app(service: SensorService) -> FastAPI:
    """Build the application around one service.

    Args:
        service: The sampling service. It must already have discovered.

    Returns:
        The application.
    """
    hub = FrameHub()

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Start the worker when the server starts, and stop it at the end."""
        hub.bind(asyncio.get_running_loop())
        service.subscribe(hub.publish)
        service.start()
        try:
            yield
        finally:
            service.unsubscribe(hub.publish)
            service.stop()

    app = FastAPI(
        title="sensors-gui",
        description="A read-only sensor monitor for one PC. No route writes to hardware.",
        lifespan=lifespan,
    )

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        """Serve the application shell."""
        return FileResponse(STATIC / "index.html", headers=REVALIDATE)

    @app.get("/gallery", include_in_schema=False)
    async def gallery() -> FileResponse:
        """Serve the component review page."""
        return FileResponse(STATIC / "gallery.html", headers=REVALIDATE)

    @app.get("/api/catalogue", summary="Every channel, its unit, its scale and its thresholds")
    async def catalogue() -> dict[str, object]:
        """Return the static description of every channel, in frame order."""
        return service.catalogue()

    @app.get("/api/frame", summary="One sample, for a client that does not want the stream")
    async def frame() -> dict[str, object]:
        """Return the newest frame, taking a pass if none has been taken yet."""
        return service.sample_once()

    @app.get("/api/alerts", summary="Every reading that left its published scale, newest first")
    async def alerts() -> dict[str, object]:
        """Return the alert log. It lives in memory; a restart empties it."""
        return {
            "alerts": service.alerts.entries(),
            "open": service.alerts.open_count(),
            "total": service.alerts.total(),
        }

    @app.post("/api/rate", summary="Change the sample rate")
    async def set_rate(request: RateRequest) -> dict[str, float]:
        """Set how many passes a second the service takes."""
        return {"hz": service.set_rate(request.hz)}

    @app.post("/api/pause", summary="Pause or resume sampling")
    async def set_paused(request: PauseRequest) -> dict[str, bool]:
        """Stop or start the worker's passes. The collectors stay open."""
        return {"paused": service.set_paused(request.paused)}

    @app.post("/api/rescan", summary="Find the sensors again")
    async def rescan() -> dict[str, object]:
        """Discover again, because a device may have appeared or gone.

        Every channel index changes, so the client must fetch the catalogue
        again before it reads another frame.
        """
        service.discover()
        return service.catalogue()

    @app.websocket("/ws")
    async def stream(socket: WebSocket) -> None:
        """Push one frame for each pass, until the client goes away."""
        await socket.accept()
        queue = hub.register()
        try:
            while True:
                await socket.send_text(await queue.get())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            hub.forget(queue)

    @app.exception_handler(404)
    async def not_found(_: object, __: object) -> JSONResponse:
        """Answer an unknown route with JSON, as the project's conventions ask."""
        return JSONResponse(status_code=404, content={"error": "no such route"})

    app.mount("/static", RevalidatedFiles(directory=STATIC), name="static")
    return app
