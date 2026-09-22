"""Tests for the NVIDIA collector.

There is no mock. The tests run against the real RTX 4090 in this machine, and
they skip when NVML cannot start. That is the correct shape for a monitor built
for one specific PC: the hardware is the fixture.

Expected values come from ADR 0003 and from `lab/exp-0002-nvidia-access/`.
"""

from __future__ import annotations

import pytest

from sensors_gui.collectors.nvidia import NvidiaCollector
from sensors_gui.model import Group, Unit

pytest.importorskip("pynvml")


@pytest.fixture
def collector() -> NvidiaCollector:
    """Give a started collector, or skip when there is no NVIDIA GPU."""
    instance = NvidiaCollector()
    specs = instance.discover()
    if not specs:
        instance.close()
        pytest.skip("no NVIDIA GPU, or NVML did not start")
    yield instance
    instance.close()


def test_discover_finds_the_gpu(collector: NvidiaCollector) -> None:
    specs = collector.discover()
    assert len(specs) > 0
    assert all(spec.group is Group.GPU for spec in specs)


def test_every_sensor_is_keyed_by_the_pci_bus_id_not_by_the_nvml_index(collector: NvidiaCollector) -> None:
    # ADR 0002: the key must survive a reboot. The NVML index does not.
    for spec in collector.discover():
        assert spec.id.source == "nvidia"
        assert ":" in spec.id.device
        assert not spec.id.device.startswith("gpu0")


def test_the_temperature_channel_reads_a_realistic_value(collector: NvidiaCollector) -> None:
    collector.discover()
    reading = _reading_named(collector, "temperature")
    assert reading.is_ok
    assert 10.0 < reading.value < 110.0


def test_the_power_channel_reads_a_realistic_value(collector: NvidiaCollector) -> None:
    collector.discover()
    reading = _reading_named(collector, "power")
    assert reading.is_ok
    assert 0.0 < reading.value < 600.0


def test_the_power_limit_is_the_480_watt_limit_of_this_card(collector: NvidiaCollector) -> None:
    spec = _spec_named(collector, "power")
    assert spec.high == 480.0


def test_memory_used_comes_from_the_version_2_structure(collector: NvidiaCollector) -> None:
    # ADR 0003 rule 1. The version 1 structure counts about 500 MiB of
    # driver-reserved memory and disagrees with every other tool.
    #
    # The expected total changed on 2026-09-21 from 24564.0 to 24564 MiB in
    # bytes. The first version of this test assumed the channel reported
    # mebibytes, which contradicted its own BYTE unit. The unit was right and
    # the collector was wrong. See `test_memory_is_reported_in_bytes...`.
    collector.discover()
    used = _reading_named(collector, "memory_used").value
    reserved = _reading_named(collector, "memory_reserved").value
    total = _spec_named(collector, "memory_used").high
    assert used is not None
    assert reserved is not None
    assert total == 24564 * 1024**2
    assert used < total


def test_the_temperature_thresholds_are_not_swapped(collector: NvidiaCollector) -> None:
    # ADR 0003 rule 2. In NVML, SHUTDOWN = 0 and SLOWDOWN = 1, so a naive read
    # reports a slowdown limit above the shutdown limit.
    spec = _spec_named(collector, "temperature")
    assert spec.warn is not None
    assert spec.critical is not None
    assert spec.warn < spec.critical


def test_the_units_are_correct(collector: NvidiaCollector) -> None:
    by_channel = {spec.id.channel: spec for spec in collector.discover()}
    assert by_channel["temperature"].unit is Unit.CELSIUS
    assert by_channel["power"].unit is Unit.WATT
    assert by_channel["fan_speed"].unit is Unit.PERCENT
    assert by_channel["clock_sm"].unit is Unit.HERTZ
    assert by_channel["memory_used"].unit is Unit.BYTE


def test_clocks_are_reported_in_hertz_not_megahertz(collector: NvidiaCollector) -> None:
    # Every collector converts to the base display unit. See docs/architecture.md.
    collector.discover()
    value = _reading_named(collector, "clock_sm").value
    assert value is not None
    assert value > 1_000_000


def test_read_gives_one_reading_for_every_spec(collector: NvidiaCollector) -> None:
    specs = collector.discover()
    readings = collector.read()
    assert {reading.id for reading in readings} == {spec.id for spec in specs}


def test_read_never_raises_after_the_collector_is_closed(collector: NvidiaCollector) -> None:
    collector.discover()
    collector.close()
    readings = collector.read()
    assert all(not reading.is_ok for reading in readings)
    assert all(reading.error is not None for reading in readings)


def test_a_collector_that_cannot_start_reports_nothing_and_does_not_raise() -> None:
    # Rule 3 of the collector contract.
    broken = NvidiaCollector(library_name="libnvidia-ml-does-not-exist.so")
    assert broken.discover() == []
    assert broken.read() == []
    broken.close()


