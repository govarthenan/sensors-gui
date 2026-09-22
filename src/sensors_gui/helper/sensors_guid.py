#!/usr/bin/env python3
"""sensors-guid — the privileged, read-only sensor helper of ADR 0005.

Three sensor sources on `dst-gova-pc` need root, and only these three:

| Source | Why root | Evidence |
|---|---|---|
| RAPL CPU energy | `intel-rapl:*/energy_uj` is mode `0400 root` | `privileged-20260922T051641Z` |
| NVMe SMART log | `/dev/nvme0` is mode `0600 root` | `privileged-20260922T051641Z` |
| Per-core energy | `/dev/cpu/N/msr` is `0600 root`, and needs CAP_SYS_RAWIO | `core-energy-20260922T055615Z` |

The probes are under `data/probes/`, captured by `scripts/probe-privileged.sh`
and `scripts/probe-core-energy.sh` on 2026-09-22. `exp-0011` and `exp-0012`
hold what they showed.

This helper runs as root, reads those two, and publishes the numbers on a Unix
domain socket that the user's screen can read. The screen itself never needs
root and never asks for a password.

**It reads. It never writes.** No file is opened for writing, no module is
loaded, and the only external command it runs is a fixed `nvme smart-log`
argument list with no shell. See ADR 0007 for why that rule is absolute here,
and ADR 0009 for the rules this file keeps.

Run it by hand, without installing anything, to see what it would publish:

    sudo python3 sensors_guid.py --once

Run it as the service:

    sudo python3 sensors_guid.py --socket /run/sensors-gui.sock --group gova

## The protocol

Newline-delimited JSON, one request per line, one response per line. The client
may send several requests on one connection.

    -> {"protocol": 1, "command": "describe"}
    <- {"protocol": 1, "ok": true, "command": "describe",
        "helper_version": "1.0", "channels": [ ... ]}

    -> {"protocol": 1, "command": "read"}
    <- {"protocol": 1, "ok": true, "command": "read",
        "readings": [{"device": ..., "channel": ..., "value": 68.4,
                      "error": null, "age": 0.42}]}

    -> anything else
    <- {"protocol": 1, "ok": false, "error": "..."}

`age` is how many seconds ago the helper itself read that value from the
hardware. The helper samples on its own clock — RAPL every second, SMART every
60 seconds — so a client that asks ten times a second costs the hardware
nothing.

**The client cannot ask for a path.** The request has no path, no device and no
command name in it. The catalogue is built here, from the machine, and the
client may only ask for all of it.
"""

from __future__ import annotations

import argparse
import contextlib
import errno
import grp
import json
import logging
import os
import re
import shutil
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = 1
HELPER_VERSION = "1.1"

DEFAULT_SOCKET_PATH = Path("/run/sensors-gui.sock")
DEFAULT_SOCKET_GROUP = "gova"
SOCKET_MODE = 0o660

# How often the helper reads each source from the hardware. A client asking
# more often is served the last value with its age.
RAPL_INTERVAL = 1.0
NVME_INTERVAL = 60.0

# One SMART read costs about 3.0 ms, measured five times on this machine
# (`smart-read-cost.txt` in the probe above). 60 seconds between reads is the
# rate ADR 0006 gives a slow-changing device.
NVME_COMMAND_TIMEOUT = 10.0

# The longest request line the helper will read. A client has no reason to send
# more than about 60 bytes, so anything larger is a fault or an attack.
MAX_REQUEST_BYTES = 4096

DEFAULT_RAPL_ROOT = Path("/sys/class/powercap")
DEFAULT_NVME_SYS_ROOT = Path("/sys/class/nvme")
DEFAULT_DEV_ROOT = Path("/dev")

# `intel-rapl:0` is a package, `intel-rapl:0:0` a domain inside it. The kernel
# uses this name on AMD as well; the driver is `intel_rapl_msr`, which supports
# the Zen RAPL MSRs. `max_energy_range_uj` on this machine is 65 532 610 987,
# so at 70 W the counter wraps about every 15 minutes. The wrap is handled.
RAPL_DOMAIN_PATTERN = re.compile(r"^intel-rapl(-mmio)?:\d+(:\d+)*$")

# NVMe reports read and written volume in units of 1000 × 512 bytes.
# NVM Express Base Specification, SMART / Health Information log page 02h.
NVME_DATA_UNIT_BYTES = 512 * 1000
SECONDS_PER_MINUTE = 60.0

logger = logging.getLogger("sensors-guid")


