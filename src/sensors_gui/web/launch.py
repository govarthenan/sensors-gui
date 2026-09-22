"""Start the server and open the window. One command, ADR 0012.

    uv run python -m sensors_gui.web

The server binds `127.0.0.1` and nothing else. The window is a Chrome
application window with its own profile directory, so it carries none of
Gova's extensions and does not touch the everyday browser profile.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import socket
import subprocess
from pathlib import Path

import uvicorn

from sensors_gui.web.server import HOST, build_app
from sensors_gui.web.service import DEFAULT_HZ, build_service

logger = logging.getLogger(__name__)

PREFERRED_PORT = 8713
PROFILE = Path.home() / ".local/state/sensors-gui/window-profile"
BROWSERS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")


def free_port(preferred: int = PREFERRED_PORT) -> int:
    """Return the preferred port, or another free one when it is taken.

    Args:
        preferred: The port to try first.

    Returns:
        A port that was free a moment ago on `127.0.0.1`.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((HOST, preferred))
        except OSError:
            probe.bind((HOST, 0))
        return int(probe.getsockname()[1])


def find_browser() -> str | None:
    """Return the first Chrome-like browser on the path, or None."""
    for name in BROWSERS:
        found = shutil.which(name)
        if found:
            return found
    return None


def open_window(url: str, profile: Path = PROFILE, width: int = 2560, height: int = 1440) -> subprocess.Popen | None:
    """Open `url` as an application window, or return None when no browser is found.

    Args:
        url: The address to open.
        profile: The browser profile directory to use.
        width: The window width in pixels.
        height: The window height in pixels.

    Returns:
        The browser process, or None when there is nothing to start it with.
    """
    browser = find_browser()
    if browser is None:
        logger.warning("launch: no Chrome-like browser found; open %s yourself", url)
        return None
    profile.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        [
            browser,
            f"--app={url}",
            f"--user-data-dir={profile}",
            f"--window-size={width},{height}",
            "--window-position=0,0",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=Translate,MediaRouter",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> None:
    """Start the service, the server and the window."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hz", type=float, default=DEFAULT_HZ, help="passes per second, 0.25 to 10")
    parser.add_argument("--port", type=int, default=PREFERRED_PORT)
    parser.add_argument("--page", default="/", help="the page to open, for example /gallery")
    parser.add_argument("--no-window", action="store_true", help="serve only; do not open a browser")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    service = build_service(hz=args.hz)
    service.discover()
    port = free_port(args.port)
    catalogue = service.catalogue()
    print(f"sensors-gui: {catalogue['shown']} channels shown, {catalogue['hidden']} hidden, at {args.hz} Hz")
    print(f"sensors-gui: http://{HOST}:{port}{args.page}")

    browser = None if args.no_window else open_window(f"http://{HOST}:{port}{args.page}")
    try:
        uvicorn.run(build_app(service), host=HOST, port=port, log_level="warning")
    finally:
        if browser is not None:
            browser.terminate()


if __name__ == "__main__":
    main()
