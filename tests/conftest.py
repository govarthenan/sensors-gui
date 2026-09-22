"""Shared fixtures.

Every fixture here builds a real thing: a real directory tree, a real file, a
real program. The project uses no mocks.

`fake_hwmon_root` builds a real directory tree that copies the shape of
`/sys/class/hwmon` on `dst-gova-pc`. It is a real filesystem, not a mock: the
collector opens real files. The values are the ones this machine reported on
2026-09-16, recorded in `lab/exp-0001-hwmon-sweep/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# name -> (device sub-path, {attribute file: contents})
FAKE_DEVICES: dict[str, tuple[str, dict[str, str]]] = {
    "hwmon2": (
        "devices/pci0000:00/0000:00:18.3",
        {
            "name": "k10temp",
            "temp1_input": "41000",
            "temp1_label": "Tctl",
            "temp3_input": "33500",
            "temp3_label": "Tccd1",
            "temp4_input": "29250",
            "temp4_label": "Tccd2",
        },
    ),
    "hwmon3": (
        "devices/pci0000:00/0000:00:14.0/i2c-0/0-0051",
        {
            "name": "spd5118",
            "temp1_input": "30250",
            "temp1_max": "55000",
            "temp1_crit": "85000",
        },
    ),
    "hwmon4": (
        "devices/pci0000:00/0000:00:14.0/i2c-0/0-0053",
        {
            "name": "spd5118",
            "temp1_input": "28750",
            "temp1_max": "55000",
            "temp1_crit": "85000",
        },
    ),
    "hwmon5": (
        "devices/pci0000:00/0000:00:08.1/0000:74:00.0",
        {
            "name": "amdgpu",
            "temp1_input": "38000",
            "temp1_label": "edge",
            "in0_input": "1305",
            "in0_label": "vddgfx",
            "power1_input": "14000",
            "power1_label": "PPT",
            "freq1_input": "600000000",
            "freq1_label": "sclk",
        },
    ),
    "hwmon1": (
        "devices/pci0000:00/0000:00:01.2/0000:02:00.0/nvme/nvme0",
        {
            "name": "nvme",
            "temp1_input": "32850",
            "temp1_label": "Composite",
            "temp1_crit": "87850",
            "temp1_max": "83850",
            "temp2_input": "45850",
            "temp2_label": "Sensor 1",
            "temp2_max": "65261850",
        },
    ),
    "hwmon6": (
        "devices/pci0000:00/0000:00:02.1/usb1/hidpp",
        {"name": "hidpp_battery_2"},
    ),
    # The nct6687 driver writes the running minimum and maximum it has seen
    # into `_min` and `_max`, not a threshold. Here `temp1_max` equals
    # `temp1_input`, which is what the real driver does on this machine.
    "hwmon7": (
        "devices/platform/nct6687.2592",
        {
            "name": "nct6687",
            "temp1_input": "58000",
            "temp1_label": "CPU",
            "temp1_min": "58000",
            "temp1_max": "58000",
            "temp3_input": "39500",
            "temp3_label": "VRM MOS",
            "temp3_min": "39500",
            "temp3_max": "39500",
            "fan1_input": "2247",
            "fan1_label": "CPU Fan",
            "fan1_min": "2222",
            "fan1_max": "2272",
            "fan4_input": "0",
            "fan4_label": "System Fan #2",
            "in0_input": "12120",
            "in0_label": "+12V",
            "in0_min": "12120",
            "in0_max": "12120",
        },
    ),
}


@pytest.fixture
def fake_hwmon_root(tmp_path: Path) -> Path:
    """Build a copy of this machine's `/sys/class/hwmon` in a temporary directory."""
    sys_root = tmp_path / "sys"
    hwmon_root = sys_root / "class" / "hwmon"
    hwmon_root.mkdir(parents=True)

    for hwmon_name, (device_subpath, files) in FAKE_DEVICES.items():
        device_dir = sys_root / device_subpath / "hwmon" / hwmon_name
        device_dir.mkdir(parents=True)
        for file_name, contents in files.items():
            (device_dir / file_name).write_text(contents + "\n")
        (hwmon_root / hwmon_name).symlink_to(device_dir)

    return hwmon_root


# --- phase 2: the privileged helper ------------------------------------------
#
# The same rule as `fake_hwmon_root` above: these are real directories, real
# files and a real program, never a mock. The values are the ones this machine
# reported on 2026-09-22, recorded in
# `data/probes/privileged-20260922T051641Z/`.

