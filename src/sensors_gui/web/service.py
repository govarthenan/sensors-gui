"""The sampling service behind the web front end.

One `SensorService` owns the registry, the sampler and the worker thread that
reads the machine. The web layer only serialises what this gives it.

The sampler runs on a **worker thread**, never on the event loop. `exp-0014`
timed 600 passes at 10 Hz: the median pass is 2.157 ms, but the p95 is
26.4 ms and the longest is 56.8 ms, and all of the tail belongs to the two
PCIe calls in the NVIDIA collector (ADR 0006, `exp-0006`). One of those passes
is longer than a whole 10 Hz period, so a pass taken on the event loop would
hold up the frame it is meant to deliver. See ADR 0012.

Nothing here writes to hardware. ADR 0007.
"""

from __future__ import annotations

import logging
import re
import statistics
import threading
import time
from collections.abc import Callable, Iterable

from sensors_gui import naming
from sensors_gui.collectors import Collector
from sensors_gui.descriptions import DERIVED, NOT_COLLECTED, UNREACHABLE, describe
from sensors_gui.model import Group, Reading, Sample, SensorId, SensorSpec
from sensors_gui.registry import Registry
from sensors_gui.sampler import Sampler
from sensors_gui.web.alerts import AlertLog

logger = logging.getLogger(__name__)

type FrameSubscriber = Callable[[dict[str, object]], None]

DEFAULT_HZ = 2.0
# The rates the "Slower" and "Faster" buttons step through. Gova, 2026-09-25:
# "Fixed steps. 10hz, 5 hz, 2 hz, 1 hz, 0.5 hz, 0.25 hz, 0.2 hz, 0.1 hz".
# Halving and doubling gave 0.63 Hz and 0.31 Hz. `--hz` can still start the
# service between two steps; a click then goes to the nearest step.
RATE_STEPS = (0.1, 0.2, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)
MIN_HZ = RATE_STEPS[0]
MAX_HZ = RATE_STEPS[-1]
PASS_WINDOW = 200


# Gova, 2026-09-23: "only log cpu readings that go above 110% above or below
# their limits". The CPU thread frequencies pass the kernel's maximum in about
# 1 % of readings, by 2.23 % at most, and log nothing of value; a margin of 10 %
# of the limit removes all of them in data/probes/2026-09-23-cpu-frequency-margin.txt.
# The display still shows every reading past the ceiling; only the log waits.
CPU_FREQUENCY_MARGIN = 0.10
_CPU_FREQUENCY = re.compile(r"^(core\d+_)?frequency$")


def alert_margin(spec: SensorSpec) -> float:
    """Return the fraction of its limit a channel may pass before the alert log records it."""
    if spec.id.source == "system" and _CPU_FREQUENCY.match(spec.id.channel):
        return CPU_FREQUENCY_MARGIN
    return 0.0


def next_deadline(deadline: float, period: float, now: float) -> float:
    """Return the time of the next pass, one period after the last deadline.

    The period is the one in use now, so a change of rate acts on the next
    pass. A deadline already past is skipped to the next one ahead, never
    run as a burst of catch-up passes.

    The loop used to compute `start + passes * period`, with `passes` counted
    since the worker started. A slower rate then put the next pass as far in
    the future as the worker had already run: the page froze (Gova,
    2026-09-25).

    Args:
        deadline: When the pass that just ran was due.
        period: The time between two passes at the rate in use now.
        now: The clock now.

    Returns:
        The next deadline, always later than `now`.
    """
    following = deadline + period
    if following <= now:
        following += (int((now - following) / period) + 1) * period
    return following


def _identity(spec: SensorSpec) -> SensorSpec:
    """Return the spec unchanged. The default when no naming layer is given."""
    return spec


def _keep_all(spec: SensorSpec) -> bool:
    """Keep every sensor. The default when no filter is given."""
    _ = spec
    return True


class PassTimes:
    """The spread of the sampler's pass time, not only its last value.

    The terminal screen prints the time of the **last** pass, which is close to
    the median and hides a tail that reaches 57 ms (`exp-0014`, finding 4). The
    GUI reports the median and the maximum instead, so the tail is on screen.
    """

    def __init__(self, window: int = PASS_WINDOW) -> None:
        """Create the record.

        Args:
            window: How many recent passes the median is taken over.
        """
        self._window = window
        self._recent: list[float] = []
        self.last_ms = 0.0
        self.max_ms = 0.0

    def record(self, milliseconds: float) -> None:
        """Add one pass time."""
        self.last_ms = milliseconds
        self.max_ms = max(self.max_ms, milliseconds)
        self._recent.append(milliseconds)
        if len(self._recent) > self._window:
            del self._recent[0 : len(self._recent) - self._window]

    @property
    def median_ms(self) -> float:
        """Return the median of the recent passes, or zero before the first one."""
        return statistics.median(self._recent) if self._recent else 0.0

    def as_dict(self) -> dict[str, float]:
        """Return the three numbers the status bar shows."""
        return {
            "last_ms": round(self.last_ms, 3),
            "median_ms": round(self.median_ms, 3),
            "max_ms": round(self.max_ms, 3),
        }


