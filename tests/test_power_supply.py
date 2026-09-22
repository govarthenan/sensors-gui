"""Tests for the power supply collector.

No mocks. A real directory tree, shaped like `/sys/class/power_supply` on
`dst-gova-pc`, is built under `tmp_path` for every test. The values come from
a real read of `/sys/class/power_supply/hidpp_battery_0/` on this machine on
2026-09-22 (see `docs/hardware-inventory.md`, section "Peripherals").

The node name is deliberately NOT what these tests key on: it was
`hidpp_battery_2`, then `_3`, then `_0` across three reboots with no hardware
change, which is exactly why ADR 0002 is applied here too.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from sensors_gui.collectors.power_supply import PowerSupplyCollector
from sensors_gui.model import Group, Unit


class FakeClock:
    """A clock the test moves by hand, not `time.monotonic`."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        """Return the current fake time in seconds."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the fake time forward."""
        self.now += seconds


MOUSE_FILES: dict[str, str] = {
    "capacity_level": "Full",
    "manufacturer": "Logitech",
    "model_name": "G305 Lightspeed Wireless Gaming Mouse",
    "online": "1",
    "scope": "Device",
    "serial_number": "f4-73-bc-80",
    "status": "Discharging",
    "type": "Battery",
}


def _build_node(root: Path, node_name: str, files: dict[str, str]) -> Path:
    """Build one `/sys/class/power_supply/<node_name>/` directory with the given files."""
    node_dir = root / node_name
    node_dir.mkdir(parents=True)
    for name, contents in files.items():
        (node_dir / name).write_text(contents + "\n")
    return node_dir


def _root_with(tmp_path: Path, node_name: str, files: dict[str, str]) -> Path:
    """Build a `power_supply` root holding one node."""
    root = tmp_path / "power_supply"
    root.mkdir(parents=True)
    _build_node(root, node_name, files)
    return root


def _battery_reading(collector: PowerSupplyCollector) -> float | None:
    """Discover and read, and return the value of the `capacity` channel."""
    specs = {spec.id: spec for spec in collector.discover()}
    for reading in collector.read():
        if specs[reading.id].label == "Battery":
            return reading.value
    raise AssertionError("no Battery channel was discovered")


# --- discovery ---------------------------------------------------------------


def test_discover_finds_a_battery_channel_for_the_mouse(tmp_path: Path) -> None:
    root = _root_with(tmp_path, "hidpp_battery_0", MOUSE_FILES)
    collector = PowerSupplyCollector(root=root)
    specs = collector.discover()
    assert any(spec.label == "Battery" for spec in specs)


def test_the_battery_channel_is_a_percent_in_the_peripheral_group(tmp_path: Path) -> None:
    root = _root_with(tmp_path, "hidpp_battery_0", MOUSE_FILES)
    collector = PowerSupplyCollector(root=root)
    battery = next(spec for spec in collector.discover() if spec.label == "Battery")
    assert battery.unit is Unit.PERCENT
    assert battery.group is Group.PERIPHERAL


def test_discover_finds_an_online_channel(tmp_path: Path) -> None:
    root = _root_with(tmp_path, "hidpp_battery_0", MOUSE_FILES)
    collector = PowerSupplyCollector(root=root)
    specs = collector.discover()
    assert any(spec.label == "Online" for spec in specs)


def test_the_battery_channel_has_the_sixty_second_interval(tmp_path: Path) -> None:
    root = _root_with(tmp_path, "hidpp_battery_0", MOUSE_FILES)
    collector = PowerSupplyCollector(root=root)
    battery = next(spec for spec in collector.discover() if spec.label == "Battery")
    assert battery.min_interval == 60.0


def test_discover_on_a_missing_root_returns_nothing_and_does_not_raise(tmp_path: Path) -> None:
    collector = PowerSupplyCollector(root=tmp_path / "does-not-exist")
    assert collector.discover() == []
    assert collector.read() == []


def test_the_collector_name_is_power_supply(tmp_path: Path) -> None:
    collector = PowerSupplyCollector(root=tmp_path)
    assert collector.name == "power_supply"


# --- ADR 0002 applied: keyed by model_name and serial_number, not the node ---


def test_the_sensor_id_does_not_contain_the_node_name(tmp_path: Path) -> None:
    root = _root_with(tmp_path, "hidpp_battery_2", MOUSE_FILES)
    collector = PowerSupplyCollector(root=root)
    battery = next(spec for spec in collector.discover() if spec.label == "Battery")
    assert "hidpp_battery_2" not in battery.id.device
    assert "G305 Lightspeed Wireless Gaming Mouse" in battery.id.device
    assert "f4-73-bc-80" in battery.id.device


def test_the_same_device_keeps_the_same_id_across_different_node_names(tmp_path: Path) -> None:
    # The real-world sequence was hidpp_battery_2 -> _3 -> _0, with no hardware
    # change. The id must be identical every time.
    first_root = _root_with(tmp_path / "boot-1", "hidpp_battery_2", MOUSE_FILES)
    second_root = _root_with(tmp_path / "boot-2", "hidpp_battery_3", MOUSE_FILES)

    first_id = next(spec for spec in PowerSupplyCollector(root=first_root).discover() if spec.label == "Battery").id
    second_id = next(spec for spec in PowerSupplyCollector(root=second_root).discover() if spec.label == "Battery").id
    assert first_id == second_id


def test_a_device_with_no_model_name_falls_back_to_the_node_name_and_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    files = {key: value for key, value in MOUSE_FILES.items() if key != "model_name"}
    root = _root_with(tmp_path, "some_battery_7", files)
    with caplog.at_level(logging.WARNING, logger="sensors_gui.collectors.power_supply"):
        collector = PowerSupplyCollector(root=root)
        battery = next(spec for spec in collector.discover() if spec.label == "Battery")
    assert "some_battery_7" in battery.id.device
    assert caplog.text  # the instability was logged


