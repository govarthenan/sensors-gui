"""The fixed rate steps of the "Slower" and "Faster" buttons.

Gova, 2026-09-25: "Fixed steps. 10hz, 5 hz, 2 hz, 1 hz, 0.5 hz, 0.25 hz,
0.2 hz, 0.1 hz". Before this, each click halved or doubled the rate, which
gave 0.63 Hz and 0.31 Hz.

The step logic runs in node against the file the browser loads. The limits
and the list come from the Python service, so the two cannot disagree.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_web_server import SteadyCollector

from sensors_gui.web.server import build_app
from sensors_gui.web.service import MAX_HZ, MIN_HZ, RATE_STEPS, SensorService

STREAM = Path(__file__).resolve().parents[1] / "src/sensors_gui/web/static/stream.js"
NEEDS_NODE = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed; the application does not need it"
)
GOVA_STEPS = [0.1, 0.2, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Return a client over the real application, with the worker running."""
    service = SensorService([SteadyCollector()], hz=10.0)
    service.discover()
    with TestClient(build_app(service)) as running:
        yield running


def next_rates(hz: float, tmp_path: Path) -> dict[str, float]:
    """Return the rate one click on each button gives, as the page computes it."""
    script = tmp_path / "steps.mjs"
    script.write_text(
        f"import {{ nextRate }} from {json.dumps(str(STREAM))};\n"
        f"const steps = {json.dumps(RATE_STEPS)};\n"
        f"console.log(JSON.stringify({{faster: nextRate(steps, {hz}, 1), slower: nextRate(steps, {hz}, -1)}}));\n"
    )
    finished = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60, check=True)
    return json.loads(finished.stdout)


def test_rate_steps_are_the_ones_gova_chose() -> None:
    assert list(RATE_STEPS) == GOVA_STEPS
    assert MIN_HZ == 0.1
    assert MAX_HZ == 10.0


def test_catalogue_carries_the_rate_steps(client: TestClient) -> None:
    body = client.get("/api/catalogue").json()
    assert body["rate_steps"] == GOVA_STEPS
    assert body["min_hz"] == 0.1


def test_rate_of_one_tenth_hz_is_accepted(client: TestClient) -> None:
    assert client.post("/api/rate", json={"hz": 0.1}).json() == {"hz": 0.1}


def test_rate_below_one_tenth_hz_is_refused(client: TestClient) -> None:
    assert client.post("/api/rate", json={"hz": 0.05}).status_code == 422


@NEEDS_NODE
@pytest.mark.parametrize(
    ("hz", "faster", "slower"),
    [
        (10.0, 10.0, 5.0),
        (5.0, 10.0, 2.0),
        (2.0, 5.0, 1.0),
        (1.0, 2.0, 0.5),
        (0.5, 1.0, 0.25),
        (0.25, 0.5, 0.2),
        (0.2, 0.25, 0.1),
        (0.1, 0.2, 0.1),
    ],
)
def test_next_rate_moves_one_step_and_stops_at_the_ends(
    hz: float, faster: float, slower: float, tmp_path: Path
) -> None:
    assert next_rates(hz, tmp_path) == {"faster": faster, "slower": slower}


@NEEDS_NODE
def test_next_rate_from_a_rate_between_steps_goes_to_the_nearest_step_each_way(tmp_path: Path) -> None:
    """`--hz 3` starts between two steps; a click must land on a step."""
    assert next_rates(3.0, tmp_path) == {"faster": 5.0, "slower": 2.0}
