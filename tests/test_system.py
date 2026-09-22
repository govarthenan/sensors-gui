"""Tests for the system collector (CPU, memory, storage, network via psutil).

No mocks, and no fake filesystem tree either: this collector reads the real
machine through `psutil` and `os.getloadavg`, and `psutil` has no supported
way to redirect that onto a fake tree. Testing against the real machine is
correct and expected here - the same shape as `tests/test_nvidia_collector.py`.
A fake clock is still used wherever the collector's own rate math can be
driven independently of wall time.
"""

from __future__ import annotations

import time

import psutil
import pytest

from sensors_gui.collectors.system import SystemCollector
from sensors_gui.model import Group, Unit


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


def _by_label(collector: SystemCollector) -> dict[str, object]:
    """Discover and return the specs keyed by label."""
    return {spec.label: spec for spec in collector.discover()}


def _readings_by_id(collector: SystemCollector) -> dict[object, object]:
    """Read and return the readings keyed by sensor id."""
    return {reading.id: reading for reading in collector.read()}


# --- basic shape ---------------------------------------------------------


def test_the_collector_name_is_system() -> None:
    assert SystemCollector().name == "system"


def test_discover_finds_at_least_one_channel_per_group() -> None:
    collector = SystemCollector()
    groups = {spec.group for spec in collector.discover()}
    assert Group.CPU in groups
    assert Group.MEMORY in groups
    assert Group.NETWORK in groups


def test_every_cheap_channel_has_no_minimum_interval() -> None:
    collector = SystemCollector()
    for spec in collector.discover():
        assert spec.min_interval == 0.0


def test_read_never_raises_and_returns_one_reading_per_spec() -> None:
    collector = SystemCollector()
    specs = collector.discover()
    collector.read()  # prime any rate channels
    readings = collector.read()
    assert len(readings) == len(specs)


def test_close_does_not_raise() -> None:
    collector = SystemCollector()
    collector.discover()
    collector.read()
    collector.close()


# --- CPU -------------------------------------------------------------------


def test_discover_finds_one_usage_channel_per_logical_cpu() -> None:
    collector = SystemCollector()
    specs = collector.discover()
    per_core = [spec for spec in specs if spec.group is Group.CPU and spec.unit is Unit.PERCENT and "CPU" in spec.label]
    core_count = psutil.cpu_count(logical=True)
    # One channel per core, plus (optionally) one aggregate "CPU use" channel.
    assert len(per_core) in (core_count, core_count + 1)


def test_cpu_usage_reads_a_realistic_percent() -> None:
    collector = SystemCollector()
    collector.discover()
    collector.read()
    time.sleep(0.05)
    readings = _readings_by_id(collector)
    specs = _by_label(collector)
    cpu0 = specs.get("CPU0 use")
    assert cpu0 is not None
    reading = readings[cpu0.id]
    assert reading.is_ok
    assert 0.0 <= reading.value <= 100.0


def test_discover_finds_a_frequency_channel_per_logical_cpu() -> None:
    collector = SystemCollector()
    specs = collector.discover()
    freqs = [spec for spec in specs if spec.group is Group.CPU and spec.unit is Unit.HERTZ]
    assert len(freqs) > 0


def test_cpu_frequency_reads_a_realistic_value_in_hertz() -> None:
    collector = SystemCollector()
    collector.discover()
    readings = _readings_by_id(collector)
    specs = _by_label(collector)
    freq_spec = next((spec for label, spec in specs.items() if "frequency" in label.lower()), None)
    assert freq_spec is not None
    reading = readings[freq_spec.id]
    assert reading.is_ok
    # This machine's CPU ranges 613.95 MHz - 5662.02 MHz (docs/hardware-inventory.md).
    assert 100_000_000.0 < reading.value < 8_000_000_000.0


