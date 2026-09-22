"""Sample the RTX 4090 thermal fields while the load changes.

The question: are the three `*_TLIMIT` fields live margins, or constants?
If they are live, one of them gives the hotspot temperature that NVML does not
report directly.

This script only reads. Usage:
    uv run python lab/exp-0013-rtx4090-board-sensors/watch-tlimit.py <seconds>
"""

from __future__ import annotations

import csv
import ctypes
import sys
import time
from datetime import UTC, datetime

import pynvml

FIELDS = {
    "tlimit_shutdown": "NVML_FI_DEV_TEMPERATURE_SHUTDOWN_TLIMIT",
    "tlimit_slowdown": "NVML_FI_DEV_TEMPERATURE_SLOWDOWN_TLIMIT",
    "tlimit_gpu_max": "NVML_FI_DEV_TEMPERATURE_GPU_MAX_TLIMIT",
}


def field_value(handle: object, field_id: int) -> int | None:
    """Return one NVML field as a signed integer, or None when it is refused."""
    values = pynvml.nvmlDeviceGetFieldValues(handle, [field_id])
    value = values[0]
    if value.nvmlReturn != 0:
        return None
    return value.value.siVal


def fan_rpm(handle: object, index: int) -> int | None:
    """Return the speed of one fan in RPM, or None when the driver refuses."""
    info = pynvml.c_nvmlFanSpeedInfo_t()
    info.version = pynvml.nvmlFanSpeedInfo_v1
    info.fan = index
    function = pynvml._nvmlGetFunctionPointer("nvmlDeviceGetFanSpeedRPM")
    if function(handle, ctypes.byref(info)) != 0:
        return None
    return info.speed


def main() -> int:
    """Sample every second and write one CSV row for each sample."""
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    ids = {key: getattr(pynvml, name) for key, name in FIELDS.items()}

    writer = csv.writer(sys.stdout)
    writer.writerow(["time", "edge_c", "power_w", "util_pct", "fan0_rpm", "fan1_rpm", *FIELDS])
    end = time.monotonic() + seconds
    try:
        while time.monotonic() < end:
            edge = pynvml.nvmlDeviceGetTemperature(handle, 0)
            power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000
            util = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
            row = [
                datetime.now(UTC).strftime("%H:%M:%S"),
                edge,
                f"{power:.1f}",
                util,
                fan_rpm(handle, 0),
                fan_rpm(handle, 1),
                *(field_value(handle, ids[key]) for key in FIELDS),
            ]
            writer.writerow(row)
            sys.stdout.flush()
            time.sleep(1.0)
    finally:
        pynvml.nvmlShutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
