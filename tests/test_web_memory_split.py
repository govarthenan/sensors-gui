"""The composition bar of the memory view, tested in the runtime that runs it.

Gova chose it on 2026-09-25: one bar for the memory the kernel can use,
divided into what is in use, the cache the kernel can take back, and what is
free. The three parts come from the kernel's own fields:

  in use        Memory used = MemTotal - MemAvailable (psutil 7.2.2)
  can take back Memory available - Memory free, made in the page
  free          Memory free = MemFree

So the three add up to the total. The middle part is no channel: it is made
from two, and its tooltip says so. The numbers below are the machine's own,
read on 2026-09-25 (60.4 GiB total, 20.0 GiB used, 40.4 GiB available,
1.7 GiB free).

No mock. The files under test are the ones the browser loads, and node is
the real runtime. Skipped when node is absent.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "src/sensors_gui/web/static"
NEEDS_NODE = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed; the application does not need it"
)
GIB = 1024**3


def run(body: str, where: Path) -> object:
    """Run `body` with the widgets, the stream and the memory view imported, and return its JSON."""
    script = where / "run.mjs"
    script.write_text(
        f"import {{ stackShares }} from {json.dumps(str(STATIC / 'widgets.js'))};\n"
        f"import {{ Catalogue, Stream }} from {json.dumps(str(STATIC / 'stream.js'))};\n"
        f"import {{ memorySplit }} from {json.dumps(str(STATIC / 'views/memory.js'))};\n"
        f"{body}\n"
    )
    finished = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60, check=True)
    return json.loads(finished.stdout)


@NEEDS_NODE
def test_memory_split_gives_used_then_what_the_kernel_can_take_back_then_free(tmp_path: Path) -> None:
    answer = run(f"console.log(JSON.stringify(memorySplit({20 * GIB}, {40.4 * GIB}, {1.7 * GIB})));", tmp_path)
    assert answer == pytest.approx([20 * GIB, 38.7 * GIB, 1.7 * GIB])


@NEEDS_NODE
def test_memory_split_is_unknown_when_any_of_the_three_readings_is_missing(tmp_path: Path) -> None:
    answer = run(
        "console.log(JSON.stringify([memorySplit(null, 1, 1), memorySplit(1, null, 1), memorySplit(1, 1, null)]));",
        tmp_path,
    )
    assert answer == [None, None, None]


@NEEDS_NODE
def test_memory_split_never_gives_a_negative_part(tmp_path: Path) -> None:
    """Two readings of one pass can disagree by a page; the bar must not draw backwards."""
    answer = run("console.log(JSON.stringify(memorySplit(10, 5, 6)));", tmp_path)
    assert answer == [10, 0, 6]


@NEEDS_NODE
def test_stack_shares_are_each_part_over_the_total(tmp_path: Path) -> None:
    answer = run(
        f"console.log(JSON.stringify(stackShares({60.4 * GIB}, [{20 * GIB}, {38.7 * GIB}, {1.7 * GIB}])));", tmp_path
    )
    assert answer == pytest.approx([20 / 60.4, 38.7 / 60.4, 1.7 / 60.4])


@NEEDS_NODE
def test_stack_shares_are_unknown_without_a_total_or_a_part(tmp_path: Path) -> None:
    answer = run(
        "console.log(JSON.stringify([stackShares(null, [1, 2]), stackShares(0, [1, 2]), stackShares(10, null)]));",
        tmp_path,
    )
    assert answer == [None, None, None]


@NEEDS_NODE
def test_stack_shares_never_pass_the_whole_bar(tmp_path: Path) -> None:
    """Parts read a moment apart can add to a little more than the total; the bar stays inside its box."""
    answer = run("console.log(JSON.stringify(stackShares(100, [50, 40, 20])));", tmp_path)
    assert answer == pytest.approx([50 / 110, 40 / 110, 20 / 110])
    assert sum(answer) == pytest.approx(1.0)


@NEEDS_NODE
def test_a_derived_channel_takes_its_value_from_the_stream_and_has_no_frame_extra(tmp_path: Path) -> None:
    """The middle part of the bar has a tooltip like a channel, but no frame carries it."""
    answer = run(
        "const catalogue = new Catalogue({channels: [{label: 'a', i: 0}, {label: 'b', i: 1}]});\n"
        "const stream = new Stream(catalogue);\n"
        "stream._take({v: [7, 3], errors: {}, ages: {}});\n"
        "const derived = {label: 'a - b', derive: (s) => s.value(catalogue.byLabel('a')) - "
        "s.value(catalogue.byLabel('b'))};\n"
        "console.log(JSON.stringify([stream.value(derived), stream.extra(derived)]));",
        tmp_path,
    )
    assert answer == [4, {}]
