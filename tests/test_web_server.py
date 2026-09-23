"""Tests for the web server: its routes, its frame stream and what it refuses.

There is no mock. The application under test is the real one, driven through
Starlette's own test client, over a real service with a real worker thread and
a small real collector standing in for the hardware.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from sensors_gui.model import Group, Reading, SensorId, SensorSpec, Unit
from sensors_gui.web.server import build_app
from sensors_gui.web.service import SensorService


class SteadyCollector:
    """A real collector with one temperature and one channel that always fails."""

    name = "steady"

    def __init__(self) -> None:
        """Build the two channels."""
        self.temperature = SensorSpec(
            id=SensorId(source="steady", device="cpu@/sys/a", channel="temp1"),
            label="Tctl",
            group=Group.CPU,
            unit=Unit.CELSIUS,
            low=0.0,
            high=100.0,
            warn=80.0,
            critical=95.0,
        )
        self.broken = SensorSpec(
            id=SensorId(source="steady", device="helper@/run/x", channel="power1"),
            label="CPU Package Power",
            group=Group.CPU,
            unit=Unit.WATT,
        )

    def discover(self) -> list[SensorSpec]:
        """Report both channels."""
        return [self.temperature, self.broken]

    def read(self) -> list[Reading]:
        """Report one value and one failure."""
        return [
            Reading.ok(self.temperature.id, 44.5, read_at=time.monotonic()),
            Reading.failed(self.broken.id, "needs the helper"),
        ]

    def close(self) -> None:
        """Nothing to close."""


@pytest.fixture
def client() -> TestClient:
    """Return a client over the real application, with the worker running."""
    service = SensorService([SteadyCollector()], hz=10.0)
    service.discover()
    with TestClient(build_app(service)) as running:
        yield running


def test_the_catalogue_is_served(client: TestClient) -> None:
    body = client.get("/api/catalogue").json()
    assert body["machine"] == "dst-gova-pc"
    assert len(body["channels"]) == 2


def test_one_frame_can_be_fetched_without_the_stream(client: TestClient) -> None:
    body = client.get("/api/frame").json()
    assert len(body["v"]) == 2
    assert 44.5 in body["v"]


def test_the_stream_sends_a_frame_for_each_pass(client: TestClient) -> None:
    with client.websocket_connect("/ws") as socket:
        first = socket.receive_json()
        second = socket.receive_json()
    assert 44.5 in first["v"]
    assert second["t"] >= first["t"]


def test_the_rate_can_be_changed_and_comes_back_in_the_frame(client: TestClient) -> None:
    assert client.post("/api/rate", json={"hz": 1.0}).json() == {"hz": 1.0}
    assert client.get("/api/frame").json()["hz"] == 1.0


def test_a_rate_outside_the_limits_is_refused_by_the_model(client: TestClient) -> None:
    assert client.post("/api/rate", json={"hz": 99.0}).status_code == 422
    assert client.post("/api/rate", json={"hz": 0.0}).status_code == 422


def test_pausing_and_resuming_is_reported(client: TestClient) -> None:
    assert client.post("/api/pause", json={"paused": True}).json() == {"paused": True}
    assert client.get("/api/frame").json()["paused"] is True
    assert client.post("/api/pause", json={"paused": False}).json() == {"paused": False}


def test_a_rescan_gives_the_catalogue_back(client: TestClient) -> None:
    body = client.post("/api/rescan").json()
    assert len(body["channels"]) == 2


def test_an_unknown_route_answers_with_json_not_html(client: TestClient) -> None:
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert response.json() == {"error": "no such route"}


def test_the_shell_and_the_gallery_are_served(client: TestClient) -> None:
    assert client.get("/").status_code == 200
    assert "component review" in client.get("/gallery").text


def test_the_static_files_are_served(client: TestClient) -> None:
    for path in ("/static/widgets.js", "/static/widgets.css", "/static/tokens.css"):
        assert client.get(path).status_code == 200


def test_no_route_offers_a_way_to_write_to_hardware(client: TestClient) -> None:
    """ADR 0007. The only routes that change anything change the reading rate.

    This reads the application's own schema rather than a list written by
    hand, so a route added later is caught here.
    """
    schema = client.get("/openapi.json").json()
    writing = {path for path, methods in schema["paths"].items() if {"post", "put", "patch", "delete"} & set(methods)}
    assert writing == {"/api/rate", "/api/pause", "/api/rescan"}


def test_static_files_tell_the_browser_to_check_them_again(client: TestClient) -> None:
    """A stale widgets.js was served after a change; the page must not lag the code."""
    for route in ("/", "/gallery", "/static/widgets.js"):
        assert client.get(route).headers["cache-control"] == "no-cache", route


def test_the_alert_log_is_served_newest_first(client: TestClient) -> None:
    response = client.get("/api/alerts")
    assert response.status_code == 200
    body = response.json()
    assert body["alerts"] == []
    assert body["open"] == 0
    assert body["total"] == 0
