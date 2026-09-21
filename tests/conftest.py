"""Shared fixtures.

`fake_hwmon_root` builds a real directory tree that copies the shape of
`/sys/class/hwmon` on `dst-gova-pc`. It is a real filesystem, not a mock: the
collector opens real files. The values are the ones this machine reported on
2026-09-16, recorded in `lab/exp-0001-hwmon-sweep/`.
"""

from __future__ import annotations

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
