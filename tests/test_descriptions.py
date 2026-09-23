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

from sensors_gui.descriptions import NOT_COLLECTED, UNREACHABLE, Description, describe
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


def _all_descriptions() -> list[Description]:
    """Return the description of every card channel."""
    found = [describe(_gpu_spec(channel)) for channel in GPU_CHANNELS]
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
    """Only the graphics card is described at checkpoint 3. The rest say so; none is guessed."""
    spec = SensorSpec(
        id=SensorId(source="hwmon", device="k10temp@/sys/devices/pci0000:00/0000:00:18.3", channel="temp1"),
        label="Tctl",
        group=Group.CPU,
        unit=Unit.CELSIUS,
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