@dataclass(frozen=True, slots=True)
class Channel:
    """One value the helper can publish.

    The field names are the wire format. They are also, on purpose, the field
    names of `sensors_gui.model.SensorSpec`, so that the client can build a
    spec from a channel without a translation table.

    Attributes:
        device: The device this channel belongs to, stable across reboots.
        channel: The name of the channel on that device.
        label: A short name for a person.
        group: A `sensors_gui.model.Group` value, as text.
        unit: A `sensors_gui.model.Unit` value, as text.
        low: The bottom of a meter scale, when one is known.
        high: The top of a meter scale, when one is known.
        warn: A threshold the hardware itself declares, never an invented one.
        critical: The same, for the critical level.
        origin: The path or command the value comes from.
    """

    device: str
    channel: str
    label: str
    group: str
    unit: str
    low: float | None = None
    high: float | None = None
    warn: float | None = None
    critical: float | None = None
    origin: str = ""

    @property
    def key(self) -> tuple[str, str]:
        """Return the pair that identifies this channel inside the helper."""
        return (self.device, self.channel)

    def as_dict(self) -> dict[str, Any]:
        """Return the channel as the plain dictionary that goes on the wire."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Value:
    """One sampled value, or the reason there is none.

    Attributes:
        value: The number, or None when the read failed.
        error: Why it failed, or None.
        read_at: The monotonic clock time of the read that produced it.
    """

    value: float | None
    error: str | None
    read_at: float


# --- source 1: RAPL energy ---------------------------------------------------


@dataclass(slots=True)
class _RaplDomain:
    """One powercap domain, and the state needed to turn energy into power."""

    device: str
    label: str
    energy_path: Path
    max_energy_uj: int
    last_energy_uj: int | None = None
    last_read_at: float | None = None
    total_joules: float = 0.0


def _read_text(path: Path) -> str | None:
    """Read a sysfs file and return its stripped text, or None when it cannot be read."""
    try:
        return path.read_text(errors="replace").strip()
    except OSError as exc:
        logger.debug("cannot read %s: %s", path, exc)
        return None


def _read_int(path: Path) -> int | None:
    """Read a sysfs file and return it as an integer, or None when it is not one."""
    text = _read_text(path)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        logger.debug("not an integer in %s: %r", path, text)
        return None


def _rapl_label(name: str, parent_name: str | None) -> str:
    """Return the name a person should see for one powercap domain.

    `package-0` is the whole CPU package. The `core` domain under it is **not**
    the power of all twelve cores: `exp-0003` and the capture of 2026-09-22
    both show it tracking one core. On 2026-09-22 the `core` domain gave
    1.69 W while `turbostat` gave 2.55 W for CPU 0 and 22.80 W for all cores.
    So it is labelled "Core 0", never "Cores".

    Since `exp-0012` the same core is also read from its own register, and the
    two agreed to 0.001 W the first time they were shown side by side. Two rows
    with one label would be unreadable, so this one says where it comes from.

    Args:
        name: The domain's own `name` file.
        parent_name: The `name` of the package above it, or None at the top.

    Returns:
        The label.
    """
    if parent_name is None:
        if name == "package-0":
            return "CPU Package"
        if name.startswith("package-"):
            return f"CPU Package {name.removeprefix('package-')}"
        return f"CPU {name}"
    if name == "core":
        return "CPU Core 0 (RAPL)"
    if name == "uncore":
        return "CPU Uncore"
    if name == "dram":
        return "Memory"
    return f"CPU {name}"


class RaplSampler:
    """Read the powercap energy counters and turn them into power.

    A RAPL domain gives a counter in microjoules that only climbs, and wraps at
    `max_energy_range_uj`. Power is the rise divided by the time it took. The
    first sample can give no power at all, because there is nothing to compare
    it with; that is reported as an error, not as zero.
    """

    def __init__(self, root: Path = DEFAULT_RAPL_ROOT, clock: Callable[[], float] = time.monotonic) -> None:
        """Create the sampler.

        Args:
            root: The directory that holds the powercap domains. A test points
                this at a temporary tree.
            clock: The source of time. It must not go backwards.
        """
        self.root = Path(root)
        self.clock = clock
        self._domains: list[_RaplDomain] = []
        self._values: dict[tuple[str, str], Value] = {}

    def discover(self) -> list[Channel]:
        """Find every powercap domain and return the channels it can give.

        Only the domain's `name` and `max_energy_range_uj` are read here, and
        both are world readable, so a client with no root can call this to
        learn what it is missing.
        """
        self._domains = []
        channels: list[Channel] = []
        if not self.root.is_dir():
            logger.info("no %s on this machine; no CPU energy channels", self.root)
            return []

        for entry in sorted(self.root.iterdir(), key=lambda path: path.name):
            if not RAPL_DOMAIN_PATTERN.match(entry.name):
                continue
            name = _read_text(entry / "name")
            max_energy = _read_int(entry / "max_energy_range_uj")
            if name is None or max_energy is None or max_energy <= 0:
                logger.warning("skipping powercap domain %s: no usable name or range", entry.name)
                continue

            parent_name = None
            if entry.name.count(":") > 1:
                parent_dir = entry.parent / entry.name.rpartition(":")[0]
                parent_name = _read_text(parent_dir / "name")
            device = name if parent_name is None else f"{parent_name}.{name}"
            label = _rapl_label(name, parent_name)
            energy_path = entry / "energy_uj"

            self._domains.append(
                _RaplDomain(
                    device=device,
                    label=label,
                    energy_path=energy_path,
                    max_energy_uj=max_energy,
                )
            )
            # No `high` is given. This board declares no RAPL power constraint
            # file, so any top of scale would be invented. ADR 0009 forbids
            # that; a channel with no scale simply gets no bar.
            channels.append(
                Channel(
                    device=device,
                    channel="power",
                    label=f"{label} Power",
                    group="cpu",
                    unit="watt",
                    low=0.0,
                    origin=str(energy_path),
                )
            )
            channels.append(
                Channel(
                    device=device,
                    channel="energy",
                    label=f"{label} Energy",
                    group="cpu",
                    unit="joule",
                    low=0.0,
                    origin=str(energy_path),
                )
            )

        logger.info("RAPL: %d domains, %d channels", len(self._domains), len(channels))
        return channels

    def sample(self) -> None:
        """Read every domain once and work out the power since the last read."""
        now = self.clock()
        for domain in self._domains:
            energy_uj = _read_int(domain.energy_path)
            if energy_uj is None:
                message = f"cannot read {domain.energy_path}; the helper needs root for it"
                self._values[(domain.device, "power")] = Value(None, message, now)
                self._values[(domain.device, "energy")] = Value(None, message, now)
                continue

            if domain.last_energy_uj is None or domain.last_read_at is None:
                domain.last_energy_uj = energy_uj
                domain.last_read_at = now
                waiting = "waiting for a second energy sample"
                self._values[(domain.device, "power")] = Value(None, waiting, now)
                self._values[(domain.device, "energy")] = Value(0.0, None, now)
                continue

            elapsed = now - domain.last_read_at
            # The counter wraps at max_energy_range_uj. The modulo gives the
            # right rise across a wrap, and the right rise when there is none.
            rise_uj = (energy_uj - domain.last_energy_uj) % (domain.max_energy_uj + 1)
            domain.last_energy_uj = energy_uj
            domain.last_read_at = now
            domain.total_joules += rise_uj / 1_000_000.0

            self._values[(domain.device, "energy")] = Value(domain.total_joules, None, now)
            if elapsed <= 0.0:
                self._values[(domain.device, "power")] = Value(None, "no time passed between samples", now)
            else:
                self._values[(domain.device, "power")] = Value(rise_uj / 1_000_000.0 / elapsed, None, now)

    def values(self) -> dict[tuple[str, str], Value]:
        """Return the last value of every channel."""
        return dict(self._values)


# --- source 3: per-core energy MSRs ------------------------------------------
#
# `exp-0012`, 2026-09-22. The powercap `core` domain above is **core 0 only**.
# The processor holds one energy counter for EACH core, and any root process
# may read it. Nothing is written to get it: `os.pread` on `/dev/cpu/N/msr` is
# a read, and the answer matched `turbostat` to 0.1 % under an all-core load.
#
# The route the plan used to name — `ryzen_smu` or `zenpower3` — writes a
# command word into the SMU mailbox to obtain the same numbers. That is a write
# to hardware, which ADR 0007 forbids with no exceptions. This route removes
# the question.
#
# The MSR numbers are not from memory. They are in this kernel's own header,
# `/usr/src/linux-headers-$(uname -r)/arch/x86/include/asm/msr-index.h`:
#
#   0xc0010299  MSR_AMD_RAPL_POWER_UNIT     bits 12:8 hold ESU
#   0xc001029a  MSR_AMD_CORE_ENERGY_STATUS  one counter for each core
#
# Reading them needs CAP_SYS_RAWIO, which `man 7 capabilities` states for
# "open devices for accessing x86 model-specific registers", and it needs the
# `msr` module, which `scripts/install-helper.sh` makes load at boot.

MSR_AMD_RAPL_POWER_UNIT = 0xC0010299
MSR_AMD_CORE_ENERGY_STATUS = 0xC001029A

# The counter is a 32-bit field inside a 64-bit register, and it wraps. At the
# 104 W this machine reached in `exp-0012`, one core counter wraps about every
# ten minutes. A reader that ignores that reports a large negative power.
CORE_COUNTER_SPAN = 1 << 32

# Bits 12:8 of the unit register hold ESU. One count is 1/2**ESU joules. This
# machine reads ESU = 16, so 15.2588 microjoules.
ENERGY_UNIT_SHIFT = 8
ENERGY_UNIT_MASK = 0x1F

# These MSRs arrived with Zen (family 17h). The check keeps the helper quiet on
# any other processor instead of reading a register that means something else
# there.
AMD_VENDOR = "AuthenticAMD"
MIN_AMD_FAMILY = 0x17

DEFAULT_CPU_SYS_ROOT = Path("/sys/devices/system/cpu")
DEFAULT_MSR_ROOT = Path("/dev/cpu")

CORE_ENERGY_DEVICE = "cpu-cores"


@dataclass(slots=True)
class _Core:
    """One physical core, and the state needed to turn energy into power."""

    core_id: int
    cpu: int
    msr_path: Path
    fd: int | None = None
    last_counts: int | None = None
    last_read_at: float | None = None


def read_cpu_vendor_and_family(cpuinfo_path: Path) -> tuple[str | None, int | None]:
    """Return the vendor and the family of the first processor in a cpuinfo file.

    Args:
        cpuinfo_path: The file to read, normally `/proc/cpuinfo`.

    Returns:
        The vendor string and the family number. Either is None when the file
        does not give it.
    """
    vendor: str | None = None
    family: int | None = None
    text = _read_text(cpuinfo_path)
    if text is None:
        return None, None
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            continue
        key = key.strip()
        value = value.strip()
        if key == "vendor_id" and vendor is None:
            vendor = value
        elif key == "cpu family" and family is None:
            try:
                family = int(value)
            except ValueError:
                family = None
        if vendor is not None and family is not None:
            break
    return vendor, family


def _first_thread_of_each_core(cpu_sys_root: Path) -> list[tuple[int, int]]:
    """Return (core id, thread) for one thread of every physical core.

    The counter is per core, so reading both threads of a core would read the
    same register twice. `exp-0012` proved this: with one thread busy, exactly
    one core counter moved.

    Args:
        cpu_sys_root: The directory that holds `cpu0`, `cpu1` and so on.

    Returns:
        The pairs, ordered by core id.
    """
    first_thread: dict[int, int] = {}
    if not cpu_sys_root.is_dir():
        return []
    for entry in cpu_sys_root.iterdir():
        if not re.fullmatch(r"cpu\d+", entry.name):
            continue
        cpu = int(entry.name.removeprefix("cpu"))
        core_id = _read_int(entry / "topology" / "core_id")
        if core_id is None:
            continue
        if core_id not in first_thread or cpu < first_thread[core_id]:
            first_thread[core_id] = cpu
    return [(core_id, first_thread[core_id]) for core_id in sorted(first_thread)]


class CoreEnergySampler:
    """Read the per-core energy MSRs and turn them into power.

    Like RAPL, the register gives a counter that only climbs. Power is the rise
    divided by the time it took, so the first sample can give no power at all.
    """

    def __init__(
        self,
        cpu_sys_root: Path = DEFAULT_CPU_SYS_ROOT,
        msr_root: Path = DEFAULT_MSR_ROOT,
        cpuinfo_path: Path = Path("/proc/cpuinfo"),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create the sampler.

        Args:
            cpu_sys_root: The sysfs directory that holds the CPU topology.
            msr_root: The directory that holds `0/msr`, `1/msr` and so on.
            cpuinfo_path: The file that names the vendor and the family.
            clock: The source of time. It must not go backwards.
        """
        self.cpu_sys_root = Path(cpu_sys_root)
        self.msr_root = Path(msr_root)
        self.cpuinfo_path = Path(cpuinfo_path)
        self.clock = clock
        self._cores: list[_Core] = []
        self._values: dict[tuple[str, str], Value] = {}
        self._joules_per_count: float | None = None
        self._unit_error: str | None = None

    # --- discovery ----------------------------------------------------------

    def discover(self) -> list[Channel]:
        """Find every core that has an MSR node, and return its channels.

        This reads the vendor, the family and the topology, which any user may
        read, and it checks that the MSR node exists. It does not open it, so a
        client with no root can call this and learn what it is missing.
        """
        self._cores = []
        self._close_all()

        vendor, family = read_cpu_vendor_and_family(self.cpuinfo_path)
        if vendor != AMD_VENDOR or family is None or family < MIN_AMD_FAMILY:
            logger.info(
                "no per-core energy channels: vendor %r family %r is not AMD family 0x%x or later",
                vendor,
                family,
                MIN_AMD_FAMILY,
            )
            return []

        channels: list[Channel] = []
        for core_id, cpu in _first_thread_of_each_core(self.cpu_sys_root):
            msr_path = self.msr_root / str(cpu) / "msr"
            if not msr_path.exists():
                logger.warning("no %s; the msr module is not loaded, so core %d cannot be read", msr_path, core_id)
                continue
            self._cores.append(_Core(core_id=core_id, cpu=cpu, msr_path=msr_path))
            channels.append(
                Channel(
                    device=f"{CORE_ENERGY_DEVICE}.core-{core_id}",
                    channel="power",
                    label=f"CPU Core {core_id} Power",
                    group="cpu",
                    unit="watt",
                    low=0.0,
                    origin=f"{msr_path}:{MSR_AMD_CORE_ENERGY_STATUS:#x}",
                )
            )

        if not channels:
            return []

        # The sum. It is the number the powercap tree cannot give, because its
        # `core` domain is core 0 alone.
        channels.append(
            Channel(
                device=CORE_ENERGY_DEVICE,
                channel="power",
                label="CPU Cores Power",
                group="cpu",
                unit="watt",
                low=0.0,
                origin=f"the sum of {len(self._cores)} core counters at {MSR_AMD_CORE_ENERGY_STATUS:#x}",
            )
        )
        logger.info("core energy: %d cores, %d channels", len(self._cores), len(channels))
        return channels

    # --- reading ------------------------------------------------------------

    def sample(self) -> None:
        """Read every core counter once and work out the power since the last read."""
        now = self.clock()
        if not self._cores:
            return

        unit = self._energy_unit()
        if unit is None:
            for core in self._cores:
                self._values[(f"{CORE_ENERGY_DEVICE}.core-{core.core_id}", "power")] = Value(
                    None, self._unit_error, now
                )
            self._values[(CORE_ENERGY_DEVICE, "power")] = Value(None, self._unit_error, now)
            return

        total: float | None = 0.0
        for core in self._cores:
            watts, error = self._core_watts(core, unit, now)
            self._values[(f"{CORE_ENERGY_DEVICE}.core-{core.core_id}", "power")] = Value(watts, error, now)
            if watts is None or total is None:
                total = None
            else:
                total += watts

        if total is None:
            self._values[(CORE_ENERGY_DEVICE, "power")] = Value(None, "not every core gave a value", now)
        else:
            self._values[(CORE_ENERGY_DEVICE, "power")] = Value(total, None, now)

    def _core_watts(self, core: _Core, joules_per_count: float, now: float) -> tuple[float | None, str | None]:
        """Return the power of one core, or the reason there is none."""
        counts, error = self._read_msr(core, MSR_AMD_CORE_ENERGY_STATUS)
        if counts is None:
            return None, error
        counts &= CORE_COUNTER_SPAN - 1

        if core.last_counts is None or core.last_read_at is None:
            core.last_counts = counts
            core.last_read_at = now
            return None, "waiting for a second energy sample"

        elapsed = now - core.last_read_at
        rise = (counts - core.last_counts) % CORE_COUNTER_SPAN
        core.last_counts = counts
        core.last_read_at = now
        if elapsed <= 0.0:
            return None, "no time passed between samples"
        return rise * joules_per_count / elapsed, None

    def _energy_unit(self) -> float | None:
        """Return the joules of one count, reading the unit register once."""
        if self._joules_per_count is not None:
            return self._joules_per_count
        if not self._cores:
            return None
        raw, error = self._read_msr(self._cores[0], MSR_AMD_RAPL_POWER_UNIT)
        if raw is None:
            self._unit_error = error
            return None
        esu = (raw >> ENERGY_UNIT_SHIFT) & ENERGY_UNIT_MASK
        self._joules_per_count = 1.0 / float(1 << esu)
        self._unit_error = None
        logger.info("core energy: one count is %.4f microjoules (ESU %d)", self._joules_per_count * 1e6, esu)
        return self._joules_per_count

    def _read_msr(self, core: _Core, register: int) -> tuple[int | None, str | None]:
        """Read one 64-bit register of one core. It opens for reading only."""
        if core.fd is None:
            try:
                core.fd = os.open(core.msr_path, os.O_RDONLY)
            except OSError as exc:
                return None, _msr_open_error(core.msr_path, exc)
        try:
            raw = os.pread(core.fd, 8, register)
        except OSError as exc:
            self._close(core)
            return None, f"cannot read {register:#x} from {core.msr_path}: {exc.strerror}"
        if len(raw) != 8:
            self._close(core)
            return None, f"{core.msr_path} gave {len(raw)} bytes for {register:#x}, not 8"
        return int.from_bytes(raw, "little"), None

    # --- clean-up -----------------------------------------------------------

    def _close(self, core: _Core) -> None:
        """Close one core's descriptor, if it is open."""
        if core.fd is not None:
            with contextlib.suppress(OSError):
                os.close(core.fd)
            core.fd = None

    def _close_all(self) -> None:
        """Close every open descriptor."""
        for core in self._cores:
            self._close(core)

    def close(self) -> None:
        """Close every descriptor this sampler holds. No hardware is touched."""
        self._close_all()

    def values(self) -> dict[tuple[str, str], Value]:
        """Return the last value of every channel."""
        return dict(self._values)


