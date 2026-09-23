"""The tooltip's five parts, tested in the runtime that shows them.

`docs/gui-goal.md` section 4.2 lists what hovering any value must show: what
it measures, where it is read from, how it differs from its neighbours, the
safe range and where the value sits in it, and the read interval with the age
of the value. `explain` in `tooltip.js` builds those five parts from a channel
and a frame, with no page, so node can run the real file.

There is no mock. The descriptions come from the real Python module, so a
test that passes here proves the two layers agree.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from sensors_gui.descriptions import describe
from sensors_gui.model import Group, SensorId, SensorSpec, Unit

TOOLTIP = Path(__file__).resolve().parents[1] / "src/sensors_gui/web/static/tooltip.js"
NEEDS_NODE = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed; the application does not need it"
)
DEVICE = "NVIDIA GeForce RTX 4090@00000000:01:00.0"


def _card_channel(channel: str, label: str, unit: str, symbol: str, decimals: int, **limits: object) -> dict:
    """Return a card channel as the catalogue sends it, with its real description."""
    spec = SensorSpec(
        id=SensorId(source="nvidia", device=DEVICE, channel=channel), label=label, group=Group.GPU, unit=Unit(unit)
    )
    description = describe(spec)
    return {
        "label": label,
        "key": spec.id.key,
        "source": "nvidia",
        "unit": unit,
        "symbol": symbol,
        "decimals": decimals,
        "low": limits.get("low"),
        "high": limits.get("high"),
        "warn": limits.get("warn"),
        "critical": limits.get("critical"),
        "min_interval": limits.get("min_interval", 0.0),
        "origin": f"nvml:{channel}@00000000:01:00.0",
        "description": None if description is None else description.as_dict(),
    }


EDGE = _card_channel("temperature", "GPU edge", "celsius", "°C", 1, low=0.0, high=104.0, warn=99.0, critical=104.0)
POWER = _card_channel("power", "GPU power", "watt", "W", 2, low=0.0, high=480.0)
PCIE = _card_channel("pcie_rx", "PCIe receive", "byte_per_second", "B/s", 1, min_interval=2.0)
TCTL = {
    "label": "Tctl",
    "key": "hwmon:k10temp@/sys/devices/pci0000:00/0000:00:18.3:temp1",
    "source": "hwmon",
    "unit": "celsius",
    "symbol": "°C",
    "decimals": 1,
    "low": None,
    "high": None,
    "warn": None,
    "critical": None,
    "min_interval": 0.0,
    "origin": "/sys/class/hwmon/hwmon3/temp1_input",
    "description": None,
}


def explain(channel: dict, value: object, extra: dict, hz: float, where: Path) -> dict:
    """Run the real `explain` in node and return the five parts it builds."""
    script = where / "run.mjs"
    script.write_text(
        f"import {{ explain }} from {json.dumps(str(TOOLTIP))};\n"
        f"console.log(JSON.stringify(explain({json.dumps(channel)}, {json.dumps(value)}, "
        f"{json.dumps(extra)}, {json.dumps(hz)})));\n"
    )
    finished = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60, check=True)
    return json.loads(finished.stdout)


@NEEDS_NODE
def test_explain_what_it_measures_is_the_python_description(tmp_path: Path) -> None:
    parts = explain(EDGE, 45.0, {}, 2.0, tmp_path)
    assert parts["measures"] == EDGE["description"]["measures"]
    assert parts["neighbours"] == EDGE["description"]["neighbours"]
    assert parts["sources"] == EDGE["description"]["sources"]


@NEEDS_NODE
def test_explain_where_names_the_library_and_the_call(tmp_path: Path) -> None:
    parts = explain(EDGE, 45.0, {}, 2.0, tmp_path)
    assert "NVML" in parts["where"]
    assert "nvmlDeviceGetTemperature" in parts["where"]


@NEEDS_NODE
def test_explain_where_names_the_driver_and_the_path_for_a_hwmon_channel(tmp_path: Path) -> None:
    parts = explain(TCTL, 50.0, {}, 2.0, tmp_path)
    assert "k10temp" in parts["where"]
    assert "/sys/class/hwmon/hwmon3/temp1_input" in parts["where"]


@NEEDS_NODE
def test_explain_a_channel_with_no_description_says_so_and_guesses_nothing(tmp_path: Path) -> None:
    parts = explain(TCTL, 50.0, {}, 2.0, tmp_path)
    assert "not described yet" in parts["measures"]
    assert parts["neighbours"] == ""
    assert parts["sources"] == []


@NEEDS_NODE
def test_explain_the_range_names_both_thresholds_and_the_distance_to_the_first(tmp_path: Path) -> None:
    parts = explain(EDGE, 45.0, {}, 2.0, tmp_path)
    assert "99.0 °C" in parts["range"]
    assert "104.0 °C" in parts["range"]
    assert "54.0 °C below the warning" in parts["range"]


@NEEDS_NODE
def test_explain_the_range_past_a_threshold_says_it_is_past(tmp_path: Path) -> None:
    parts = explain(EDGE, 100.0, {}, 2.0, tmp_path)
    assert "past the warning" in parts["range"]


@NEEDS_NODE
def test_explain_a_scale_with_no_threshold_says_no_state_is_judged(tmp_path: Path) -> None:
    parts = explain(POWER, 120.0, {}, 2.0, tmp_path)
    assert "0 to 480 W" in parts["range"]
    assert "25 % of the scale" in parts["range"]
    assert "no threshold" in parts["range"]


@NEEDS_NODE
def test_explain_a_channel_with_no_scale_says_the_hardware_publishes_none(tmp_path: Path) -> None:
    parts = explain(TCTL, 50.0, {}, 2.0, tmp_path)
    assert "publishes no scale and no threshold" in parts["range"]


@NEEDS_NODE
def test_explain_a_channel_read_on_every_pass_gives_the_pass_period(tmp_path: Path) -> None:
    parts = explain(EDGE, 45.0, {}, 2.0, tmp_path)
    assert "every pass, every 0.5 s" in parts["read"]
    assert "from this pass" in parts["read"]


@NEEDS_NODE
def test_explain_a_slow_channel_gives_its_interval_and_the_age_of_its_value(tmp_path: Path) -> None:
    parts = explain(PCIE, 1000.0, {"age": 1.4}, 10.0, tmp_path)
    assert "at most once every 2 s" in parts["read"]
    assert "1.4 s old" in parts["read"]


@NEEDS_NODE
def test_explain_a_failed_read_gives_the_reason_and_no_number(tmp_path: Path) -> None:
    parts = explain(POWER, None, {"error": "NVML: GPU is lost"}, 2.0, tmp_path)
    assert parts["value"] == "—"
    assert "NVML: GPU is lost" in parts["read"]
    assert parts["state"] == "unavailable"


@NEEDS_NODE
def test_explain_a_value_that_cannot_be_read_gives_the_reason_and_the_sources(tmp_path: Path) -> None:
    from sensors_gui.descriptions import UNREACHABLE

    hotspot = next(entry for entry in UNREACHABLE if entry.label == "GPU hotspot")
    entry = {**hotspot.as_dict(), "missing": "unreachable"}
    parts = explain(entry, None, {}, 2.0, tmp_path)
    assert parts["value"] == "not readable"
    assert parts["state"] == "unavailable"
    assert parts["measures"] == hotspot.reason
    assert "docs/decisions/0011-no-i2c-route-to-the-graphics-card.md" in parts["sources"]
