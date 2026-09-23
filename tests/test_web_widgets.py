"""The rules the widget set keeps, tested in the runtime that runs them.

Three of these rules are promises about honesty, not about appearance, and
they are the ones worth a test:

  - a meter is drawn only where the hardware publishes a scale;
  - a state comes from a published threshold, never from a guess;
  - a vertical axis keeps a floor and does not move while the data fits it.

There is no mock. The file under test is the one the browser loads, and node
is the real runtime. Skipped when node is absent, because the application
itself does not need node.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

WIDGETS = Path(__file__).resolve().parents[1] / "src/sensors_gui/web/static/widgets.js"
NEEDS_NODE = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed; the application does not need it"
)

# A channel as the catalogue sends it. Tctl is the real case that matters:
# k10temp publishes no maximum and no threshold for it, and the spike drew it
# against an invented 0 to 100 anyway.
TCTL = {
    "label": "Tctl",
    "unit": "celsius",
    "symbol": "°C",
    "decimals": 1,
    "low": None,
    "high": None,
    "warn": None,
    "critical": None,
}
GPU_EDGE = {
    "label": "GPU edge",
    "unit": "celsius",
    "symbol": "°C",
    "decimals": 1,
    "low": 0.0,
    "high": 104.0,
    "warn": 99.0,
    "critical": 104.0,
}
DIMM = {
    "label": "DIMM A2",
    "unit": "celsius",
    "symbol": "°C",
    "decimals": 1,
    "low": 0.0,
    "high": None,
    "warn": 55.0,
    "critical": 85.0,
}
GPU_POWER = {
    "label": "GPU power",
    "unit": "watt",
    "symbol": "W",
    "decimals": 2,
    "low": 0.0,
    "high": 480.0,
    "warn": None,
    "critical": None,
}


def run_in_node(body: str, where: Path) -> object:
    """Run `body` against the real widgets module and return what it printed.

    Args:
        body: JavaScript that ends by printing JSON to the output.
        where: A directory the test may write to.

    Returns:
        Whatever the script printed, parsed from JSON.
    """
    script = where / "run.mjs"
    script.write_text(
        "import { stateOf, hasScale, scaleTop, niceAxis, niceStep, scaleLabel, fixed } "
        f"from {json.dumps(str(WIDGETS))};\n{body}\n"
    )
    finished = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60, check=True)
    return json.loads(finished.stdout)


@NEEDS_NODE
def test_a_channel_with_no_published_maximum_gets_no_meter(tmp_path: Path) -> None:
    """The defect Gova saw: the spike drew Tctl against a scale nobody published."""
    answer = run_in_node(
        f"const tctl = {json.dumps(TCTL)};\nconsole.log(JSON.stringify(hasScale(tctl)));",
        tmp_path,
    )
    assert answer is False


@NEEDS_NODE
def test_a_channel_with_a_published_maximum_gets_a_meter(tmp_path: Path) -> None:
    answer = run_in_node(
        f"const gpu = {json.dumps(GPU_EDGE)};\nconsole.log(JSON.stringify([hasScale(gpu), scaleTop(gpu)]));",
        tmp_path,
    )
    assert answer == [True, 104.0]


@NEEDS_NODE
def test_a_critical_threshold_is_the_top_of_the_scale_when_there_is_no_maximum(tmp_path: Path) -> None:
    """A DIMM publishes no maximum but does publish 85 °C as critical."""
    answer = run_in_node(
        f"const dimm = {json.dumps(DIMM)};\nconsole.log(JSON.stringify([hasScale(dimm), scaleTop(dimm)]));",
        tmp_path,
    )
    assert answer == [True, 85.0]


@NEEDS_NODE
def test_the_state_comes_from_the_published_thresholds(tmp_path: Path) -> None:
    answer = run_in_node(
        f"const dimm = {json.dumps(DIMM)};\n"
        "console.log(JSON.stringify([\n"
        "  stateOf(30, dimm), stateOf(55, dimm), stateOf(60, dimm),\n"
        "  stateOf(80, dimm), stateOf(85, dimm), stateOf(120, dimm),\n"
        "]));",
        tmp_path,
    )
    assert answer == ["normal", "warning", "warning", "serious", "critical", "critical"]


@NEEDS_NODE
def test_a_channel_with_no_threshold_is_never_called_warm(tmp_path: Path) -> None:
    """Tctl at 95 °C is hot to a person, and the hardware says nothing about it.

    The application must not invent the judgement. The number is shown; the
    state stays `normal`, and the view says no threshold is published.
    """
    answer = run_in_node(
        f"const tctl = {json.dumps(TCTL)};\n"
        "console.log(JSON.stringify([stateOf(30, tctl), stateOf(95, tctl), stateOf(200, tctl)]));",
        tmp_path,
    )
    assert answer == ["normal", "normal", "normal"]


@NEEDS_NODE
def test_a_value_that_cannot_be_read_is_unavailable_and_never_zero(tmp_path: Path) -> None:
    answer = run_in_node(
        f"const gpu = {json.dumps(GPU_POWER)};\n"
        "console.log(JSON.stringify([\n"
        "  stateOf(null, gpu), stateOf(0, gpu, { error: 'needs the helper' }),\n"
        "]));",
        tmp_path,
    )
    assert answer == ["unavailable", "unavailable"]


@NEEDS_NODE
def test_the_axis_keeps_a_floor_so_a_small_wobble_is_not_made_violent(tmp_path: Path) -> None:
    """Four samples a quarter of a degree apart must not fill the box."""
    answer = run_in_node(
        "const axis = niceAxis([41.0, 41.25, 41.0, 41.25], null, 1);\n"
        "console.log(JSON.stringify(axis.high - axis.low));",
        tmp_path,
    )
    assert answer >= 1.0


@NEEDS_NODE
def test_the_axis_does_not_move_while_the_data_still_fits_it(tmp_path: Path) -> None:
    """Recomputing the bounds every frame makes the whole line jump."""
    answer = run_in_node(
        "const first = niceAxis([40, 44, 48], null, 1);\n"
        "const again = niceAxis([41, 45, 47], first, 1);\n"
        "console.log(JSON.stringify([first.low === again.low, first.high === again.high]));",
        tmp_path,
    )
    assert answer == [True, True]


@NEEDS_NODE
def test_the_axis_does_move_when_the_data_leaves_it(tmp_path: Path) -> None:
    answer = run_in_node(
        "const first = niceAxis([40, 44, 48], null, 1);\n"
        "const again = niceAxis([40, 44, 96], first, 1);\n"
        "console.log(JSON.stringify(again.high > first.high));",
        tmp_path,
    )
    assert answer is True


@NEEDS_NODE
def test_the_axis_steps_are_round_numbers(tmp_path: Path) -> None:
    answer = run_in_node(
        "console.log(JSON.stringify([niceStep(0.3), niceStep(1.2), niceStep(3), niceStep(7), niceStep(230)]));",
        tmp_path,
    )
    assert answer == [0.5, 2, 5, 10, 500]


@NEEDS_NODE
def test_the_ends_of_a_scale_lose_the_decimals_of_their_unit(tmp_path: Path) -> None:
    """A 480 W limit is a round number, not a measurement of 480.00 W."""
    answer = run_in_node(
        f"const gpu = {json.dumps(GPU_POWER)};\n"
        "console.log(JSON.stringify([scaleLabel(0, gpu), scaleLabel(480, gpu)]));",
        tmp_path,
    )
    assert answer == ["0", "480"]


# --- the core display ---------------------------------------------------------

TOPOLOGY = WIDGETS.parent / "topology.js"
PROBE = Path(__file__).resolve().parents[1] / "data/probes/2026-09-22-cpu-topology.txt"


def topology_from_the_probe() -> dict[int, list[int]]:
    """Return core_id -> its two threads, read from the recorded probe.

    The probe is what the machine said on 2026-09-22. The front end holds a
    copy of the same table, and this is what keeps the two the same.
    """
    pairs: dict[int, list[int]] = {}
    for line in PROBE.read_text().splitlines():
        if line.startswith("#") or line.startswith("cpu ") or not line.strip():
            continue
        thread, core_id, _die, siblings = line.split()
        pairs.setdefault(int(core_id), sorted(int(part) for part in siblings.split(",")))
        assert int(thread) in pairs[int(core_id)]
    return pairs


@NEEDS_NODE
def test_the_front_end_pairs_the_threads_the_way_the_machine_reported(tmp_path: Path) -> None:
    """A thread's sibling is 12 away, not next to it.

    Pairing `cpu0` with `cpu1` would put two different cores side by side and
    make a busy core look half idle. The machine's own answer is in
    `data/probes/2026-09-22-cpu-topology.txt`.
    """
    script = tmp_path / "cores.mjs"
    script.write_text(f"import {{ CORES }} from {json.dumps(str(TOPOLOGY))};\nconsole.log(JSON.stringify(CORES));\n")
    finished = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60, check=True)
    from_front_end = {row["core"]: sorted(row["threads"]) for row in json.loads(finished.stdout)}
    assert from_front_end == topology_from_the_probe()


@NEEDS_NODE
def test_every_core_is_on_the_die_the_machine_put_it_on(tmp_path: Path) -> None:
    script = tmp_path / "dies.mjs"
    script.write_text(
        f"import {{ CORES }} from {json.dumps(str(TOPOLOGY))};\n"
        "console.log(JSON.stringify(CORES.map((c) => [c.core, c.die])));\n"
    )
    finished = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60, check=True)
    from_front_end = dict(json.loads(finished.stdout))

    from_probe: dict[int, int] = {}
    for line in PROBE.read_text().splitlines():
        if line.startswith("#") or line.startswith("cpu ") or not line.strip():
            continue
        _thread, core_id, die, _siblings = line.split()
        # The probe counts dies from zero and the display names them from one,
        # because the temperature channels are Tccd1 and Tccd2.
        from_probe[int(core_id)] = int(die) + 1
    assert from_front_end == from_probe


@NEEDS_NODE
def test_an_axis_never_goes_below_the_bottom_of_the_published_scale(tmp_path: Path) -> None:
    """A fan at rest read 0 RPM and the axis ran from -1 to 1: a speed below zero."""
    script = tmp_path / "run.mjs"
    script.write_text(
        f"import {{ niceAxis, floorAt }} from {json.dumps(str(WIDGETS))};\n"
        "const axis = floorAt(niceAxis([0, 0, 0], null, 1), 0);\n"
        "console.log(JSON.stringify([axis.low, axis.high > 0, axis.ticks.every((t) => t >= 0)]));\n"
    )
    finished = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60, check=True)
    assert json.loads(finished.stdout) == [0, True, True]


# --- a reading past its ceiling (Gova, 2026-09-23) ------------------------------


def run_widgets(body: str, where: Path) -> object:
    """Run `body` with every export of the real widgets module in scope."""
    script = where / "run.mjs"
    script.write_text(f"import * as w from {json.dumps(str(WIDGETS))};\n{body}\n")
    finished = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60, check=True)
    return json.loads(finished.stdout)


@NEEDS_NODE
def test_state_of_a_reading_above_the_ceiling_says_so(tmp_path: Path) -> None:
    answer = run_widgets(
        f"const power = {json.dumps(GPU_POWER)};\n"
        "console.log(JSON.stringify([w.stateOf(480, power), w.stateOf(512, power), w.stateOf(-2, power),"
        " w.STATES.over.word, w.STATES.under.word]));",
        tmp_path,
    )
    assert answer == ["normal", "over", "under", "above ceiling", "below floor"]


@NEEDS_NODE
def test_state_of_a_critical_reading_stays_critical_when_it_is_also_past_the_ceiling(tmp_path: Path) -> None:
    """The edge sensor's ceiling is its critical threshold, and critical is the stronger word."""
    answer = run_widgets(f"console.log(JSON.stringify(w.stateOf(106, {json.dumps(GPU_EDGE)})));", tmp_path)
    assert answer == "critical"