def _msr_open_error(path: Path, exc: OSError) -> str:
    """Return a message that says what to do, not only what failed."""
    if exc.errno == errno.ENOENT:
        return f"no {path}; the msr module is not loaded (modprobe msr)"
    if exc.errno in (errno.EACCES, errno.EPERM):
        return f"cannot open {path}; an MSR read needs root with CAP_SYS_RAWIO"
    if exc.errno == errno.EIO:
        return f"{path} refused the read; kernel lockdown can block this"
    return f"cannot open {path}: {exc.strerror}"


# --- source 2: NVMe SMART ----------------------------------------------------


@dataclass(frozen=True, slots=True)
class _SmartField:
    """One field of the SMART log, and how it becomes a channel.

    Attributes:
        channel: The channel name.
        label: The label for a person.
        unit: A `sensors_gui.model.Unit` value, as text.
        field: The key in the JSON that `nvme smart-log -o json` prints.
        convert: The call that turns the raw number into the display unit.
        low: The bottom of a meter scale, when one is known.
        high: The top of a meter scale, when one is known.
    """

    channel: str
    label: str
    unit: str
    field: str
    convert: Callable[[float], float] = float
    low: float | None = None
    high: float | None = None


def _data_units_to_bytes(units: float) -> float:
    """Return the byte count for an NVMe data-unit count.

    One data unit is 1000 blocks of 512 bytes. NVM Express Base Specification,
    log page 02h.
    """
    return units * NVME_DATA_UNIT_BYTES


