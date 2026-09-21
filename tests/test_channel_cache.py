"""Tests for the shared channel cache (ADR 0006).

Both the hwmon collector and the NVIDIA collector have channels that cost far
more to read than the rest. The cache is the one place that holds the rule.
"""

from __future__ import annotations

import pytest

from sensors_gui.collectors.cache import ChannelCache
from sensors_gui.model import SensorId


class FakeClock:
    """A clock the test moves by hand."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        """Return the current fake time."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the fake time forward."""
        self.now += seconds


SENSOR = SensorId(source="test", device="d@/sys/x", channel="c1")


def test_a_channel_with_no_interval_is_read_every_time() -> None:
    clock = FakeClock()
    cache = ChannelCache(clock)
    calls = []

    def reader() -> float:
        calls.append(1)
        return float(len(calls))

    assert cache.serve(SENSOR, 0.0, reader).value == 1.0
    assert cache.serve(SENSOR, 0.0, reader).value == 2.0
    assert len(calls) == 2


def test_a_channel_with_an_interval_is_served_from_the_cache() -> None:
    clock = FakeClock()
    cache = ChannelCache(clock)
    calls = []

    def reader() -> float:
        calls.append(1)
        return float(len(calls))

    assert cache.serve(SENSOR, 5.0, reader).value == 1.0
    clock.advance(4.9)
    assert cache.serve(SENSOR, 5.0, reader).value == 1.0
    assert len(calls) == 1


def test_the_channel_is_read_again_once_the_interval_has_passed() -> None:
    clock = FakeClock()
    cache = ChannelCache(clock)
    calls = []

    def reader() -> float:
        calls.append(1)
        return float(len(calls))

    cache.serve(SENSOR, 5.0, reader)
    clock.advance(5.0)
    assert cache.serve(SENSOR, 5.0, reader).value == 2.0


def test_a_cached_reading_keeps_the_time_of_the_read_that_made_it() -> None:
    clock = FakeClock()
    cache = ChannelCache(clock)
    first = cache.serve(SENSOR, 5.0, lambda: 1.0)
    clock.advance(3.0)
    second = cache.serve(SENSOR, 5.0, lambda: 2.0)
    assert second.read_at == first.read_at == 100.0
    assert second.age(clock()) == 3.0


def test_a_reader_that_raises_becomes_a_failed_reading_and_does_not_propagate() -> None:
    cache = ChannelCache(FakeClock())

    def reader() -> float:
        raise OSError("the device went away")

    reading = cache.serve(SENSOR, 0.0, reader)
    assert not reading.is_ok
    assert reading.error is not None
    assert "went away" in reading.error


def test_a_failed_read_is_also_held_for_the_interval() -> None:
    # Retrying a dead device every pass costs as much as reading a live one.
    clock = FakeClock()
    cache = ChannelCache(clock)
    calls = []

    def reader() -> float:
        calls.append(1)
        raise OSError("gone")

    cache.serve(SENSOR, 5.0, reader)
    clock.advance(1.0)
    cache.serve(SENSOR, 5.0, reader)
    assert len(calls) == 1


def test_a_reader_that_gives_none_becomes_a_failed_reading() -> None:
    cache = ChannelCache(FakeClock())
    reading = cache.serve(SENSOR, 0.0, lambda: None)
    assert not reading.is_ok
    assert reading.error is not None


def test_forget_drops_everything_the_cache_holds() -> None:
    clock = FakeClock()
    cache = ChannelCache(clock)
    calls = []

    def reader() -> float:
        calls.append(1)
        return 1.0

    cache.serve(SENSOR, 5.0, reader)
    cache.forget()
    cache.serve(SENSOR, 5.0, reader)
    assert len(calls) == 2


def test_two_channels_are_held_apart() -> None:
    clock = FakeClock()
    cache = ChannelCache(clock)
    other = SensorId(source="test", device="d@/sys/x", channel="c2")
    cache.serve(SENSOR, 5.0, lambda: 1.0)
    assert cache.serve(other, 5.0, lambda: 2.0).value == 2.0


def test_the_default_clock_moves_forward() -> None:
    cache = ChannelCache()
    reading = cache.serve(SENSOR, 0.0, lambda: 1.0)
    assert reading.read_at is not None
    assert reading.read_at > 0.0


@pytest.mark.parametrize("interval", [-1.0, float("nan")])
def test_a_nonsense_interval_is_treated_as_read_every_time(interval: float) -> None:
    clock = FakeClock()
    cache = ChannelCache(clock)
    calls = []

    def reader() -> float:
        calls.append(1)
        return 1.0

    cache.serve(SENSOR, interval, reader)
    cache.serve(SENSOR, interval, reader)
    assert len(calls) == 2