@NEEDS_NODE
def test_meter_geometry_inside_the_scale_fills_to_the_value(tmp_path: Path) -> None:
    answer = run_widgets(f"console.log(JSON.stringify(w.meterGeometry(120, {json.dumps(GPU_POWER)})));", tmp_path)
    assert answer == {"fill": 0.25, "ceiling": 1, "over": 0, "top": 480}


@NEEDS_NODE
def test_meter_geometry_past_the_ceiling_moves_the_ceiling_in_and_runs_past_it(tmp_path: Path) -> None:
    """The fill must visibly cross the ceiling mark, never stop at the end of the track."""
    answer = run_widgets(f"console.log(JSON.stringify(w.meterGeometry(528, {json.dumps(GPU_POWER)})));", tmp_path)
    assert answer["fill"] == 1
    assert 0.8 <= answer["ceiling"] < 0.95
    assert answer["over"] > 0
    assert answer["top"] > 528


@NEEDS_NODE
def test_an_axis_is_not_floored_when_the_data_is_below_the_floor(tmp_path: Path) -> None:
    """The floor must never hide a reading that is below it: that reading is the alert."""
    answer = run_widgets(
        "const axis = w.floorAt(w.niceAxis([-3, 5, 10], null, 1), 0, -3);\n"
        "console.log(JSON.stringify(axis.low <= -3));",
        tmp_path,
    )
    assert answer is True