def _minutes_to_seconds(minutes: float) -> float:
    """Return seconds for a field the NVMe specification records in minutes."""
    return minutes * SECONDS_PER_MINUTE


# The health set, chosen by Gova on 2026-09-22. Every field name below was
# read from this machine, not guessed: see
# `data/probes/privileged-20260922T051641Z/nvme0-smart-log.json`,
# captured with nvme-cli 2.8.
#
# The two time bases are not the same, and the specification is the reason:
# `warning_temp_time` and `critical_comp_time` are counted in MINUTES, while
# `thm_temp1_total_time` and `thm_temp2_total_time` are counted in SECONDS.
# Both are published here in seconds.
SMART_FIELDS: tuple[_SmartField, ...] = (
    _SmartField("wear", "SSD Wear", "percent", "percent_used", low=0.0, high=100.0),
    _SmartField("spare", "Spare Available", "percent", "avail_spare", low=0.0, high=100.0),
    _SmartField("data_written", "Data Written", "byte", "data_units_written", _data_units_to_bytes),
    _SmartField("data_read", "Data Read", "byte", "data_units_read", _data_units_to_bytes),
    _SmartField("power_on_hours", "Power-On Hours", "hour", "power_on_hours"),
    _SmartField("power_cycles", "Power Cycles", "count", "power_cycles"),
    _SmartField("unsafe_shutdowns", "Unsafe Shutdowns", "count", "unsafe_shutdowns"),
    _SmartField("media_errors", "Media Errors", "count", "media_errors"),
    _SmartField("critical_warning", "Critical Warning", "count", "critical_warning"),
    _SmartField("throttle_t1_count", "Throttle T1 Count", "count", "thm_temp1_trans_count"),
    _SmartField("throttle_t2_count", "Throttle T2 Count", "count", "thm_temp2_trans_count"),
    _SmartField("throttle_t1_time", "Throttle T1 Time", "second", "thm_temp1_total_time"),
    _SmartField("throttle_t2_time", "Throttle T2 Time", "second", "thm_temp2_total_time"),
    _SmartField("warning_temp_time", "Warning Temp Time", "second", "warning_temp_time", _minutes_to_seconds),
    _SmartField("critical_temp_time", "Critical Temp Time", "second", "critical_comp_time", _minutes_to_seconds),
)


