"""Tests for `Sampler`.

No mocks. A fake collector is a small real class that implements the
`Collector` protocol. A fake clock and a fake sleeper are real callables the
test drives by hand, following the pattern in `tests/test_read_intervals.py`.

`pytest-asyncio` runs in strict mode in this project (see `pyproject.toml`),
so every async test carries `pytest.mark.asyncio`. No ini change was needed.
"""

from __future__ import annotations

import asyncio
import statistics
import time

import pytest

from sensors_gui.collectors import Collector
from sensors_gui.collectors.hwmon import HwmonCollector
from sensors_gui.model import Group, Reading, Sample, SensorId, SensorSpec, Unit
from sensors_gui.registry import Registry
from sensors_gui.sampler import Sampler


class FakeCollector:
    """A collector whose specs and readings are set up entirely by the test."""

    def __init__(self, name: str, specs: list[SensorSpec], readings: list[list[Reading]]) -> None:
        """Create the fake.

        Args:
            name: The collector name.
            specs: What `discover()` returns.
            readings: One list of readings per call to `read()`. The last
                entry repeats once the list is exhausted.
        """
        self.name = name
        self._specs = specs
        self._readings = readings
        self._read_calls = 0

    def discover(self) -> list[SensorSpec]:
        """Return the specs set up by the test."""
        return self._specs

    def read(self) -> list[Reading]:
        """Return the next configured readings."""
        if not self._readings:
            return []
        index = min(self._read_calls, len(self._readings) - 1)
        self._read_calls += 1
        return self._readings[index]

    def close(self) -> None:
        """Do nothing. The fake holds no resource."""


class RaisingCollector:
    """A collector whose `read()` breaks its contract and raises."""

    name = "raising"

    def discover(self) -> list[SensorSpec]:
        """Return no specs."""
        return []

    def read(self) -> list[Reading]:
        """Raise, to prove the sampler defends against a broken contract."""
        raise RuntimeError("raising: read failed")

    def close(self) -> None:
        """Do nothing."""


class FakeClock:
    """A monotonic clock the test moves by hand."""

    def __init__(self, start: float = 0.0) -> None:
        """Start the clock at `start` seconds."""
        self.now = start

    def __call__(self) -> float:
        """Return the current fake time in seconds."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the fake time forward."""
        self.now += seconds


class FakeSleeper:
    """A real async callable that advances a fake clock instead of waiting."""

    def __init__(self, clock: FakeClock) -> None:
        """Create the sleeper, tied to the given fake clock."""
        self.clock = clock
        self.requests: list[float] = []

    async def __call__(self, seconds: float) -> None:
        """Record the requested delay and advance the fake clock by it.

        Yields control once with a real `asyncio.sleep(0)`, so that a task
        cancelled from inside a subscriber (running on this same task) has a
        genuine suspension point to be delivered at, instead of the loop
        running forever without ever returning to the event loop.
        """
        self.requests.append(seconds)
        self.clock.advance(seconds)
        await asyncio.sleep(0)


def _id(source: str, channel: str) -> SensorId:
    """Build a sensor id for a test."""
    return SensorId(source=source, device="dev", channel=channel)


def _spec(source: str, channel: str) -> SensorSpec:
    """Build a minimal spec for a test."""
    return SensorSpec(id=_id(source, channel), label=channel, group=Group.OTHER, unit=Unit.CELSIUS)


def test_sample_returns_a_sample_with_readings_from_every_collector() -> None:
    id_a = _id("a", "temp1")
    id_b = _id("b", "temp1")
    collector_a = FakeCollector("a", specs=[_spec("a", "temp1")], readings=[[Reading.ok(id_a, 41.0)]])
    collector_b = FakeCollector("b", specs=[_spec("b", "temp1")], readings=[[Reading.ok(id_b, 55.0)]])
    registry = Registry([collector_a, collector_b])
    registry.discover()
    sampler = Sampler(registry)

    sample = sampler.sample()

    assert {reading.id for reading in sample.readings} == {id_a, id_b}


