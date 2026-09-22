"""Tests for `PrivilegedCollector`, the client half of ADR 0005.

No mocks. Every test here talks to a real Unix socket. Most of them talk to a
real `sensors-guid` server, built over the same temporary sysfs trees the
helper tests use; a few talk to a small scripted server that answers a fixed
line, which is how a helper that answers badly is tested without pretending.
"""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import REAL_SMART_LOG, FakeCpus, FakeNvme, FakePowercap

from sensors_gui.collectors.privileged import NO_HELPER_ERROR, PrivilegedCollector
from sensors_gui.helper import sensors_guid
from sensors_gui.helper.sensors_guid import (
    Catalogue,
    CoreEnergySampler,
    HelperServer,
    NvmeSampler,
    RaplSampler,
)
from sensors_gui.model import Group, Unit


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


class RunningHelper:
    """A real `sensors-guid` server on a temporary socket, in a thread."""

    def __init__(self, socket_path: Path, catalogue: Catalogue) -> None:
        self.server = HelperServer(socket_path, catalogue, group=None)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        """Stop the server and wait for its thread."""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5.0)


class ScriptedHelper:
    """A real socket server that answers one fixed line, to test a bad helper."""

    def __init__(self, socket_path: Path, answer: str) -> None:
        self.answer = answer
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(socket_path))
        self.socket.listen(4)
        # A timeout on accept, so that `stop` does not wait for a connection
        # that never comes. Closing a listening socket from another thread does
        # not reliably wake accept on Linux.
        self.socket.settimeout(0.1)
        self.running = True
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        while self.running:
            try:
                connection, _ = self.socket.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with connection:
                try:
                    connection.recv(4096)
                    connection.sendall(self.answer.encode())
                except OSError:
                    return

    def stop(self) -> None:
        """Stop answering and close the listening socket."""
        self.running = False
        self.socket.close()
        self.thread.join(timeout=5.0)


@pytest.fixture
def sampled_catalogue(fake_powercap: FakePowercap, fake_nvme: FakeNvme, fake_cpus: FakeCpus) -> Catalogue:
    """A catalogue over the temporary trees, sampled twice so power exists."""
    clock = FakeClock()
    catalogue = Catalogue(
        rapl=RaplSampler(root=fake_powercap.root, clock=clock),
        nvme=NvmeSampler(
            sys_root=fake_nvme.sys_root,
            dev_root=fake_nvme.dev_root,
            nvme_command=str(fake_nvme.command),
            clock=clock,
        ),
        cores=CoreEnergySampler(
            cpu_sys_root=fake_cpus.cpu_sys_root,
            msr_root=fake_cpus.msr_root,
            cpuinfo_path=fake_cpus.cpuinfo_path,
            clock=clock,
        ),
        clock=clock,
    )
    catalogue.discover()
    catalogue.sample()
    fake_powercap.set_energy(fake_powercap.package, 68_400_000)
    clock.advance(1.0)
    catalogue.sample()
    return catalogue


@pytest.fixture
def helper_socket(tmp_path: Path) -> Path:
    return tmp_path / "sensors-gui.sock"


@pytest.fixture
def running_helper(helper_socket: Path, sampled_catalogue: Catalogue) -> Iterator[RunningHelper]:
    helper = RunningHelper(helper_socket, sampled_catalogue)
    yield helper
    helper.stop()


def _catalogue_of(fake_powercap: FakePowercap, fake_nvme: FakeNvme, fake_cpus: FakeCpus) -> list[sensors_guid.Channel]:
    """Return the catalogue the client builds for itself when the helper is absent."""
    return sensors_guid.discover_channels(
        rapl_root=fake_powercap.root,
        nvme_sys_root=fake_nvme.sys_root,
        dev_root=fake_nvme.dev_root,
        cpu_sys_root=fake_cpus.cpu_sys_root,
        msr_root=fake_cpus.msr_root,
        cpuinfo_path=fake_cpus.cpuinfo_path,
    )


# --- with the helper running -------------------------------------------------


def test_discover_gives_every_channel_the_helper_has(running_helper: RunningHelper, helper_socket: Path) -> None:
    collector = PrivilegedCollector(socket_path=helper_socket)

    specs = collector.discover()
    collector.close()

    assert len(specs) == 24
    assert {spec.id.source for spec in specs} == {"privileged"}