class Channel:
    """One sensor as the front end sees it: its spec, and where it sits in a frame."""

    def __init__(self, index: int, spec: SensorSpec, hidden: bool) -> None:
        """Create the channel.

        Args:
            index: Its position in every frame's value array.
            spec: The sensor, after the naming layer has run.
            hidden: Whether the BIOS ground truth says this reading misleads.
                A hidden channel is still sent; the front end decides.
        """
        self.index = index
        self.spec = spec
        self.hidden = hidden

    def as_dict(self) -> dict[str, object]:
        """Return the static description the front end fetches once."""
        spec = self.spec
        return {
            "i": self.index,
            "key": spec.id.key,
            "label": spec.label,
            "group": str(spec.group),
            "unit": str(spec.unit),
            "symbol": spec.unit.symbol,
            "decimals": spec.decimals if spec.decimals is not None else spec.unit.decimals,
            "low": spec.low,
            "high": spec.high,
            "warn": spec.warn,
            "critical": spec.critical,
            "min_interval": spec.min_interval,
            "origin": spec.origin,
            "source": spec.id.source,
            "hidden": self.hidden,
            "description": None if (found := describe(spec)) is None else found.as_dict(),
            "alert_margin": alert_margin(spec),
        }


class SensorService:
    """Reads the machine on a worker thread and hands each pass to its subscribers."""

    def __init__(
        self,
        collectors: Iterable[Collector],
        hz: float = DEFAULT_HZ,
        decorate: Callable[[SensorSpec], SensorSpec] = _identity,
        keep: Callable[[SensorSpec], bool] = _keep_all,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create the service.

        Args:
            collectors: The sources to read. The service owns them and closes
                them when it stops.
            hz: How many passes to take each second.
            decorate: Gives a sensor a name and a group a person recognises.
            keep: Decides whether a sensor is shown by default. It is given the
                sensor **as the driver reported it**, before `decorate` runs,
                because a judgement keyed on the label cannot survive a rename.
                A sensor it rejects is marked hidden, never dropped.
            clock: The source of time that paces the worker. A test passes a
                real callable of its own.
        """
        self._registry = Registry(list(collectors))
        self._sampler = Sampler(self._registry)
        self._decorate = decorate
        self._keep = keep
        self._clock = clock
        self._hz = max(MIN_HZ, min(hz, MAX_HZ))
        self._channels: list[Channel] = []
        self._by_id: dict[SensorId, Channel] = {}
        self._subscribers: list[FrameSubscriber] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._paused = False
        self.passes = PassTimes()
        # Gova, 2026-09-23: every reading past its ceiling is logged. In memory
        # only; see alerts.py.
        self.alerts = AlertLog(margin=alert_margin)
        self.started_at = time.time()
        self.last_sample_at: float | None = None

    # --- the catalogue ------------------------------------------------------

    def discover(self) -> None:
        """Find every sensor and fix the order of every later frame.

        The index of a channel is its position here, and every frame is an
        array in that order. So a frame carries no names, and a re-scan is the
        only thing that can change what an index means.
        """
        self._registry.discover()
        channels: list[Channel] = []
        for raw in self._registry.specs():
            spec = self._decorate(raw)
            channels.append(Channel(index=len(channels), spec=spec, hidden=not self._keep(raw)))
        channels.sort(key=lambda channel: (str(channel.spec.group), channel.spec.label))
        for position, channel in enumerate(channels):
            channel.index = position
        with self._lock:
            self._channels = channels
            self._by_id = {channel.spec.id: channel for channel in channels}

    def channels(self) -> list[Channel]:
        """Return every channel, in frame order."""
        with self._lock:
            return list(self._channels)

    def catalogue(self) -> dict[str, object]:
        """Return everything the front end needs once, before the first frame."""
        channels = self.channels()
        return {
            "machine": "dst-gova-pc",
            "hz": self._hz,
            "min_hz": MIN_HZ,
            "max_hz": MAX_HZ,
            "rate_steps": list(RATE_STEPS),
            "paused": self._paused,
            "groups": [str(group) for group in Group],
            "shown": sum(1 for channel in channels if not channel.hidden),
            "hidden": sum(1 for channel in channels if channel.hidden),
            "channels": [channel.as_dict() for channel in channels],
            # What a person would expect and the application does not show,
            # each with its reason. `docs/gui-goal.md` 4.2: never a silent gap.
            "unreachable": [entry.as_dict() for entry in UNREACHABLE],
            "not_collected": [entry.as_dict() for entry in NOT_COLLECTED],
            "derived": {key: description.as_dict() for key, description in DERIVED.items()},
        }

    # --- frames -------------------------------------------------------------

    def frame(self, sample: Sample) -> dict[str, object]:
        """Turn one sample into the compact frame the WebSocket carries.

        The value array is in catalogue order, so a frame carries no names. A
        channel that failed carries its reason in `errors`, keyed by index, and
        one that is older than a pass carries its age in `ages`. Both are
        sparse, because on this machine almost every channel is fine and fresh.

        Args:
            sample: The pass to describe.

        Returns:
            The frame, ready to be serialised.
        """
        channels = self.channels()
        values: list[float | None] = [None] * len(channels)
        errors: dict[str, str] = {}
        ages: dict[str, float] = {}
        now = time.monotonic()
        for reading in sample.readings:
            channel = self._by_id.get(reading.id)
            if channel is None:
                continue
            values[channel.index] = reading.value
            if reading.error is not None:
                errors[str(channel.index)] = reading.error
            age = reading.age(now)
            if age is not None and age > 1.0 / self._hz:
                ages[str(channel.index)] = round(age, 2)
        return {
            "t": sample.timestamp,
            "hz": self._hz,
            "paused": self._paused,
            "pass": self.passes.as_dict(),
            "alerts": {"open": self.alerts.open_count(), "total": self.alerts.total()},
            "v": values,
            "errors": errors,
            "ages": ages,
        }

    def sample_once(self) -> dict[str, object]:
        """Take one pass and return its frame. This never raises."""
        began = time.perf_counter()
        sample = self._sampler.sample()
        self.passes.record((time.perf_counter() - began) * 1000)
        self.last_sample_at = sample.timestamp
        channels = self.channels()
        self.alerts.observe(
            [channel.spec for channel in channels],
            sample.readings,
            sample.timestamp,
            hidden={channel.spec.id for channel in channels if channel.hidden},
        )
        return self.frame(sample)

    def history(self, sensor_id: SensorId) -> list[float | None]:
        """Return the ring buffer of one sensor, oldest first."""
        return self._sampler.history(sensor_id)

    def latest_readings(self) -> dict[SensorId, Reading]:
        """Return the readings of the most recent pass, keyed by identity."""
        sample = self._sampler.latest()
        return {} if sample is None else sample.by_id()

    # --- the worker ---------------------------------------------------------

    def subscribe(self, callback: FrameSubscriber) -> None:
        """Register a callback that receives every frame.

        The callback runs **on the worker thread**, so it must not block. The
        web layer uses it only to hand the frame to the event loop.

        Args:
            callback: Called with each frame. An exception it raises is logged
                and does not stop the worker.
        """
        with self._lock:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: FrameSubscriber) -> None:
        """Remove a callback. Removing one that was never added does nothing."""
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def start(self) -> None:
        """Start the worker thread. Calling it twice does nothing the second time."""
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="sensors-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the worker and close every collector."""
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=5.0)
        self._registry.close()

    def _run(self) -> None:
        """Sample at the chosen rate until stopped.

        Each deadline is the last one plus the period in use now, so the loop
        does not drift, and a change of rate acts on the next pass. When a pass
        runs past a deadline, the loop skips to the next one still ahead
        instead of firing a burst of catch-up passes. See `next_deadline`.
        """
        deadline = self._clock()
        while not self._stop.is_set():
            if not self._paused:
                try:
                    frame = self.sample_once()
                except Exception as exc:  # noqa: BLE001 - the worker must outlive one bad pass
                    logger.error("service: a pass raised, which is against contract: %s", exc)
                else:
                    self._publish(frame)
            deadline = next_deadline(deadline, 1.0 / self._hz, self._clock())
            self._stop.wait(max(deadline - self._clock(), 0.0))

    def _publish(self, frame: dict[str, object]) -> None:
        """Hand one frame to every subscriber. A raising subscriber is logged, not fatal."""
        with self._lock:
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(frame)
            except Exception as exc:  # noqa: BLE001 - one bad subscriber must not kill the worker
                logger.error("service: a subscriber raised: %s", exc)

    # --- control ------------------------------------------------------------

    @property
    def hz(self) -> float:
        """Return the current sample rate."""
        return self._hz

    def set_rate(self, hz: float) -> float:
        """Set the sample rate, held between 0.1 Hz and 10 Hz.

        Args:
            hz: The wanted rate.

        Returns:
            The rate that was actually set.
        """
        self._hz = max(MIN_HZ, min(hz, MAX_HZ))
        return self._hz

    @property
    def paused(self) -> bool:
        """Return whether sampling is paused."""
        return self._paused

    def set_paused(self, paused: bool) -> bool:
        """Pause or resume sampling, and return the new state."""
        self._paused = paused
        return self._paused


def build_service(hz: float = DEFAULT_HZ) -> SensorService:
    """Build the service with every collector this machine has.

    Args:
        hz: The starting sample rate.

    Returns:
        A service that has not discovered or started yet.
    """
    from sensors_gui.collectors.hwmon import HwmonCollector
    from sensors_gui.collectors.memory_pressure import MemoryPressureCollector
    from sensors_gui.collectors.nvidia import NvidiaCollector
    from sensors_gui.collectors.power_supply import PowerSupplyCollector
    from sensors_gui.collectors.privileged import PrivilegedCollector
    from sensors_gui.collectors.system import SystemCollector

    return SensorService(
        collectors=[
            HwmonCollector(),
            NvidiaCollector(),
            PowerSupplyCollector(),
            PrivilegedCollector(),
            SystemCollector(),
            MemoryPressureCollector(),
        ],
        hz=hz,
        decorate=naming.friendly,
        keep=lambda spec: naming.verdict(spec) != "wrong",
    )