GPU_VIEW = WIDGETS.parent / "views/gpu.js"


@NEEDS_NODE
def test_the_front_end_names_the_clock_event_bits_as_the_collector_does(tmp_path: Path) -> None:
    """Two copies of the bit table, one in Python and one in JavaScript, must not drift."""
    from sensors_gui.collectors.nvidia import CLOCK_EVENT_REASONS

    script = tmp_path / "run.mjs"
    script.write_text(
        "globalThis.document = undefined;\n"
        f"const m = await import({json.dumps(str(GPU_VIEW))});\n"
        "console.log(JSON.stringify([m.CLOCK_EVENT_REASONS, m.activeReasons(0x45)]));\n"
    )
    finished = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60, check=True)
    table, active = json.loads(finished.stdout)
    assert {bit: name for bit, name in table} == CLOCK_EVENT_REASONS
    assert active == ["GPU idle", "Software power cap", "Hardware thermal slowdown"]


# --- the core columns, checkpoint 4 ---------------------------------------------

CPU_FREQUENCY = {"label": "CPU0 frequency", "unit": "hertz", "symbol": "Hz", "decimals": 1}


@NEEDS_NODE
def test_axis_unit_writes_a_frequency_axis_in_one_prefix(tmp_path: Path) -> None:
    """614 MHz to 5.7 GHz on one axis: one unit, GHz, and every tick a plain number."""
    answer = run_widgets(f"console.log(JSON.stringify(w.axisUnit(5662016000, {json.dumps(CPU_FREQUENCY)})));", tmp_path)
    assert answer == {"factor": 1_000_000_000, "unit": "GHz"}


