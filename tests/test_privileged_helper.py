"""Tests for `sensors-guid`, the privileged helper of ADR 0005.

No mocks. The RAPL tests read a real directory tree, the NVMe tests run a real
program through a real pipe, and the socket tests open a real Unix socket in a
temporary directory. The clock is a real callable that a test moves by hand,
which is the pattern the rest of this suite uses.
"""

from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

import pytest
from conftest import FAKE_MAX_ENERGY_UJ, REAL_SMART_LOG, FakeNvme, FakePowercap

from sensors_gui.helper import sensors_guid
from sensors_gui.helper.sensors_guid import (
    PROTOCOL_VERSION,
    Catalogue,
    HelperServer,
    NvmeSampler,
    RaplSampler,
    handle_request,
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


# --- RAPL --------------------------------------------------------------------


def test_rapl_discover_finds_both_domains_of_this_machine(fake_powercap: FakePowercap) -> None:
    channels = RaplSampler(root=fake_powercap.root).discover()

    assert [(channel.device, channel.channel) for channel in channels] == [
        ("package-0", "power"),
        ("package-0", "energy"),
        ("package-0.core", "power"),
        ("package-0.core", "energy"),
    ]


def test_rapl_labels_the_core_domain_as_core_zero(fake_powercap: FakePowercap) -> None:
    # exp-0003 finding 2, confirmed again on 2026-09-22: the powercap `core`
    # domain follows one core, not the twelve. Calling it "Cores" would be a
    # lie of a factor of ten.
    channels = RaplSampler(root=fake_powercap.root).discover()
    labels = {channel.device: channel.label for channel in channels if channel.channel == "power"}

    assert labels["package-0"] == "CPU Package Power"
    assert labels["package-0.core"] == "CPU Core 0 Power"


def test_rapl_declares_no_top_of_scale_because_the_board_declares_none(fake_powercap: FakePowercap) -> None:
    channels = RaplSampler(root=fake_powercap.root).discover()

    assert all(channel.high is None for channel in channels)


def test_rapl_first_sample_reports_no_power_instead_of_zero(fake_powercap: FakePowercap) -> None:
    sampler = RaplSampler(root=fake_powercap.root, clock=FakeClock())
    sampler.discover()

    sampler.sample()

    power = sampler.values()[("package-0", "power")]
    assert power.value is None
    assert "second energy sample" in power.error


def test_rapl_power_is_the_energy_rise_divided_by_the_time(fake_powercap: FakePowercap) -> None:
    clock = FakeClock()
    sampler = RaplSampler(root=fake_powercap.root, clock=clock)
    sampler.discover()
    fake_powercap.set_energy(fake_powercap.package, 1_000_000)
    sampler.sample()

    # 68.4 joules in one second is 68.4 watts, which is what this machine
    # actually drew while the probe ran.
    fake_powercap.set_energy(fake_powercap.package, 1_000_000 + 68_400_000)
    clock.advance(1.0)
    sampler.sample()

    assert sampler.values()[("package-0", "power")].value == pytest.approx(68.4)


def test_rapl_energy_adds_up_across_passes(fake_powercap: FakePowercap) -> None:
    clock = FakeClock()
    sampler = RaplSampler(root=fake_powercap.root, clock=clock)
    sampler.discover()
    sampler.sample()

    for step in (1, 2, 3):
        fake_powercap.set_energy(fake_powercap.package, step * 2_000_000)
        clock.advance(1.0)
        sampler.sample()

    assert sampler.values()[("package-0", "energy")].value == pytest.approx(6.0)


def test_rapl_handles_the_counter_wrapping(fake_powercap: FakePowercap) -> None:
    # The counter wraps at max_energy_range_uj. On this machine that is
    # 65 532 610 987 microjoules, which at 70 W is about every 15 minutes, so
    # this is an ordinary event and not an edge case.
    clock = FakeClock()
    sampler = RaplSampler(root=fake_powercap.root, clock=clock)
    sampler.discover()
    fake_powercap.set_energy(fake_powercap.package, FAKE_MAX_ENERGY_UJ - 10_000_000)
    sampler.sample()

    fake_powercap.set_energy(fake_powercap.package, 60_000_000)
    clock.advance(1.0)
    sampler.sample()

    # 10 J up to the wrap, 1 microjoule for the wrap itself, then 60 J after.
    assert sampler.values()[("package-0", "power")].value == pytest.approx(70.000001)


def test_rapl_without_root_says_it_needs_root(fake_powercap: FakePowercap) -> None:
    sampler = RaplSampler(root=fake_powercap.root, clock=FakeClock())
    sampler.discover()
    fake_powercap.make_unreadable(fake_powercap.package)

    sampler.sample()

    power = sampler.values()[("package-0", "power")]
    assert power.value is None
    assert "needs root" in power.error


def test_rapl_with_no_powercap_directory_finds_nothing(tmp_path: Path) -> None:
    assert RaplSampler(root=tmp_path / "absent").discover() == []


# --- NVMe SMART --------------------------------------------------------------


def _nvme_sampler(fake_nvme: FakeNvme, clock: FakeClock | None = None) -> NvmeSampler:
    return NvmeSampler(
        sys_root=fake_nvme.sys_root,
        dev_root=fake_nvme.dev_root,
        nvme_command=str(fake_nvme.command),
        clock=clock or FakeClock(),
    )


def test_nvme_discover_gives_the_fifteen_channels_gova_chose(fake_nvme: FakeNvme) -> None:
    channels = _nvme_sampler(fake_nvme).discover()

    assert [channel.channel for channel in channels] == [
        "wear",
        "spare",
        "data_written",
        "data_read",
        "power_on_hours",
        "power_cycles",
        "unsafe_shutdowns",
        "media_errors",
        "critical_warning",
        "throttle_t1_count",
        "throttle_t2_count",
        "throttle_t1_time",
        "throttle_t2_time",
        "warning_temp_time",
        "critical_temp_time",
    ]


def test_nvme_identifies_the_drive_by_model_and_serial_not_by_index(fake_nvme: FakeNvme) -> None:
    # ADR 0002: `nvme0` is an index, and an index is not an identity.
    channels = _nvme_sampler(fake_nvme).discover()

    assert {channel.device for channel in channels} == {"WD_BLACK SN770 1TB@234639803238"}


def test_nvme_reads_the_real_smart_log_of_this_drive(fake_nvme: FakeNvme) -> None:
    sampler = _nvme_sampler(fake_nvme)
    sampler.discover()

    sampler.sample()

    values = sampler.values()
    device = fake_nvme.device
    assert values[(device, "wear")].value == 0.0
    assert values[(device, "spare")].value == 100.0
    assert values[(device, "power_on_hours")].value == 331.0
    assert values[(device, "power_cycles")].value == 150.0
    assert values[(device, "unsafe_shutdowns")].value == 31.0
    assert values[(device, "media_errors")].value == 0.0


def test_nvme_data_written_is_in_bytes_not_in_data_units(fake_nvme: FakeNvme) -> None:
    # One NVMe data unit is 1000 blocks of 512 bytes. 19 702 733 units is
    # 10.09 TB, and a screen that showed "19702733" would mean nothing.
    sampler = _nvme_sampler(fake_nvme)
    sampler.discover()

    sampler.sample()

    written = sampler.values()[(fake_nvme.device, "data_written")].value
    assert written == REAL_SMART_LOG["data_units_written"] * 512 * 1000


def test_nvme_turns_the_minute_fields_into_seconds(fake_nvme: FakeNvme) -> None:
    # The specification counts `warning_temp_time` in minutes and
    # `thm_temp1_total_time` in seconds. Both leave here in seconds.
    log = dict(REAL_SMART_LOG, warning_temp_time=3, critical_comp_time=2, thm_temp1_total_time=45)
    fake_nvme.set_output(json.dumps(log))
    sampler = _nvme_sampler(fake_nvme)
    sampler.discover()

    sampler.sample()

    values = sampler.values()
    assert values[(fake_nvme.device, "warning_temp_time")].value == 180.0
    assert values[(fake_nvme.device, "critical_temp_time")].value == 120.0
    assert values[(fake_nvme.device, "throttle_t1_time")].value == 45.0


def test_nvme_failure_reports_the_reason_and_not_the_usage_banner(fake_nvme: FakeNvme) -> None:
    # Found by running the helper as a normal user: nvme-cli prints its usage
    # banner in bold on every failure, and taking the first line of stderr hid
    # "Permission denied", which is the one word that tells a person what to do.
    fake_nvme.set_output(
        stdout="/dev/nvme0: Permission denied\n",
        stderr="\x1b[1mUsage: nvme smart-log <device> [OPTIONS]\x1b[0m\n",
        exit_code=1,
    )
    sampler = _nvme_sampler(fake_nvme)
    sampler.discover()

    sampler.sample()

    error = sampler.values()[(fake_nvme.device, "wear")].error
    assert "Permission denied" in error
    assert "Usage:" not in error


def test_nvme_broken_json_becomes_an_error_and_not_a_crash(fake_nvme: FakeNvme) -> None:
    fake_nvme.set_output("this is not JSON")
    sampler = _nvme_sampler(fake_nvme)
    sampler.discover()

    sampler.sample()

    assert "did not give JSON" in sampler.values()[(fake_nvme.device, "wear")].error


def test_nvme_missing_field_becomes_an_error_and_not_a_zero(fake_nvme: FakeNvme) -> None:
    log = {key: value for key, value in REAL_SMART_LOG.items() if key != "percent_used"}
    fake_nvme.set_output(json.dumps(log))
    sampler = _nvme_sampler(fake_nvme)
    sampler.discover()

    sampler.sample()

    wear = sampler.values()[(fake_nvme.device, "wear")]
    assert wear.value is None
    assert "percent_used" in wear.error


def test_nvme_without_the_tool_reports_it_and_still_lists_the_channels(fake_nvme: FakeNvme) -> None:
    sampler = NvmeSampler(
        sys_root=fake_nvme.sys_root,
        dev_root=fake_nvme.dev_root,
        nvme_command=None,
        clock=FakeClock(),
    )
    channels = sampler.discover()
    sampler.sample()

    assert len(channels) == 15
    assert sampler.values()[(fake_nvme.device, "wear")].error == "nvme-cli is not installed"


# --- the catalogue -----------------------------------------------------------


def _catalogue(fake_powercap: FakePowercap, fake_nvme: FakeNvme, clock: FakeClock) -> Catalogue:
    return Catalogue(
        rapl=RaplSampler(root=fake_powercap.root, clock=clock),
        nvme=_nvme_sampler(fake_nvme, clock),
        clock=clock,
    )


def test_the_catalogue_holds_every_channel_of_both_sources(fake_powercap: FakePowercap, fake_nvme: FakeNvme) -> None:
    catalogue = _catalogue(fake_powercap, fake_nvme, FakeClock())

    assert len(catalogue.discover()) == 4 + 15


def test_the_catalogue_reads_the_drive_on_its_own_slow_interval(
    fake_powercap: FakePowercap, fake_nvme: FakeNvme
) -> None:
    # ADR 0006: an expensive channel gets its own interval. A SMART read costs
    # 3.0 ms on this machine, so it happens once a minute, not ten times a
    # second along with RAPL.
    clock = FakeClock()
    catalogue = _catalogue(fake_powercap, fake_nvme, clock)
    catalogue.discover()
    catalogue.sample()

    fake_nvme.set_output(json.dumps(dict(REAL_SMART_LOG, power_on_hours=999)))
    clock.advance(30.0)
    catalogue.sample()
    after_thirty_seconds = _value_of(catalogue, fake_nvme.device, "power_on_hours")

    clock.advance(31.0)
    catalogue.sample()
    after_a_minute = _value_of(catalogue, fake_nvme.device, "power_on_hours")

    assert after_thirty_seconds == 331.0
    assert after_a_minute == 999.0


def test_a_channel_that_was_never_sampled_reports_that_and_not_a_zero(
    fake_powercap: FakePowercap, fake_nvme: FakeNvme
) -> None:
    catalogue = _catalogue(fake_powercap, fake_nvme, FakeClock())
    catalogue.discover()

    readings = catalogue.readings()

    assert all(reading["value"] is None for reading in readings)
    assert all(reading["error"] == "not sampled yet" for reading in readings)


def _value_of(catalogue: Catalogue, device: str, channel: str) -> float | None:
    for reading in catalogue.readings():
        if reading["device"] == device and reading["channel"] == channel:
            return reading["value"]
    raise AssertionError(f"no such channel: {device} {channel}")


# --- the protocol ------------------------------------------------------------


@pytest.fixture
def catalogue(fake_powercap: FakePowercap, fake_nvme: FakeNvme) -> Catalogue:
    clock = FakeClock()
    built = _catalogue(fake_powercap, fake_nvme, clock)
    built.discover()
    built.sample()
    return built


def test_describe_lists_every_channel_with_its_unit(catalogue: Catalogue) -> None:
    answer = handle_request(catalogue, json.dumps({"protocol": 1, "command": "describe"}))

    assert answer["ok"] is True
    assert answer["helper_version"] == sensors_guid.HELPER_VERSION
    assert len(answer["channels"]) == 19
    assert {channel["unit"] for channel in answer["channels"]} == {
        "watt",
        "joule",
        "percent",
        "byte",
        "hour",
        "count",
        "second",
    }


def test_read_gives_a_value_and_an_age_for_every_channel(catalogue: Catalogue) -> None:
    answer = handle_request(catalogue, json.dumps({"protocol": 1, "command": "read"}))

    assert answer["ok"] is True
    assert len(answer["readings"]) == 19
    assert all("age" in reading for reading in answer["readings"])


def test_ping_answers_without_reading_a_sensor(catalogue: Catalogue) -> None:
    answer = handle_request(catalogue, json.dumps({"protocol": 1, "command": "ping"}))

    assert answer == {
        "protocol": PROTOCOL_VERSION,
        "ok": True,
        "command": "ping",
        "helper_version": sensors_guid.HELPER_VERSION,
    }


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("not json at all", "not JSON"),
        ("[1, 2, 3]", "not a JSON object"),
        ('{"protocol": 99, "command": "read"}', "protocol 1"),
        ('{"protocol": 1, "command": "delete_everything"}', "unknown command"),
        ('{"protocol": 1}', "unknown command"),
    ],
)
def test_a_bad_request_is_refused_with_a_reason(catalogue: Catalogue, line: str, expected: str) -> None:
    answer = handle_request(catalogue, line)

    assert answer["ok"] is False
    assert expected in answer["error"]


