"""The shared channel cache, from ADR 0006.

Not every sensor costs the same to read. Measured on this machine:

| Channel | Cost of one read |
|---|---|
| NVML `pcie_tx` / `pcie_rx` | 20.6 ms each (NVML samples over a window) |
| NVML `energy` | 3.0 ms |
| hwmon `nvme` | 2.0 ms (an NVMe admin command) |
| hwmon `spd5118` | 1.5 ms (an SMBus transaction) |
| hwmon `k10temp`, `amdgpu` | 0.005 ms (a register the kernel already holds) |

A cheap channel is read on every pass. An expensive one is read on its own
interval, and the cache serves the last value between reads, with the time of
the read that made it.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable

from sensors_gui.model import Reading, SensorId

type ValueReader = Callable[[], float | None]


class ChannelCache:
    """Hold the last reading of each channel and decide when to read again."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        """Create the cache.

        Args:
            clock: The source of time. It must give seconds and must not go
                backwards. `time.monotonic` is the right default, because the
                wall clock can jump.
        """
        self._clock = clock
        self._last: dict[SensorId, Reading] = {}

    def serve(self, sensor_id: SensorId, min_interval: float, reader: ValueReader) -> Reading:
        """Return a reading, from the cache when it is young enough, else from the reader.

        The reader is never allowed to raise out of this call. An exception, or
        a `None` result, becomes a failed reading. A failure is held for the
        same interval as a success, because retrying a dead device on every
        pass costs as much as reading a live one.

        Args:
            sensor_id: Which channel this is.
            min_interval: The shortest time in seconds between two reads. Zero,
                a negative number or a non-number means "read every time".
            reader: The call that produces the value.

        Returns:
            The reading.
        """
        now = self._clock()
        cached = self._last.get(sensor_id)
        if cached is not None and self._is_fresh(cached, min_interval, now):
            return cached

        try:
            value = reader()
        except Exception as exc:  # noqa: BLE001 - a dead sensor must not stop the application
            reading = Reading.failed(sensor_id, f"{type(exc).__name__}: {exc}", read_at=now)
        else:
            if value is None:
                reading = Reading.failed(sensor_id, "the reader gave no value", read_at=now)
            else:
                reading = Reading.ok(sensor_id, float(value), read_at=now)

        self._last[sensor_id] = reading
        return reading

    def forget(self, sensor_id: SensorId | None = None) -> None:
        """Drop the held reading of one channel, or of every channel.

        Args:
            sensor_id: The channel to drop. None drops all of them.
        """
        if sensor_id is None:
            self._last.clear()
        else:
            self._last.pop(sensor_id, None)

    @staticmethod
    def _is_fresh(cached: Reading, min_interval: float, now: float) -> bool:
        """Return True when the held reading is young enough to serve again."""
        if cached.read_at is None:
            return False
        if not math.isfinite(min_interval) or min_interval <= 0.0:
            return False
        return (now - cached.read_at) < min_interval
