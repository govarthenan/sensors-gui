"""Tests for the naming layer.

No mocks. The ground-truth table is the real file at
`data/evidence/bios-ground-truth-2026-09-22/linux-vs-bios.json`, and the
"file is missing" behaviour is tested with a real temporary directory tree,
not a faked object. One test also runs against the real `nct6687` device on
this machine, and skips when it is not present.

Expected values come from `data/evidence/bios-ground-truth-2026-09-22/linux-vs-bios.json`,
`lab/exp-0007-nct6687-verification/README.md` and `docs/phase-3-plan.md`.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from sensors_gui import naming
from sensors_gui.collectors.hwmon import HwmonCollector
from sensors_gui.model import Group, SensorId, SensorSpec, Unit

NCT6687_DEVICE = "nct6687@/sys/devices/platform/nct6687.2592"


def _spec(
    source: str,
    device: str,
    channel: str,
    label: str,
    group: Group = Group.OTHER,
    unit: Unit = Unit.CELSIUS,
) -> SensorSpec:
    """Build a minimal spec, shaped like one the hwmon collector would give."""
    return SensorSpec(id=SensorId(source=source, device=device, channel=channel), label=label, group=group, unit=unit)


def _nct6687(channel: str, label: str, unit: Unit = Unit.VOLT) -> SensorSpec:
    """Build a spec for one channel of the real nct6687 device on this machine."""
    return _spec("hwmon", NCT6687_DEVICE, channel, label, group=Group.BOARD, unit=unit)


# --- friendly(): renaming from the ground-truth table -----------------------


def test_friendly_renames_dram_to_cpu_vddio() -> None:
    spec = _nct6687("in7", "DRAM")
    assert naming.friendly(spec).label == "CPU VDDIO"


def test_friendly_renames_avcc3_to_system_3_3v() -> None:
    spec = _nct6687("in11", "AVCC3")
    assert naming.friendly(spec).label == "System 3.3V"


def test_friendly_leaves_a_wrong_voltage_label_unchanged() -> None:
    spec = _nct6687("in5", "CPU 1P8")
    assert naming.friendly(spec).label == "CPU 1P8"


def test_friendly_leaves_a_correct_voltage_label_unchanged() -> None:
    spec = _nct6687("in0", "+12V")
    assert naming.friendly(spec).label == "+12V"


def test_friendly_leaves_an_unverified_voltage_label_unchanged() -> None:
    spec = _nct6687("in9", "CPU SA")
    assert naming.friendly(spec).label == "CPU SA"


# --- friendly(): DIMMs, network, board -----------------------------------


def test_friendly_names_the_dimm_at_0051_a2() -> None:
    spec = _spec(
        "hwmon",
        "spd5118@/sys/devices/pci0000:00/0000:00:14.0/i2c-0/0-0051",
        "temp1",
        "temp1",
        group=Group.MEMORY,
    )
    assert naming.friendly(spec).label == "DIMM A2"


def test_friendly_names_the_dimm_at_0053_b2() -> None:
    spec = _spec(
        "hwmon",
        "spd5118@/sys/devices/pci0000:00/0000:00:14.0/i2c-0/0-0053",
        "temp1",
        "temp1",
        group=Group.MEMORY,
    )
    assert naming.friendly(spec).label == "DIMM B2"


def test_friendly_puts_the_ethernet_phy_in_the_network_group() -> None:
    spec = _spec(
        "hwmon",
        "r8169_0_b00:00@/sys/devices/pci0000:00/.../0000:0b:00.0",
        "temp1",
        "temp1",
        group=Group.OTHER,
    )
    friendly = naming.friendly(spec)
    assert friendly.group is Group.NETWORK
    assert friendly.label == "Ethernet PHY"


def test_friendly_puts_every_nct6687_channel_in_the_board_group() -> None:
    spec = _nct6687("in0", "+12V")
    assert naming.friendly(spec).group is Group.BOARD


# --- friendly(): empty fan headers, kept visible -----------------------


@pytest.mark.parametrize("number", [2, 3, 4, 5, 6])
def test_friendly_marks_an_empty_system_fan_header(number: int) -> None:
    spec = _nct6687(f"fan{number + 2}", f"System Fan #{number}", unit=Unit.RPM)
    friendly = naming.friendly(spec)
    assert friendly.label == f"SYS_FAN{number} (empty)"


def test_friendly_does_not_touch_a_fan_header_that_is_not_empty() -> None:
    spec = _nct6687("fan1", "CPU Fan", unit=Unit.RPM)
    assert naming.friendly(spec).label == "CPU Fan"


def test_friendly_does_not_touch_system_fan_1_which_is_real() -> None:
    spec = _nct6687("fan3", "System Fan #1", unit=Unit.RPM)
    assert naming.friendly(spec).label == "System Fan #1"


# --- friendly(): the CPU temperature duplicate and the empty thermistors ---


def test_friendly_marks_the_board_cpu_temperature_as_a_duplicate_of_tctl() -> None:
    # The wording changed on 2026-09-22, from "(duplicate of k10temp Tctl)" to
    # "(same as Tctl)". The first version was 27 characters, which did not fit
    # the 24-character label column and was shown cut in half. The requirement
    # is unchanged: the label must say this channel is the same reading as
    # Tctl, so that nobody reads it as a second measurement.
    spec = _nct6687("temp1", "CPU", unit=Unit.CELSIUS)
    friendly = naming.friendly(spec)
    assert "same as" in friendly.label.lower()
    assert "Tctl" in friendly.label
    assert len(friendly.label) <= 24


@pytest.mark.parametrize("label", ["CPU Socket", "PCIe x1", "M2_1"])
def test_friendly_marks_an_unplugged_thermistor_header_as_empty(label: str) -> None:
    spec = _nct6687("temp5", label, unit=Unit.CELSIUS)
    friendly = naming.friendly(spec)
    assert friendly.label == f"{label} (empty)"


def test_friendly_does_not_touch_a_real_board_temperature() -> None:
    spec = _nct6687("temp2", "System", unit=Unit.CELSIUS)
    assert naming.friendly(spec).label == "System"


# --- friendly(): does not mutate, and leaves other sources alone -----------


def test_friendly_does_not_mutate_the_input_spec() -> None:
    spec = _nct6687("in7", "DRAM")
    naming.friendly(spec)
    assert spec.label == "DRAM"


def test_friendly_leaves_a_non_hwmon_spec_unchanged() -> None:
    spec = _spec("nvidia", "GeForce RTX 4090@0000:01:00.0", "temperature", "GPU edge", group=Group.GPU)
    friendly = naming.friendly(spec)
    assert friendly.label == "GPU edge"
    assert friendly.group is Group.GPU


def test_friendly_leaves_an_unrelated_hwmon_driver_unchanged() -> None:
    spec = _spec("hwmon", "k10temp@/sys/devices/pci0000:00/0000:00:18.3", "temp1", "Tctl", group=Group.CPU)
    friendly = naming.friendly(spec)
    assert friendly.label == "Tctl"
    assert friendly.group is Group.CPU


# --- verdict(): from the ground-truth table --------------------------------


@pytest.mark.parametrize(
    ("channel", "label", "expected"),
    [
        ("in0", "+12V", "correct"),
        ("in1", "+5V", "correct"),
        ("in3", "CPU Soc", "correct"),
        ("in4", "CPU Vcore", "correct"),
        ("in7", "DRAM", "rename"),
        ("in11", "AVCC3", "rename"),
        ("in2", "+3.3V", "wrong"),
        ("in5", "CPU 1P8", "wrong"),
        ("in6", "CPU VDDP", "wrong"),
        ("in12", "AVSB", "wrong"),
        ("in8", "Chipset", "wrong"),
        ("in13", "VBat", "wrong"),
        ("in9", "CPU SA", "unverified"),
        ("in10", "Voltage #2", "unverified"),
    ],
)
def test_verdict_of_every_nct6687_voltage(channel: str, label: str, expected: str) -> None:
    assert naming.verdict(_nct6687(channel, label)) == expected


@pytest.mark.parametrize(
    ("channel", "label"),
    [("fan1", "CPU Fan"), ("fan2", "Pump Fan"), ("fan3", "System Fan #1")],
)
def test_verdict_of_a_real_fan_is_correct(channel: str, label: str) -> None:
    spec = _nct6687(channel, label, unit=Unit.RPM)
    assert naming.verdict(spec) == "correct"


@pytest.mark.parametrize("number", [2, 3, 4, 5, 6])
def test_verdict_of_an_empty_fan_header_is_correct_not_wrong(number: int) -> None:
    # The BIOS agrees the header is empty (it prints N/A, Linux prints 0), so
    # the reading is correct. It must not be "wrong", or a naive screen would
    # hide a fan that could have stopped.
    spec = _nct6687(f"fan{number + 2}", f"System Fan #{number}", unit=Unit.RPM)
    assert naming.verdict(spec) == "correct"


def test_verdict_of_the_duplicate_board_cpu_temperature_is_wrong() -> None:
    # "wrong" is what the app/sensors_app.py `keep` seam is expected to hide
    # by default (see docs/phase-3-plan.md and src/sensors_gui/app/sensors_app.py).
    spec = _nct6687("temp1", "CPU", unit=Unit.CELSIUS)
    assert naming.verdict(spec) == "wrong"


@pytest.mark.parametrize("label", ["CPU Socket", "PCIe x1", "M2_1"])
def test_verdict_of_an_empty_thermistor_header_is_wrong(label: str) -> None:
    spec = _nct6687("temp5", label, unit=Unit.CELSIUS)
    assert naming.verdict(spec) == "wrong"


def test_verdict_of_an_unevidenced_board_temperature_is_unknown() -> None:
    spec = _nct6687("temp2", "System", unit=Unit.CELSIUS)
    assert naming.verdict(spec) == "unknown"


def test_verdict_of_an_unrelated_driver_is_unknown() -> None:
    spec = _spec("hwmon", "k10temp@/sys/devices/pci0000:00/0000:00:18.3", "temp1", "Tctl", group=Group.CPU)
    assert naming.verdict(spec) == "unknown"


def test_verdict_of_a_non_hwmon_spec_is_unknown() -> None:
    spec = _spec("nvidia", "GeForce RTX 4090@0000:01:00.0", "temperature", "GPU edge", group=Group.GPU)
    assert naming.verdict(spec) == "unknown"


# --- degrading gracefully when the evidence file is missing ---------------


def test_load_ground_truth_from_a_missing_file_returns_none_and_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    missing = tmp_path / "does-not-exist.json"
    with caplog.at_level(logging.WARNING, logger="sensors_gui.naming"):
        result = naming._load_ground_truth_from(missing)
    assert result is None
    assert "cannot read" in caplog.text.lower() or "not" in caplog.text.lower()


def test_load_ground_truth_from_malformed_json_returns_none_and_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{ not valid json ")
    with caplog.at_level(logging.WARNING, logger="sensors_gui.naming"):
        result = naming._load_ground_truth_from(broken)
    assert result is None
    assert caplog.text  # something was logged


def test_friendly_and_verdict_still_run_when_the_repo_root_cannot_be_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The application must still run without the evidence file.

    Rules that do not depend on the ground-truth JSON (DIMM naming, the
    network group, empty fan headers, the CPU duplicate, empty thermistors)
    must still work. Only the voltage rename/wrong/unverified verdicts, which
    need the file, degrade to "unknown".
    """
    monkeypatch.setattr(naming, "_find_repo_root", lambda: tmp_path)
    naming._load_ground_truth.cache_clear()
    try:
        dimm = _spec(
            "hwmon",
            "spd5118@/sys/devices/pci0000:00/0000:00:14.0/i2c-0/0-0051",
            "temp1",
            "temp1",
            group=Group.MEMORY,
        )
        assert naming.friendly(dimm).label == "DIMM A2"

        duplicate = _nct6687("temp1", "CPU", unit=Unit.CELSIUS)
        assert naming.verdict(duplicate) == "wrong"

        voltage = _nct6687("in7", "DRAM")
        # No ground truth is reachable, so the rename cannot happen, and the
        # verdict cannot be anything but "unknown". Neither call raises.
        assert naming.friendly(voltage).label == "DRAM"
        assert naming.verdict(voltage) == "unknown"
    finally:
        naming._load_ground_truth.cache_clear()


