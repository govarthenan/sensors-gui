"""Render the monitor screen once, headless, and print it.

    uv run python scripts/preview-screen.py

A terminal application cannot be looked at from inside a session that has no
terminal, and every defect that mattered in this project was found by looking
at the thing rather than by running the tests. This renders the real screen,
against the real machine, into plain text.

It reads only. It starts the application in Textual's test harness, waits for
a few samples so the sparklines fill, prints every panel and the status line,
then stops.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sensors_gui import naming
from sensors_gui.__main__ import worth_showing
from sensors_gui.app.panel import GroupPanel
from sensors_gui.app.sensors_app import SensorsApp
from sensors_gui.app.status import StatusBar
from sensors_gui.collectors.hwmon import HwmonCollector
from sensors_gui.collectors.nvidia import NvidiaCollector
from sensors_gui.collectors.power_supply import PowerSupplyCollector
from sensors_gui.collectors.system import SystemCollector

logging.basicConfig(level=logging.ERROR, format="%(levelname)s %(name)s: %(message)s")


async def render(rows: int, settle: float, show_all: bool) -> None:
    """Start the application, let it settle, then print what it drew.

    Args:
        rows: How many rows of each panel to print. 0 prints every row.
        settle: How many seconds to sample before printing.
        show_all: Whether to include the channels the BIOS proved wrong.
    """
    app = SensorsApp(
        collectors=[HwmonCollector(), NvidiaCollector(), PowerSupplyCollector(), SystemCollector()],
        hz=10.0,
        decorate=naming.friendly,
        keep=(lambda spec: True) if show_all else worth_showing,
    )
    async with app.run_test(size=(120, 60)) as pilot:
        await pilot.pause(settle)
        for panel in app.query(GroupPanel):
            lines = panel.render_rows().plain.splitlines()
            print(f"\n┌─ {panel.border_title} ({len(lines)}) " + "─" * 40)
            shown = lines if rows == 0 else lines[:rows]
            for line in shown:
                print("│ " + line.rstrip())
            if len(lines) > len(shown):
                print(f"│ ... {len(lines) - len(shown)} more")
        print("\n" + app.query_one(StatusBar).render_status())


def main() -> None:
    """Parse the arguments and render."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=9, help="rows per panel; 0 for all")
    parser.add_argument("--settle", type=float, default=1.5, help="seconds to sample before printing")
    parser.add_argument("--all", action="store_true", help="include the channels hidden by default")
    args = parser.parse_args()
    asyncio.run(render(args.rows, args.settle, args.all))


if __name__ == "__main__":
    main()