def test_the_protocol_has_no_way_to_ask_for_a_path(catalogue: Catalogue) -> None:
    # ADR 0005 rule 2 and ADR 0009: the client may ask for the catalogue, and
    # for nothing else. A request that names a file is simply an unknown
    # command; the helper never opens what a client names.
    answer = handle_request(catalogue, json.dumps({"protocol": 1, "command": "read", "path": "/etc/shadow"}))

    assert answer["ok"] is True
    assert all("shadow" not in reading["device"] for reading in answer["readings"])


# --- the socket --------------------------------------------------------------


def test_the_server_answers_over_a_real_unix_socket(catalogue: Catalogue, tmp_path: Path) -> None:
    socket_path = tmp_path / "helper.sock"
    server = HelperServer(socket_path, catalogue, group=None)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(5.0)
            client.connect(str(socket_path))
            stream = client.makefile("rwb")
            stream.write(json.dumps({"protocol": 1, "command": "describe"}).encode() + b"\n")
            stream.flush()
            describe = json.loads(stream.readline())
            # The same connection serves a second request.
            stream.write(json.dumps({"protocol": 1, "command": "read"}).encode() + b"\n")
            stream.flush()
            read = json.loads(stream.readline())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5.0)

    assert len(describe["channels"]) == 19
    assert len(read["readings"]) == 19


def test_the_socket_file_goes_away_when_the_server_closes(catalogue: Catalogue, tmp_path: Path) -> None:
    socket_path = tmp_path / "helper.sock"
    server = HelperServer(socket_path, catalogue, group=None)
    assert socket_path.is_socket()

    server.server_close()

    assert not socket_path.exists()


def test_a_socket_left_by_a_dead_helper_is_replaced(catalogue: Catalogue, tmp_path: Path) -> None:
    socket_path = tmp_path / "helper.sock"
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(str(socket_path))
    stale.close()  # bound, never listening: exactly what a killed helper leaves

    server = HelperServer(socket_path, catalogue, group=None)
    try:
        assert socket_path.is_socket()
    finally:
        server.server_close()


def test_an_ordinary_file_in_the_socket_path_is_never_deleted(catalogue: Catalogue, tmp_path: Path) -> None:
    # The helper runs as root. A bug that unlinked whatever was in its way
    # would be a bug that deletes a root-owned file, so it refuses instead.
    not_a_socket = tmp_path / "important.txt"
    not_a_socket.write_text("keep me")

    with pytest.raises(OSError):
        HelperServer(not_a_socket, catalogue, group=None)

    assert not_a_socket.read_text() == "keep me"