def test_sample_discards_the_first_pass_after_discovery() -> None:
    # exp-0007 finding 4: the nct6687 driver reports zeros for several
    # channels until it has updated once. The first pass after discover()
    # must be taken and discarded, never shown to a caller.
    sensor_id = _id("nct6687", "in0")
    collector = FakeCollector(
        "nct6687",
        specs=[_spec("nct6687", "in0")],
        readings=[[Reading.ok(sensor_id, 0.0)], [Reading.ok(sensor_id, 12.12)]],
    )
    registry = Registry([collector])
    registry.discover()
    sampler = Sampler(registry)

    sample = sampler.sample()

    assert sample.value_of(sensor_id) == 12.12


def test_the_warm_up_discard_happens_only_once() -> None:
    sensor_id = _id("nct6687", "in0")
    collector = FakeCollector(
        "nct6687",
        specs=[_spec("nct6687", "in0")],
        readings=[[Reading.ok(sensor_id, 0.0)], [Reading.ok(sensor_id, 1.0)], [Reading.ok(sensor_id, 2.0)]],
    )
    registry = Registry([collector])
    registry.discover()
    sampler = Sampler(registry)

    first = sampler.sample()
    second = sampler.sample()

    assert first.value_of(sensor_id) == 1.0
    assert second.value_of(sensor_id) == 2.0


def test_a_collector_that_raises_in_read_never_stops_a_sample() -> None:
    sensor_id = _id("good", "temp1")
    good = FakeCollector("good", specs=[_spec("good", "temp1")], readings=[[Reading.ok(sensor_id, 41.0)]])
    registry = Registry([RaisingCollector(), good])
    registry.discover()
    sampler = Sampler(registry)

    sample = sampler.sample()  # must not raise, even though a collector breaks its contract

    assert sample.value_of(sensor_id) == 41.0


def test_latest_is_none_before_any_sample_is_taken() -> None:
    registry = Registry([])
    registry.discover()
    sampler = Sampler(registry)

    assert sampler.latest() is None


def test_latest_returns_the_most_recent_sample() -> None:
    sensor_id = _id("a", "temp1")
    collector = FakeCollector(
        "a",
        specs=[_spec("a", "temp1")],
        readings=[[Reading.ok(sensor_id, 0.0)], [Reading.ok(sensor_id, 1.0)], [Reading.ok(sensor_id, 2.0)]],
    )
    registry = Registry([collector])
    registry.discover()
    sampler = Sampler(registry)

    sampler.sample()  # the discovery-time discard already happened inside registry.discover()
    second = sampler.sample()

    assert sampler.latest() is second


def test_history_is_empty_for_a_sensor_never_sampled() -> None:
    registry = Registry([])
    registry.discover()
    sampler = Sampler(registry)

    assert sampler.history(_id("ghost", "temp1")) == []


def test_history_records_a_value_per_sample() -> None:
    sensor_id = _id("a", "temp1")
    collector = FakeCollector(
        "a",
        specs=[_spec("a", "temp1")],
        readings=[
            [Reading.ok(sensor_id, 0.0)],
            [Reading.ok(sensor_id, 1.0)],
            [Reading.ok(sensor_id, 2.0)],
        ],
    )
    registry = Registry([collector])
    registry.discover()
    sampler = Sampler(registry)

    sampler.sample()
    sampler.sample()

    assert sampler.history(sensor_id) == [1.0, 2.0]


def test_history_holds_a_failed_reading_as_none() -> None:
    sensor_id = _id("a", "temp1")
    collector = FakeCollector(
        "a",
        specs=[_spec("a", "temp1")],
        readings=[[Reading.failed(sensor_id, "dead sensor")]],
    )
    registry = Registry([collector])
    registry.discover()
    sampler = Sampler(registry)

    sampler.sample()

    assert sampler.history(sensor_id) == [None]


