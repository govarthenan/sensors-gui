"""Collectors. Each one reads one kind of sensor source.

See `docs/architecture.md` for the contract that every collector must keep.

`HwmonCollector` and `NvidiaCollector` are not re-exported here; they are
frozen for phase 3 (`docs/phase-3-plan.md`) and stay reachable the way
`src/sensors_gui/__main__.py` already imports them, from their own module.
`PowerSupplyCollector` and `SystemCollector` are new in phase 3 and are
re-exported here for convenience. `PrivilegedCollector` is new in phase 2
and joins them; it is the client half of the helper of ADR 0005.
"""

from sensors_gui.collectors.base import Collector
from sensors_gui.collectors.power_supply import PowerSupplyCollector
from sensors_gui.collectors.privileged import PrivilegedCollector
from sensors_gui.collectors.system import SystemCollector

__all__ = ["Collector", "PowerSupplyCollector", "PrivilegedCollector", "SystemCollector"]
