"""The airflow drawing of the cooling view, held against the documents it draws.

The drawing (`views/airflow-diagram.js`, checkpoint 5a, 2026-10-27) keeps a
copy of Gova's airflow table from `docs/physical-build.md`, and a list of the
board fan headers with the fans each one drives. Two copies drift, so the
copy is checked against the document here. While Q20 is open no source says
which fans a header drives, so no header may be placed on a group of fans.

No mock. The file under test is the one the browser loads, and node is the
real runtime. Skipped when node is absent.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/sensors_gui/web/static"
NEEDS_NODE = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed; the application does not need it"
)


def drawing_tables(where: Path) -> dict:
    """Return the drawing's exported tables, read by node from the real file."""
    script = where / "run.mjs"
    script.write_text(
        f"import {{ AIRFLOW, HEADERS, SOURCES }} from {json.dumps(str(STATIC / 'views/airflow-diagram.js'))};\n"
        "console.log(JSON.stringify({ AIRFLOW, HEADERS, SOURCES }));\n"
    )
    finished = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60, check=True)
    return json.loads(finished.stdout)


def airflow_table() -> list[tuple[int, str, str | None, str]]:
    """Return the rows of the CORRECTION airflow table in `docs/physical-build.md`."""
    lines = (ROOT / "docs/physical-build.md").read_text().splitlines()
    start = lines.index("| Fans | Where | Air | Serves |") + 2
    rows = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        count, where, air, serves = (cell.strip() for cell in line.strip("|").split("|"))
        bold = re.search(r"\*\*(\w+)\*\*", air)
        rows.append((0 if count == "—" else int(count), where, bold.group(1) if bold else None, serves))
    return rows


@NEEDS_NODE
def test_the_drawing_has_the_same_fans_as_the_airflow_table_of_the_physical_build(tmp_path: Path) -> None:
    drawn = [(row["count"], row["where"], row["air"], row["serves"]) for row in drawing_tables(tmp_path)["AIRFLOW"]]
    assert drawn == airflow_table()


@NEEDS_NODE
def test_the_drawing_has_10_fans_and_1_pump(tmp_path: Path) -> None:
    airflow = drawing_tables(tmp_path)["AIRFLOW"]
    assert sum(row["count"] for row in airflow) == 10
    assert [row["id"] for row in airflow if row["count"] == 0] == ["pump"]


@NEEDS_NODE
def test_every_source_the_drawing_names_is_a_file_in_the_repository(tmp_path: Path) -> None:
    for source in drawing_tables(tmp_path)["SOURCES"]:
        assert (ROOT / source).is_file(), source


@NEEDS_NODE
def test_no_board_header_is_placed_on_a_fan_while_q20_is_open(tmp_path: Path) -> None:
    headers = drawing_tables(tmp_path)["HEADERS"]
    assert [entry["header"] for entry in headers] == ["CPU_FAN1", "PUMP_SYS1", "SYS_FAN1", "JAF_1"]
    assert all(entry["fans"] is None for entry in headers)
