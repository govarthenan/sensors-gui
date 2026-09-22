"""The widget that draws one group of sensors."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from sensors_gui.app.meters import Level, bar, fraction, level_of
from sensors_gui.model import Group, Reading, SensorId, SensorSpec

LEVEL_STYLES: dict[Level, str] = {
    Level.UNKNOWN: "dim",
    Level.NORMAL: "green",
    Level.WARN: "yellow bold",
    Level.CRITICAL: "red bold",
}

GROUP_TITLES: dict[Group, str] = {
    Group.CPU: "CPU",
    Group.GPU: "GPU",
    Group.MEMORY: "Memory",
    Group.STORAGE: "Storage",
    Group.NETWORK: "Network",
    Group.BOARD: "Motherboard",
    Group.PERIPHERAL: "Peripherals",
    Group.SYSTEM: "System",
    Group.OTHER: "Other",
}

LABEL_WIDTH = 20
VALUE_WIDTH = 13
BAR_WIDTH = 18
STALE_AFTER_SECONDS = 3.0


class GroupPanel(Static):
    """One titled block of sensor rows, for a single group."""

    DEFAULT_CSS = """
    GroupPanel {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        border: round $primary-darken-2;
    }
    """

    def __init__(self, group: Group, specs: list[SensorSpec], **kwargs: object) -> None:
        """Create the panel.

        Args:
            group: Which group this panel shows.
            specs: The sensors in it, in the order they should appear.
            **kwargs: Passed to `Static`.
        """
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.group = group
        self.specs = specs
        self.border_title = GROUP_TITLES.get(group, group.value)
        self._readings: dict[SensorId, Reading] = {}
        self._now: float = 0.0

    def update_readings(self, readings: dict[SensorId, Reading], now: float) -> None:
        """Take a new set of readings and redraw.

        Args:
            readings: The latest reading of each sensor, keyed by identity.
            now: The current clock value, used to age each reading.
        """
        self._readings = readings
        self._now = now
        self.update(self.render_rows())

    def render_rows(self) -> Text:
        """Build the text of every row in this panel."""
        text = Text()
        for index, spec in enumerate(self.specs):
            if index:
                text.append("\n")
            self._append_row(text, spec)
        return text

    def _append_row(self, text: Text, spec: SensorSpec) -> None:
        """Append one sensor row to the running text."""
        reading = self._readings.get(spec.id)
        value = reading.value if reading else None
        level = level_of(spec, value)

        text.append(f"{spec.label[:LABEL_WIDTH]:<{LABEL_WIDTH}}", style="bold")
        text.append(f"{spec.format(value):>{VALUE_WIDTH}} ", style=LEVEL_STYLES[level])
        text.append(bar(fraction(spec, value), BAR_WIDTH), style=LEVEL_STYLES[level])

        text.append(self._suffix(spec, reading), style="dim")

    def _suffix(self, spec: SensorSpec, reading: Reading | None) -> str:
        """Return the dim text after the bar: an error, an age, or a threshold."""
        if reading is not None and reading.error is not None:
            return f"  {reading.error[:40]}"

        age = reading.age(self._now) if reading is not None else None
        if age is not None and age > STALE_AFTER_SECONDS:
            return f"  {age:.0f}s old"

        if spec.critical is not None:
            return f"  crit {spec.format(spec.critical)}"
        if spec.warn is not None:
            return f"  max {spec.format(spec.warn)}"
        return ""
