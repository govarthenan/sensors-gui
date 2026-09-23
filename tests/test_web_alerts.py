"""Tests for the alert log: a reading outside the scale its spec publishes.

Gova, 2026-09-23: "If we get a reading higher than the recognized ceiling, what
happens then? ... Log an alert on a seperate screen." The ceiling is the spec's
`high`, and the floor its `low`. A channel that publishes neither can never
alert, because the application does not invent a limit.

There is no mock. The specs and readings are the real dataclasses, and the
time is passed in, so a test can say what happens five seconds later.
"""

from __future__ import annotations

from sensors_gui.model import Group, Reading, SensorId, SensorSpec, Unit
from sensors_gui.web.alerts import ABOVE, BELOW, AlertLog

POWER = SensorSpec(
    id=SensorId(source="nvidia", device="card@01:00.0", channel="power"),
    label="GPU power",
    group=Group.GPU,
    unit=Unit.WATT,
    low=0.0,
    high=480.0,
)
FAN = SensorSpec(
    id=SensorId(source="nvidia", device="card@01:00.0", channel="fan0_rpm"),
    label="GPU fan 1",
    group=Group.GPU,
    unit=Unit.RPM,
    low=0.0,
)
TCTL = SensorSpec(
    id=SensorId(source="hwmon", device="k10temp@/sys/x", channel="temp1"),
    label="Tctl",
    group=Group.CPU,
    unit=Unit.CELSIUS,
)


def observe(log: AlertLog, now: float, **values: float | None) -> None:
    """Show the log one pass: `power=500.0` sets the GPU power reading, and so on."""
    specs = {"power": POWER, "fan": FAN, "tctl": TCTL}
    readings = []
    for name, value in values.items():
        spec = specs[name]
        readings.append(Reading.failed(spec.id, "gone") if value is None else Reading.ok(spec.id, value, read_at=now))
    log.observe([POWER, FAN, TCTL], readings, now)


def test_observe_a_reading_inside_the_scale_logs_nothing() -> None:
    log = AlertLog()
    observe(log, 100.0, power=250.0)
    assert log.entries() == []


def test_observe_a_reading_above_the_ceiling_opens_one_alert() -> None:
    log = AlertLog()
    observe(log, 100.0, power=512.5)
    [alert] = log.entries()
    assert alert["label"] == "GPU power"
    assert alert["kind"] == ABOVE
    assert alert["limit"] == 480.0
    assert alert["peak"] == 512.5
    assert alert["started"] == 100.0
    assert alert["ended"] is None


def test_observe_a_reading_at_the_ceiling_is_not_above_it() -> None:
    log = AlertLog()
    observe(log, 100.0, power=480.0)
    assert log.entries() == []


def test_observe_a_long_excursion_is_one_alert_with_its_peak_and_its_length() -> None:
    log = AlertLog()
    observe(log, 100.0, power=490.0)
    observe(log, 101.0, power=530.0)
    observe(log, 102.0, power=500.0)
    [alert] = log.entries()
    assert alert["peak"] == 530.0
    assert alert["last"] == 500.0
    assert alert["passes"] == 3


def test_observe_a_reading_back_inside_closes_the_alert() -> None:
    log = AlertLog()
    observe(log, 100.0, power=490.0)
    observe(log, 101.0, power=300.0)
    [alert] = log.entries()
    assert alert["ended"] == 101.0
    assert log.open_count() == 0


def test_observe_a_return_within_the_merge_window_reopens_the_same_alert() -> None:
    """A value that rattles on the ceiling must not fill the screen with one-pass alerts."""
    log = AlertLog(merge_seconds=5.0)
    observe(log, 100.0, power=490.0)
    observe(log, 101.0, power=470.0)
    observe(log, 103.0, power=495.0)
    [alert] = log.entries()
    assert alert["ended"] is None
    assert alert["peak"] == 495.0


def test_observe_a_return_after_the_merge_window_opens_a_new_alert() -> None:
    log = AlertLog(merge_seconds=5.0)
    observe(log, 100.0, power=490.0)
    observe(log, 101.0, power=470.0)
    observe(log, 120.0, power=495.0)
    newest, oldest = log.entries()
    assert newest["started"] == 120.0
    assert oldest["ended"] == 101.0


def test_observe_a_reading_below_the_floor_is_logged_as_below() -> None:
    log = AlertLog()
    observe(log, 100.0, power=-3.0)
    [alert] = log.entries()
    assert alert["kind"] == BELOW
    assert alert["limit"] == 0.0
    assert alert["peak"] == -3.0


def test_observe_a_channel_with_no_ceiling_never_alerts() -> None:
    """Tctl publishes no scale. 120 °C is alarming to a person, and still not a ceiling."""
    log = AlertLog()
    observe(log, 100.0, tctl=120.0, fan=9000.0)
    assert log.entries() == []


def test_observe_a_failed_read_neither_opens_nor_closes_an_alert() -> None:
    log = AlertLog()
    observe(log, 100.0, power=490.0)
    observe(log, 101.0, power=None)
    [alert] = log.entries()
    assert alert["ended"] is None


def test_observe_the_log_keeps_only_the_newest_entries() -> None:
    log = AlertLog(capacity=3, merge_seconds=0.0)
    for second in range(5):
        observe(log, 100.0 + second * 2, power=490.0)
        observe(log, 101.0 + second * 2, power=100.0)
    entries = log.entries()
    assert len(entries) == 3
    assert entries[0]["started"] == 108.0


def test_observe_counts_every_alert_ever_opened_even_after_the_oldest_are_dropped() -> None:
    log = AlertLog(capacity=2, merge_seconds=0.0)
    for second in range(4):
        observe(log, 100.0 + second * 2, power=490.0)
        observe(log, 101.0 + second * 2, power=100.0)
    assert log.total() == 4


def test_observe_a_hidden_channel_is_not_watched() -> None:
    """A channel the BIOS proved wrong is hidden; its value would raise false alerts."""
    log = AlertLog()
    log.observe([POWER], [Reading.ok(POWER.id, 999.0, read_at=1.0)], 1.0, hidden={POWER.id})
    assert log.entries() == []


def test_observe_a_margin_lets_a_reading_just_past_the_ceiling_go_unlogged() -> None:
    """Gova, 2026-09-23: CPU frequencies are logged only past 110 % of the ceiling or 90 % of the floor."""
    log = AlertLog(margin=lambda spec: 0.10 if spec.id == POWER.id else 0.0)
    observe(log, 100.0, power=520.0)
    assert log.entries() == []
    observe(log, 101.0, power=530.0)
    [alert] = log.entries()
    assert alert["limit"] == 480.0
    assert alert["margin"] == 0.10


def test_observe_a_margin_applies_below_the_floor_too() -> None:
    """The margin is relative to the limit itself: 90 % of a 614 MHz floor is 552.6 MHz."""
    frequency = SensorSpec(
        id=SensorId(source="system", device="cpu", channel="core9_frequency"),
        label="CPU9 frequency",
        group=Group.CPU,
        unit=Unit.HERTZ,
        low=613_954_000.0,
        high=5_662_016_000.0,
    )
    log = AlertLog(margin=lambda spec: 0.10)
    log.observe([frequency], [Reading.ok(frequency.id, 560e6, read_at=1.0)], 1.0)
    assert log.entries() == []
    log.observe([frequency], [Reading.ok(frequency.id, 500e6, read_at=2.0)], 2.0)
    [alert] = log.entries()
    assert alert["kind"] == BELOW
