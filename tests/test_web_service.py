"""Tests for the sampling service behind the web front end.

There is no mock. A small real collector stands in for the hardware, so the
test controls the values without pretending to be the application, and the
service under test is the real one: a real registry, a real sampler and a real
worker thread.
"""

from __future__ import annotations

import threading
import time
from dataclasses import replace

import pytest

from sensors_gui.model import Group, Reading, SensorId, SensorSpec, Unit
from sensors_gui.web.service import MAX_HZ, MIN_HZ, PassTimes, SensorService


class RecordingCollector:
    """A real collector that reports values a test sets. Not a mock."""

    name = "recording"

    def __init__(self) -> None:
        """Start with a temperature that has thresholds, a fan and a broken channel."""
        self.temperature = SensorSpec(
            id=SensorId(source="recording", device="cpu@/sys/a", channel="temp1"),
            label="Tctl",
            group=Group.CPU,
            unit=Unit.CELSIUS,
            low=0.0,
            high=100.0,
            warn=80.0,
            critical=95.0,
            origin="/sys/a/temp1_input",
        )
        self.fan = SensorSpec(
            id=SensorId(source="recording", device="board@/sys/b", channel="fan1"),
            label="CPU Fan",
            group=Group.BOARD,
            unit=Unit.RPM,
        )
        self.broken = SensorSpec(
            id=SensorId(source="recording", device="helper@/run/x", channel="power1"),
            label="CPU Package Power",
            group=Group.CPU,
            unit=Unit.WATT,
        )
        self.values = {self.temperature.id: 41.0, self.fan.id: 1500.0}
        self.reads = 0

    def discover(self) -> list[SensorSpec]:
        """Report the three channels."""
        return [self.temperature, self.fan, self.broken]

    def read(self) -> list[Reading]:
        """Report the values a test set, and one channel that always fails."""
        self.reads += 1
        return [
            Reading.ok(self.temperature.id, self.values[self.temperature.id], read_at=time.monotonic()),
            Reading.ok(self.fan.id, self.values[self.fan.id], read_at=time.monotonic()),
            Reading.failed(self.broken.id, "needs the helper"),
        ]

    def close(self) -> None:
        """Nothing to close."""


@pytest.fixture
def collector() -> RecordingCollector:
    """Return a fresh collector."""
    return RecordingCollector()


@pytest.fixture
def service(collector: RecordingCollector) -> SensorService:
    """Return a discovered service that has not started its worker."""
    built = SensorService([collector], hz=10.0)
    built.discover()
    return built


def test_discover_gives_every_channel_a_stable_index(service: SensorService) -> None:
    indexes = [channel.index for channel in service.channels()]
    assert indexes == list(range(len(indexes)))


def test_catalogue_reports_the_counts_and_every_channel(service: SensorService) -> None:
    catalogue = service.catalogue()
    assert catalogue["shown"] == 3
    assert catalogue["hidden"] == 0
    assert len(catalogue["channels"]) == 3
    assert {channel["label"] for channel in catalogue["channels"]} == {"Tctl", "CPU Fan", "CPU Package Power"}


def test_catalogue_carries_the_scale_and_the_thresholds(service: SensorService) -> None:
    catalogue = service.catalogue()
    temperature = next(row for row in catalogue["channels"] if row["label"] == "Tctl")
    assert temperature["low"] == 0.0
    assert temperature["high"] == 100.0
    assert temperature["warn"] == 80.0
    assert temperature["critical"] == 95.0
    assert temperature["symbol"] == "°C"


def test_a_channel_with_no_scale_says_so_rather_than_inventing_one(service: SensorService) -> None:
    catalogue = service.catalogue()
    fan = next(row for row in catalogue["channels"] if row["label"] == "CPU Fan")
    assert fan["low"] is None
    assert fan["high"] is None


def test_the_frame_holds_one_value_for_each_channel_in_catalogue_order(service: SensorService) -> None:
    frame = service.sample_once()
    channels = service.channels()
    assert len(frame["v"]) == len(channels)
    by_label = {channel.spec.label: channel.index for channel in channels}
    assert frame["v"][by_label["Tctl"]] == 41.0
    assert frame["v"][by_label["CPU Fan"]] == 1500.0


def test_a_failed_channel_carries_its_reason_and_never_a_zero(service: SensorService) -> None:
    frame = service.sample_once()
    index = next(channel.index for channel in service.channels() if channel.spec.label == "CPU Package Power")
    assert frame["v"][index] is None
    assert frame["errors"][str(index)] == "needs the helper"


def test_the_error_map_holds_only_the_channels_that_failed(service: SensorService) -> None:
    frame = service.sample_once()
    assert len(frame["errors"]) == 1


def test_the_frame_reports_the_median_and_the_maximum_pass_not_only_the_last(service: SensorService) -> None:
    for _ in range(5):
        service.sample_once()
    reported = service.sample_once()["pass"]
    assert set(reported) == {"last_ms", "median_ms", "max_ms"}
    assert reported["max_ms"] >= reported["median_ms"]


