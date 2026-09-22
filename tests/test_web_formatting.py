"""The browser and the Python model must format a number the same way.

The GUI cannot call `SensorSpec.format`, so `widgets.js` holds a second copy
of that rule. Two copies drift. This test runs the real JavaScript in node
against the real Python for the same inputs, so a change to one that is not
made to the other fails here.

It has already earned its place twice. Python rounds a tie to the even digit
and `Number.toFixed` rounds it away from zero, so 41.25 read `41.2` in the
terminal and `41.3` in the window; and `Intl.NumberFormat` with `halfEven`,
the obvious repair, turns -40.15 into -40.2 where Python gives -40.1, because
it rounds the shortest decimal form rather than the number itself.

There is no mock: the file under test is the one the browser loads, and node
is the real runtime. The test is skipped when node is absent, because the
application itself does not need node.
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from sensors_gui.model import Group, SensorId, SensorSpec, Unit

WIDGETS = Path(__file__).resolve().parents[1] / "src/sensors_gui/web/static/widgets.js"
NEEDS_NODE = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed; the application does not need it"
)

# One case for each rule in the formatter: every unit that scales, one that
# does not, either side of a prefix step, a negative number and zero.
CASES: list[tuple[Unit, float]] = [
    (Unit.CELSIUS, 41.25),
    (Unit.CELSIUS, -40.15),
    (Unit.CELSIUS, 0.0),
    (Unit.VOLT, 3.116),
    (Unit.WATT, 103.984),
    (Unit.RPM, 1470.0),
    (Unit.PERCENT, 0.4),
    (Unit.PERCENT, 100.0),
    (Unit.COUNT, 31.0),
    (Unit.HOUR, 333.0),
    (Unit.SECOND, 0.0),
    (Unit.HERTZ, 999.0),
    (Unit.HERTZ, 1000.0),
    (Unit.HERTZ, 210000000.0),
    (Unit.HERTZ, 5662020000.0),
    (Unit.JOULE, 868900.0),
    (Unit.BYTE, 1023.0),
    (Unit.BYTE, 1024.0),
    (Unit.BYTE, 25757220864.0),
    (Unit.BYTE_PER_SECOND, 1900.0),
    (Unit.BYTE_PER_SECOND, 0.0),
    (Unit.NONE, 5.0),
    # Exact ties, where the two disagreed until this test was written.
    (Unit.CELSIUS, 0.25),
    (Unit.CELSIUS, -0.25),
    (Unit.COUNT, 0.5),
    (Unit.COUNT, 1.5),
    (Unit.COUNT, 2.5),
    (Unit.COUNT, -2.5),
    (Unit.PERCENT, 0.5),
    (Unit.PERCENT, 1.5),
    (Unit.VOLT, 1.0625),
    (Unit.WATT, 0.125),
    (Unit.WATT, -0.125),
]


def spec_for(unit: Unit) -> SensorSpec:
    """Return a spec carrying one unit, for the formatter to use."""
    return SensorSpec(
        id=SensorId(source="test", device="d@/sys/x", channel="c1"),
        label="channel",
        group=Group.OTHER,
        unit=unit,
    )


def format_in_node(cases: list[tuple[Unit, float]], where: Path) -> list[str]:
    """Run the real `formatValue` in node over `cases` and return what it said.

    The cases travel through a file, not the command line, because a wide
    sweep is longer than the kernel accepts as an argument.

    Args:
        cases: The unit and the value of each case.
        where: A directory the test may write to.

    Returns:
        One piece of text for each case, in the same order.
    """
    data = where / "cases.json"
    data.write_text(
        json.dumps(
            [
                {"unit": str(unit), "symbol": unit.symbol, "decimals": unit.decimals, "value": value}
                for unit, value in cases
            ]
        )
    )
    script = where / "run.mjs"
    script.write_text(
        f"import {{ formatValue }} from {json.dumps(str(WIDGETS))};\n"
        "import { readFileSync } from 'node:fs';\n"
        f"const cases = JSON.parse(readFileSync({json.dumps(str(data))}, 'utf8'));\n"
        "console.log(JSON.stringify(cases.map((c) => formatValue(c.value, c))));\n"
    )
    finished = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=120, check=True)
    return json.loads(finished.stdout)


@NEEDS_NODE
def test_the_browser_formats_every_unit_exactly_as_python_does(tmp_path: Path) -> None:
    from_browser = format_in_node(CASES, tmp_path)
    from_python = [spec_for(unit).format(value) for unit, value in CASES]
    assert from_browser == from_python


@NEEDS_NODE
def test_a_missing_value_is_an_em_dash_in_both(tmp_path: Path) -> None:
    script = tmp_path / "none.mjs"
    script.write_text(
        f"import {{ formatValue }} from {json.dumps(str(WIDGETS))};\n"
        'console.log(formatValue(null, { unit: "celsius", symbol: "°C", decimals: 1 }));\n'
    )
    finished = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60, check=True)
    assert finished.stdout.strip() == spec_for(Unit.CELSIUS).format(None)


@NEEDS_NODE
def test_the_two_agree_over_a_wide_sweep_of_values(tmp_path: Path) -> None:
    """A fixed sweep across every unit and sixteen orders of magnitude.

    The list above holds the cases a person thought of. This holds the ones
    nobody did, over the range this machine really produces, and at each step
    where a prefix changes.
    """
    generator = random.Random(20260922)
    sweep: list[tuple[Unit, float]] = []
    for unit in Unit:
        for exponent in range(-3, 13):
            for _ in range(6):
                sweep.append((unit, generator.uniform(-1.0, 1.0) * (10.0**exponent)))
            for step in (1000.0, 1024.0):
                edge = step ** (exponent % 4)
                sweep.extend([(unit, edge), (unit, edge - 0.5), (unit, edge + 0.5)])

    from_browser = format_in_node(sweep, tmp_path)
    from_python = [spec_for(unit).format(value) for unit, value in sweep]
    disagreements = [
        (str(unit), value, browser, python)
        for (unit, value), browser, python in zip(sweep, from_browser, from_python, strict=True)
        if browser != python
    ]
    assert disagreements == []