# `max_energy_range_uj` of both RAPL domains on dst-gova-pc.
FAKE_MAX_ENERGY_UJ = 65532610987

# The SMART log of the WD_BLACK SN770, exactly as `nvme smart-log -o json
# /dev/nvme0` printed it on 2026-09-22 under nvme-cli 2.8. A copy, not a link:
# the probe directory can be tidied away, and this test must still run.
REAL_SMART_LOG: dict[str, int] = {
    "critical_warning": 0,
    "temperature": 318,
    "avail_spare": 100,
    "spare_thresh": 10,
    "percent_used": 0,
    "endurance_grp_critical_warning_summary": 0,
    "data_units_read": 5149676,
    "data_units_written": 19702733,
    "host_read_commands": 91619714,
    "host_write_commands": 570202432,
    "controller_busy_time": 345,
    "power_cycles": 150,
    "power_on_hours": 331,
    "unsafe_shutdowns": 31,
    "media_errors": 0,
    "num_err_log_entries": 0,
    "warning_temp_time": 0,
    "critical_comp_time": 0,
    "temperature_sensor_1": 339,
    "temperature_sensor_2": 315,
    "thm_temp1_trans_count": 0,
    "thm_temp2_trans_count": 0,
    "thm_temp1_total_time": 0,
    "thm_temp2_total_time": 0,
}


class FakePowercap:
    """A real directory tree shaped like `/sys/class/powercap` on this machine."""

    def __init__(self, root: Path) -> None:
        """Build the tree with both domains this machine has."""
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.package = self._make_domain("intel-rapl:0", "package-0")
        self.core = self._make_domain("intel-rapl:0:0", "core")

    def _make_domain(self, dir_name: str, name: str) -> Path:
        domain = self.root / dir_name
        domain.mkdir()
        (domain / "name").write_text(name + "\n")
        (domain / "max_energy_range_uj").write_text(f"{FAKE_MAX_ENERGY_UJ}\n")
        (domain / "energy_uj").write_text("0\n")
        return domain

    def set_energy(self, domain: Path, energy_uj: int) -> None:
        """Put a new value in one domain's counter, as the hardware would."""
        (domain / "energy_uj").write_text(f"{energy_uj}\n")

    def make_unreadable(self, domain: Path) -> None:
        """Take the counter away, the way mode 0400 takes it away from a normal user."""
        (domain / "energy_uj").unlink()


class FakeNvme:
    """A real NVMe controller tree, a real device node and a real `nvme` program.

    The program is a small shell script. It prints whatever
    `set_output` last stored and exits with whatever `set_exit_code` last
    stored, so a test drives a real process through a real pipe.
    """

    def __init__(self, root: Path, model: str = "WD_BLACK SN770 1TB", serial: str = "234639803238") -> None:
        """Build the tree, the node and the program."""
        self.sys_root = root / "sys" / "class" / "nvme"
        self.dev_root = root / "dev"
        self.sys_root.mkdir(parents=True)
        self.dev_root.mkdir(parents=True)

        controller = self.sys_root / "nvme0"
        controller.mkdir()
        (controller / "model").write_text(model + "\n")
        (controller / "serial").write_text(serial + "\n")
        self.device = f"{model}@{serial}"

        # A plain file stands in for the character device. The helper only
        # checks that the node exists and passes its path to the program.
        (self.dev_root / "nvme0").write_text("")

        self._stdout = root / "nvme-stdout"
        self._stderr = root / "nvme-stderr"
        self._code = root / "nvme-exit-code"
        self.set_output(json.dumps(REAL_SMART_LOG))

        self.command = root / "fake-nvme"
        self.command.write_text(
            f'#!/bin/sh\ncat "{self._stdout}"\ncat "{self._stderr}" >&2\nexit "$(cat "{self._code}")"\n'
        )
        self.command.chmod(0o755)

    def set_output(self, stdout: str, stderr: str = "", exit_code: int = 0) -> None:
        """Choose what the next run of the program prints and returns."""
        self._stdout.write_text(stdout)
        self._stderr.write_text(stderr)
        self._code.write_text(str(exit_code))


@pytest.fixture
def fake_powercap(tmp_path: Path) -> FakePowercap:
    """A copy of this machine's `/sys/class/powercap` in a temporary directory."""
    return FakePowercap(tmp_path / "powercap")


@pytest.fixture
def fake_nvme(tmp_path: Path) -> FakeNvme:
    """A copy of this machine's NVMe controller, with a real stand-in `nvme` program."""
    return FakeNvme(tmp_path / "nvme")