# nvme-cli prints its usage banner, in bold, whenever a command fails for any
# reason, and the real reason can be on either stream. Taking the first line of
# stderr gave "Usage: nvme smart-log ..." and hid "Permission denied", which is
# the one word that tells a person what to do. Found by running the helper.
_ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")
_BANNER_PREFIXES = ("Usage:", "usage:", "Retrieve", "Options:", "-", "The following")


def _failure_reason(stdout: str, stderr: str, returncode: int) -> str:
    """Return the most useful line nvme-cli printed when a command failed.

    Args:
        stdout: What the command wrote to its output stream.
        stderr: What it wrote to its error stream.
        returncode: The exit code, used when it printed nothing useful.

    Returns:
        One short line.
    """
    for stream in (stderr, stdout):
        for raw_line in stream.splitlines():
            line = _ANSI_PATTERN.sub("", raw_line).strip()
            if not line or line.startswith(_BANNER_PREFIXES):
                continue
            return line
    return f"exit code {returncode}"


def find_nvme_command() -> str | None:
    """Return the full path of the `nvme` program, or None when it is not installed."""
    return shutil.which("nvme")


@dataclass(slots=True)
class _NvmeController:
    """One NVMe controller the helper can ask for a SMART log."""

    device: str
    node: Path


def _nvme_device_key(sys_dir: Path) -> str | None:
    """Return a stable identity for one NVMe controller.

    The node name `nvme0` is an index, and ADR 0002 says an index is not an
    identity. The model and the serial number are engraved in the controller,
    so they are used instead.

    Args:
        sys_dir: The controller's directory under `/sys/class/nvme`.

    Returns:
        `model@serial`, or None when neither can be read.
    """
    model = _read_text(sys_dir / "model")
    serial = _read_text(sys_dir / "serial")
    if model and serial:
        return f"{model}@{serial}"
    if model:
        return model
    logger.warning("%s has no model; it cannot be identified stably", sys_dir)
    return None


