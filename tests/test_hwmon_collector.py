"""Tests for the hwmon collector.

Expected values come from the kernel hwmon ABI scale factors and from this
machine's recorded readings (`lab/exp-0001-hwmon-sweep/`).
"""

from __future__ import annotations

from pathlib import Path

from sensors_gui.collectors.hwmon import HwmonCollector
from sensors_gui.model import Group, Unit


def test_discover_finds_every_device_that_has_at_least_one_channel(fake_hwmon_root: Path) -> None:
    collector = HwmonCollector(root=fake_hwmon_root)
    specs = collector.discover()
    devices = {spec.id.device.split("@", 1)[0] for spec in specs}
    assert devices == {"k10temp", "spd5118", "amdgpu", "nvme"}


def test_discover_skips_a_device_with_no_channels(fake_hwmon_root: Path) -> None:
    collector = HwmonCollector(root=fake_hwmon_root)
    specs = collector.discover()
    assert not any("hidpp" in spec.id.device for spec in specs)


def test_discover_keys_a_sensor_by_name_and_device_path_not_by_hwmon_index(fake_hwmon_root: Path) -> None:
    collector = HwmonCollector(root=fake_hwmon_root)
    specs = collector.discover()
    tctl = next(spec for spec in specs if spec.label == "Tctl")
    assert tctl.id.device == "k10temp@/sys/devices/pci0000:00/0000:00:18.3"
    assert "hwmon2" not in tctl.id.key


def test_discover_separates_the_two_dimms_by_their_i2c_address(fake_hwmon_root: Path) -> None:
    collector = HwmonCollector(root=fake_hwmon_root)
    dimms = [spec for spec in collector.discover() if spec.id.device.startswith("spd5118@")]
    assert len(dimms) == 2
    assert len({spec.id.key for spec in dimms}) == 2


def test_discover_uses_the_label_file_as_the_label_when_it_exists(fake_hwmon_root: Path) -> None:
    collector = HwmonCollector(root=fake_hwmon_root)
    labels = {spec.label for spec in collector.discover()}
    assert {"Tctl", "Tccd1", "Tccd2", "edge", "vddgfx", "PPT", "sclk", "Composite"} <= labels


def test_discover_falls_back_to_the_channel_name_when_there_is_no_label(fake_hwmon_root: Path) -> None:
    collector = HwmonCollector(root=fake_hwmon_root)
    dimm = next(spec for spec in collector.discover() if spec.id.device.endswith("0-0051"))
    assert dimm.label == "temp1"


def test_discover_assigns_the_unit_from_the_channel_kind(fake_hwmon_root: Path) -> None:
    collector = HwmonCollector(root=fake_hwmon_root)
    by_label = {spec.label: spec for spec in collector.discover()}
    assert by_label["Tctl"].unit is Unit.CELSIUS
    assert by_label["vddgfx"].unit is Unit.VOLT
    assert by_label["PPT"].unit is Unit.WATT
    assert by_label["sclk"].unit is Unit.HERTZ


def test_discover_assigns_a_group_from_the_driver_name(fake_hwmon_root: Path) -> None:
    collector = HwmonCollector(root=fake_hwmon_root)
    by_label = {spec.label: spec for spec in collector.discover()}
    assert by_label["Tctl"].group is Group.CPU
    assert by_label["edge"].group is Group.GPU
    assert by_label["Composite"].group is Group.STORAGE


def test_discover_reads_the_warn_and_critical_limits_from_max_and_crit(fake_hwmon_root: Path) -> None:
    collector = HwmonCollector(root=fake_hwmon_root)
    composite = next(spec for spec in collector.discover() if spec.label == "Composite")
    assert composite.warn == 83.85
    assert composite.critical == 87.85


def test_discover_rejects_an_absurd_limit_from_the_drive_firmware(fake_hwmon_root: Path) -> None:
    # `Sensor 1` reports max = 65261850 millidegrees, which is a placeholder.
    collector = HwmonCollector(root=fake_hwmon_root)
    sensor_one = next(spec for spec in collector.discover() if spec.label == "Sensor 1")
    assert sensor_one.warn is None


def test_read_scales_a_millidegree_value_to_degrees(fake_hwmon_root: Path) -> None:
    collector = HwmonCollector(root=fake_hwmon_root)
    collector.discover()
    values = {reading.id.channel: reading.value for reading in collector.read() if "k10temp" in reading.id.device}
    assert values["temp1"] == 41.0
    assert values["temp3"] == 33.5


def test_read_scales_millivolt_microwatt_and_hertz_correctly(fake_hwmon_root: Path) -> None:
    collector = HwmonCollector(root=fake_hwmon_root)
    specs = {spec.label: spec.id for spec in collector.discover()}
    values = {reading.id: reading.value for reading in collector.read()}
    assert values[specs["vddgfx"]] == 1.305
    assert values[specs["PPT"]] == 0.014
    assert values[specs["sclk"]] == 600000000.0


def test_read_returns_one_reading_for_each_discovered_spec(fake_hwmon_root: Path) -> None:
    collector = HwmonCollector(root=fake_hwmon_root)
    specs = collector.discover()
    assert len(collector.read()) == len(specs)


def test_read_reports_an_error_instead_of_raising_when_a_file_disappears(fake_hwmon_root: Path) -> None:
    collector = HwmonCollector(root=fake_hwmon_root)
    collector.discover()
    (fake_hwmon_root / "hwmon2" / "temp1_input").unlink()

    failed = [reading for reading in collector.read() if not reading.is_ok]
    assert len(failed) == 1
    assert failed[0].id.channel == "temp1"
    assert failed[0].error is not None


def test_read_on_an_empty_tree_returns_nothing_and_does_not_raise(tmp_path: Path) -> None:
    collector = HwmonCollector(root=tmp_path / "does-not-exist")
    assert collector.discover() == []
    assert collector.read() == []
