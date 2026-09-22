"""The system collector: CPU, memory, storage and network, via `psutil` and `/proc`.

Everything here is a cheap, local, non-bus read - nothing here talks to a
device over I2C or NVMe admin commands the way `hwmon.py`'s slow channels do -
so every channel keeps `min_interval` at 0 and is read on every pass.

The expensive part is not any single read; it is calling `psutil` once per
*channel* instead of once per *pass*. `psutil.cpu_percent(percpu=True)`, for
example, measures the time since its own last call, so calling it once per
core per pass would make every core after the first measure a window a few
microseconds wide and read close to 0 %. `read()` avoids this by refreshing a
small set of batches - one `psutil`/`os` call per metric family - once at the
top of the pass, in `_refresh_batches`, and every channel's reader is then a
cheap lookup into that batch. The batches still go through the shared
`ChannelCache`, which is harmless at `min_interval=0.0`: the cache always
calls the reader, and the reader is now cheap.

Disk and network throughput are given as `Unit.BYTE_PER_SECOND`, computed as a
delta over time against the collector's own clock, never as the raw
cumulative counters `psutil` returns. The first read after `discover()` has no
previous sample, so it reads `None` - a failed `Reading`, not a fabricated
number - the same shape as the "throw away the first sample" rule for
`nct6687` (`exp-0007`, finding 4), reached independently here because a rate
needs two points no matter what the source is. A counter that reads lower
than its predecessor is treated as having wrapped or been reset, and the
delta is taken to be the new value alone, never the huge number that
subtracting through a 64-bit wrap would give.

Virtual network interfaces are skipped at discovery: `lo`, `docker0`,
`virbr0`, and anything starting with `br-` or `veth`. This machine has many,
from Docker and libvirt (`docs/hardware-inventory.md`), and none of them is a
sensor.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import psutil

from sensors_gui.collectors.cache import ChannelCache
from sensors_gui.model import Group, Reading, SensorId, SensorSpec, Unit

logger = logging.getLogger(__name__)

SOURCE = "system"
MHZ = 1_000_000.0

# Interfaces that are not a physical or a real network connection on this
# machine. Docker and libvirt make several of these, and their traffic is not
# what "network" means on a sensor screen. See docs/hardware-inventory.md.
_SKIP_EXACT_INTERFACES: frozenset[str] = frozenset({"lo", "docker0", "virbr0"})
_SKIP_INTERFACE_PREFIXES: tuple[str, ...] = ("br-", "veth")


def _is_virtual_interface(name: str) -> bool:
    """Return True for an interface that is not worth showing as a sensor."""
    return name in _SKIP_EXACT_INTERFACES or name.startswith(_SKIP_INTERFACE_PREFIXES)


def _rate_between(previous: tuple[float, int, int] | None, now: float, current: int, index: int) -> float | None:
    """Return the per-second rate between a previous snapshot and now.

    Args:
        previous: `(time, value_a, value_b)` recorded on the previous pass,
            or None on the first pass for this device.
        now: The current time, from the collector's own clock.
        current: The current raw cumulative counter.
        index: 1 to compare `current` against `value_a`, 2 against `value_b`.

    Returns:
        The rate, or None when there is no previous sample yet, or the clock
        did not move forward. A counter that reads lower than its previous
        value is treated as having wrapped or been reset: the delta is taken
        to be the new value alone, not a huge number from a 64-bit wrap.
    """
    if previous is None:
        return None
    prev_time = previous[0]
    prev_value = previous[index]
    dt = now - prev_time
    if dt <= 0:
        return None
    delta = current - prev_value if current >= prev_value else current
    return delta / dt


@dataclass(slots=True)
class _Channel:
    """One discovered channel, with the call that reads its value."""

    spec: SensorSpec
    read_value: Callable[[], float | None]


class SystemCollector:
    """Read CPU, memory, storage and network through `psutil` and `/proc`."""

    name = SOURCE

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        """Create the collector.

        Args:
            clock: The source of time used for every rate. It must give
                seconds and must not go backwards. `psutil` is not asked for
                its own timing, so a test can drive this clock by hand.
        """
        self.clock = clock
        self._cache = ChannelCache(lambda: self.clock())
        self._channels: list[_Channel] = []

        self._cpu_percents: list[float] = []
        self._cpu_percent_total: float = 0.0
        self._freq_percpu: bool = True
        self._cpu_freqs: list[Any] = []  # psutil's own scpufreq namedtuples
        self._load_avg: tuple[float, float, float] = (0.0, 0.0, 0.0)

        self._vmem: Any = None  # psutil's own svmem namedtuple
        self._smem: Any = None  # psutil's own sswap namedtuple
        self._swap_prev: tuple[float, int, int] | None = None
        self._swap_rates: tuple[float | None, float | None] = (None, None)

        self._disk_prev: dict[str, tuple[float, int, int]] = {}
        self._disk_rates: dict[str, tuple[float | None, float | None]] = {}
        self._net_prev: dict[str, tuple[float, int, int]] = {}
        self._net_rates: dict[str, tuple[float | None, float | None]] = {}

    def discover(self) -> list[SensorSpec]:
        """Find every channel `psutil` and `/proc` can give on this machine."""
        self._channels = []
        self._channels.extend(self._discover_cpu())
        self._channels.extend(self._discover_memory())
        self._channels.extend(self._discover_swap())
        self._channels.extend(self._discover_storage())
        self._channels.extend(self._discover_network())
        logger.info("system: found %d channels", len(self._channels))
        return [channel.spec for channel in self._channels]

    def read(self) -> list[Reading]:
        """Read every channel found by the last `discover` call. This never raises."""
        self._refresh_batches()
        return [
            self._cache.serve(channel.spec.id, channel.spec.min_interval, channel.read_value)
            for channel in self._channels
        ]

    def close(self) -> None:
        """Release the discovered channels, the cache, and every rate baseline."""
        self._channels = []
        self._cache.forget()
        self._swap_prev = None
        self._swap_rates = (None, None)
        self._disk_prev = {}
        self._disk_rates = {}
        self._net_prev = {}
        self._net_rates = {}

    # --- discovery: CPU ------------------------------------------------------

    def _discover_cpu(self) -> list[_Channel]:
        """Build the per-core usage, aggregate usage, frequency and load channels."""
        channels: list[_Channel] = []
        core_count = psutil.cpu_count(logical=True) or 0

        # Prime psutil's own internal delta state. Its first call after
        # import is documented to give a meaningless 0.0; calling it once
        # here, at discovery, means the first real read from a caller already
        # measures a real window instead of handing out that meaningless zero.
        psutil.cpu_percent(percpu=True)
        psutil.cpu_percent(percpu=False)

        for core in range(core_count):
            sensor_id = SensorId(source=SOURCE, device="cpu", channel=f"core{core}_percent")
            channels.append(
                _Channel(
                    spec=SensorSpec(
                        id=sensor_id,
                        label=f"CPU{core} use",
                        group=Group.CPU,
                        unit=Unit.PERCENT,
                        low=0.0,
                        high=100.0,
                        min_interval=0.0,
                        origin="psutil.cpu_percent(percpu=True)",
                    ),
                    read_value=self._cpu_percent_reader(core),
                )
            )

        channels.append(
            _Channel(
                spec=SensorSpec(
                    id=SensorId(source=SOURCE, device="cpu", channel="percent"),
                    label="CPU use",
                    group=Group.CPU,
                    unit=Unit.PERCENT,
                    low=0.0,
                    high=100.0,
                    min_interval=0.0,
                    origin="psutil.cpu_percent()",
                ),
                read_value=lambda: self._cpu_percent_total,
            )
        )

        channels.extend(self._discover_cpu_frequency(core_count))

        for index, channel_name, label in (
            (0, "load1", "Load average (1 min)"),
            (1, "load5", "Load average (5 min)"),
            (2, "load15", "Load average (15 min)"),
        ):
            channels.append(
                _Channel(
                    spec=SensorSpec(
                        id=SensorId(source=SOURCE, device="cpu", channel=channel_name),
                        label=label,
                        group=Group.CPU,
                        unit=Unit.NONE,
                        low=0.0,
                        min_interval=0.0,
                        origin="os.getloadavg()",
                    ),
                    read_value=self._load_avg_reader(index),
                )
            )
        return channels

    def _discover_cpu_frequency(self, core_count: int) -> list[_Channel]:
        """Build one frequency channel per core, or one aggregate channel when that fails."""
        try:
            freqs = psutil.cpu_freq(percpu=True)
        except Exception as exc:  # noqa: BLE001 - a missing cpufreq node must not stop discovery
            logger.info("system: cpu_freq(percpu=True) is not available: %s", exc)
            freqs = None

        if freqs and len(freqs) == core_count:
            self._freq_percpu = True
            return [
                _Channel(
                    spec=SensorSpec(
                        id=SensorId(source=SOURCE, device="cpu", channel=f"core{core}_frequency"),
                        label=f"CPU{core} frequency",
                        group=Group.CPU,
                        unit=Unit.HERTZ,
                        low=freq.min * MHZ if freq.min is not None else None,
                        high=freq.max * MHZ if freq.max is not None else None,
                        min_interval=0.0,
                        origin="psutil.cpu_freq(percpu=True)",
                    ),
                    read_value=self._cpu_freq_reader(core),
                )
                for core, freq in enumerate(freqs)
            ]

        self._freq_percpu = False
        try:
            aggregate = psutil.cpu_freq(percpu=False)
        except Exception as exc:  # noqa: BLE001 - no cpufreq at all must not stop discovery
            logger.info("system: cpu_freq() is not available: %s", exc)
            return []
        if aggregate is None:
            return []
        return [
            _Channel(
                spec=SensorSpec(
                    id=SensorId(source=SOURCE, device="cpu", channel="frequency"),
                    label="CPU frequency",
                    group=Group.CPU,
                    unit=Unit.HERTZ,
                    low=aggregate.min * MHZ if aggregate.min is not None else None,
                    high=aggregate.max * MHZ if aggregate.max is not None else None,
                    min_interval=0.0,
                    origin="psutil.cpu_freq()",
                ),
                read_value=self._cpu_freq_reader(0),
            )
        ]

    def _cpu_percent_reader(self, core: int) -> Callable[[], float | None]:
        """Return a reader for one core's usage, from the batch `_refresh_batches` fills."""

        def read_value() -> float | None:
            if core < len(self._cpu_percents):
                return self._cpu_percents[core]
            return None

        return read_value

    def _cpu_freq_reader(self, index: int) -> Callable[[], float | None]:
        """Return a reader for one core's (or the aggregate) frequency, in hertz."""

        def read_value() -> float | None:
            if index < len(self._cpu_freqs):
                current = self._cpu_freqs[index].current
                return current * MHZ if current is not None else None
            return None

        return read_value

    def _load_avg_reader(self, index: int) -> Callable[[], float | None]:
        """Return a reader for one of the three load-average figures."""

        def read_value() -> float | None:
            return self._load_avg[index]

        return read_value

    # --- discovery: memory and swap -------------------------------------------

    def _discover_memory(self) -> list[_Channel]:
        """Build one channel per field of `psutil.virtual_memory()` this platform gives."""
        channels: list[_Channel] = []
        fields: tuple[tuple[str, str, Unit], ...] = (
            ("total", "Memory total", Unit.BYTE),
            ("available", "Memory available", Unit.BYTE),
            ("used", "Memory used", Unit.BYTE),
            ("free", "Memory free", Unit.BYTE),
            ("percent", "Memory use", Unit.PERCENT),
            ("buffers", "Memory buffers", Unit.BYTE),
            ("cached", "Memory cached", Unit.BYTE),
            ("shared", "Memory shared", Unit.BYTE),
        )
        try:
            sample = psutil.virtual_memory()
        except Exception as exc:  # noqa: BLE001 - memory must always be readable, but do not trust that
            logger.warning("system: virtual_memory() failed: %s", exc)
            return []

        for field, label, unit in fields:
            if not hasattr(sample, field):
                continue
            channels.append(
                _Channel(
                    spec=SensorSpec(
                        id=SensorId(source=SOURCE, device="memory", channel=field),
                        label=label,
                        group=Group.MEMORY,
                        unit=unit,
                        low=0.0,
                        high=100.0 if unit is Unit.PERCENT else None,
                        min_interval=0.0,
                        origin=f"psutil.virtual_memory().{field}",
                    ),
                    read_value=self._memory_field_reader(field),
                )
            )
        return channels

    def _memory_field_reader(self, field: str) -> Callable[[], float | None]:
        """Return a reader for one field of the latest `virtual_memory()` batch."""

        def read_value() -> float | None:
            value = getattr(self._vmem, field, None) if self._vmem is not None else None
            return float(value) if value is not None else None

        return read_value

    def _discover_swap(self) -> list[_Channel]:
        """Build the swap level channels and the swap-in / swap-out rate channels."""
        channels: list[_Channel] = []
        for field, label, unit in (
            ("total", "Swap total", Unit.BYTE),
            ("used", "Swap used", Unit.BYTE),
            ("free", "Swap free", Unit.BYTE),
            ("percent", "Swap use", Unit.PERCENT),
        ):
            channels.append(
                _Channel(
                    spec=SensorSpec(
                        id=SensorId(source=SOURCE, device="swap", channel=field),
                        label=label,
                        group=Group.MEMORY,
                        unit=unit,
                        low=0.0,
                        high=100.0 if unit is Unit.PERCENT else None,
                        min_interval=0.0,
                        origin=f"psutil.swap_memory().{field}",
                    ),
                    read_value=self._swap_field_reader(field),
                )
            )

        for index, field, label in ((0, "sin", "Swap in"), (1, "sout", "Swap out")):
            channels.append(
                _Channel(
                    spec=SensorSpec(
                        id=SensorId(source=SOURCE, device="swap", channel=f"{field}_rate"),
                        label=label,
                        group=Group.MEMORY,
                        unit=Unit.BYTE_PER_SECOND,
                        low=0.0,
                        min_interval=0.0,
                        origin=f"psutil.swap_memory().{field}",
                    ),
                    read_value=self._swap_rate_reader(index),
                )
            )
        return channels

    def _swap_field_reader(self, field: str) -> Callable[[], float | None]:
        """Return a reader for one field of the latest `swap_memory()` batch."""

        def read_value() -> float | None:
            value = getattr(self._smem, field, None) if self._smem is not None else None
            return float(value) if value is not None else None

        return read_value

    def _swap_rate_reader(self, index: int) -> Callable[[], float | None]:
        """Return a reader for the swap-in (0) or swap-out (1) rate."""

        def read_value() -> float | None:
            return self._swap_rates[index]

        return read_value

    # --- discovery: storage and network rates ---------------------------------

    def _discover_storage(self) -> list[_Channel]:
        """Build a read-rate and write-rate channel for every disk `psutil` reports."""
        try:
            counters = psutil.disk_io_counters(perdisk=True) or {}
        except Exception as exc:  # noqa: BLE001 - no disk counters must not stop discovery
            logger.info("system: disk_io_counters is not available: %s", exc)
            counters = {}

        channels: list[_Channel] = []
        for device in sorted(counters):
            channels.append(
                _Channel(
                    spec=SensorSpec(
                        id=SensorId(source=SOURCE, device=f"disk:{device}", channel="read_rate"),
                        label=f"{device} read",
                        group=Group.STORAGE,
                        unit=Unit.BYTE_PER_SECOND,
                        low=0.0,
                        min_interval=0.0,
                        origin="psutil.disk_io_counters(perdisk=True)",
                    ),
                    read_value=self._disk_rate_reader(device, index=0),
                )
            )
            channels.append(
                _Channel(
                    spec=SensorSpec(
                        id=SensorId(source=SOURCE, device=f"disk:{device}", channel="write_rate"),
                        label=f"{device} write",
                        group=Group.STORAGE,
                        unit=Unit.BYTE_PER_SECOND,
                        low=0.0,
                        min_interval=0.0,
                        origin="psutil.disk_io_counters(perdisk=True)",
                    ),
                    read_value=self._disk_rate_reader(device, index=1),
                )
            )
        return channels

    def _disk_rate_reader(self, device: str, index: int) -> Callable[[], float | None]:
        """Return a reader for one disk's read (0) or write (1) rate."""

        def read_value() -> float | None:
            rates = self._disk_rates.get(device)
            return rates[index] if rates else None

        return read_value

    def _discover_network(self) -> list[_Channel]:
        """Build an upload and download rate channel for every real network interface."""
        try:
            counters = psutil.net_io_counters(pernic=True) or {}
        except Exception as exc:  # noqa: BLE001 - no network counters must not stop discovery
            logger.info("system: net_io_counters is not available: %s", exc)
            counters = {}

        channels: list[_Channel] = []
        for iface in sorted(counters):
            if _is_virtual_interface(iface):
                continue
            channels.append(
                _Channel(
                    spec=SensorSpec(
                        id=SensorId(source=SOURCE, device=f"net:{iface}", channel="bytes_sent_rate"),
                        label=f"{iface} upload",
                        group=Group.NETWORK,
                        unit=Unit.BYTE_PER_SECOND,
                        low=0.0,
                        min_interval=0.0,
                        origin="psutil.net_io_counters(pernic=True)",
                    ),
                    read_value=self._net_rate_reader(iface, index=0),
                )
            )
            channels.append(
                _Channel(
                    spec=SensorSpec(
                        id=SensorId(source=SOURCE, device=f"net:{iface}", channel="bytes_recv_rate"),
                        label=f"{iface} download",
                        group=Group.NETWORK,
                        unit=Unit.BYTE_PER_SECOND,
                        low=0.0,
                        min_interval=0.0,
                        origin="psutil.net_io_counters(pernic=True)",
                    ),
                    read_value=self._net_rate_reader(iface, index=1),
                )
            )
        return channels

    def _net_rate_reader(self, iface: str, index: int) -> Callable[[], float | None]:
        """Return a reader for one interface's upload (0) or download (1) rate."""

        def read_value() -> float | None:
            rates = self._net_rates.get(iface)
            return rates[index] if rates else None

        return read_value

    # --- refreshing the batches, once per read() pass -------------------------

    def _refresh_batches(self) -> None:
        """Call `psutil` and `/proc` once per metric family, for every channel to share."""
        now = self.clock()

        try:
            self._cpu_percents = psutil.cpu_percent(percpu=True) or []
        except Exception as exc:  # noqa: BLE001 - a bad pass must not stop the rest of the batch
            logger.debug("system: cpu_percent(percpu=True) failed: %s", exc)
            self._cpu_percents = []

        try:
            self._cpu_percent_total = psutil.cpu_percent(percpu=False)
        except Exception as exc:  # noqa: BLE001
            logger.debug("system: cpu_percent() failed: %s", exc)
            self._cpu_percent_total = 0.0

        try:
            raw_freqs = psutil.cpu_freq(percpu=self._freq_percpu)
        except Exception as exc:  # noqa: BLE001
            logger.debug("system: cpu_freq() failed: %s", exc)
            raw_freqs = None
        if self._freq_percpu:
            self._cpu_freqs = raw_freqs or []
        else:
            self._cpu_freqs = [raw_freqs] if raw_freqs is not None else []

        try:
            self._load_avg = os.getloadavg()
        except OSError as exc:
            logger.debug("system: getloadavg() failed: %s", exc)
            self._load_avg = (0.0, 0.0, 0.0)

        try:
            self._vmem = psutil.virtual_memory()
        except Exception as exc:  # noqa: BLE001
            logger.debug("system: virtual_memory() failed: %s", exc)
            self._vmem = None

        try:
            self._smem = psutil.swap_memory()
        except Exception as exc:  # noqa: BLE001
            logger.debug("system: swap_memory() failed: %s", exc)
            self._smem = None

        self._refresh_swap_rates(now)
        self._refresh_disk_rates(now)
        self._refresh_net_rates(now)

    def _refresh_swap_rates(self, now: float) -> None:
        """Recompute the swap-in / swap-out rates from the latest `swap_memory()` batch."""
        if self._smem is None:
            self._swap_rates = (None, None)
            return
        previous = self._swap_prev
        sin_rate = _rate_between(previous, now, self._smem.sin, index=1)
        sout_rate = _rate_between(previous, now, self._smem.sout, index=2)
        self._swap_rates = (sin_rate, sout_rate)
        self._swap_prev = (now, self._smem.sin, self._smem.sout)

    def _refresh_disk_rates(self, now: float) -> None:
        """Recompute every disk's read/write rate from a fresh `disk_io_counters` call."""
        try:
            counters = psutil.disk_io_counters(perdisk=True) or {}
        except Exception as exc:  # noqa: BLE001 - a transient failure must not stop the pass
            logger.debug("system: disk_io_counters failed: %s", exc)
            counters = {}

        new_prev: dict[str, tuple[float, int, int]] = {}
        new_rates: dict[str, tuple[float | None, float | None]] = {}
        for device, counter in counters.items():
            previous = self._disk_prev.get(device)
            read_rate = _rate_between(previous, now, counter.read_bytes, index=1)
            write_rate = _rate_between(previous, now, counter.write_bytes, index=2)
            new_rates[device] = (read_rate, write_rate)
            new_prev[device] = (now, counter.read_bytes, counter.write_bytes)
        self._disk_prev = new_prev
        self._disk_rates = new_rates

    def _refresh_net_rates(self, now: float) -> None:
        """Recompute every interface's upload/download rate from a fresh `net_io_counters` call."""
        try:
            counters = psutil.net_io_counters(pernic=True) or {}
        except Exception as exc:  # noqa: BLE001 - a transient failure must not stop the pass
            logger.debug("system: net_io_counters failed: %s", exc)
            counters = {}

        new_prev: dict[str, tuple[float, int, int]] = {}
        new_rates: dict[str, tuple[float | None, float | None]] = {}
        for iface, counter in counters.items():
            previous = self._net_prev.get(iface)
            sent_rate = _rate_between(previous, now, counter.bytes_sent, index=1)
            recv_rate = _rate_between(previous, now, counter.bytes_recv, index=2)
            new_rates[iface] = (sent_rate, recv_rate)
            new_prev[iface] = (now, counter.bytes_sent, counter.bytes_recv)
        self._net_prev = new_prev
        self._net_rates = new_rates