def test_hidden_channels_are_marked_and_never_dropped(collector: RecordingCollector) -> None:
    service = SensorService([collector], keep=lambda spec: spec.label != "CPU Fan")
    service.discover()
    catalogue = service.catalogue()
    assert catalogue["shown"] == 2
    assert catalogue["hidden"] == 1
    assert len(catalogue["channels"]) == 3
    fan = next(row for row in catalogue["channels"] if row["label"] == "CPU Fan")
    assert fan["hidden"] is True


def test_the_filter_judges_the_driver_label_before_the_naming_layer(collector: RecordingCollector) -> None:
    """A verdict keyed on the driver's label must survive the rename.

    `keep` is given the raw spec and `decorate` renames it afterwards. If the
    two ran in the other order, the filter would look for a label that no
    longer exists and would hide nothing.
    """
    service = SensorService(
        [collector],
        decorate=lambda spec: replace(spec, label=f"{spec.label} (renamed)"),
        keep=lambda spec: spec.label != "CPU Fan",
    )
    service.discover()
    catalogue = service.catalogue()
    assert catalogue["hidden"] == 1
    fan = next(row for row in catalogue["channels"] if row["label"] == "CPU Fan (renamed)")
    assert fan["hidden"] is True


def test_the_rate_is_held_between_the_two_limits(service: SensorService) -> None:
    assert service.set_rate(100.0) == MAX_HZ
    assert service.set_rate(0.001) == MIN_HZ
    assert service.set_rate(2.0) == 2.0


def test_pausing_stops_the_passes_and_resuming_starts_them(
    service: SensorService, collector: RecordingCollector
) -> None:
    service.set_rate(10.0)
    service.start()
    try:
        time.sleep(0.4)
        taken = collector.reads
        assert taken > 1
        service.set_paused(True)
        time.sleep(0.4)
        assert collector.reads - taken <= 1
        service.set_paused(False)
        time.sleep(0.4)
        assert collector.reads > taken + 1
    finally:
        service.stop()


def test_the_worker_hands_every_pass_to_its_subscribers(service: SensorService) -> None:
    seen: list[dict[str, object]] = []
    arrived = threading.Event()

    def record(frame: dict[str, object]) -> None:
        seen.append(frame)
        arrived.set()

    service.subscribe(record)
    service.start()
    try:
        assert arrived.wait(timeout=3.0)
    finally:
        service.stop()
    assert seen and "v" in seen[0]


def test_a_subscriber_that_raises_does_not_stop_the_worker(service: SensorService) -> None:
    survived: list[int] = []

    def explode(_: dict[str, object]) -> None:
        raise RuntimeError("this subscriber is broken on purpose")

    def count(_: dict[str, object]) -> None:
        survived.append(1)

    service.subscribe(explode)
    service.subscribe(count)
    service.start()
    try:
        time.sleep(0.5)
    finally:
        service.stop()
    assert len(survived) > 1


def test_unsubscribing_one_that_was_never_added_does_nothing(service: SensorService) -> None:
    service.unsubscribe(lambda frame: None)


def test_stopping_a_service_that_never_started_is_safe(service: SensorService) -> None:
    service.stop()


def test_starting_twice_runs_one_worker(service: SensorService) -> None:
    service.start()
    first = service._thread  # noqa: SLF001 - the test is about there being one thread
    service.start()
    try:
        assert service._thread is first  # noqa: SLF001
    finally:
        service.stop()


def test_pass_times_keeps_the_median_and_the_maximum() -> None:
    times = PassTimes(window=4)
    for value in (2.0, 2.0, 50.0, 2.0, 2.0, 2.0):
        times.record(value)
    assert times.max_ms == 50.0
    assert times.median_ms == 2.0
    assert times.last_ms == 2.0


def test_pass_times_before_the_first_pass_is_zero_not_an_error() -> None:
    assert PassTimes().median_ms == 0.0


def test_catalogue_gives_a_channel_with_no_description_a_null_not_a_guess(service: SensorService) -> None:
    """Only the graphics card is described at checkpoint 3; the others must say nothing."""
    catalogue = service.catalogue()
    assert all(row["description"] is None for row in catalogue["channels"])


def test_catalogue_carries_the_description_of_a_card_channel() -> None:
    spec = SensorSpec(
        id=SensorId(source="nvidia", device="NVIDIA GeForce RTX 4090@00000000:01:00.0", channel="power"),
        label="GPU power",
        group=Group.GPU,
        unit=Unit.WATT,
    )

    class OneChannel:
        """A real collector with the one card channel. Not a mock."""

        name = "nvidia"

        def discover(self) -> list[SensorSpec]:
            return [spec]

        def read(self) -> list[Reading]:
            return [Reading.ok(spec.id, 40.0, read_at=time.monotonic())]

        def close(self) -> None:
            """Nothing to close."""

    built = SensorService([OneChannel()], hz=10.0)
    built.discover()
    row = built.catalogue()["channels"][0]
    assert row["description"]["call"].startswith("nvmlDeviceGetPowerUsage")
    assert row["description"]["sources"]


def test_catalogue_lists_the_values_that_cannot_be_read_and_why(service: SensorService) -> None:
    catalogue = service.catalogue()
    labels = {entry["label"] for entry in catalogue["unreachable"]}
    assert "GPU hotspot" in labels
    assert all(entry["reason"] for entry in catalogue["unreachable"])
    assert {entry["label"] for entry in catalogue["not_collected"]} >= {"PCIe link"}