def test_history_defaults_to_120_entries() -> None:
    sensor_id = _id("a", "temp1")
    readings = [[Reading.ok(sensor_id, float(value))] for value in range(200)]
    collector = FakeCollector("a", specs=[_spec("a", "temp1")], readings=readings)
    registry = Registry([collector])
    registry.discover()
    sampler = Sampler(registry)

    for _ in range(150):
        sampler.sample()

    history = sampler.history(sensor_id)
    assert len(history) == 120
    # registry.discover() already discarded value 0.0 before the loop ran.
    # The 150 sample() calls each record exactly one value, in order:
    # 1.0, 2.0, ..., 150.0. The ring buffer keeps only the most recent 120
    # of those: 31.0 .. 150.0.
    assert history[0] == 31.0
    assert history[-1] == 150.0


def test_history_size_is_configurable() -> None:
    sensor_id = _id("a", "temp1")
    readings = [[Reading.ok(sensor_id, float(value))] for value in range(20)]
    collector = FakeCollector("a", specs=[_spec("a", "temp1")], readings=readings)
    registry = Registry([collector])
    sampler = Sampler(registry, history=5)

    registry.discover()
    for _ in range(10):
        sampler.sample()

    assert len(sampler.history(sensor_id)) == 5


def test_a_sensor_that_appears_later_gets_its_history_padded_with_none() -> None:
    id_a = _id("fake", "a")
    id_b = _id("fake", "b")
    collector = FakeCollector(
        "fake",
        specs=[_spec("fake", "a"), _spec("fake", "b")],
        readings=[
            [Reading.ok(id_a, 0.0)],  # consumed by registry.discover()'s discard pass
            [Reading.ok(id_a, 2.0)],  # b is silent here
            [Reading.ok(id_a, 3.0), Reading.ok(id_b, 100.0)],  # b appears
        ],
    )
    registry = Registry([collector])
    registry.discover()
    sampler = Sampler(registry)

    sampler.sample()
    sampler.sample()

    assert sampler.history(id_a) == [2.0, 3.0]
    assert sampler.history(id_b) == [None, 100.0]


def test_subscribe_registers_a_callback_but_manual_sample_does_not_call_it() -> None:
    # run() is the loop that notifies subscribers; a bare sample() call does
    # not, so that a caller can poll sample() without side effects.
    received: list[object] = []
    registry = Registry([])
    registry.discover()
    sampler = Sampler(registry)
    sampler.subscribe(received.append)

    sampler.sample()

    assert received == []


@pytest.mark.asyncio
async def test_run_calls_sample_and_then_every_subscriber() -> None:
    sensor_id = _id("a", "temp1")
    readings = [[Reading.ok(sensor_id, float(value))] for value in range(10)]
    collector = FakeCollector("a", specs=[_spec("a", "temp1")], readings=readings)
    registry = Registry([collector])
    registry.discover()
    clock = FakeClock()
    sleeper = FakeSleeper(clock)
    sampler = Sampler(registry, clock=clock, sleep=sleeper)
    received: list[float | None] = []

    def on_sample(sample: Sample) -> None:
        received.append(sample.value_of(sensor_id))
        if len(received) >= 3:
            task.cancel()

    sampler.subscribe(on_sample)
    task = asyncio.ensure_future(sampler.run(hz=2.0))

    with pytest.raises(asyncio.CancelledError):
        await task

    assert received == [1.0, 2.0, 3.0]


@pytest.mark.asyncio
async def test_a_raising_subscriber_is_logged_and_does_not_kill_the_loop() -> None:
    sensor_id = _id("a", "temp1")
    readings = [[Reading.ok(sensor_id, float(value))] for value in range(10)]
    collector = FakeCollector("a", specs=[_spec("a", "temp1")], readings=readings)
    registry = Registry([collector])
    registry.discover()
    clock = FakeClock()
    sleeper = FakeSleeper(clock)
    sampler = Sampler(registry, clock=clock, sleep=sleeper)

    def broken_subscriber(sample: Sample) -> None:
        raise RuntimeError("subscriber broke")

    calls = 0

    def counting_subscriber(sample: Sample) -> None:
        nonlocal calls
        calls += 1
        if calls >= 3:
            task.cancel()

    sampler.subscribe(broken_subscriber)
    sampler.subscribe(counting_subscriber)
    task = asyncio.ensure_future(sampler.run(hz=2.0))

    with pytest.raises(asyncio.CancelledError):
        await task

    assert calls == 3