class NvmeSampler:
    """Read the SMART / health log of every NVMe controller.

    The log is fetched by running `nvme smart-log -o json <node>`: a fixed
    argument list, no shell, and no part of it comes from the client. ADR 0009
    gives the reasons, of which the first is that the NVMe passthrough ioctl
    can carry a write command and this cannot.
    """

    def __init__(
        self,
        sys_root: Path = DEFAULT_NVME_SYS_ROOT,
        dev_root: Path = DEFAULT_DEV_ROOT,
        nvme_command: str | None = None,
        clock: Callable[[], float] = time.monotonic,
        timeout: float = NVME_COMMAND_TIMEOUT,
    ) -> None:
        """Create the sampler.

        Args:
            sys_root: The directory that holds the NVMe controllers.
            dev_root: The directory that holds the character devices.
            nvme_command: The `nvme` program, or None when there is none. The
                search of the PATH is `find_nvme_command()`, kept outside this
                class on purpose: a None that quietly searched the PATH made
                "nvme-cli is not installed" impossible to test on a machine
                that has it. A test gives a path to its own script, which is
                how the parsing is tested against a real process, not a mock.
            clock: The source of time. It must not go backwards.
            timeout: How long one SMART read may take before it is abandoned.
        """
        self.sys_root = Path(sys_root)
        self.dev_root = Path(dev_root)
        self.nvme_command = nvme_command
        self.clock = clock
        self.timeout = timeout
        self._controllers: list[_NvmeController] = []
        self._values: dict[tuple[str, str], Value] = {}

    def discover(self) -> list[Channel]:
        """Find every NVMe controller and return the channels it can give.

        Only `model` and `serial` are read here, and both are world readable,
        so a client with no root can call this to learn what it is missing.
        """
        self._controllers = []
        channels: list[Channel] = []
        if not self.sys_root.is_dir():
            logger.info("no %s on this machine; no SMART channels", self.sys_root)
            return []
        if self.nvme_command is None:
            logger.warning("nvme-cli is not installed; SMART channels will report an error")

        for entry in sorted(self.sys_root.iterdir(), key=lambda path: path.name):
            node = self.dev_root / entry.name
            if not node.exists():
                logger.warning("%s has no device node at %s; skipping", entry.name, node)
                continue
            device = _nvme_device_key(entry)
            if device is None:
                continue

            self._controllers.append(_NvmeController(device=device, node=node))
            origin = f"nvme smart-log -o json {node}"
            for field in SMART_FIELDS:
                channels.append(
                    Channel(
                        device=device,
                        channel=field.channel,
                        label=field.label,
                        group="storage",
                        unit=field.unit,
                        low=field.low,
                        high=field.high,
                        origin=origin,
                    )
                )

        logger.info("NVMe: %d controllers, %d channels", len(self._controllers), len(channels))
        return channels

    def sample(self) -> None:
        """Read the SMART log of every controller once."""
        for controller in self._controllers:
            now = self.clock()
            log, error = self._read_smart_log(controller.node)
            for field in SMART_FIELDS:
                key = (controller.device, field.channel)
                if error is not None:
                    self._values[key] = Value(None, error, now)
                    continue
                raw = log.get(field.field)
                if not isinstance(raw, int | float):
                    self._values[key] = Value(None, f"the SMART log has no usable {field.field}", now)
                    continue
                self._values[key] = Value(field.convert(float(raw)), None, now)

    def values(self) -> dict[tuple[str, str], Value]:
        """Return the last value of every channel."""
        return dict(self._values)

    def _read_smart_log(self, node: Path) -> tuple[dict[str, Any], str | None]:
        """Run the fixed SMART command for one node and parse its JSON.

        Returns:
            The parsed log and None, or an empty log and the reason it failed.
            This never raises: a drive that stops answering must not stop the
            helper.
        """
        if self.nvme_command is None:
            return {}, "nvme-cli is not installed"

        command = [self.nvme_command, "smart-log", "-o", "json", str(node)]
        try:
            completed = subprocess.run(  # noqa: S603 - a fixed argument list, no shell, no client input
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
            )
        except subprocess.TimeoutExpired:
            return {}, f"nvme smart-log took longer than {self.timeout:.0f} s"
        except OSError as exc:
            return {}, f"cannot run nvme smart-log: {exc}"

        if completed.returncode != 0:
            reason = _failure_reason(completed.stdout, completed.stderr, completed.returncode)
            return {}, f"nvme smart-log failed: {reason}"

        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            return {}, f"nvme smart-log did not give JSON: {exc}"
        if not isinstance(parsed, dict):
            return {}, "nvme smart-log gave JSON that is not an object"
        return parsed, None


# --- the catalogue both sides share -----------------------------------------


