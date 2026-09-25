"""Tests for the core model objects.

The expected values come from two sources:
  1. the kernel hwmon ABI, which fixes the raw scale factors, and
  2. `docs/hardware-inventory.md`, which records what this machine reports.
"""

from __future__ import annotations

import pytest

from sensors_gui.model import Group, Reading, Sample, SensorId, SensorSpec, Unit


def test_sensor_id_key_joins_the_three_parts_with_colons() -> None:
    sensor_id = SensorId(source="hwmon", device="k10temp@/sys/devices/pci0000:00/0000:00:18.3", channel="temp1")
    assert sensor_id.key == "hwmon:k10temp@/sys/devices/pci0000:00/0000:00:18.3:temp1"


def test_sensor_id_round_trips_through_its_key() -> None:
    sensor_id = SensorId(source="hwmon", device="k10temp@/sys/devices/pci0000:00/0000:00:18.3", channel="temp1")
    assert SensorId.from_key(sensor_id.key) == sensor_id


def test_sensor_id_from_key_rejects_a_string_with_too_few_parts() -> None:
    with pytest.raises(ValueError, match="key"):
        SensorId.from_key("hwmon:temp1")


def test_sensor_id_is_hashable_so_it_can_be_a_dictionary_key() -> None:
    first = SensorId(source="hwmon", device="nvme@/sys/x", channel="temp1")
    second = SensorId(source="hwmon", device="nvme@/sys/x", channel="temp1")
    assert {first: 1}[second] == 1


def test_two_spd5118_dimms_get_different_ids_because_their_device_paths_differ() -> None:
    dimm_a = SensorId(
        source="hwmon", device="spd5118@/sys/devices/pci0000:00/0000:00:14.0/i2c-0/0-0051", channel="temp1"
    )
    dimm_b = SensorId(
        source="hwmon", device="spd5118@/sys/devices/pci0000:00/0000:00:14.0/i2c-0/0-0053", channel="temp1"
    )
    assert dimm_a != dimm_b


def test_unit_gives_its_display_symbol() -> None:
    assert Unit.CELSIUS.symbol == "°C"
    assert Unit.WATT.symbol == "W"
    assert Unit.RPM.symbol == "RPM"
    assert Unit.PERCENT.symbol == "%"


def test_reading_ok_holds_a_value_and_no_error() -> None:
    sensor_id = SensorId(source="hwmon", device="k10temp@/sys/x", channel="temp1")
    reading = Reading.ok(sensor_id, 41.0)
    assert reading.value == 41.0
    assert reading.error is None
    assert reading.is_ok is True


def test_reading_failed_holds_an_error_and_no_value() -> None:
    sensor_id = SensorId(source="hwmon", device="k10temp@/sys/x", channel="temp1")
    reading = Reading.failed(sensor_id, "permission denied")
    assert reading.value is None
    assert reading.error == "permission denied"
    assert reading.is_ok is False


def test_sample_finds_a_reading_by_its_sensor_id() -> None:
    sensor_id = SensorId(source="hwmon", device="k10temp@/sys/x", channel="temp1")
    sample = Sample(timestamp=1.0, readings=[Reading.ok(sensor_id, 41.0)])
    assert sample.value_of(sensor_id) == 41.0


def test_sample_returns_none_for_a_sensor_it_does_not_hold() -> None:
    present = SensorId(source="hwmon", device="k10temp@/sys/x", channel="temp1")
    absent = SensorId(source="hwmon", device="k10temp@/sys/x", channel="temp3")
    sample = Sample(timestamp=1.0, readings=[Reading.ok(present, 41.0)])
    assert sample.value_of(absent) is None


def test_sensor_spec_formats_a_value_with_its_unit() -> None:
    spec = SensorSpec(
        id=SensorId(source="hwmon", device="k10temp@/sys/x", channel="temp1"),
        label="CPU Tctl",
        group=Group.CPU,
        unit=Unit.CELSIUS,
    )
    assert spec.format(41.0) == "41.0 °C"


def test_sensor_spec_formats_a_missing_value_as_a_dash() -> None:
    spec = SensorSpec(
        id=SensorId(source="hwmon", device="k10temp@/sys/x", channel="temp1"),
        label="CPU Tctl",
        group=Group.CPU,
        unit=Unit.CELSIUS,
    )
    assert spec.format(None) == "—"


def test_sensor_spec_uses_more_decimals_for_volts_than_for_degrees() -> None:
    volt_spec = SensorSpec(
        id=SensorId(source="hwmon", device="amdgpu@/sys/x", channel="in0"),
        label="vddgfx",
        group=Group.GPU,
        unit=Unit.VOLT,
    )
    assert volt_spec.format(1.305) == "1.305 V"


def test_per_second_unit_scales_on_the_decimal_step_with_the_symbol_per_second() -> None:
    """Page faults each second, 2026-09-25: 12 400 of them read as 12.4 k/s."""
    spec = SensorSpec(
        id=SensorId(source="proc", device="vmstat", channel="pgfault_rate"),
        label="Page faults",
        group=Group.MEMORY,
        unit=Unit.PER_SECOND,
    )
    assert Unit.PER_SECOND.symbol == "/s"
    assert spec.format(12400.0) == "12.4 k/s"
    assert spec.format(3.0) == "3.0 /s"


def test_spec_decimals_override_the_unit_for_one_channel() -> None:
    """Memory pressure, 2026-09-25: the kernel gives two decimals, and 0.40 % must not read as 0 %."""
    spec = SensorSpec(
        id=SensorId(source="proc", device="pressure/memory", channel="some_avg10"),
        label="Memory pressure, some, 10 s",
        group=Group.MEMORY,
        unit=Unit.PERCENT,
        decimals=2,
    )
    assert spec.format(0.4) == "0.40 %"


def test_spec_without_decimals_keeps_the_decimals_of_its_unit() -> None:
    spec = SensorSpec(
        id=SensorId(source="system", device="memory", channel="percent"),
        label="Memory use",
        group=Group.MEMORY,
        unit=Unit.PERCENT,
    )
    assert spec.decimals is None
    assert spec.format(33.4) == "33 %"
