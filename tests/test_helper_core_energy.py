"""Tests for the per-core energy source of `sensors-guid`. See `exp-0012`.

No mocks. The topology is a real directory tree, the MSR nodes are real sparse
files that the helper opens with `os.open` and reads with `os.pread`, and the
clock is a real callable that a test moves by hand.

The numbers are this machine's. One count is 1/65536 joules, because
`0xc0010299` on `dst-gova-pc` reads `a1000`, so ESU is 16.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import REAL_JOULES_PER_COUNT, FakeCpus, FakeNvme, FakePowercap

from sensors_gui.helper.sensors_guid import (
    CORE_COUNTER_SPAN,
    Catalogue,
    CoreEnergySampler,
    NvmeSampler,
    RaplSampler,
    read_cpu_vendor_and_family,
)


class FakeClock:
    """A clock a test moves by hand. It is a real callable, not a mock."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        """Return the time this clock is stopped at."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the clock forward."""
        self.now += seconds


def make_sampler(cpus: FakeCpus, clock: FakeClock) -> CoreEnergySampler:
    """Return a sampler pointed at a temporary machine."""
    return CoreEnergySampler(
        cpu_sys_root=cpus.cpu_sys_root,
        msr_root=cpus.msr_root,
        cpuinfo_path=cpus.cpuinfo_path,
        clock=clock,
    )


def primed(cpus: FakeCpus, clock: FakeClock) -> CoreEnergySampler:
    """Return a sampler whose counters all stand at a known zero.

    The first sample is what makes the sampler read the energy unit. Only after
    that can a test put its own numbers in the counters, because the unit
    register and the counter overlap in the fake file. `FakeCpus` says why.
    """
    sampler = make_sampler(cpus, clock)
    sampler.discover()
    sampler.sample()
    cpus.zero_counters()
    clock.advance(1.0)
    sampler.sample()
    return sampler


# --- what the machine is -----------------------------------------------------


def test_the_vendor_and_family_are_read_from_cpuinfo(fake_cpus: FakeCpus) -> None:
    assert read_cpu_vendor_and_family(fake_cpus.cpuinfo_path) == ("AuthenticAMD", 26)


def test_a_missing_cpuinfo_gives_no_vendor_and_no_family(tmp_path: Path) -> None:
    assert read_cpu_vendor_and_family(tmp_path / "not-here") == (None, None)


def test_an_intel_processor_gives_no_channels(tmp_path: Path) -> None:
    # These registers are AMD's. On another vendor the same numbers mean
    # something else, so the helper must not read them at all.
    cpus = FakeCpus(tmp_path / "intel", cores=2, vendor="GenuineIntel", family=6)

    assert make_sampler(cpus, FakeClock()).discover() == []


def test_a_pre_zen_amd_processor_gives_no_channels(tmp_path: Path) -> None:
    cpus = FakeCpus(tmp_path / "old-amd", cores=2, family=0x15)

    assert make_sampler(cpus, FakeClock()).discover() == []


# --- discovery ---------------------------------------------------------------


def test_discover_gives_one_channel_for_each_core_and_a_total(fake_cpus: FakeCpus) -> None:
    channels = make_sampler(fake_cpus, FakeClock()).discover()

    assert [(channel.device, channel.channel) for channel in channels] == [
        ("cpu-cores.core-0", "power"),
        ("cpu-cores.core-1", "power"),
        ("cpu-cores.core-2", "power"),
        ("cpu-cores.core-3", "power"),
        ("cpu-cores", "power"),
    ]


def test_discover_reads_one_thread_of_each_core_only(fake_cpus: FakeCpus) -> None:
    # The counter is per core. exp-0012 proved it: with one thread busy,
    # exactly one core counter moved. Reading both threads would read the same
    # register twice and count the core twice in the total.
    channels = make_sampler(fake_cpus, FakeClock()).discover()
    origins = [channel.origin for channel in channels if channel.device != "cpu-cores"]

    assert origins == [f"{fake_cpus.msr_path(cpu)}:0xc001029a" for cpu in range(fake_cpus.cores)]


def test_discover_says_the_unit_and_the_group_a_person_sees(fake_cpus: FakeCpus) -> None:
    channels = make_sampler(fake_cpus, FakeClock()).discover()

    assert channels[0].label == "CPU Core 0 Power"
    assert channels[-1].label == "CPU Cores Power"
    assert {channel.unit for channel in channels} == {"watt"}
    assert {channel.group for channel in channels} == {"cpu"}