def test_discover_keeps_the_unit_and_the_group_of_each_channel(
    running_helper: RunningHelper, helper_socket: Path
) -> None:
    collector = PrivilegedCollector(socket_path=helper_socket)

    by_channel = {(spec.id.device, spec.id.channel): spec for spec in collector.discover()}
    collector.close()

    package_power = by_channel[("package-0", "power")]
    wear = by_channel[("WD_BLACK SN770 1TB@234639803238", "wear")]
    assert (package_power.unit, package_power.group) == (Unit.WATT, Group.CPU)
    assert (wear.unit, wear.group) == (Unit.PERCENT, Group.STORAGE)
    assert wear.high == 100.0


def test_read_gives_the_values_the_helper_sampled(running_helper: RunningHelper, helper_socket: Path) -> None:
    collector = PrivilegedCollector(socket_path=helper_socket)
    collector.discover()

    readings = {(reading.id.device, reading.id.channel): reading for reading in collector.read()}
    collector.close()

    assert readings[("package-0", "power")].value == pytest.approx(68.4)
    assert readings[("WD_BLACK SN770 1TB@234639803238", "power_on_hours")].value == 331.0
    assert readings[("WD_BLACK SN770 1TB@234639803238", "data_written")].value == (
        REAL_SMART_LOG["data_units_written"] * 512 * 1000
    )


def test_the_age_of_a_value_is_the_age_of_the_hardware_read(running_helper: RunningHelper, helper_socket: Path) -> None:
    # The helper samples on its own clock. What the screen must show is how old
    # the sensor value is, not how long ago the socket answered.
    clock = FakeClock(now=1000.0)
    collector = PrivilegedCollector(socket_path=helper_socket, clock=clock)
    collector.discover()

    reading = next(item for item in collector.read() if item.id.channel == "power")
    collector.close()

    assert reading.read_at is not None
    assert reading.read_at <= clock.now


def test_the_collector_reconnects_after_the_helper_restarts(helper_socket: Path, sampled_catalogue: Catalogue) -> None:
    helper = RunningHelper(helper_socket, sampled_catalogue)
    collector = PrivilegedCollector(socket_path=helper_socket)
    collector.discover()
    assert collector.read()[0].is_ok
    helper.stop()

    restarted = RunningHelper(helper_socket, sampled_catalogue)
    try:
        readings = collector.read()
    finally:
        collector.close()
        restarted.stop()

    assert readings[0].is_ok


# --- with no helper ----------------------------------------------------------


def test_without_the_helper_the_channels_are_still_discovered(
    helper_socket: Path, fake_powercap: FakePowercap, fake_nvme: FakeNvme, fake_cpus: FakeCpus
) -> None:
    # ADR 0005 rule 3. Hiding the rows would hide the reason they are missing.
    collector = PrivilegedCollector(
        socket_path=helper_socket,
        catalogue_source=lambda: _catalogue_of(fake_powercap, fake_nvme, fake_cpus),
    )

    specs = collector.discover()
    collector.close()

    assert len(specs) == 24


def test_without_the_helper_every_reading_says_so(
    helper_socket: Path, fake_powercap: FakePowercap, fake_nvme: FakeNvme, fake_cpus: FakeCpus
) -> None:
    collector = PrivilegedCollector(
        socket_path=helper_socket,
        catalogue_source=lambda: _catalogue_of(fake_powercap, fake_nvme, fake_cpus),
    )
    collector.discover()

    readings = collector.read()
    collector.close()

    assert len(readings) == 24
    assert all(reading.value is None for reading in readings)
    assert all(reading.error == NO_HELPER_ERROR for reading in readings)


def test_the_collector_waits_before_trying_a_dead_socket_again(
    helper_socket: Path,
    sampled_catalogue: Catalogue,
    fake_powercap: FakePowercap,
    fake_nvme: FakeNvme,
    fake_cpus: FakeCpus,
) -> None:
    # A screen at 10 Hz must not try to connect ten times a second.
    clock = FakeClock()
    collector = PrivilegedCollector(
        socket_path=helper_socket,
        clock=clock,
        reconnect_interval=5.0,
        catalogue_source=lambda: _catalogue_of(fake_powercap, fake_nvme, fake_cpus),
    )
    collector.discover()
    assert collector.read()[0].error == NO_HELPER_ERROR

    helper = RunningHelper(helper_socket, sampled_catalogue)
    try:
        clock.advance(1.0)
        during_the_wait = collector.read()
        clock.advance(5.0)
        after_the_wait = collector.read()
    finally:
        collector.close()
        helper.stop()

    assert during_the_wait[0].error == NO_HELPER_ERROR
    assert after_the_wait[0].is_ok


