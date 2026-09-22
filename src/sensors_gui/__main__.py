"""Run the sensor monitor.

uv run python -m sensors_gui
"""

from __future__ import annotations

import logging

from sensors_gui import naming
from sensors_gui.app.sensors_app import SensorsApp
from sensors_gui.collectors.hwmon import HwmonCollector
from sensors_gui.collectors.nvidia import NvidiaCollector
from sensors_gui.collectors.power_supply import PowerSupplyCollector
from sensors_gui.collectors.system import SystemCollector
from sensors_gui.model import SensorSpec


def worth_showing(spec: SensorSpec) -> bool:
    """Return False for a channel the BIOS proved wrong.

    A channel this rejects is not deleted. It is counted in the status bar and
    the `h` key brings it back, so nothing is ever silently lost.

    Args:
        spec: The sensor, after the naming layer has been applied.

    Returns:
        Whether the sensor is shown by default.
    """
    return naming.verdict(spec) != "wrong"


def main() -> None:
    """Start the application with every collector this machine has."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    SensorsApp(
        collectors=[
            HwmonCollector(),
            NvidiaCollector(),
            PowerSupplyCollector(),
            SystemCollector(),
        ],
        decorate=naming.friendly,
        keep=worth_showing,
    ).run()


if __name__ == "__main__":
    main()