def test_a_core_with_no_msr_node_is_left_out(fake_cpus: FakeCpus) -> None:
    fake_cpus.msr_path(2).unlink()

    channels = make_sampler(fake_cpus, FakeClock()).discover()

    assert ("cpu-cores.core-2", "power") not in [(channel.device, channel.channel) for channel in channels]
    assert len(channels) == 4


def test_no_msr_node_at_all_gives_no_channels_and_no_total(fake_cpus: FakeCpus) -> None:
    for cpu in range(fake_cpus.cores * 2):
        fake_cpus.msr_path(cpu).unlink()

    assert make_sampler(fake_cpus, FakeClock()).discover() == []


# --- reading -----------------------------------------------------------------


def test_the_first_sample_gives_no_power_and_says_why(fake_cpus: FakeCpus) -> None:
    # The same rule as RAPL: one counter is not a rate. A first sample that
    # reported zero would be a lie about an idle core.
    sampler = make_sampler(fake_cpus, FakeClock())
    sampler.discover()

    sampler.sample()

    value = sampler.values()[("cpu-cores.core-0", "power")]
    assert value.value is None
    assert value.error == "waiting for a second energy sample"


def test_power_is_the_rise_divided_by_the_time(fake_cpus: FakeCpus) -> None:
    clock = FakeClock()
    sampler = primed(fake_cpus, clock)

    # 65536 counts is exactly one joule on this machine. Over two seconds that
    # is half a watt.
    fake_cpus.set_core_counter(0, 65536)
    clock.advance(2.0)
    sampler.sample()

    value = sampler.values()[("cpu-cores.core-0", "power")]
    assert value.error is None
    assert value.value == pytest.approx(0.5)


def test_each_core_is_read_on_its_own(fake_cpus: FakeCpus) -> None:
    # This is exp-0012 phase B in a test: one core busy, the others idle.
    clock = FakeClock()
    sampler = primed(fake_cpus, clock)

    fake_cpus.set_core_counter(1, 65536 * 17)
    clock.advance(1.0)
    sampler.sample()

    values = sampler.values()
    assert values[("cpu-cores.core-1", "power")].value == pytest.approx(17.0)
    assert values[("cpu-cores.core-0", "power")].value == pytest.approx(0.0)
    assert values[("cpu-cores.core-3", "power")].value == pytest.approx(0.0)


def test_a_counter_that_wraps_gives_a_positive_power(fake_cpus: FakeCpus) -> None:
    # The counter is 32 bits. At the 104 W this machine reached under load, one
    # core wraps about every ten minutes. Without the modulo the screen would
    # show a power of about minus 65 kW four times an hour.
    clock = FakeClock()
    sampler = primed(fake_cpus, clock)
    fake_cpus.set_core_counter(0, CORE_COUNTER_SPAN - 32768)
    clock.advance(1.0)
    sampler.sample()

    fake_cpus.set_core_counter(0, 32768)
    clock.advance(1.0)
    sampler.sample()

    # 32768 counts before the wrap and 32768 after it is one joule in one
    # second.
    assert sampler.values()[("cpu-cores.core-0", "power")].value == pytest.approx(1.0)


def test_the_unit_comes_from_the_register_not_from_a_constant(fake_cpus: FakeCpus) -> None:
    # A part with another ESU must not be read with this machine's number.
    # ESU 14 gives 1/16384 joules, so the same rise is four times the power.
    for cpu in range(fake_cpus.cores * 2):
        fake_cpus.set_unit(cpu, 0x000A0E00)
    clock = FakeClock()
    sampler = primed(fake_cpus, clock)

    fake_cpus.set_core_counter(0, 16384)
    clock.advance(1.0)
    sampler.sample()

    assert sampler.values()[("cpu-cores.core-0", "power")].value == pytest.approx(1.0)


def test_no_time_between_two_samples_gives_no_power(fake_cpus: FakeCpus) -> None:
    sampler = make_sampler(fake_cpus, FakeClock())
    sampler.discover()
    sampler.sample()

    sampler.sample()

    assert sampler.values()[("cpu-cores.core-0", "power")].error == "no time passed between samples"


# --- the total ---------------------------------------------------------------


def test_the_total_is_the_sum_of_every_core(fake_cpus: FakeCpus) -> None:
    clock = FakeClock()
    sampler = primed(fake_cpus, clock)

    for core_id in range(fake_cpus.cores):
        fake_cpus.set_core_counter(core_id, 65536 * (core_id + 1))
    clock.advance(1.0)
    sampler.sample()

    # 1 + 2 + 3 + 4 watts.
    assert sampler.values()[("cpu-cores", "power")].value == pytest.approx(10.0)


