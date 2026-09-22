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
from sensors_gui.app.status import StatusBar
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


def _keep_all(spec: SensorSpec) -> bool:
    """Keep every sensor. The default when no filter is given."""
    _ = spec
    return True


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
        Binding("h", "toggle_hidden", "Show all"),
        Binding("plus,equals_sign", "faster", "Faster"),
        Binding("minus", "slower", "Slower"),
    ]

    def __init__(
        self,
        collectors: Iterable[Collector],
        hz: float = DEFAULT_HZ,
        decorate: Callable[[SensorSpec], SensorSpec] = _identity,
        keep: Callable[[SensorSpec], bool] = _keep_all,
    ) -> None:
        """Create the application.

        Args:
            collectors: The sources to read. The application owns them and
                closes them when it stops.
            hz: How many times a second to read.
            decorate: A function that gives a sensor a name and a group a person
                would recognise. The default leaves the sensor as the driver
                reported it.
            keep: A function that decides whether a sensor is worth showing.
                A sensor it rejects is counted in the status bar and can be
                revealed with the `h` key. Nothing is ever silently dropped.
        """
        super().__init__()
        self._collectors = list(collectors)
        self._hz = hz
        self._decorate = decorate
        self._keep = keep
        self._panels: dict[Group, GroupPanel] = {}
        self._specs: dict[SensorId, SensorSpec] = {}
        self._paused = False
        self._show_hidden = False
        self._hidden_count = 0
        self._status = StatusBar()

    # --- composition --------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Build the widget tree."""
        yield Header(show_clock=True)
        with VerticalScroll(id="panels"):
            for group, specs in self._discover().items():
                panel = GroupPanel(group, specs, id=f"panel-{group.value}")
                self._panels[group] = panel
                yield panel
        yield self._status
        yield Footer()

    def on_mount(self) -> None:
        """Take the first reading, discard it, then start the refresh timer."""
        # The nct6687 driver reports zeros until it has updated once. See
        # exp-0007, finding 4.
        self._read_all()
        self.set_interval(1.0 / self._hz, self._refresh_readings)
        self._refresh_readings()
        self._update_status()

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
        self._hidden_count = 0
        grouped: dict[Group, list[SensorSpec]] = {}
        for collector in self._collectors:
            try:
                found = collector.discover()
            except Exception as exc:  # noqa: BLE001 - one bad source must not stop the rest
                logger.warning("discover failed for %s: %s", collector.name, exc)
                continue
            for raw in found:
                spec = self._decorate(raw)
                if not self._show_hidden and not self._keep(spec):
                    self._hidden_count += 1
                    continue
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
        started = time.perf_counter()
        readings = self._read_all()
        self._status.pass_ms = (time.perf_counter() - started) * 1000
        now = time.monotonic()
        for panel in self._panels.values():
            panel.update_readings(readings, now)
        self._status.failing = sum(
            1 for sensor_id, reading in readings.items() if sensor_id in self._specs and not reading.is_ok
        )
        self._update_status()

    # --- actions ------------------------------------------------------------

    def _update_status(self) -> None:
        """Copy the current counters into the status bar and redraw it."""
        self._status.hz = self._hz
        self._status.channels = len(self._specs)
        self._status.hidden = self._hidden_count
        self._status.paused = self._paused
        self._status.refresh_status()

    def action_toggle_pause(self) -> None:
        """Stop or start the refresh."""
        self._paused = not self._paused
        self.sub_title = "dst-gova-pc — paused" if self._paused else "dst-gova-pc"
        self._update_status()

    async def action_toggle_hidden(self) -> None:
        """Show or hide the channels the naming layer keeps out of the way."""
        self._show_hidden = not self._show_hidden
        await self._rebuild_panels()

    async def action_rescan(self) -> None:
        """Find the sensors again. A device may have appeared or gone."""
        self.notify("Re-scanning sensors", timeout=2)
        await self._rebuild_panels()

    async def _rebuild_panels(self) -> None:
        """Discover again and replace every panel with the new set.

        The removal must be awaited before the new panels are mounted. A panel
        carries the group name as its id, so mounting a second panel for the
        same group before the first has gone raises `DuplicateIds`.
        """
        grouped = self._discover()
        container = self.query_one("#panels")
        await container.remove_children()
        self._panels = {}
        for group, specs in grouped.items():
            panel = GroupPanel(group, specs, id=f"panel-{group.value}")
            self._panels[group] = panel
        await container.mount_all(self._panels.values())
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
        self._update_status()
        self.notify(f"{self._hz:g} Hz", timeout=1)