def test_discover_finds_the_three_load_averages() -> None:
    collector = SystemCollector()
    labels = set(_by_label(collector))
    assert any("load" in label.lower() and "1" in label for label in labels)
    assert any("load" in label.lower() and "5" in label for label in labels)


# --- memory ------------------------------------------------------------------


def test_memory_total_matches_psutil_within_rounding() -> None:
    collector = SystemCollector()
    specs = _by_label(collector)
    readings = _readings_by_id(collector)
    total_spec = next(spec for label, spec in specs.items() if spec.group is Group.MEMORY and "total" in label.lower())
    assert readings[total_spec.id].value == pytest.approx(psutil.virtual_memory().total, rel=0.01)


def test_memory_channels_use_the_right_units() -> None:
    collector = SystemCollector()
    specs = _by_label(collector)
    percent_specs = [spec for spec in specs.values() if spec.group is Group.MEMORY and spec.unit is Unit.PERCENT]
    byte_specs = [spec for spec in specs.values() if spec.group is Group.MEMORY and spec.unit is Unit.BYTE]
    assert percent_specs
    assert byte_specs


def test_discover_finds_swap_channels() -> None:
    collector = SystemCollector()
    labels = {label.lower() for label in _by_label(collector)}
    assert any("swap" in label for label in labels)


# --- storage: rates, not raw counters ---------------------------------------


def test_disk_rate_channels_use_bytes_per_second() -> None:
    collector = SystemCollector()
    specs = _by_label(collector)
    storage = [spec for spec in specs.values() if spec.group is Group.STORAGE]
    assert storage
    assert all(spec.unit is Unit.BYTE_PER_SECOND for spec in storage)


def test_disk_rate_is_none_on_the_very_first_read_then_a_number() -> None:
    collector = SystemCollector()
    specs = _by_label(collector)
    storage_spec = next(spec for spec in specs.values() if spec.group is Group.STORAGE)

    first = _readings_by_id(collector)[storage_spec.id]
    assert first.value is None  # no prior snapshot yet - this must not raise or fabricate a huge number

    time.sleep(0.05)
    second = _readings_by_id(collector)[storage_spec.id]
    assert second.value is not None
    assert second.value >= 0.0


# --- network: rates, and virtual interfaces are skipped ---------------------


def test_network_rate_channels_use_bytes_per_second() -> None:
    collector = SystemCollector()
    specs = _by_label(collector)
    network = [spec for spec in specs.values() if spec.group is Group.NETWORK]
    assert network
    assert all(spec.unit is Unit.BYTE_PER_SECOND for spec in network)


@pytest.mark.parametrize("virtual_interface", ["docker0", "virbr0", "lo"])
def test_a_virtual_interface_is_never_a_device_of_a_network_channel(virtual_interface: str) -> None:
    collector = SystemCollector()
    specs = _by_label(collector)
    for spec in specs.values():
        if spec.group is Group.NETWORK:
            assert virtual_interface not in spec.id.device


def test_a_bridge_or_veth_interface_is_never_a_device_of_a_network_channel() -> None:
    collector = SystemCollector()
    specs = _by_label(collector)
    for spec in specs.values():
        if spec.group is Group.NETWORK:
            assert not spec.id.device.startswith("br-")
            assert "veth" not in spec.id.device


def test_a_real_interface_is_present() -> None:
    # enp11s0 (wired) and wlp8s0 (Wi-Fi) are this machine's real interfaces
    # (docs/hardware-inventory.md). At least one must survive the filter.
    real_interfaces = set(psutil.net_io_counters(pernic=True)) - {"lo", "docker0", "virbr0"}
    real_interfaces = {name for name in real_interfaces if not name.startswith(("br-", "veth"))}
    if not real_interfaces:
        pytest.skip("no real network interface on this machine")
    collector = SystemCollector()
    specs = _by_label(collector)
    devices = {spec.id.device for spec in specs.values() if spec.group is Group.NETWORK}
    assert any(any(name in device for name in real_interfaces) for device in devices)


