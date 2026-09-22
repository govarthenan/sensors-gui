"""Tests for the screen itself, driven through Textual's own test pilot.

There is no mock. A small real collector stands in for the hardware, so the
test controls the values without pretending to be the application.
"""

from __future__ import annotations

import pytest

from sensors_gui.app.panel import GROUP_TITLES, GroupPanel
from sensors_gui.app.sensors_app import SensorsApp
from sensors_gui.model import Group, Reading, SensorId, SensorSpec, Unit

pytestmark = pytest.mark.asyncio


class FakeCollector:
    """A real collector that reports values a test sets. Not a mock."""

    name = "fake"

    def __init__(self) -> None:
        """Start with a CPU temperature, a fan and a GPU power channel."""
        self.specs = [
            SensorSpec(
                id=SensorId(source="fake", device="cpu@/sys/x", channel="temp1"),
                label="Tctl",
                group=Group.CPU,
                unit=Unit.CELSIUS,
                low=0.0,
                high=100.0,
                warn=80.0,
                critical=95.0,
            ),
            SensorSpec(
                id=SensorId(source="fake", device="board@/sys/y", channel="fan1"),
                label="CPU Fan",
                group=Group.BOARD,
                unit=Unit.RPM,
                low=0.0,
                high=3000.0,
            ),
            SensorSpec(
                id=SensorId(source="fake", device="gpu@/sys/z", channel="power"),
                label="GPU power",
                group=Group.GPU,
                unit=Unit.WATT,
                low=0.0,
                high=480.0,
            ),
        ]
        self.values: dict[str, float | None] = {"temp1": 41.0, "fan1": 2200.0, "power": 38.0}
        self.closed = False
        self.reads = 0

    def discover(self) -> list[SensorSpec]:
        """Return the fixed set of sensors."""
        return list(self.specs)

    def read(self) -> list[Reading]:
        """Return the values the test last set."""
        self.reads += 1
        return [Reading.ok(spec.id, self.values[spec.id.channel], read_at=0.0) for spec in self.specs]  # type: ignore[arg-type]

    def close(self) -> None:
        """Record that the application closed us."""
        self.closed = True


class BrokenCollector:
    """A collector that fails at every step, to prove one bad source is survivable."""

    name = "broken"

    def discover(self) -> list[SensorSpec]:
        """Fail."""
        raise RuntimeError("no device")

    def read(self) -> list[Reading]:
        """Fail."""
        raise RuntimeError("no device")

    def close(self) -> None:
        """Fail."""
        raise RuntimeError("no device")


async def test_the_screen_shows_a_panel_for_each_group_that_has_sensors() -> None:
    app = SensorsApp([FakeCollector()])
    async with app.run_test():
        titles = {panel.border_title for panel in app.query(GroupPanel)}
    assert titles == {GROUP_TITLES[Group.CPU], GROUP_TITLES[Group.GPU], GROUP_TITLES[Group.BOARD]}


async def test_the_panels_appear_in_the_fixed_group_order() -> None:
    app = SensorsApp([FakeCollector()])
    async with app.run_test():
        groups = [panel.group for panel in app.query(GroupPanel)]
    assert groups == [Group.CPU, Group.GPU, Group.BOARD]


async def test_a_value_reaches_the_screen() -> None:
    collector = FakeCollector()
    app = SensorsApp([collector])
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#panel-cpu", GroupPanel)
        assert "41.0 °C" in panel.render_rows().plain


async def test_a_changed_value_reaches_the_screen_on_the_next_refresh() -> None:
    collector = FakeCollector()
    app = SensorsApp([collector], hz=50.0)
    async with app.run_test() as pilot:
        collector.values["temp1"] = 77.5
        await pilot.pause(0.1)
        panel = app.query_one("#panel-cpu", GroupPanel)
        assert "77.5 °C" in panel.render_rows().plain


async def test_the_first_reading_is_taken_and_discarded() -> None:
    # exp-0007 finding 4: the nct6687 driver reports zeros until it has updated
    # once, so the first pass after discovery must not be shown.
    collector = FakeCollector()
    app = SensorsApp([collector])
    async with app.run_test() as pilot:
        await pilot.pause()
    assert collector.reads >= 2


async def test_pausing_stops_the_screen_from_reading() -> None:
    collector = FakeCollector()
    app = SensorsApp([collector], hz=50.0)
    async with app.run_test() as pilot:
        await pilot.press("p")
        await pilot.pause()
        before = collector.reads
        await pilot.pause(0.2)
        assert collector.reads == before
        assert "paused" in app.sub_title


async def test_unpausing_starts_it_again() -> None:
    collector = FakeCollector()
    app = SensorsApp([collector], hz=50.0)
    async with app.run_test() as pilot:
        await pilot.press("p")
        await pilot.press("p")
        before = collector.reads
        await pilot.pause(0.2)
        assert collector.reads > before


async def test_one_broken_collector_does_not_stop_the_others() -> None:
    collector = FakeCollector()
    app = SensorsApp([BrokenCollector(), collector])
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#panel-cpu", GroupPanel)
        assert "41.0 °C" in panel.render_rows().plain


async def test_every_collector_is_closed_when_the_screen_stops() -> None:
    collector = FakeCollector()
    app = SensorsApp([collector])
    async with app.run_test():
        pass
    assert collector.closed is True


async def test_a_collector_that_raises_on_close_does_not_stop_the_others() -> None:
    collector = FakeCollector()
    app = SensorsApp([BrokenCollector(), collector])
    async with app.run_test():
        pass
    assert collector.closed is True


async def test_the_refresh_rate_can_be_changed_from_the_keyboard() -> None:
    app = SensorsApp([FakeCollector()], hz=2.0)
    async with app.run_test() as pilot:
        await pilot.press("plus")
        assert app._hz == 4.0  # noqa: SLF001 - the test checks internal state on purpose
        await pilot.press("minus")
        await pilot.press("minus")
        assert app._hz == 1.0  # noqa: SLF001


async def test_the_refresh_rate_is_bounded_at_both_ends() -> None:
    app = SensorsApp([FakeCollector()], hz=2.0)
    async with app.run_test() as pilot:
        for _ in range(8):
            await pilot.press("plus")
        assert app._hz == 10.0  # noqa: SLF001
        for _ in range(10):
            await pilot.press("minus")
        assert app._hz == 0.25  # noqa: SLF001
