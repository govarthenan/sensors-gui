"""Tests for the per-device read interval and the value cache (ADR 0006).

A fake clock is used. It is a real callable that returns a number the test
controls, not a mock of the collector.
"""

from __future__ import annotations

from pathlib import Path

from sensors_gui.collectors.hwmon import HwmonCollector


class FakeClock:
    """A clock the test moves by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        """Return the current fake time in seconds."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the fake time forward."""
        self.now += seconds


def _value_of(collector: HwmonCollector, label: str) -> float | None:
    """Return the value of the first channel with the given label."""
    specs = {spec.id: spec for spec in collector.discover()}
    for reading in collector.read():
        if specs[reading.id].label == label:
            return reading.value
    return None


def test_a_register_backed_channel_has_no_wait_between_reads(fake_hwmon_root: Path) -> None:
    collector = HwmonCollector(root=fake_hwmon_root)
    tctl = next(spec for spec in collector.discover() if spec.label == "Tctl")
    assert tctl.min_interval == 0.0


def test_a_dimm_channel_gets_the_slow_interval(fake_hwmon_root: Path) -> None:
    collector = HwmonCollector(root=fake_hwmon_root)
    dimm = next(spec for spec in collector.discover() if "spd5118" in spec.id.device)
    assert dimm.min_interval == 5.0


def test_an_nvme_channel_gets_the_slow_interval(fake_hwmon_root: Path) -> None:
    collector = HwmonCollector(root=fake_hwmon_root)
    composite = next(spec for spec in collector.discover() if spec.label == "Composite")
    assert composite.min_interval == 5.0


def test_a_slow_channel_is_not_read_again_before_its_interval_has_passed(fake_hwmon_root: Path) -> None:
    clock = FakeClock()
    collector = HwmonCollector(root=fake_hwmon_root, clock=clock)
    collector.discover()
    assert _value_of(collector, "Composite") == 32.85

    # Change the file. Without a cache the next read would see the new value.
    (fake_hwmon_root / "hwmon1" / "temp1_input").write_text("50000\n")
    clock.advance(1.0)
    assert _value_of(collector, "Composite") == 32.85


def test_a_slow_channel_is_read_again_once_its_interval_has_passed(fake_hwmon_root: Path) -> None:
    clock = FakeClock()
    collector = HwmonCollector(root=fake_hwmon_root, clock=clock)
    collector.discover()
    _value_of(collector, "Composite")

    (fake_hwmon_root / "hwmon1" / "temp1_input").write_text("50000\n")
    clock.advance(5.1)
    assert _value_of(collector, "Composite") == 50.0


def test_a_fast_channel_is_read_again_on_every_pass(fake_hwmon_root: Path) -> None:
    clock = FakeClock()
    collector = HwmonCollector(root=fake_hwmon_root, clock=clock)
    collector.discover()
    assert _value_of(collector, "Tctl") == 41.0

    (fake_hwmon_root / "hwmon2" / "temp1_input").write_text("70000\n")
    assert _value_of(collector, "Tctl") == 70.0


def test_a_reading_records_the_time_of_the_read_not_the_time_of_the_pass(fake_hwmon_root: Path) -> None:
    clock = FakeClock()
    collector = HwmonCollector(root=fake_hwmon_root)
    collector.clock = clock
    specs = {spec.id: spec for spec in collector.discover()}
    first = {reading.id: reading for reading in collector.read()}

    clock.advance(2.0)
    second = {reading.id: reading for reading in collector.read()}

    composite = next(spec.id for spec in specs.values() if spec.label == "Composite")
    tctl = next(spec.id for spec in specs.values() if spec.label == "Tctl")

    assert second[composite].read_at == first[composite].read_at  # served from the cache
    assert second[tctl].read_at == 1002.0  # read again


def test_a_cached_reading_reports_its_age(fake_hwmon_root: Path) -> None:
    clock = FakeClock()
    collector = HwmonCollector(root=fake_hwmon_root, clock=clock)
    collector.discover()
    collector.read()

    clock.advance(3.0)
    specs = {spec.id: spec for spec in collector.discover()}
    composite = next(reading for reading in collector.read() if specs[reading.id].label == "Composite")
    assert composite.age(clock()) == 3.0