# --- capacity_level is text, mapped to a number, and kept as text -----------


@pytest.mark.parametrize(
    ("level", "expected_percent"),
    [
        ("Critical", 5.0),
        ("Low", 20.0),
        ("Normal", 55.0),
        ("High", 85.0),
        ("Full", 100.0),
    ],
)
def test_capacity_level_text_is_mapped_to_a_number(tmp_path: Path, level: str, expected_percent: float) -> None:
    files = dict(MOUSE_FILES, capacity_level=level)
    root = _root_with(tmp_path, "hidpp_battery_0", files)
    collector = PowerSupplyCollector(root=root)
    assert _battery_reading(collector) == expected_percent


def test_the_raw_capacity_level_text_is_still_available(tmp_path: Path) -> None:
    root = _root_with(tmp_path, "hidpp_battery_0", MOUSE_FILES)
    collector = PowerSupplyCollector(root=root)
    battery = next(spec for spec in collector.discover() if spec.label == "Battery")
    collector.read()
    assert collector.capacity_level_text(battery.id) == "Full"


def test_an_unrecognised_capacity_level_text_gives_a_failed_reading_not_a_crash(tmp_path: Path) -> None:
    files = dict(MOUSE_FILES, capacity_level="Unknown")
    root = _root_with(tmp_path, "hidpp_battery_0", files)
    collector = PowerSupplyCollector(root=root)
    specs = {spec.id: spec for spec in collector.discover()}
    battery_reading = next(r for r in collector.read() if specs[r.id].label == "Battery")
    assert not battery_reading.is_ok
    assert battery_reading.error is not None


def test_a_real_capacity_percent_is_preferred_over_capacity_level(tmp_path: Path) -> None:
    files = dict(MOUSE_FILES, capacity_level="Low", capacity="72")
    root = _root_with(tmp_path, "hidpp_battery_0", files)
    collector = PowerSupplyCollector(root=root)
    assert _battery_reading(collector) == 72.0


# --- online ------------------------------------------------------------------


def test_online_reads_as_one_when_connected(tmp_path: Path) -> None:
    root = _root_with(tmp_path, "hidpp_battery_0", MOUSE_FILES)
    collector = PowerSupplyCollector(root=root)
    specs = {spec.id: spec for spec in collector.discover()}
    online = next(r for r in collector.read() if specs[r.id].label == "Online")
    assert online.value == 1.0


def test_online_reads_as_zero_when_disconnected(tmp_path: Path) -> None:
    files = dict(MOUSE_FILES, online="0")
    root = _root_with(tmp_path, "hidpp_battery_0", files)
    collector = PowerSupplyCollector(root=root)
    specs = {spec.id: spec for spec in collector.discover()}
    online = next(r for r in collector.read() if specs[r.id].label == "Online")
    assert online.value == 0.0


# --- read() never raises ------------------------------------------------------


def test_read_reports_an_error_instead_of_raising_on_garbage_content(tmp_path: Path) -> None:
    files = dict(MOUSE_FILES, capacity="not-a-number")
    del files["capacity_level"]
    root = _root_with(tmp_path, "hidpp_battery_0", files)
    collector = PowerSupplyCollector(root=root)
    specs = {spec.id: spec for spec in collector.discover()}
    battery_reading = next(r for r in collector.read() if specs[r.id].label == "Battery")
    assert not battery_reading.is_ok


def test_read_reports_an_error_instead_of_raising_when_a_file_disappears(tmp_path: Path) -> None:
    root = _root_with(tmp_path, "hidpp_battery_0", MOUSE_FILES)
    collector = PowerSupplyCollector(root=root)
    collector.discover()
    (root / "hidpp_battery_0" / "capacity_level").unlink()
    readings = collector.read()
    assert all(reading is not None for reading in readings)  # this alone must not raise


def test_read_on_a_freshly_constructed_collector_with_no_discover_returns_nothing(tmp_path: Path) -> None:
    collector = PowerSupplyCollector(root=tmp_path)
    assert collector.read() == []


# --- the 60 second interval is honoured, with a fake clock -------------------


def test_the_value_is_cached_within_the_sixty_second_interval(tmp_path: Path) -> None:
    clock = FakeClock()
    root = _root_with(tmp_path, "hidpp_battery_0", MOUSE_FILES)
    collector = PowerSupplyCollector(root=root, clock=clock)
    assert _battery_reading(collector) == 100.0

    (root / "hidpp_battery_0" / "capacity_level").write_text("Critical\n")
    clock.advance(30.0)
    assert _battery_reading(collector) == 100.0  # still cached


def test_the_value_is_refreshed_after_the_sixty_second_interval(tmp_path: Path) -> None:
    clock = FakeClock()
    root = _root_with(tmp_path, "hidpp_battery_0", MOUSE_FILES)
    collector = PowerSupplyCollector(root=root, clock=clock)
    assert _battery_reading(collector) == 100.0

    (root / "hidpp_battery_0" / "capacity_level").write_text("Critical\n")
    clock.advance(60.1)
    assert _battery_reading(collector) == 5.0


# --- close() ------------------------------------------------------------------


def test_close_does_not_raise_and_clears_the_channels(tmp_path: Path) -> None:
    root = _root_with(tmp_path, "hidpp_battery_0", MOUSE_FILES)
    collector = PowerSupplyCollector(root=root)
    collector.discover()
    collector.close()
    assert collector.read() == []