@NEEDS_NODE
def test_axis_unit_leaves_a_unit_with_no_prefix_alone(tmp_path: Path) -> None:
    answer = run_widgets(f"console.log(JSON.stringify(w.axisUnit(480, {json.dumps(GPU_POWER)})));", tmp_path)
    assert answer == {"factor": 1, "unit": "W"}


@NEEDS_NODE
def test_following_top_rounds_up_to_a_round_step_above_the_peak(tmp_path: Path) -> None:
    answer = run_widgets("console.log(JSON.stringify(w.followingTop(2.3, null, 2)));", tmp_path)
    assert answer == 3


@NEEDS_NODE
def test_following_top_does_not_move_while_the_peak_still_fits(tmp_path: Path) -> None:
    """The columns must not jump on every frame; the line chart keeps the same rule."""
    answer = run_widgets("console.log(JSON.stringify(w.followingTop(2.9, 3, 2)));", tmp_path)
    assert answer == 3


@NEEDS_NODE
def test_following_top_grows_when_a_column_leaves_it(tmp_path: Path) -> None:
    answer = run_widgets("console.log(JSON.stringify(w.followingTop(4.1, 3, 2)));", tmp_path)
    assert answer > 4.1


@NEEDS_NODE
def test_following_top_comes_down_to_the_floor_when_the_peak_is_small(tmp_path: Path) -> None:
    answer = run_widgets("console.log(JSON.stringify(w.followingTop(0.5, 3, 2)));", tmp_path)
    assert answer == 2


@NEEDS_NODE
def test_bar_ticks_of_a_frequency_scale_start_at_the_hardware_floor(tmp_path: Path) -> None:
    """The floor is the processor's lowest frequency, a published end, and it is labelled as one."""
    answer = run_widgets("console.log(JSON.stringify(w.barTicks(613954000, 5662016000, true)));", tmp_path)
    assert answer[0] == 613954000
    assert answer[-1] == 5662016000
    assert all(tick % 1_000_000_000 == 0 for tick in answer[1:-1])


@NEEDS_NODE
def test_bar_ticks_of_a_following_scale_are_round(tmp_path: Path) -> None:
    answer = run_widgets("console.log(JSON.stringify(w.barTicks(0, 3, false)));", tmp_path)
    assert answer == [0, 1, 2, 3]
