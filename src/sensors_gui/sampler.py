"""The sampler: reads every collector on a schedule and keeps a short history.

See `docs/architecture.md` for the shape of the collection layer, and
`docs/phase-3-plan.md`, "Stream B builds", for the fixed interface.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections import deque
from collections.abc import Awaitable, Callable

from sensors_gui.model import Sample, SensorId
from sensors_gui.registry import Registry

logger = logging.getLogger(__name__)

type Subscriber = Callable[[Sample], None]

DEFAULT_HISTORY = 120
DEFAULT_HZ = 2.0


class Sampler:
    """Reads every collector on a schedule and keeps a short history."""

    def __init__(
        self,
        registry: Registry,
        history: int = DEFAULT_HISTORY,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Create the sampler.

        Args:
            registry: The registry to read. `registry.discover()` must have
                already been called; the registry itself throws away the
                first pass after discovery (see `Registry.discover`).
            history: How many values the ring buffer of each sensor holds.
            clock: The source of time used to pace `run()`. It must give
                seconds and must not go backwards. Tests pass a fake clock
                that is a real callable, so the loop can be tested without
                waiting on the wall clock.
            sleep: The async callable used to wait inside `run()`. Tests pass
                a fake sleeper that advances the fake clock instead of
                waiting, for the same reason.
        """
        self._registry = registry
        self._history_size = history
        self._clock = clock
        self._sleep = sleep
        self._history: dict[SensorId, deque[float | None]] = {}
        self._sample_count = 0
        self._latest: Sample | None = None
        self._subscribers: list[Subscriber] = []

    def sample(self) -> Sample:
        """Take one synchronous pass over every collector and record it.

        Returns:
            The sample just taken. It is also recorded into history and
            becomes the value `latest()` returns.
        """
        readings = self._registry.read_all()
        sample = Sample(timestamp=time.time(), readings=readings)
        self._record_history(sample)
        self._latest = sample
        return sample

    async def run(self, hz: float = DEFAULT_HZ) -> None:
        """Call `sample()` and then every subscriber, forever, at the given rate.

        The next deadline is always computed from a fixed monotonic start,
        not by sleeping a fixed amount, so the loop does not drift as passes
        take a little time. When a pass runs so long that a deadline has
        already gone by, the loop skips forward to the next deadline still
        in the future rather than firing a burst of catch-up passes.

        The loop runs until the task it is on is cancelled, which is the
        normal way to stop it; `asyncio.CancelledError` propagates out of
        this call.

        Args:
            hz: How many passes to take per second.
        """
        period = 1.0 / hz
        start = self._clock()
        passes = 0
        while True:
            sample = self.sample()
            self._notify(sample)

            passes += 1
            target = start + passes * period
            now = self._clock()
            delay = target - now
            if delay < 0:
                # Behind schedule: jump to the next deadline still ahead,
                # instead of trying to replay every deadline that was missed.
                passes = math.floor((now - start) / period) + 1
                target = start + passes * period
                delay = target - now
            await self._sleep(delay)

    def latest(self) -> Sample | None:
        """Return the most recent sample, or None before the first one."""
        return self._latest

    def history(self, sensor_id: SensorId) -> list[float | None]:
        """Return the recorded values of one sensor, oldest first.

        Args:
            sensor_id: Which sensor's history to return.

        Returns:
            The values, aligned by sample index with every other sensor's
            history. Empty when the sensor has never appeared in a sample.
        """
        buffer = self._history.get(sensor_id)
        return list(buffer) if buffer is not None else []

    def subscribe(self, callback: Subscriber) -> None:
        """Register a callback that receives every sample taken by `run()`.

        A plain call to `sample()` does not notify subscribers; only the
        loop in `run()` does, so that polling `sample()` has no side effect
        on anyone else.

        Args:
            callback: Called with each new `Sample`. An exception it raises
                is logged and does not stop the loop.
        """
        self._subscribers.append(callback)

    def _record_history(self, sample: Sample) -> None:
        """Append one sample's values into every sensor's ring buffer.

        A sensor seen for the first time starts its buffer padded with None
        for every earlier sample index, so that every series stays aligned
        and a sparkline can be drawn straight from it. A sensor that was
        known before but is missing from this pass gets None for this index.
        """
        seen: set[SensorId] = set()
        for reading in sample.readings:
            seen.add(reading.id)
            buffer = self._history.get(reading.id)
            if buffer is None:
                # A ring buffer only ever keeps its last `_history_size` entries
                # anyway, so padding is capped there too: a sensor that
                # appears after a very long uptime does not allocate a huge
                # throwaway list.
                padding = min(self._sample_count, self._history_size)
                buffer = deque([None] * padding, maxlen=self._history_size)
                self._history[reading.id] = buffer
            buffer.append(reading.value)

        for sensor_id, buffer in self._history.items():
            if sensor_id not in seen:
                buffer.append(None)

        self._sample_count += 1

    def _notify(self, sample: Sample) -> None:
        """Call every subscriber with the sample. A raising subscriber is logged, not fatal."""
        for callback in self._subscribers:
            try:
                callback(sample)
            except Exception as exc:  # noqa: BLE001 - one bad subscriber must not kill the loop
                logger.error("sampler: a subscriber raised: %s", exc)
