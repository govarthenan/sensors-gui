"""The contract that every collector must keep."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sensors_gui.model import Reading, SensorSpec


@runtime_checkable
class Collector(Protocol):
    """One source of sensor values.

    Rules, from `docs/architecture.md`:
        1. `discover` runs once at start, and again only on a re-scan.
        2. `read` must never raise. A failure becomes a `Reading` with no value
           and an error, so that one dead sensor cannot stop the application.
        3. A collector that cannot start at all reports zero specs and stays
           quiet.
        4. `read` must be quick. The budget for a full pass of all collectors
           is 50 ms.
    """

    name: str

    def discover(self) -> list[SensorSpec]:
        """Find every sensor this collector can read."""
        ...

    def read(self) -> list[Reading]:
        """Read every sensor found by the last `discover` call."""
        ...

    def close(self) -> None:
        """Release anything the collector holds."""
        ...