class Catalogue:
    """Every channel the helper publishes, and the last value of each.

    The client builds the same catalogue when it cannot reach the helper, so
    that the screen can show the rows with the reason "needs the helper"
    instead of hiding them. That is ADR 0005 rule 3, and it is why `discover`
    reads nothing that needs root.
    """

    def __init__(
        self,
        rapl: RaplSampler | None = None,
        nvme: NvmeSampler | None = None,
        cores: CoreEnergySampler | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create the catalogue.

        Args:
            rapl: The RAPL sampler, or None for the default one.
            nvme: The NVMe sampler, or None for the default one.
            cores: The per-core energy sampler, or None for the default one.
            clock: The source of time, used for the age of a value.
        """
        self.clock = clock
        self.rapl = rapl if rapl is not None else RaplSampler(clock=clock)
        self.nvme = nvme if nvme is not None else NvmeSampler(nvme_command=find_nvme_command(), clock=clock)
        self.cores = cores if cores is not None else CoreEnergySampler(clock=clock)
        self._channels: list[Channel] = []
        self._lock = threading.Lock()
        self._next_nvme_sample = 0.0

    def discover(self) -> list[Channel]:
        """Find every channel from both sources. This needs no root."""
        with self._lock:
            self._channels = self.rapl.discover() + self.cores.discover() + self.nvme.discover()
            return list(self._channels)

    def channels(self) -> list[Channel]:
        """Return the channels found by the last `discover` call."""
        with self._lock:
            return list(self._channels)

    def sample(self) -> None:
        """Read RAPL and the cores every time, and NVMe only when its own interval has passed."""
        with self._lock:
            self.rapl.sample()
            self.cores.sample()
            now = self.clock()
            if now >= self._next_nvme_sample:
                self._next_nvme_sample = now + NVME_INTERVAL
                self.nvme.sample()

    def readings(self) -> list[dict[str, Any]]:
        """Return the last value of every channel, in the wire format.

        A channel that has never been sampled is reported as an error, never
        as a zero.
        """
        with self._lock:
            values = {**self.rapl.values(), **self.cores.values(), **self.nvme.values()}
            now = self.clock()
            out: list[dict[str, Any]] = []
            for channel in self._channels:
                held = values.get(channel.key)
                if held is None:
                    out.append(
                        {
                            "device": channel.device,
                            "channel": channel.channel,
                            "value": None,
                            "error": "not sampled yet",
                            "age": None,
                        }
                    )
                    continue
                out.append(
                    {
                        "device": channel.device,
                        "channel": channel.channel,
                        "value": held.value,
                        "error": held.error,
                        "age": round(now - held.read_at, 3),
                    }
                )
            return out


def discover_channels(
    rapl_root: Path = DEFAULT_RAPL_ROOT,
    nvme_sys_root: Path = DEFAULT_NVME_SYS_ROOT,
    dev_root: Path = DEFAULT_DEV_ROOT,
    cpu_sys_root: Path = DEFAULT_CPU_SYS_ROOT,
    msr_root: Path = DEFAULT_MSR_ROOT,
    cpuinfo_path: Path = Path("/proc/cpuinfo"),
) -> list[Channel]:
    """Return every channel this machine would publish, without reading a value.

    This is the one function the client calls directly. It touches only world
    readable files, so it gives the same answer with or without root, and with
    or without the helper running.

    Args:
        rapl_root: The powercap directory.
        nvme_sys_root: The NVMe class directory.
        dev_root: The directory that holds the device nodes.
        cpu_sys_root: The sysfs directory that holds the CPU topology.
        msr_root: The directory that holds the MSR nodes.
        cpuinfo_path: The file that names the vendor and the family.

    Returns:
        The channels, in a fixed order.
    """
    rapl = RaplSampler(root=rapl_root)
    cores = CoreEnergySampler(cpu_sys_root=cpu_sys_root, msr_root=msr_root, cpuinfo_path=cpuinfo_path)
    nvme = NvmeSampler(sys_root=nvme_sys_root, dev_root=dev_root, nvme_command=find_nvme_command())
    return rapl.discover() + cores.discover() + nvme.discover()


# --- the server --------------------------------------------------------------


def handle_request(catalogue: Catalogue, line: str) -> dict[str, Any]:
    """Turn one request line into one response.

    This is a plain function with no socket in it, so that the whole protocol
    can be tested without one.

    Args:
        catalogue: The catalogue that answers.
        line: One line of the request stream.

    Returns:
        The response, ready to be written as JSON.
    """
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        return _error(f"the request is not JSON: {exc}")
    if not isinstance(request, dict):
        return _error("the request is not a JSON object")

    protocol = request.get("protocol")
    if protocol != PROTOCOL_VERSION:
        return _error(f"this helper speaks protocol {PROTOCOL_VERSION}, the request asked for {protocol!r}")

    command = request.get("command")
    if command == "describe":
        return {
            "protocol": PROTOCOL_VERSION,
            "ok": True,
            "command": "describe",
            "helper_version": HELPER_VERSION,
            "channels": [channel.as_dict() for channel in catalogue.channels()],
        }
    if command == "read":
        return {
            "protocol": PROTOCOL_VERSION,
            "ok": True,
            "command": "read",
            "readings": catalogue.readings(),
        }
    if command == "ping":
        return {"protocol": PROTOCOL_VERSION, "ok": True, "command": "ping", "helper_version": HELPER_VERSION}
    return _error(f"unknown command: {command!r}")


def _error(message: str) -> dict[str, Any]:
    """Return a failure response."""
    return {"protocol": PROTOCOL_VERSION, "ok": False, "error": message}


class _RequestHandler(socketserver.StreamRequestHandler):
    """Answer requests on one connection until the client closes it."""

    def handle(self) -> None:
        """Read request lines and write one response line for each."""
        catalogue: Catalogue = self.server.catalogue  # type: ignore[attr-defined]
        while True:
            try:
                raw = self.rfile.readline(MAX_REQUEST_BYTES)
            except OSError as exc:
                logger.debug("connection lost while reading: %s", exc)
                return
            if not raw:
                return
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                response = handle_request(catalogue, line)
            except Exception as exc:  # noqa: BLE001 - one bad request must not stop the helper
                logger.exception("failed to answer a request")
                response = _error(f"{type(exc).__name__}: {exc}")
            try:
                self.wfile.write((json.dumps(response) + "\n").encode("utf-8"))
                self.wfile.flush()
            except OSError as exc:
                logger.debug("connection lost while writing: %s", exc)
                return


class HelperServer(socketserver.ThreadingUnixStreamServer):
    """The Unix socket server, with the socket owned by root and read by one group."""

    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, socket_path: Path, catalogue: Catalogue, group: str | None) -> None:
        """Create and bind the server.

        Args:
            socket_path: Where the socket file goes.
            catalogue: The catalogue that answers requests.
            group: The group allowed to read the socket, or None to leave the
                socket owned by root alone.
        """
        self.socket_path = Path(socket_path)
        self.catalogue = catalogue
        self.group = group
        # Nothing is ever unlinked until this says the bind succeeded and the
        # file at that path is the socket this server made. socketserver calls
        # `server_close` when `server_bind` fails, and this helper runs as
        # root, so an unconditional unlink there would delete whatever stood in
        # the way. A test proves it does not.
        self._bound = False
        _remove_stale_socket(self.socket_path)
        # The socket is created inside bind, so the mode is set the moment
        # after. umask makes it tighter, never wider, in the gap.
        previous_umask = os.umask(0o177)
        try:
            super().__init__(str(self.socket_path), _RequestHandler)
        finally:
            os.umask(previous_umask)
        self._bound = True
        self._set_socket_permissions()

    def _set_socket_permissions(self) -> None:
        """Give the socket mode 0660 and the chosen group, as ADR 0005 requires."""
        if self.group is not None:
            try:
                gid = grp.getgrnam(self.group).gr_gid
            except KeyError:
                logger.error("there is no group %r; the socket stays owned by root alone", self.group)
            else:
                os.chown(self.socket_path, 0, gid)
        os.chmod(self.socket_path, SOCKET_MODE)
        logger.info("listening on %s, mode %o, group %s", self.socket_path, SOCKET_MODE, self.group or "root")

    def server_close(self) -> None:
        """Close the server and take its own socket file away with it.

        Only a socket this server bound is removed. A bind that failed leaves
        whatever was already at the path untouched.
        """
        super().server_close()
        if not self._bound:
            return
        try:
            if self.socket_path.is_socket():
                self.socket_path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            logger.warning("cannot remove %s: %s", self.socket_path, exc)


def _remove_stale_socket(path: Path) -> None:
    """Remove a socket file left behind by a helper that died.

    A path that is not a socket is left alone and the bind then fails, which is
    the safe result: the helper must never unlink an ordinary file.
    """
    try:
        is_socket = path.is_socket()
    except OSError:
        return
    if not is_socket:
        return
    try:
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            probe.connect(str(path))
        finally:
            probe.close()
    except OSError as exc:
        if exc.errno in (errno.ECONNREFUSED, errno.ENOENT):
            logger.warning("removing the stale socket %s", path)
            path.unlink(missing_ok=True)
            return
    raise SystemExit(f"{path} is already served by another sensors-guid; stop it first")


def _sample_forever(catalogue: Catalogue, stop: threading.Event, interval: float = RAPL_INTERVAL) -> None:
    """Sample every source on the helper's own clock until `stop` is set."""
    while not stop.is_set():
        try:
            catalogue.sample()
        except Exception:  # noqa: BLE001 - the sampler thread must never die
            logger.exception("a sample pass failed; carrying on")
        stop.wait(interval)


# --- the command line --------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="sensors-guid",
        description="The privileged, read-only sensor helper for sensors-gui. It never writes to hardware.",
    )
    parser.add_argument(
        "--socket",
        type=Path,
        default=DEFAULT_SOCKET_PATH,
        help=f"where to put the Unix socket (default: {DEFAULT_SOCKET_PATH})",
    )
    parser.add_argument(
        "--group",
        default=DEFAULT_SOCKET_GROUP,
        help=f"the group allowed to read the socket (default: {DEFAULT_SOCKET_GROUP})",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="sample twice, print the readings as JSON, and exit. No socket is made.",
    )
    parser.add_argument("--verbose", action="store_true", help="log every step")
    return parser