def test_read_before_discover_gives_nothing_and_does_not_raise(helper_socket: Path) -> None:
    assert PrivilegedCollector(socket_path=helper_socket).read() == []


# --- with a helper that answers badly ----------------------------------------


def test_an_answer_that_is_not_json_becomes_an_error_and_not_a_crash(
    helper_socket: Path, fake_powercap: FakePowercap, fake_nvme: FakeNvme, fake_cpus: FakeCpus
) -> None:
    helper = ScriptedHelper(helper_socket, "this is not JSON\n")
    collector = PrivilegedCollector(
        socket_path=helper_socket,
        catalogue_source=lambda: _catalogue_of(fake_powercap, fake_nvme, fake_cpus),
    )
    try:
        specs = collector.discover()
        readings = collector.read()
    finally:
        collector.close()
        helper.stop()

    assert len(specs) == 24
    assert all(reading.error == NO_HELPER_ERROR for reading in readings)


def test_a_refusal_from_the_helper_is_shown_as_the_helper_wrote_it(
    helper_socket: Path, fake_powercap: FakePowercap, fake_nvme: FakeNvme, fake_cpus: FakeCpus
) -> None:
    refusal = json.dumps({"protocol": 1, "ok": False, "error": "this helper speaks protocol 2"})
    helper = ScriptedHelper(helper_socket, refusal + "\n")
    collector = PrivilegedCollector(
        socket_path=helper_socket,
        catalogue_source=lambda: _catalogue_of(fake_powercap, fake_nvme, fake_cpus),
    )
    try:
        collector.discover()
        readings = collector.read()
    finally:
        collector.close()
        helper.stop()

    assert all(reading.error == "this helper speaks protocol 2" for reading in readings)


def test_a_channel_the_helper_forgets_is_reported_and_not_dropped(
    helper_socket: Path, fake_powercap: FakePowercap, fake_nvme: FakeNvme, fake_cpus: FakeCpus
) -> None:
    describe = {
        "protocol": 1,
        "ok": True,
        "command": "describe",
        "helper_version": sensors_guid.HELPER_VERSION,
        "channels": [
            {
                "device": "package-0",
                "channel": "power",
                "label": "CPU Package Power",
                "group": "cpu",
                "unit": "watt",
                "low": 0.0,
                "high": None,
                "warn": None,
                "critical": None,
                "origin": "/sys/class/powercap/intel-rapl:0/energy_uj",
            }
        ],
    }
    helper = ScriptedHelper(helper_socket, json.dumps(describe) + "\n")
    collector = PrivilegedCollector(socket_path=helper_socket)
    try:
        collector.discover()
        # The scripted helper answers `read` with the describe line, which
        # holds no readings at all.
        readings = collector.read()
    finally:
        collector.close()
        helper.stop()

    assert len(readings) == 1
    assert readings[0].error == "the helper did not report this channel"


def test_a_unit_this_client_does_not_know_does_not_lose_the_channel(
    helper_socket: Path,
) -> None:
    describe = {
        "protocol": 1,
        "ok": True,
        "command": "describe",
        "helper_version": sensors_guid.HELPER_VERSION,
        "channels": [
            {
                "device": "package-0",
                "channel": "power",
                "label": "CPU Package Power",
                "group": "spaceship",
                "unit": "furlong",
                "low": None,
                "high": None,
                "warn": None,
                "critical": None,
                "origin": "",
            }
        ],
    }
    helper = ScriptedHelper(helper_socket, json.dumps(describe) + "\n")
    collector = PrivilegedCollector(socket_path=helper_socket)
    try:
        specs = collector.discover()
    finally:
        collector.close()
        helper.stop()

    assert len(specs) == 1
    assert specs[0].unit == Unit.NONE
    assert specs[0].group == Group.OTHER
