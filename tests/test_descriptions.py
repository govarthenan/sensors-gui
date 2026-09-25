"""Tests for the channel descriptions that the tooltips show.

`docs/gui-goal.md` section 4.2 sets the rule these tests hold: every sentence
about the hardware needs a source under `docs/`, `lab/` or `data/`, and a fact
with no source says "not established". So the tests check the sources exist
as files, not only that a description is present.

There is no mock. The coverage test runs against the real RTX 4090 and skips
when NVML cannot start, as `tests/test_nvidia_collector.py` does.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sensors_gui.descriptions import DERIVED, NOT_COLLECTED, UNREACHABLE, Description, describe
from sensors_gui.model import Group, SensorId, SensorSpec, Unit

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOTS = ("docs/", "lab/", "data/", "src/")

# Every channel the NVIDIA collector builds on this card: 20 fixed channels and
# an RPM and a percent channel for each of the 2 fans (exp-0013). Three were
# added on 2026-09-23, on Gova's answer to Q13 (exp-0016).
GPU_CHANNELS = (
    "temperature",
    "power",
    "energy",
    "fan_speed",
    "utilization",
    "memory_utilization",
    "memory_used",
    "memory_reserved",
    "clock_sm",
    "clock_memory",
    "encoder_utilization",
    "decoder_utilization",
    "pcie_tx",
    "pcie_rx",
    "performance_state",
    "graphics_processes",
    "compute_processes",
    "clock_event_reasons",
    "pcie_link_gen",
    "pcie_link_width",
    "fan0_rpm",
    "fan0_percent",
    "fan1_rpm",
    "fan1_percent",
)


def _gpu_spec(channel: str) -> SensorSpec:
    """Build the spec of one card channel, as the collector names it."""
    return SensorSpec(
        id=SensorId(source="nvidia", device="NVIDIA GeForce RTX 4090@00000000:01:00.0", channel=channel),
        label=channel,
        group=Group.GPU,
        unit=Unit.NONE,
    )


def _machine_specs(groups: tuple[Group, ...]) -> list[SensorSpec]:
    """Return the specs the real collectors find on this machine, in the given groups.

    The fixture is the hardware, as for the card: what the collectors find, the
    tooltips must cover. The helper's channels are discovered even when the
    helper is not running (ADR 0005 rule 3), so none of these needs root.
    """
    from sensors_gui.collectors.hwmon import HwmonCollector
    from sensors_gui.collectors.memory_pressure import MemoryPressureCollector
    from sensors_gui.collectors.privileged import PrivilegedCollector
    from sensors_gui.collectors.system import SystemCollector

    specs: list[SensorSpec] = []
    for collector in (HwmonCollector(), PrivilegedCollector(), SystemCollector(), MemoryPressureCollector()):
        try:
            specs.extend(spec for spec in collector.discover() if spec.group in groups)
        finally:
            collector.close()
    return specs


def _all_descriptions() -> list[Description]:
    """Return the description of every card channel, and of every processor and memory channel here."""
    found = [describe(_gpu_spec(channel)) for channel in GPU_CHANNELS]
    found += [describe(spec) for spec in _machine_specs((Group.CPU, Group.MEMORY))]
    return [description for description in found if description is not None]


@pytest.mark.parametrize("channel", GPU_CHANNELS)
def test_describe_every_card_channel_has_a_description(channel: str) -> None:
    assert describe(_gpu_spec(channel)) is not None


@pytest.mark.parametrize("channel", GPU_CHANNELS)
def test_describe_every_card_channel_names_the_call_it_is_read_with(channel: str) -> None:
    description = describe(_gpu_spec(channel))
    assert description is not None
    assert description.call.startswith("nvmlDevice")


def test_describe_a_channel_of_another_group_has_no_description_yet() -> None:
    """The card, the processor and the memory are described by checkpoint 4. The board is not yet; none is guessed."""
    spec = SensorSpec(
        id=SensorId(source="hwmon", device="nct6687@/sys/devices/platform/nct6687.2592", channel="fan1"),
        label="CPU Fan",
        group=Group.BOARD,
        unit=Unit.RPM,
    )
    assert describe(spec) is None


def test_describe_a_third_fan_that_this_card_does_not_have_is_not_described() -> None:
    """The text of a fan names the two fans NVML reports. A third fan would make it false."""
    assert describe(_gpu_spec("fan2_rpm")) is None


def test_describe_the_fan_text_carries_the_fan_number_a_person_reads() -> None:
    first = describe(_gpu_spec("fan0_rpm"))
    second = describe(_gpu_spec("fan1_percent"))
    assert first is not None and second is not None
    assert "fan 1" in first.measures
    assert "fan 2" in second.measures


def test_every_description_has_a_sentence_and_at_least_one_source() -> None:
    for description in _all_descriptions():
        assert description.measures.strip().endswith(".")
        assert description.sources


def test_every_source_of_a_description_is_a_file_in_this_repository() -> None:
    """A source that is not a file is a link, and CLAUDE.md says copy evidence, never link."""
    for description in _all_descriptions():
        for source in description.sources:
            assert source.startswith(EVIDENCE_ROOTS), source
            assert (ROOT / source).is_file(), source


def test_the_edge_sensor_says_the_other_three_temperatures_cannot_be_read() -> None:
    edge = describe(_gpu_spec("temperature"))
    assert edge is not None
    assert "ADR 0011" in edge.neighbours
    for part in ("hotspot", "memory", "VRM"):
        assert part in edge.neighbours


def test_the_three_unreadable_card_temperatures_are_listed_with_a_reason() -> None:
    labels = {entry.label for entry in UNREACHABLE if entry.group is Group.GPU}
    assert labels == {"GPU hotspot", "GPU memory (GDDR6X)", "GPU VRM"}
    for entry in UNREACHABLE:
        assert entry.reason.strip().endswith(".")
        assert "docs/decisions/0011-no-i2c-route-to-the-graphics-card.md" in entry.sources


def test_nothing_the_card_gives_is_left_uncollected() -> None:
    """Q13 is answered: the clock event reasons and the PCIe link are channels now."""
    assert [entry for entry in NOT_COLLECTED if entry.group is Group.GPU] == []


def test_every_source_of_a_missing_value_is_a_file_in_this_repository() -> None:
    for entry in (*UNREACHABLE, *NOT_COLLECTED):
        for source in entry.sources:
            assert source.startswith(EVIDENCE_ROOTS), source
            assert (ROOT / source).is_file(), source


def test_as_dict_gives_the_front_end_every_part_of_the_tooltip() -> None:
    description = describe(_gpu_spec("power"))
    assert description is not None
    shown = description.as_dict()
    assert set(shown) == {"measures", "call", "neighbours", "sources"}
    assert isinstance(shown["sources"], list)


def test_every_channel_the_real_card_reports_is_described() -> None:
    """The fixture is the hardware: what the collector finds, the tooltips must cover."""
    pytest.importorskip("pynvml")
    from sensors_gui.collectors.nvidia import NvidiaCollector

    collector = NvidiaCollector()
    try:
        specs = collector.discover()
        if not specs:
            pytest.skip("no NVIDIA GPU, or NVML did not start")
        missing = [spec.id.channel for spec in specs if describe(spec) is None]
    finally:
        collector.close()
    assert missing == []


# --- the processor and the memory, checkpoint 4 --------------------------------


def _one(label: str) -> Description:
    """Return the description of the channel with this label on this machine."""
    from sensors_gui.naming import friendly

    for spec in _machine_specs((Group.CPU, Group.MEMORY)):
        if friendly(spec).label == label:
            description = describe(spec)
            assert description is not None, label
            return description
    pytest.skip(f"{label} is not on this machine")


def test_every_processor_and_memory_channel_on_this_machine_is_described() -> None:
    """Checkpoint 4: all 88 channels of the two groups, from the real collectors."""
    specs = _machine_specs((Group.CPU, Group.MEMORY))
    if not specs:
        pytest.skip("no processor or memory channel found")
    missing = [spec.id.key for spec in specs if describe(spec) is None]
    assert missing == []


def test_every_processor_and_memory_description_names_the_call_or_path() -> None:
    for spec in _machine_specs((Group.CPU, Group.MEMORY)):
        description = describe(spec)
        assert description is not None and description.call.strip(), spec.id.key


def test_tctl_says_how_it_differs_from_the_two_die_sensors() -> None:
    tctl = _one("Tctl")
    assert "Tccd1" in tctl.neighbours and "Tccd2" in tctl.neighbours


def test_each_die_sensor_names_the_cores_on_its_die() -> None:
    assert "0-5" in _one("Tccd1").neighbours
    assert "8-13" in _one("Tccd2").neighbours


def test_the_rapl_core_domain_says_it_is_core_0_alone() -> None:
    rapl = _one("CPU Core 0 (RAPL) Power")
    assert "core 0" in rapl.measures.lower() or "core 0" in rapl.neighbours.lower()
    assert "register" in rapl.neighbours


def test_a_core_power_names_its_core_and_its_die() -> None:
    first = _one("CPU Core 0 Power")
    last = _one("CPU Core 13 Power")
    assert "core 0" in first.measures and "die 1" in first.neighbours
    assert "core 13" in last.measures and "die 2" in last.neighbours


def test_a_thread_names_the_other_thread_of_its_core() -> None:
    """The sibling is 12 away: cpu0 and cpu12 are one core (the topology probe)."""
    assert "cpu12" in _one("CPU0 use").neighbours
    assert "cpu11" in _one("CPU23 frequency").neighbours


def test_each_dimm_names_its_slot_and_its_address() -> None:
    a2 = _one("DIMM A2")
    b2 = _one("DIMM B2")
    assert "A2" in a2.measures and "0-0051" in a2.neighbours
    assert "B2" in b2.measures and "0-0053" in b2.neighbours


# --- values a view makes from two channels, 2026-09-25 --------------------------


def test_the_memory_the_kernel_can_take_back_is_described_as_made_from_two_channels() -> None:
    """The middle part of the memory bar is no channel; its tooltip must say what it is made from."""
    description = DERIVED["memory_reclaimable"]
    assert "Memory available" in description.call
    assert "Memory free" in description.call
    assert description.measures.strip().endswith(".")


def test_every_source_of_a_derived_value_is_a_file_in_this_repository() -> None:
    assert DERIVED
    for description in DERIVED.values():
        for source in description.sources:
            assert source.startswith(EVIDENCE_ROOTS), source
            assert (ROOT / source).is_file(), source