def run_once(catalogue: Catalogue, settle: float = RAPL_INTERVAL) -> dict[str, Any]:
    """Sample, wait, sample again, and return the describe and read answers together.

    Two passes are needed because power is a difference between two energy
    readings. One pass can only ever report "waiting for a second sample".

    Args:
        catalogue: The catalogue to sample.
        settle: How long to wait between the two passes.

    Returns:
        A dictionary holding the channels and the readings.
    """
    catalogue.discover()
    catalogue.sample()
    time.sleep(settle)
    catalogue.sample()
    return {
        "protocol": PROTOCOL_VERSION,
        "helper_version": HELPER_VERSION,
        "channels": [channel.as_dict() for channel in catalogue.channels()],
        "readings": catalogue.readings(),
    }


def main(argv: list[str] | None = None) -> int:
    """Run the helper.

    Args:
        argv: The command line, or None for `sys.argv`.

    Returns:
        The exit code.
    """
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if os.geteuid() != 0:
        logger.warning("sensors-guid is not running as root; every privileged value will report an error")

    catalogue = Catalogue()

    if args.once:
        print(json.dumps(run_once(catalogue), indent=2))
        return 0

    found = catalogue.discover()
    if not found:
        logger.error("no privileged channels on this machine; nothing to serve")
        return 1

    stop = threading.Event()
    sampler = threading.Thread(target=_sample_forever, args=(catalogue, stop), name="sampler", daemon=True)
    sampler.start()

    server = HelperServer(args.socket, catalogue, args.group)

    def shut_down(signum: int, _frame: object) -> None:
        logger.info("signal %d; shutting down", signum)
        stop.set()
        threading.Thread(target=server.shutdown, name="shutdown", daemon=True).start()

    signal.signal(signal.SIGTERM, shut_down)
    signal.signal(signal.SIGINT, shut_down)

    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()
    logger.info("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
