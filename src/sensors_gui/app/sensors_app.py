"""The Textual application (ADR 0004).

The screen is a column of group panels, one for each part of the machine, each
holding a row for every sensor. It refreshes at a set rate and never writes to
hardware.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header

from sensors_gui.app.meters import sort_key
from sensors_gui.app.panel import GroupPanel
from sensors_gui.collectors import Collector
from sensors_gui.model import Group, Reading, SensorId, SensorSpec

logger = logging.getLogger(__name__)

DEFAULT_HZ = 2.0

# The order the groups appear down the screen.
GROUP_ORDER: tuple[Group, ...] = (
    Group.CPU,
    Group.GPU,
    Group.BOARD,
    Group.MEMORY,
    Group.STORAGE,
    Group.NETWORK,
    Group.PERIPHERAL,
    Group.SYSTEM,
    Group.OTHER,
)


def _identity(spec: SensorSpec) -> SensorSpec:
    """Return the spec unchanged. The default when no naming layer is given."""
    return spec


class SensorsApp(App[None]):
    """A sensor monitor for one specific PC."""

    TITLE = "sensors-gui"
    SUB_TITLE = "dst-gova-pc"

    CSS = """
    Screen { background: $surface; }
    VerticalScroll { padding: 1 2; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "toggle_pause", "Pause"),
        Binding("r", "rescan", "Re-scan"),
        Binding("plus,equals_sign", "faster", "Faster"),
        Binding("minus", "slower", "Slower"),
    ]

    def __init__(
        self,
        collectors: Iterable[Collector],
        hz: float = DEFAULT_HZ,
        decorate: Callable[[SensorSpec], SensorSpec] = _identity,
    ) -> None:
        """Create the application.

        Args:
            collectors: The sources to read. The application owns them and
                closes them when it stops.
            hz: How many times a second to read.
            decorate: A function that gives a sensor a name and a group a person
                would recognise. The default leaves the sensor as the driver
                reported it.
        """
        super().__init__()
        self._collectors = list(collectors)
        self._hz = hz
        self._decorate = decorate
        self._panels: dict[Group, GroupPanel] = {}
        self._specs: dict[SensorId, SensorSpec] = {}
        self._paused = False

    # --- composition --------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Build the widget tree."""
        yield Header(show_clock=True)
        with VerticalScroll(id="panels"):
            for group, specs in self._discover().items():
                panel = GroupPanel(group, specs, id=f"panel-{group.value}")
                self._panels[group] = panel
                yield panel
        yield Footer()

    def on_mount(self) -> None:
        """Take the first reading, discard it, then start the refresh timer."""
        # The nct6687 driver reports zeros until it has updated once. See
        # exp-0007, finding 4.
        self._read_all()
        self.set_interval(1.0 / self._hz, self._refresh_readings)
        self._refresh_readings()

    def on_unmount(self) -> None:
        """Close every collector."""
        for collector in self._collectors:
            try:
                collector.close()
            except Exception as exc:  # noqa: BLE001 - shutting down must not raise
                logger.debug("closing %s failed: %s", collector.name, exc)

    # --- data ---------------------------------------------------------------

    def _discover(self) -> dict[Group, list[SensorSpec]]:
        """Find every sensor and group it for display."""
        self._specs = {}
        grouped: dict[Group, list[SensorSpec]] = {}
        for collector in self._collectors:
            try:
                found = collector.discover()
            except Exception as exc:  # noqa: BLE001 - one bad source must not stop the rest
                logger.warning("discover failed for %s: %s", collector.name, exc)
                continue
            for raw in found:
                spec = self._decorate(raw)
                self._specs[spec.id] = spec
                grouped.setdefault(spec.group, []).append(spec)

        for specs in grouped.values():
            specs.sort(key=sort_key)
        return {group: grouped[group] for group in GROUP_ORDER if group in grouped}

    def _read_all(self) -> dict[SensorId, Reading]:
        """Read every collector once. This never raises."""
        readings: dict[SensorId, Reading] = {}
        for collector in self._collectors:
            try:
                for reading in collector.read():
                    readings[reading.id] = reading
            except Exception as exc:  # noqa: BLE001 - the contract says read cannot raise, but defend
                logger.warning("read failed for %s: %s", collector.name, exc)
        return readings

    def _refresh_readings(self) -> None:
        """Read every sensor and hand the values to the panels."""
        if self._paused:
            return
        readings = self._read_all()
        now = time.monotonic()
        for group, panel in self._panels.items():
            panel.update_readings(readings, now)
            _ = group

    # --- actions ------------------------------------------------------------

    def action_toggle_pause(self) -> None:
        """Stop or start the refresh."""
        self._paused = not self._paused
        self.sub_title = "dst-gova-pc — paused" if self._paused else "dst-gova-pc"

    def action_rescan(self) -> None:
        """Find the sensors again. A device may have appeared or gone."""
        self.notify("Re-scanning sensors", timeout=2)
        self._discover()
        self._refresh_readings()

    def action_faster(self) -> None:
        """Double the refresh rate, up to 10 Hz."""
        self._set_rate(min(self._hz * 2, 10.0))

    def action_slower(self) -> None:
        """Halve the refresh rate, down to 0.25 Hz."""
        self._set_rate(max(self._hz / 2, 0.25))

    def _set_rate(self, hz: float) -> None:
        """Change the refresh rate and restart the timer."""
        self._hz = hz
        for timer in list(self._timers):
            timer.stop()
        self.set_interval(1.0 / self._hz, self._refresh_readings)
        self.notify(f"{self._hz:g} Hz", timeout=1)
