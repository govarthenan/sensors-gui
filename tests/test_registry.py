"""Tests for `Registry`.

No mocks. Every collector here is a small real class that implements the
`Collector` protocol - a fake, not a mock - as `tests/conftest.py` and
`docs/phase-3-plan.md` require.
"""

from __future__ import annotations

from sensors_gui.model import Group, Reading, SensorId, SensorSpec, Unit
from sensors_gui.registry import Registry


class FakeCollector:
    """A collector whose specs and readings are set up entirely by the test."""

    def __init__(
        self,
        name: str,
        specs: list[SensorSpec] | None = None,
        readings: list[list[Reading]] | None = None,
        *,
        fail_discover: bool = False,
        fail_read: bool = False,
        fail_close: bool = False,
    ) -> None:
        """Create the fake.

        Args:
            name: The collector name.
            specs: What `discover()` returns.
            readings: One list of readings per call to `read()`. The last
                entry repeats once the list is exhausted.
            fail_discover: Raise from `discover()` instead of returning.
            fail_read: Raise from `read()` instead of returning.
            fail_close: Raise from `close()` instead of returning.
        """
        self.name = name
        self._specs = specs or []
        self._readings = readings or []
        self._read_calls = 0
        self.fail_discover = fail_discover
        self.fail_read = fail_read
        self.fail_close = fail_close
        self.discover_calls = 0
        self.close_calls = 0

    def discover(self) -> list[SensorSpec]:
        """Return the specs set up by the test, or raise when asked to."""
        self.discover_calls += 1
        if self.fail_discover:
            raise RuntimeError(f"{self.name}: discovery failed")
        return self._specs

    def read(self) -> list[Reading]:
        """Return the next configured readings, or raise when asked to."""
        if self.fail_read:
            raise RuntimeError(f"{self.name}: read failed")
        if not self._readings:
            return []
        index = min(self._read_calls, len(self._readings) - 1)
        self._read_calls += 1
        return self._readings[index]

    def close(self) -> None:
        """Record the call, or raise when asked to."""
        self.close_calls += 1
        if self.fail_close:
            raise RuntimeError(f"{self.name}: close failed")


def _spec(source: str, channel: str, group: Group = Group.OTHER, unit: Unit = Unit.CELSIUS) -> SensorSpec:
    """Build a minimal spec for a test."""
    return SensorSpec(id=SensorId(source=source, device="dev", channel=channel), label=channel, group=group, unit=unit)


def test_discover_collects_specs_from_every_collector() -> None:
    cpu = FakeCollector("cpu", specs=[_spec("cpu", "temp1", group=Group.CPU)])
    gpu = FakeCollector("gpu", specs=[_spec("gpu", "temp1", group=Group.GPU)])
    registry = Registry([cpu, gpu])

    registry.discover()

    assert {spec.id.source for spec in registry.specs()} == {"cpu", "gpu"}
    assert len(registry.specs()) == 2


def test_spec_returns_the_matching_spec() -> None:
    spec = _spec("cpu", "temp1")
    registry = Registry([FakeCollector("cpu", specs=[spec])])
    registry.discover()

    assert registry.spec(spec.id) == spec


def test_spec_returns_none_for_an_unknown_id() -> None:
    registry = Registry([FakeCollector("cpu", specs=[_spec("cpu", "temp1")])])
    registry.discover()

    assert registry.spec(SensorId(source="ghost", device="nowhere", channel="temp1")) is None


def test_by_group_groups_specs_by_their_group() -> None:
    cpu = FakeCollector("cpu", specs=[_spec("cpu", "temp1", group=Group.CPU), _spec("cpu", "temp2", group=Group.CPU)])
    gpu = FakeCollector("gpu", specs=[_spec("gpu", "temp1", group=Group.GPU)])
    registry = Registry([cpu, gpu])
    registry.discover()

    grouped = registry.by_group()

    assert len(grouped[Group.CPU]) == 2
    assert len(grouped[Group.GPU]) == 1
    assert Group.MEMORY not in grouped


def test_a_collector_that_raises_in_discover_is_skipped_not_fatal() -> None:
    broken = FakeCollector("broken", fail_discover=True)
    working = FakeCollector("working", specs=[_spec("working", "temp1")])
    registry = Registry([broken, working])

    registry.discover()  # must not raise

    assert len(registry.specs()) == 1
    assert registry.specs()[0].id.source == "working"


def test_a_rescan_reflects_the_new_state_not_the_old_one() -> None:
    collector = FakeCollector("cpu", specs=[_spec("cpu", "temp1")])
    registry = Registry([collector])
    registry.discover()
    assert len(registry.specs()) == 1

    collector._specs = [_spec("cpu", "temp1"), _spec("cpu", "temp2")]
    registry.discover()

    assert len(registry.specs()) == 2


def test_close_closes_every_collector() -> None:
    cpu = FakeCollector("cpu")
    gpu = FakeCollector("gpu")
    registry = Registry([cpu, gpu])

    registry.close()

    assert cpu.close_calls == 1
    assert gpu.close_calls == 1


def test_close_of_one_collector_does_not_stop_the_rest() -> None:
    broken = FakeCollector("broken", fail_close=True)
    working = FakeCollector("working")
    registry = Registry([broken, working])

    registry.close()  # must not raise

    assert broken.close_calls == 1
    assert working.close_calls == 1


def test_read_all_returns_readings_from_every_collector() -> None:
    id_a = SensorId(source="cpu", device="dev", channel="temp1")
    id_b = SensorId(source="gpu", device="dev", channel="temp1")
    cpu = FakeCollector("cpu", specs=[_spec("cpu", "temp1")], readings=[[Reading.ok(id_a, 41.0)]])
    gpu = FakeCollector("gpu", specs=[_spec("gpu", "temp1")], readings=[[Reading.ok(id_b, 55.0)]])
    registry = Registry([cpu, gpu])
    registry.discover()

    readings = registry.read_all()

    assert {reading.id for reading in readings} == {id_a, id_b}


def test_read_all_defends_against_a_collector_that_raises_in_read() -> None:
    # read() is contractually not allowed to raise, but the registry must
    # defend anyway: one broken collector must never stop the rest.
    id_b = SensorId(source="gpu", device="dev", channel="temp1")
    broken = FakeCollector("broken", specs=[_spec("broken", "temp1")], fail_read=True)
    working = FakeCollector("gpu", specs=[_spec("gpu", "temp1")], readings=[[Reading.ok(id_b, 55.0)]])
    registry = Registry([broken, working])
    registry.discover()

    readings = registry.read_all()  # must not raise

    assert {reading.id for reading in readings} == {id_b}
