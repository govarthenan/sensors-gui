"""Tests for value formatting.

A raw sensor value is in the base unit: hertz, byte, watt. A human does not
read `210000000 Hz`. The formatter must give `210 MHz`.

Rules agreed for this project:
  - Hertz, byte per second, watt, joule and ampere take an SI prefix.
  - A byte count takes a binary prefix (KiB, MiB, GiB), because that is what
    every other tool on this machine shows for memory.
  - Degrees Celsius, volt, percent, RPM and a plain count never take a prefix.
"""

from __future__ import annotations

import pytest

from sensors_gui.model import Group, SensorId, SensorSpec, Unit


def _spec(unit: Unit) -> SensorSpec:
    """Build a throwaway spec with the given unit."""
    return SensorSpec(
        id=SensorId(source="test", device="test@/sys/x", channel="c1"),
        label="test",
        group=Group.OTHER,
        unit=unit,
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (210_000_000.0, "210.0 MHz"),
        (3_165_000_000.0, "3.2 GHz"),
        (405_000_000.0, "405.0 MHz"),
        (600_000_000.0, "600.0 MHz"),
        (0.0, "0.0 Hz"),
    ],
)
def test_hertz_takes_an_si_prefix(value: float, expected: str) -> None:
    assert _spec(Unit.HERTZ).format(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1_179_648_000.0, "1.1 GiB"),
        (25_757_220_864.0, "24.0 GiB"),
        (528_482_304.0, "504.0 MiB"),
        (1024.0, "1.0 KiB"),
        (512.0, "512.0 B"),
    ],
)
def test_bytes_take_a_binary_prefix(value: float, expected: str) -> None:
    assert _spec(Unit.BYTE).format(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (38_916_000.0, "38.9 MB/s"),
        (634_000.0, "634.0 kB/s"),
        (0.0, "0.0 B/s"),
    ],
)
def test_byte_per_second_takes_a_decimal_si_prefix(value: float, expected: str) -> None:
    # A transfer rate is a decimal quantity. Every network tool shows it that way.
    assert _spec(Unit.BYTE_PER_SECOND).format(value) == expected


def test_joules_take_an_si_prefix_because_the_gpu_counter_is_large() -> None:
    assert _spec(Unit.JOULE).format(482_665.5) == "482.7 kJ"


@pytest.mark.parametrize(
    ("unit", "value", "expected"),
    [
        (Unit.CELSIUS, 41.0, "41.0 °C"),
        (Unit.CELSIUS, 104.0, "104.0 °C"),
        (Unit.VOLT, 1.305, "1.305 V"),
        (Unit.PERCENT, 100.0, "100 %"),
        (Unit.RPM, 1450.0, "1450 RPM"),
        (Unit.COUNT, 8.0, "8"),
        (Unit.WATT, 38.26, "38.26 W"),
    ],
)
def test_a_unit_with_no_prefix_is_unchanged(unit: Unit, value: float, expected: str) -> None:
    assert _spec(unit).format(value) == expected


def test_watts_take_a_prefix_only_when_the_number_is_large() -> None:
    # A GPU draws 480 W, never 0.48 kW. The prefix must not appear too early.
    assert _spec(Unit.WATT).format(480.0) == "480.00 W"


def test_a_missing_value_is_an_em_dash_whatever_the_unit() -> None:
    for unit in (Unit.HERTZ, Unit.BYTE, Unit.CELSIUS, Unit.BYTE_PER_SECOND):
        assert _spec(unit).format(None) == "—"


def test_a_negative_value_keeps_its_sign() -> None:
    assert _spec(Unit.CELSIUS).format(-7.0) == "-7.0 °C"