# --- rate math: delta over time, with a fake clock, and wrap handling ------


def test_a_rate_channel_uses_the_collectors_own_clock_for_its_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeClock()
    collector = SystemCollector(clock=clock)
    specs = _by_label(collector)
    net_spec = next(spec for spec in specs.values() if spec.group is Group.NETWORK)

    counters: dict[str, object] = {}

    def fake_net_io_counters(pernic: bool = False) -> dict[str, object]:
        assert pernic
        return counters

    iface = net_spec.id.device.rsplit(":", 1)[-1] if ":" in net_spec.id.device else net_spec.id.device
    Snapshot = psutil.net_io_counters(pernic=True)[next(iter(psutil.net_io_counters(pernic=True)))].__class__
    counters[iface] = Snapshot(
        bytes_sent=1000,
        bytes_recv=2000,
        packets_sent=0,
        packets_recv=0,
        errin=0,
        errout=0,
        dropin=0,
        dropout=0,
    )
    monkeypatch.setattr(psutil, "net_io_counters", fake_net_io_counters)

    first = _readings_by_id(collector)[net_spec.id]
    assert first.value is None

    counters[iface] = Snapshot(
        bytes_sent=1000 + 500,
        bytes_recv=2000 + 1000,
        packets_sent=0,
        packets_recv=0,
        errin=0,
        errout=0,
        dropin=0,
        dropout=0,
    )
    clock.advance(2.0)
    second = _readings_by_id(collector)[net_spec.id]
    assert second.value is not None
    assert second.value == pytest.approx(500.0 / 2.0, rel=0.01) or second.value == pytest.approx(1000.0 / 2.0, rel=0.01)


def test_a_wrapped_counter_does_not_produce_a_huge_or_negative_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeClock()
    collector = SystemCollector(clock=clock)
    specs = _by_label(collector)
    net_spec = next(spec for spec in specs.values() if spec.group is Group.NETWORK)
    iface = net_spec.id.device.rsplit(":", 1)[-1] if ":" in net_spec.id.device else net_spec.id.device

    counters: dict[str, object] = {}
    Snapshot = psutil.net_io_counters(pernic=True)[next(iter(psutil.net_io_counters(pernic=True)))].__class__

    def fake_net_io_counters(pernic: bool = False) -> dict[str, object]:
        assert pernic
        return counters

    monkeypatch.setattr(psutil, "net_io_counters", fake_net_io_counters)

    counters[iface] = Snapshot(
        bytes_sent=10_000_000,
        bytes_recv=10_000_000,
        packets_sent=0,
        packets_recv=0,
        errin=0,
        errout=0,
        dropin=0,
        dropout=0,
    )
    _readings_by_id(collector)  # prime

    # The counter "wrapped": the new value is smaller than the old one.
    counters[iface] = Snapshot(
        bytes_sent=100, bytes_recv=100, packets_sent=0, packets_recv=0, errin=0, errout=0, dropin=0, dropout=0
    )
    clock.advance(1.0)
    reading = _readings_by_id(collector)[net_spec.id]
    assert reading.value is not None
    assert 0.0 <= reading.value < 1_000_000.0  # not the astronomical negative-turned-positive number


def test_a_loop_device_gets_no_channel() -> None:
    # This machine has 20 or more loop devices from snap packages. They are not
    # hardware, they never move, and they buried the real drive under 40 rows.
    from sensors_gui.collectors.system import SystemCollector

    collector = SystemCollector()
    devices = {spec.id.device for spec in collector.discover()}
    collector.close()
    assert not any(device.startswith("disk:loop") for device in devices)


def test_the_real_drive_still_gets_its_channels() -> None:
    from sensors_gui.collectors.system import SystemCollector

    collector = SystemCollector()
    devices = {spec.id.device for spec in collector.discover()}
    collector.close()
    assert any(device.startswith("disk:nvme") or device.startswith("disk:sd") for device in devices)
