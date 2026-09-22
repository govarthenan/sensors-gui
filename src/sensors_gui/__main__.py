"""Run the sensor monitor.

uv run python -m sensors_gui
"""

from __future__ import annotations

import logging

from sensors_gui.app.sensors_app import SensorsApp
from sensors_gui.collectors.hwmon import HwmonCollector
from sensors_gui.collectors.nvidia import NvidiaCollector


def main() -> None:
    """Start the application with every collector this machine has."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    SensorsApp(collectors=[HwmonCollector(), NvidiaCollector()]).run()


if __name__ == "__main__":
    main()
