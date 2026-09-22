"""The one-line status bar at the foot of the screen."""

from __future__ import annotations

from textual.widgets import Static


class StatusBar(Static):
    """Shows the refresh rate, the cost of a pass, and what is not being shown.

    The hidden count matters as much as the rest. A channel that the naming
    layer keeps out of the way must still be visible as a number, so that it is
    never silently lost.
    """

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        padding: 0 2;
        color: $text-muted;
        background: $panel;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        """Create an empty status bar."""
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.hz = 0.0
        self.channels = 0
        self.hidden = 0
        self.failing = 0
        self.pass_ms: float | None = None
        self.paused = False

    def render_status(self) -> str:
        """Build the status line."""
        parts = [f"{self.channels} channels", f"{self.hz:g} Hz"]
        if self.pass_ms is not None:
            parts.append(f"{self.pass_ms:.2f} ms/pass")
        if self.failing:
            parts.append(f"{self.failing} failing")
        if self.hidden:
            parts.append(f"{self.hidden} hidden (h)")
        if self.paused:
            parts.append("PAUSED")
        parts.append("read-only")
        return "   ".join(parts)

    def refresh_status(self) -> None:
        """Redraw the status line from the current counters."""
        self.update(self.render_status())