def _spec_named(collector: NvidiaCollector, channel: str):  # noqa: ANN202
    """Return the spec of one channel."""
    return next(spec for spec in collector.discover() if spec.id.channel == channel)


def _reading_named(collector: NvidiaCollector, channel: str):  # noqa: ANN202
    """Return the reading of one channel."""
    return next(reading for reading in collector.read() if reading.id.channel == channel)


def test_the_expensive_pcie_channels_get_a_long_read_interval(collector: NvidiaCollector) -> None:
    # Measured: nvmlDeviceGetPcieThroughput costs 20.6 ms per call, because
    # NVML samples over a window. Two of them took 92 % of a pass.
    for channel in ("pcie_tx", "pcie_rx"):
        assert _spec_named(collector, channel).min_interval >= 2.0


def test_the_energy_and_fan_channels_get_a_short_read_interval(collector: NvidiaCollector) -> None:
    # Measured: energy 3.0 ms, fan speed 0.58 ms.
    assert _spec_named(collector, "energy").min_interval >= 1.0
    assert _spec_named(collector, "fan_speed").min_interval >= 1.0


def test_the_cheap_channels_are_read_on_every_pass(collector: NvidiaCollector) -> None:
    for channel in ("temperature", "power", "clock_sm", "utilization"):
        assert _spec_named(collector, channel).min_interval == 0.0


def test_memory_is_reported_in_bytes_not_in_mebibytes(collector: NvidiaCollector) -> None:
    # The unit of the channel is BYTE, so the value must be a byte count.
    # 24564 MiB of VRAM is about 2.6e10 bytes.
    collector.discover()
    total = _spec_named(collector, "memory_used").high
    assert total is not None
    assert total > 2.5e10
    used = _reading_named(collector, "memory_used").value
    assert used is not None
    assert used > 1e8


def test_a_warmed_pass_costs_less_than_five_milliseconds(collector: NvidiaCollector) -> None:
    import statistics
    import time

    collector.discover()
    collector.read()  # warm the cache, which pays the expensive reads once

    timings = []
    for _ in range(10):
        start = time.perf_counter()
        collector.read()
        timings.append((time.perf_counter() - start) * 1000)
    assert statistics.median(timings) < 5.0


# --- Per-fan channels, exp-0013 -------------------------------------------
#
# Gova's specification, 2026-09-22: give an RPM channel and a percent channel
# for each fan, and keep the original single `fan_speed` channel.
#
# Expected values on this card, measured in
# `lab/exp-0013-rtx4090-board-sensors/results/tlimit-under-load.csv`:
#   fan 0   0 RPM when stopped, 1203 RPM under a light load
#   fan 1   0 RPM when stopped, 1513 RPM under the same load


def test_the_card_reports_two_fans(collector: NvidiaCollector) -> None:
    # The MSI RTX 4090 SUPRIM has three fans on the shroud, and NVML groups
    # them into two controlled channels. docs/physical-build.md.
    channels = {spec.id.channel for spec in collector.discover()}
    assert "fan0_rpm" in channels
    assert "fan1_rpm" in channels


def test_each_fan_gets_an_rpm_channel_and_a_percent_channel(collector: NvidiaCollector) -> None:
    by_channel = {spec.id.channel: spec for spec in collector.discover()}
    for index in (0, 1):
        assert by_channel[f"fan{index}_rpm"].unit is Unit.RPM
        assert by_channel[f"fan{index}_percent"].unit is Unit.PERCENT
        assert by_channel[f"fan{index}_percent"].low == 0.0
        assert by_channel[f"fan{index}_percent"].high == 100.0


def test_the_single_fan_speed_channel_stays(collector: NvidiaCollector) -> None:
    # Gova asked for the original channel to be kept beside the new ones.
    assert _spec_named(collector, "fan_speed").unit is Unit.PERCENT


def test_the_fan_rpm_channels_read_a_speed_a_fan_can_turn_at(collector: NvidiaCollector) -> None:
    collector.discover()
    for index in (0, 1):
        reading = _reading_named(collector, f"fan{index}_rpm")
        assert reading.is_ok
        assert reading.value is not None
        assert reading.value == 0.0 or 300.0 <= reading.value <= 4000.0


def test_the_fan_rpm_channel_has_no_false_upper_limit(collector: NvidiaCollector) -> None:
    # A fan bar needs a real scale. NVML gives no maximum RPM, so the spec
    # must not invent one. Same rule as the board fans.
    for index in (0, 1):
        assert _spec_named(collector, f"fan{index}_rpm").high is None


def test_the_per_fan_channels_get_a_read_interval(collector: NvidiaCollector) -> None:
    # Measured in exp-0013; the original fan_speed call costs 0.58 ms.
    for index in (0, 1):
        assert _spec_named(collector, f"fan{index}_rpm").min_interval >= 1.0
        assert _spec_named(collector, f"fan{index}_percent").min_interval >= 1.0
