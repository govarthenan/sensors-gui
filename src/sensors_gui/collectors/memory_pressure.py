"""The memory pressure collector: `/proc/pressure/memory` and `/proc/vmstat`.

Gova chose these channels on 2026-09-25 for the memory view ("Add memory
pressure"). The kernel's account of memory (psutil, in `system.py`) says how
much memory is in use. It does not say whether the machine is short of it.
These channels do:

- **Pressure stall information (PSI).** The share of time in which at least
  one task (`some`) or every non-idle task (`full`) waited for memory, as a
  running average over 10, 60 and 300 seconds. The kernel publishes the six
  averages as percentages. Format and meaning:
  `data/evidence/memory-pressure-sources-2026-09-25/`.
- **Page faults.** `pgfault` and `pgmajfault` in `/proc/vmstat` count every
  page fault, and those that needed a read from the drive. They are
  cumulative counters, so this collector gives a rate, as `system.py` does
  for the disks and the network.

Both files are plain text the kernel writes on each read. Reading them asks
nothing of any device. Both are readable without root.

**`/proc/pressure/memory` is writable by every user** (`-rw-rw-rw-`, in
`probe-this-machine.txt`): a write registers a trigger (`psi.rst`, "Monitoring
for pressure thresholds"). This collector only ever opens it to read, with
`Path.read_text`. It never writes to it. ADR 0007.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sensors_gui.collectors.cache import ChannelCache
from sensors_gui.collectors.system import _rate_between
from sensors_gui.model import Group, Reading, SensorId, SensorSpec, Unit

logger = logging.getLogger(__name__)

SOURCE = "proc"
DEFAULT_PROC = Path("/proc")

# The two lines of the pressure file, and the three windows on each.
PRESSURE_KINDS = ("some", "full")
PRESSURE_WINDOWS = ("10", "60", "300")
# The two counters of /proc/vmstat, with the label of their rate.
FAULT_COUNTERS = (("pgfault", "Page faults"), ("pgmajfault", "Major page faults"))


@dataclass(slots=True)
class _Channel:
    """One discovered channel, with the call that reads its value."""

    spec: SensorSpec
    read_value: Callable[[], float | None]


def parse_pressure(text: str) -> dict[str, float]:
    """Return every average of a PSI file, keyed `some_avg10` and so on.

    Args:
        text: The file as the kernel wrote it, for example
            `some avg10=1.53 avg60=0.87 avg300=0.21 total=4780829`.

    Returns:
        The averages, in percent. The `total` field is left out.
    """
    values: dict[str, float] = {}
    for line in text.splitlines():
        kind, *fields = line.split()
        for field in fields:
            name, _, number = field.partition("=")
            if name.startswith("avg"):
                values[f"{kind}_{name}"] = float(number)
    return values


def parse_vmstat(text: str) -> dict[str, int]:
    """Return every counter of `/proc/vmstat`, one `name value` pair on each line."""
    values: dict[str, int] = {}
    for line in text.splitlines():
        name, _, number = line.partition(" ")
        if number:
            values[name] = int(number)
    return values


class MemoryPressureCollector:
    """Read memory pressure and the page fault rates from `/proc`."""

    name = SOURCE

    def __init__(self, proc_root: Path | str = DEFAULT_PROC, clock: Callable[[], float] = time.monotonic) -> None:
        """Create the collector.

        Args:
            proc_root: Where `/proc` is. A test points this at a temporary tree.
            clock: The source of time for the fault rates. It must give
                seconds and must not go backwards.
        """
        self.proc_root = Path(proc_root)
        self.clock = clock
        self._cache = ChannelCache(lambda: self.clock())
        self._channels: list[_Channel] = []
        self._pressure: dict[str, float] = {}
        self._fault_prev: tuple[float, int, int] | None = None
        self._fault_rates: tuple[float | None, float | None] = (None, None)

    @property
    def _pressure_file(self) -> Path:
        return self.proc_root / "pressure" / "memory"

    @property
    def _vmstat_file(self) -> Path:
        return self.proc_root / "vmstat"

    def discover(self) -> list[SensorSpec]:
        """Find the channels this kernel publishes. A missing file gives no channels."""
        self._channels = []
        if self._pressure_file.is_file():
            self._channels.extend(self._discover_pressure())
        else:
            logger.info("proc: no %s; the kernel has no pressure stall information", self._pressure_file)
        if self._vmstat_file.is_file():
            self._channels.extend(self._discover_faults())
        else:
            logger.info("proc: no %s", self._vmstat_file)
        logger.info("proc: found %d channels", len(self._channels))
        return [channel.spec for channel in self._channels]

    def read(self) -> list[Reading]:
        """Read both files once, then every channel. This never raises."""
        self._refresh()
        return [
            self._cache.serve(channel.spec.id, channel.spec.min_interval, channel.read_value)
            for channel in self._channels
        ]

    def close(self) -> None:
        """Release the channels, the cache and the rate baseline."""
        self._channels = []
        self._cache.forget()
        self._pressure = {}
        self._fault_prev = None
        self._fault_rates = (None, None)

    def _discover_pressure(self) -> list[_Channel]:
        """Build the six pressure channels, `some` first, in the order of the file."""
        channels: list[_Channel] = []
        for kind in PRESSURE_KINDS:
            for window in PRESSURE_WINDOWS:
                key = f"{kind}_avg{window}"
                spec = SensorSpec(
                    id=SensorId(source=SOURCE, device="pressure/memory", channel=key),
                    label=f"Memory pressure, {kind}, {window} s",
                    group=Group.MEMORY,
                    unit=Unit.PERCENT,
                    low=0.0,
                    high=100.0,
                    origin=f"{self._pressure_file} {kind} avg{window}",
                    # The kernel writes two decimals (psi.rst); 0.40 % must not read 0 %.
                    decimals=2,
                )
                channels.append(_Channel(spec=spec, read_value=self._pressure_reader(key)))
        return channels

    def _discover_faults(self) -> list[_Channel]:
        """Build the two fault rate channels."""
        channels: list[_Channel] = []
        for index, (counter, label) in enumerate(FAULT_COUNTERS):
            spec = SensorSpec(
                id=SensorId(source=SOURCE, device="vmstat", channel=f"{counter}_rate"),
                label=label,
                group=Group.MEMORY,
                unit=Unit.PER_SECOND,
                low=0.0,
                origin=f"{self._vmstat_file} {counter}",
            )
            channels.append(_Channel(spec=spec, read_value=self._fault_reader(index)))
        return channels

    def _pressure_reader(self, key: str) -> Callable[[], float | None]:
        """Return a reader for one average of the latest pressure read."""

        def read_value() -> float | None:
            return self._pressure.get(key)

        return read_value

    def _fault_reader(self, index: int) -> Callable[[], float | None]:
        """Return a reader for the fault rate (0) or the major fault rate (1)."""

        def read_value() -> float | None:
            return self._fault_rates[index]

        return read_value

    def _refresh(self) -> None:
        """Read each file once for the pass, so every channel shares one read."""
        now = self.clock()
        try:
            self._pressure = parse_pressure(self._pressure_file.read_text())
        except (OSError, ValueError) as error:
            logger.debug("proc: cannot read %s: %s", self._pressure_file, error)
            self._pressure = {}
        try:
            counters = parse_vmstat(self._vmstat_file.read_text())
            faults, major = counters["pgfault"], counters["pgmajfault"]
        except (OSError, ValueError, KeyError) as error:
            logger.debug("proc: cannot read the fault counters in %s: %s", self._vmstat_file, error)
            self._fault_prev = None
            self._fault_rates = (None, None)
            return
        previous = self._fault_prev
        self._fault_rates = (
            _rate_between(previous, now, faults, index=1),
            _rate_between(previous, now, major, index=2),
        )
        self._fault_prev = (now, faults, major)
