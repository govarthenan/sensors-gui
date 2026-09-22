"""The registry: holds every `SensorSpec` from every collector, and finds them again.

See `docs/architecture.md` for the shape of the collection layer, and
`docs/phase-3-plan.md`, "Stream B builds", for the fixed interface.
"""

from __future__ import annotations

import logging

from sensors_gui.collectors import Collector
from sensors_gui.model import Group, Reading, SensorId, SensorSpec

logger = logging.getLogger(__name__)


class Registry:
    """Holds every `SensorSpec` from every collector, and finds them again."""

    def __init__(self, collectors: list[Collector]) -> None:
        """Create the registry.

        Args:
            collectors: Every collector this registry manages. Nothing is
                read or discovered yet; call `discover()` to do that.
        """
        self._collectors = list(collectors)
        self._specs: dict[SensorId, SensorSpec] = {}

    def discover(self) -> None:
        """Find every sensor from every collector, replacing what was known before.

        A collector that raises while discovering is logged and skipped; the
        rest still run, so one broken source never stops the others.

        Once specs are collected, one read pass is taken from every collector
        and thrown away. `exp-0007` finding 4: the `nct6687` driver reports
        zero for several channels until it has updated once, and other
        drivers may behave the same way after they first appear. Throwing
        the first pass away here means every caller of `read_all()` only
        ever sees settled values.
        """
        specs: dict[SensorId, SensorSpec] = {}
        for collector in self._collectors:
            try:
                found = collector.discover()
            except Exception as exc:  # noqa: BLE001 - one bad collector must not stop the rest
                logger.warning("registry: %s failed to discover, skipping: %s", collector.name, exc)
                continue
            for spec in found:
                specs[spec.id] = spec
        self._specs = specs
        self.read_all()  # the first pass after discovery; taken and discarded

    def specs(self) -> list[SensorSpec]:
        """Return every known spec."""
        return list(self._specs.values())

    def spec(self, sensor_id: SensorId) -> SensorSpec | None:
        """Return the spec of one sensor, or None when it is not known.

        Args:
            sensor_id: The identity to look up.
        """
        return self._specs.get(sensor_id)

    def by_group(self) -> dict[Group, list[SensorSpec]]:
        """Return every known spec, grouped by `SensorSpec.group`."""
        grouped: dict[Group, list[SensorSpec]] = {}
        for spec in self._specs.values():
            grouped.setdefault(spec.group, []).append(spec)
        return grouped

    def read_all(self) -> list[Reading]:
        """Read every collector once and return every reading.

        `read()` is contractually not allowed to raise, but this defends
        anyway: a collector that breaks the contract is logged and skipped,
        and every other collector still gets read.

        Returns:
            Every reading from every collector, in collector order.
        """
        readings: list[Reading] = []
        for collector in self._collectors:
            try:
                readings.extend(collector.read())
            except Exception as exc:  # noqa: BLE001 - one bad collector must not stop the rest
                logger.error("registry: %s raised in read(), which is against contract: %s", collector.name, exc)
        return readings

    def close(self) -> None:
        """Close every collector.

        A collector that raises while closing is logged and skipped, so that
        one bad shutdown never leaves the rest of the hardware held open.
        """
        for collector in self._collectors:
            try:
                collector.close()
            except Exception as exc:  # noqa: BLE001 - one bad collector must not stop the rest
                logger.warning("registry: %s failed to close: %s", collector.name, exc)