@pytest.mark.asyncio
async def test_run_does_not_drift_when_a_pass_takes_less_than_the_period() -> None:
    sensor_id = _id("a", "temp1")
    readings = [[Reading.ok(sensor_id, float(value))] for value in range(10)]
    collector = FakeCollector("a", specs=[_spec("a", "temp1")], readings=readings)
    registry = Registry([collector])
    registry.discover()
    clock = FakeClock()
    sleeper = FakeSleeper(clock)
    sampler = Sampler(registry, clock=clock, sleep=sleeper)

    passes = 0

    def slow_but_not_too_slow(sample: Sample) -> None:
        nonlocal passes
        clock.advance(0.2)  # simulate 0.2 s of processing inside one pass
        passes += 1
        if passes >= 3:
            task.cancel()

    sampler.subscribe(slow_but_not_too_slow)
    task = asyncio.ensure_future(sampler.run(hz=1.0))

    with pytest.raises(asyncio.CancelledError):
        await task

    # Each requested sleep must be shortened by the 0.2 s already spent, so
    # that three ticks land on t=1.0, t=2.0, t=3.0 and never drift later.
    assert sleeper.requests == pytest.approx([0.8, 0.8, 0.8])
    assert clock.now == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_run_skips_a_missed_deadline_instead_of_piling_up() -> None:
    sensor_id = _id("a", "temp1")
    readings = [[Reading.ok(sensor_id, float(value))] for value in range(10)]
    collector = FakeCollector("a", specs=[_spec("a", "temp1")], readings=readings)
    registry = Registry([collector])
    registry.discover()
    clock = FakeClock()
    sleeper = FakeSleeper(clock)
    sampler = Sampler(registry, clock=clock, sleep=sleeper)

    call_times: list[float] = []

    def too_slow(sample: Sample) -> None:
        call_times.append(clock.now)
        clock.advance(1.5)  # slower than the 1.0 s period: every pass misses
        if len(call_times) >= 3:
            task.cancel()

    sampler.subscribe(too_slow)
    task = asyncio.ensure_future(sampler.run(hz=1.0))

    with pytest.raises(asyncio.CancelledError):
        await task

    # Each pass costs 1.5 s against a 1.0 s period, so the deadline one
    # period ahead is always already gone. The loop must jump to the next
    # still-future deadline rather than firing a burst of catch-up passes.
    assert call_times == pytest.approx([0.0, 2.0, 4.0])


def test_a_full_sample_stays_under_the_fifty_millisecond_budget() -> None:
    # docs/architecture.md: the budget for one full pass of *all* collectors
    # is 50 ms. Uses the real hwmon tree, and the real GPU through NVML when
    # both are present on this machine; skips cleanly when neither is, so
    # the test suite runs on any machine.
    collectors: list[Collector] = [HwmonCollector()]
    try:
        import pynvml  # noqa: F401

        from sensors_gui.collectors.nvidia import NvidiaCollector

        collectors.append(NvidiaCollector())
    except ImportError:
        pass

    registry = Registry(collectors)
    registry.discover()
    if not registry.specs():
        registry.close()
        pytest.skip("no real sensor hardware available on this machine")

    sampler = Sampler(registry)
    sampler.sample()  # warm any interval caches before timing, as exp-0004 and exp-0006 do

    timings: list[float] = []
    for _ in range(10):
        start = time.perf_counter()
        sampler.sample()
        timings.append((time.perf_counter() - start) * 1000)
    registry.close()

    assert statistics.median(timings) < 50.0
