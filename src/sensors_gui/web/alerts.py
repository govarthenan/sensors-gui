"""The alert log: every reading that left the scale its spec publishes.

Gova asked for it on 2026-09-23: *"If we get a reading higher than the
recognized ceiling, what happens then? ... Log an alert on a seperate screen."*

- The **ceiling** is the spec's `high` and the **floor** its `low`. A channel
  that publishes neither can never alert: the application does not invent a
  limit, as it does not invent a threshold.
- One **excursion** is one alert. It records when it started, when it ended,
  the value furthest outside the limit, and how many passes it lasted. A value
  that returns within `merge_seconds` reopens the same alert, so a reading
  that rattles on its ceiling does not fill the screen.
- The log lives **in memory only**, and keeps the newest `capacity` alerts.
  History storage was dropped on 2026-09-22 and this does not bring it back:
  nothing is written to disk, and a restart empties the log.

The log runs in the sampling service, on every pass, so an alert is caught
whichever view is on screen, or when no window is open at all.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from sensors_gui.model import Reading, SensorId, SensorSpec

ABOVE = "above ceiling"
BELOW = "below floor"
DEFAULT_CAPACITY = 500
DEFAULT_MERGE_SECONDS = 5.0


@dataclass(slots=True)
class _Alert:
    """One excursion of one channel outside its scale."""

    number: int
    spec: SensorSpec
    kind: str
    limit: float
    started: float
    peak: float
    last: float
    passes: int = 1
    ended: float | None = None

    def take(self, value: float) -> None:
        """Record one more reading outside the limit."""
        self.last = value
        self.passes += 1
        self.peak = max(self.peak, value) if self.kind == ABOVE else min(self.peak, value)

    def as_dict(self) -> dict[str, object]:
        """Return the alert as the alerts screen receives it."""
        spec = self.spec
        return {
            "number": self.number,
            "key": spec.id.key,
            "label": spec.label,
            "group": str(spec.group),
            "unit": str(spec.unit),
            "symbol": spec.unit.symbol,
            "decimals": spec.unit.decimals,
            "kind": self.kind,
            "limit": self.limit,
            "peak": self.peak,
            "last": self.last,
            "passes": self.passes,
            "started": self.started,
            "ended": self.ended,
        }


def _outside(spec: SensorSpec, value: float) -> tuple[str, float] | None:
    """Return which limit a value is past, and the limit, or None when it is inside."""
    if spec.high is not None and value > spec.high:
        return ABOVE, spec.high
    if spec.low is not None and value < spec.low:
        return BELOW, spec.low
    return None


class AlertLog:
    """Watches every channel with a published scale, and records each excursion."""

    def __init__(self, capacity: int = DEFAULT_CAPACITY, merge_seconds: float = DEFAULT_MERGE_SECONDS) -> None:
        """Create an empty log.

        Args:
            capacity: How many alerts to keep. The oldest go first.
            merge_seconds: A return outside the limit within this many seconds
                of the last alert's end reopens that alert.
        """
        self._entries: deque[_Alert] = deque(maxlen=capacity)
        self._open: dict[SensorId, _Alert] = {}
        self._closed_last: dict[SensorId, _Alert] = {}
        self._merge = merge_seconds
        self._total = 0
        self._lock = threading.Lock()

    def observe(
        self,
        specs: Iterable[SensorSpec],
        readings: Iterable[Reading],
        now: float,
        hidden: set[SensorId] | frozenset[SensorId] = frozenset(),
    ) -> None:
        """Look at one pass and update the log.

        Args:
            specs: Every channel, with its scale.
            readings: The readings of the pass.
            now: The time of the pass, in seconds from the epoch.
            hidden: Channels the BIOS proved misleading. They are not watched,
                because their values would raise alerts about nothing.
        """
        by_id = {spec.id: spec for spec in specs if spec.high is not None or spec.low is not None}
        with self._lock:
            for reading in readings:
                spec = by_id.get(reading.id)
                if spec is None or reading.value is None or reading.id in hidden:
                    continue
                self._take(spec, reading.value, now)

    def _take(self, spec: SensorSpec, value: float, now: float) -> None:
        """Update the log with one reading of one watched channel."""
        outside = _outside(spec, value)
        current = self._open.get(spec.id)
        if outside is None:
            if current is not None:
                current.ended = now
                self._closed_last[spec.id] = self._open.pop(spec.id)
            return
        if current is not None and current.kind == outside[0]:
            current.take(value)
            return
        recent = self._closed_last.get(spec.id)
        if (
            recent is not None
            and recent.kind == outside[0]
            and recent.ended is not None
            and now - recent.ended <= self._merge
            and recent in self._entries
        ):
            recent.ended = None
            recent.take(value)
            self._open[spec.id] = recent
            return
        self._total += 1
        alert = _Alert(
            number=self._total, spec=spec, kind=outside[0], limit=outside[1], started=now, peak=value, last=value
        )
        self._entries.append(alert)
        self._open[spec.id] = alert

    def entries(self) -> list[dict[str, object]]:
        """Return every kept alert, newest first."""
        with self._lock:
            return [alert.as_dict() for alert in reversed(self._entries)]

    def open_count(self) -> int:
        """Return how many channels are outside their scale now."""
        with self._lock:
            return len(self._open)

    def total(self) -> int:
        """Return how many alerts were ever opened, including any the log no longer keeps."""
        with self._lock:
            return self._total