def test_the_real_ground_truth_file_loads_from_the_actual_repo() -> None:
    naming._load_ground_truth.cache_clear()
    try:
        ground_truth = naming._load_ground_truth()
        assert ground_truth is not None
        assert "DRAM" in ground_truth.voltages
        assert ground_truth.voltages["DRAM"].verdict == "rename"
    finally:
        naming._load_ground_truth.cache_clear()


# --- against the real machine ----------------------------------------------


def test_against_the_real_nct6687_device_on_this_machine() -> None:
    collector = HwmonCollector()
    specs = collector.discover()
    nct6687_specs = [spec for spec in specs if spec.id.device.startswith("nct6687@")]
    if not nct6687_specs:
        pytest.skip("no nct6687 device on this machine")

    friendly_labels = {naming.friendly(spec).label for spec in nct6687_specs}
    assert "CPU VDDIO" in friendly_labels
    assert "System 3.3V" in friendly_labels
    assert "DIMM A2" not in friendly_labels  # that's a memory channel, not board

    verdicts = {spec.label: naming.verdict(spec) for spec in nct6687_specs}
    assert verdicts["+12V"] == "correct"
    assert verdicts["DRAM"] == "rename"
    assert verdicts["Chipset"] == "wrong"

    # Every spec must survive both calls without raising, whatever it is.
    for spec in specs:
        naming.friendly(spec)
        naming.verdict(spec)