def test_the_total_is_withheld_when_one_core_cannot_be_read(fake_cpus: FakeCpus) -> None:
    # A sum that quietly drops a core would read like a cooler processor. The
    # helper says it cannot give the number instead.
    clock = FakeClock()
    sampler = primed(fake_cpus, clock)
    # An open descriptor survives the unlink, exactly as it does on the
    # machine, so the sampler must first let the descriptor go.
    sampler.close()
    fake_cpus.msr_path(2).unlink()
    clock.advance(1.0)

    sampler.sample()

    total = sampler.values()[("cpu-cores", "power")]
    assert total.value is None
    assert total.error == "not every core gave a value"


# --- what it says when it cannot read ---------------------------------------


def test_an_unreadable_node_says_that_the_read_needs_rawio(fake_cpus: FakeCpus) -> None:
    for cpu in range(fake_cpus.cores * 2):
        fake_cpus.msr_path(cpu).chmod(0o000)
    sampler = make_sampler(fake_cpus, FakeClock())
    sampler.discover()

    sampler.sample()

    error = sampler.values()[("cpu-cores.core-0", "power")].error
    assert error is not None
    assert "CAP_SYS_RAWIO" in error


def test_a_node_that_disappears_says_the_module_is_not_loaded(fake_cpus: FakeCpus) -> None:
    sampler = make_sampler(fake_cpus, FakeClock())
    sampler.discover()
    for cpu in range(fake_cpus.cores * 2):
        fake_cpus.msr_path(cpu).unlink()

    sampler.sample()

    error = sampler.values()[("cpu-cores.core-0", "power")].error
    assert error is not None
    assert "modprobe msr" in error


def test_the_sampler_opens_nothing_for_writing(fake_cpus: FakeCpus) -> None:
    # ADR 0007. The counters are read with O_RDONLY, so a fault in the code
    # above cannot become a write. A node with no write permission at all must
    # still be readable.
    clock = FakeClock()
    sampler = primed(fake_cpus, clock)
    for cpu in range(fake_cpus.cores * 2):
        fake_cpus.msr_path(cpu).chmod(0o400)
    for cpu in (0, fake_cpus.cores):
        fake_cpus.msr_path(cpu).chmod(0o600)
    fake_cpus.set_core_counter(0, 65536)
    for cpu in (0, fake_cpus.cores):
        fake_cpus.msr_path(cpu).chmod(0o400)
    clock.advance(1.0)

    sampler.sample()

    assert sampler.values()[("cpu-cores.core-0", "power")].value == pytest.approx(1.0)


def test_close_releases_every_descriptor(fake_cpus: FakeCpus) -> None:
    sampler = make_sampler(fake_cpus, FakeClock())
    sampler.discover()
    sampler.sample()

    sampler.close()

    # Reading again reopens, so the sampler still works after a close.
    sampler.sample()
    assert ("cpu-cores.core-0", "power") in sampler.values()


# --- the catalogue -----------------------------------------------------------


def test_the_catalogue_publishes_the_core_channels(
    fake_cpus: FakeCpus, fake_powercap: FakePowercap, fake_nvme: FakeNvme
) -> None:
    clock = FakeClock()
    catalogue = Catalogue(
        rapl=RaplSampler(root=fake_powercap.root, clock=clock),
        nvme=NvmeSampler(
            sys_root=fake_nvme.sys_root,
            dev_root=fake_nvme.dev_root,
            nvme_command=fake_nvme.command,
            clock=clock,
        ),
        cores=make_sampler(fake_cpus, clock),
        clock=clock,
    )

    channels = catalogue.discover()
    catalogue.sample()
    clock.advance(1.0)
    catalogue.sample()

    devices = {channel.device for channel in channels}
    assert "cpu-cores" in devices
    assert "cpu-cores.core-0" in devices
    readings = {(item["device"], item["channel"]): item for item in catalogue.readings()}
    assert readings[("cpu-cores", "power")]["value"] == pytest.approx(0.0)
    assert readings[("cpu-cores", "power")]["error"] is None


def test_one_count_is_the_value_this_machine_reports() -> None:
    # 0xc0010299 read `a1000` on dst-gova-pc on 2026-09-22, so ESU is 16.
    assert pytest.approx(15.2588, abs=0.0001) == REAL_JOULES_PER_COUNT * 1e6
