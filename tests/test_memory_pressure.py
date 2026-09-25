"""Tests for the memory pressure collector: `/proc/pressure/memory` and `/proc/vmstat`.

Gova chose these channels on 2026-09-25, for the memory view: "Add memory
pressure". The expected values come from the kernel's own formats, copied in
`data/evidence/memory-pressure-sources-2026-09-25/`.

No mocks. Each test builds a real `/proc`-shaped tree in a temporary
directory, and a clock the test moves by hand drives the fault rates. One
test reads the real `/proc` of this machine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sensors_gui.collectors.memory_pressure import MemoryPressureCollector
from sensors_gui.model import Group, Unit

PRESSURE = (
    "some avg10=1.53 avg60=0.87 avg300=0.21 total=4780829\nfull avg10=0.40 avg60=0.10 avg300=0.00 total=4611134\n"
)
EXPECTED_PRESSURE = {
    "Memory pressure, some, 10 s": 1.53,
    "Memory pressure, some, 60 s": 0.87,
    "Memory pressure, some, 300 s": 0.21,
    "Memory pressure, full, 10 s": 0.40,
    "Memory pressure, full, 60 s": 0.10,
    "Memory pressure, full, 300 s": 0.0,
}


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


def vmstat_text(faults: int, major: int) -> str:
    """Return a `/proc/vmstat` with the two counters among others, as the kernel writes it."""
    return f"nr_free_pages 430379\npgpgin 118426\npgfault {faults}\npgmajfault {major}\npgrefill 0\n"


@pytest.fixture
def proc(tmp_path: Path) -> Path:
    """Return a proc tree with both files."""
    (tmp_path / "pressure").mkdir()
    (tmp_path / "pressure" / "memory").write_text(PRESSURE)
    (tmp_path / "vmstat").write_text(vmstat_text(1000, 10))
    return tmp_path


def values_by_label(collector: MemoryPressureCollector) -> dict[str, float | None]:
    """Read once and return each value by its label."""
    labels = {spec.id: spec.label for spec in collector.discover()}
    return {labels[reading.id]: reading.value for reading in collector.read()}


def test_collector_name_is_proc() -> None:
    assert MemoryPressureCollector().name == "proc"


def test_discover_finds_six_pressure_and_two_fault_channels_in_the_memory_group(proc: Path) -> None:
    specs = MemoryPressureCollector(proc_root=proc).discover()
    assert [spec.label for spec in specs] == [*EXPECTED_PRESSURE, "Page faults", "Major page faults"]
    assert {spec.group for spec in specs} == {Group.MEMORY}
    assert all(spec.min_interval == 0.0 for spec in specs)


def test_pressure_channels_are_percent_on_a_zero_to_hundred_scale(proc: Path) -> None:
    specs = MemoryPressureCollector(proc_root=proc).discover()
    for spec in specs[:6]:
        assert (spec.unit, spec.low, spec.high) == (Unit.PERCENT, 0.0, 100.0)
        assert spec.warn is None
        assert spec.critical is None


def test_fault_channels_are_per_second_with_no_top(proc: Path) -> None:
    specs = MemoryPressureCollector(proc_root=proc).discover()
    for spec in specs[6:]:
        assert (spec.unit, spec.low, spec.high) == (Unit.PER_SECOND, 0.0, None)


def test_pressure_reads_the_six_averages_as_the_kernel_wrote_them(proc: Path) -> None:
    values = values_by_label(MemoryPressureCollector(proc_root=proc, clock=FakeClock()))
    for label, expected in EXPECTED_PRESSURE.items():
        assert values[label] == pytest.approx(expected), label


def test_fault_rates_are_absent_on_the_first_read_because_a_rate_needs_two_points(proc: Path) -> None:
    values = values_by_label(MemoryPressureCollector(proc_root=proc, clock=FakeClock()))
    assert values["Page faults"] is None
    assert values["Major page faults"] is None


def test_fault_rates_are_the_counter_change_over_the_clock_change(proc: Path) -> None:
    clock = FakeClock()
    collector = MemoryPressureCollector(proc_root=proc, clock=clock)
    labels = {spec.id: spec.label for spec in collector.discover()}
    collector.read()
    (proc / "vmstat").write_text(vmstat_text(1600, 14))
    clock.advance(2.0)
    values = {labels[reading.id]: reading.value for reading in collector.read()}
    assert values["Page faults"] == pytest.approx(300.0)
    assert values["Major page faults"] == pytest.approx(2.0)


def test_a_counter_that_goes_down_counts_from_zero_not_through_a_wrap(proc: Path) -> None:
    clock = FakeClock()
    collector = MemoryPressureCollector(proc_root=proc, clock=clock)
    labels = {spec.id: spec.label for spec in collector.discover()}
    collector.read()
    (proc / "vmstat").write_text(vmstat_text(50, 1))
    clock.advance(1.0)
    values = {labels[reading.id]: reading.value for reading in collector.read()}
    assert values["Page faults"] == pytest.approx(50.0)
    assert values["Major page faults"] == pytest.approx(1.0)


def test_no_pressure_file_gives_no_pressure_channels(proc: Path) -> None:
    """A kernel built without PSI, or booted with psi=0, has no such file."""
    (proc / "pressure" / "memory").unlink()
    labels = [spec.label for spec in MemoryPressureCollector(proc_root=proc).discover()]
    assert labels == ["Page faults", "Major page faults"]


def test_no_vmstat_gives_no_fault_channels(proc: Path) -> None:
    (proc / "vmstat").unlink()
    labels = [spec.label for spec in MemoryPressureCollector(proc_root=proc).discover()]
    assert labels == list(EXPECTED_PRESSURE)


def test_a_file_that_goes_away_after_discovery_gives_failed_readings_and_does_not_raise(proc: Path) -> None:
    collector = MemoryPressureCollector(proc_root=proc, clock=FakeClock())
    collector.discover()
    (proc / "pressure" / "memory").unlink()
    (proc / "vmstat").unlink()
    readings = collector.read()
    assert len(readings) == 8
    assert all(reading.value is None and reading.error for reading in readings)


def test_the_real_machine_gives_all_eight_channels_and_a_fault_rate() -> None:
    collector = MemoryPressureCollector()
    specs = collector.discover()
    assert len(specs) == 8
    collector.read()
    readings = collector.read()
    for reading in readings[:6]:
        assert reading.is_ok
        assert 0.0 <= reading.value <= 100.0
    assert readings[6].is_ok
    assert readings[6].value >= 0.0
    collector.close()


def test_pressure_channels_keep_the_two_decimals_the_kernel_writes(proc: Path) -> None:
    specs = MemoryPressureCollector(proc_root=proc).discover()
    assert all(spec.decimals == 2 for spec in specs[:6])
    assert specs[0].format(0.4) == "0.40 %"
