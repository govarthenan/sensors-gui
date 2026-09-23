"""Read-only probe of the RTX 4090's two NVML fan channels, at idle.

Gova's question: which NVML fan channel (index 0 or 1) is the fan mounted ON the
card, and what does the other channel drive (the two radiator fans)? This script
does not answer that by itself — see README.md — it only gathers every read-only
NVML fact about the fans that this driver and this pynvml binding expose, once at
the start, plus a 60-second time series at 2 Hz.

This script calls no `nvmlDeviceSet*` function and touches no I2C bus. See ADR
0007 and ADR 0010. It does NOT load the GPU — no stress tool is run here, by the
owner's rule against heating the machine for a test. Run it with the machine
otherwise idle.

Usage:
    uv run python lab/exp-0017-gpu-fan-channels/probe.py
"""

from __future__ import annotations

import csv
import ctypes
import json
import socket
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pynvml

COMMAND = "uv run python lab/exp-0017-gpu-fan-channels/probe.py"
DURATION_S = 60.0
INTERVAL_S = 0.5  # 2 Hz
RESULTS_DIR = Path(__file__).parent / "results"

COOLER_TARGET_BITS = {
    "NONE": "NVML_THERMAL_COOLER_TARGET_NONE",
    "GPU": "NVML_THERMAL_COOLER_TARGET_GPU",
    "MEMORY": "NVML_THERMAL_COOLER_TARGET_MEMORY",
    "POWER_SUPPLY": "NVML_THERMAL_COOLER_TARGET_POWER_SUPPLY",
}


def fan_rpm(handle: Any, index: int) -> int | str:  # noqa: ANN401
    """Read one fan's RPM by index, through the raw function pointer.

    `pynvml.nvmlDeviceGetFanSpeedRPM` fixes the fan number at 0 in this binding
    (nvidia-ml-py); this calls the same NVML function through the same pointer
    with the fan number set, exactly as
    `lab/exp-0013-rtx4090-board-sensors/probe-nvml-fields.py` does. Read only.
    """
    try:
        info = pynvml.c_nvmlFanSpeedInfo_t()
        info.version = pynvml.nvmlFanSpeedInfo_v1
        info.fan = index
        function = pynvml._nvmlGetFunctionPointer("nvmlDeviceGetFanSpeedRPM")
        code = function(handle, ctypes.byref(info))
        if code != 0:
            return f"nvmlReturn={code}"
        return info.speed
    except pynvml.NVMLError as error:
        return str(error)


def cooler_info(handle: Any, index: int) -> dict[str, Any]:  # noqa: ANN401
    """Read `nvmlDeviceGetCoolerInfo` for one cooler index.

    The pynvml binding's own `nvmlDeviceGetCoolerInfo` wrapper hardcodes
    `index = 0`; this repeats its own approach with the index set to reach
    cooler 1, the same way `fan_rpm` above repeats `nvmlDeviceGetFanSpeedRPM`
    for fan 1. Read only — no `nvmlDeviceSet*` call exists for this structure.
    """
    try:
        info = pynvml.c_nvmlCoolerInfo_t()
        info.version = pynvml.nvmlCoolerInfo_v1
        info.index = index
        function = pynvml._nvmlGetFunctionPointer("nvmlDeviceGetCoolerInfo")
        code = function(handle, ctypes.byref(info))
        if code != 0:
            return {"error": f"nvmlReturn={code}"}
        control_type = int(info.coolerControlType)
        target_raw = int(info.coolerTarget)
        target_names = [name for name, const in COOLER_TARGET_BITS.items() if target_raw & getattr(pynvml, const)]
        return {
            "coolerControlType": control_type,
            "coolerTarget_raw": target_raw,
            "coolerTarget_names": target_names,
        }
    except pynvml.NVMLError as error:
        return {"error": str(error)}
    except Exception as error:  # the structure may not match this driver  # noqa: BLE001
        return {"error": f"{type(error).__name__}: {error}"}


def fan_or_cooler_field_constants() -> dict[int, str]:
    """Every `NVML_FI_*` field constant whose name contains FAN or COOLER."""
    out: dict[int, str] = {}
    for name in dir(pynvml):
        if not name.startswith("NVML_FI_"):
            continue
        upper = name.upper()
        if "FAN" not in upper and "COOLER" not in upper:
            continue
        value = getattr(pynvml, name)
        if isinstance(value, int):
            out[value] = name
    return out


def read_field(handle: Any, field_id: int) -> dict[str, Any]:  # noqa: ANN401
    """Read one NVML field value. Read only."""
    try:
        values = pynvml.nvmlDeviceGetFieldValues(handle, [field_id])
    except pynvml.NVMLError as error:
        return {"error": str(error)}
    value = values[0]
    if value.nvmlReturn != 0:
        return {"error": f"nvmlReturn={value.nvmlReturn}"}
    kinds = {0: "dVal", 1: "uiVal", 2: "ulVal", 3: "ullVal", 4: "sllVal", 5: "siVal"}
    attribute = kinds.get(value.valueType)
    return {
        "value": getattr(value.value, attribute) if attribute else None,
        "valueType": value.valueType,
        "latency_us": value.latencyUsec,
    }


def gather_once(handle: Any, count: int) -> dict[str, Any]:  # noqa: ANN401
    """Everything read once, at the start: counts, ranges, policy, targets, fields."""
    once: dict[str, Any] = {"num_fans": count}

    try:
        min_speed, max_speed = pynvml.nvmlDeviceGetMinMaxFanSpeed(handle)
        once["min_max_fan_speed_pct"] = {"min": min_speed, "max": max_speed}
    except pynvml.NVMLError as error:
        once["min_max_fan_speed_pct"] = {"error": str(error)}

    per_fan: dict[str, Any] = {}
    for index in range(count):
        entry: dict[str, Any] = {}
        try:
            entry["fan_control_policy"] = pynvml.nvmlDeviceGetFanControlPolicy_v2(handle, index)
        except pynvml.NVMLError as error:
            entry["fan_control_policy"] = {"error": str(error)}
        try:
            entry["target_fan_speed_pct"] = pynvml.nvmlDeviceGetTargetFanSpeed(handle, index)
        except pynvml.NVMLError as error:
            entry["target_fan_speed_pct"] = {"error": str(error)}
        entry["cooler_info"] = cooler_info(handle, index)
        per_fan[f"fan_{index}"] = entry
    once["per_fan"] = per_fan

    fields = fan_or_cooler_field_constants()
    once["fan_or_cooler_field_constants_found"] = fields
    once["fan_or_cooler_field_values"] = {name: read_field(handle, fid) for fid, name in fields.items()}

    return once


def sample(handle: Any) -> dict[str, Any]:  # noqa: ANN401
    """One 2 Hz sample of the live channels."""
    try:
        temperature: int | str = pynvml.nvmlDeviceGetTemperature(handle, 0)
    except pynvml.NVMLError as error:
        temperature = str(error)
    try:
        power_w: float | str = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000
    except pynvml.NVMLError as error:
        power_w = str(error)
    try:
        utilization: int | str = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
    except pynvml.NVMLError as error:
        utilization = str(error)
    try:
        legacy_fan_speed: int | str = pynvml.nvmlDeviceGetFanSpeed(handle)
    except pynvml.NVMLError as error:
        legacy_fan_speed = str(error)
    try:
        fan0_pct: int | str = pynvml.nvmlDeviceGetFanSpeed_v2(handle, 0)
    except pynvml.NVMLError as error:
        fan0_pct = str(error)
    try:
        fan1_pct: int | str = pynvml.nvmlDeviceGetFanSpeed_v2(handle, 1)
    except pynvml.NVMLError as error:
        fan1_pct = str(error)

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "temperature_c": temperature,
        "power_w": round(power_w, 1) if isinstance(power_w, float) else power_w,
        "utilization_pct": utilization,
        "fan0_rpm": fan_rpm(handle, 0),
        "fan1_rpm": fan_rpm(handle, 1),
        "fan0_pct": fan0_pct,
        "fan1_pct": fan1_pct,
        "legacy_fan_speed_pct": legacy_fan_speed,
    }


def main() -> int:
    """Run the once-off reads, then the 60 s / 2 Hz series, and write JSON + CSV."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    host = socket.gethostname()
    started = datetime.now(UTC)

    pynvml.nvmlInit()
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        driver = pynvml.nvmlSystemGetDriverVersion()
        nvml_version = pynvml.nvmlSystemGetNVMLVersion()
        device_name = pynvml.nvmlDeviceGetName(handle)
        count = pynvml.nvmlDeviceGetNumFans(handle)

        once = gather_once(handle, count)

        series: list[dict[str, Any]] = []
        end = time.monotonic() + DURATION_S
        next_tick = time.monotonic()
        while time.monotonic() < end:
            series.append(sample(handle))
            next_tick += INTERVAL_S
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
    finally:
        pynvml.nvmlShutdown()

    meta = {
        "command": COMMAND,
        "date": started.date().isoformat(),
        "host": host,
        "captured_utc": started.isoformat(),
        "driver": driver,
        "nvml": nvml_version,
        "device": device_name,
    }

    report = {"meta": meta, "once": once, "series": series}

    json_path = RESULTS_DIR / "probe.json"
    json_path.write_text(json.dumps(report, indent=2, default=str))

    csv_path = RESULTS_DIR / "probe-series.csv"
    columns = [
        "timestamp",
        "temperature_c",
        "power_w",
        "utilization_pct",
        "fan0_rpm",
        "fan1_rpm",
        "fan0_pct",
        "fan1_pct",
        "legacy_fan_speed_pct",
    ]
    with csv_path.open("w", newline="") as csv_file:
        csv_file.write(f"# command: {COMMAND}\n")
        csv_file.write(f"# date: {meta['date']}\n")
        csv_file.write(f"# host: {host}\n")
        writer = csv.writer(csv_file)
        writer.writerow(columns)
        for row in series:
            writer.writerow([row[column] for column in columns])

    print(f"Wrote {len(series)} samples over {DURATION_S:.0f}s to {json_path} and {csv_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
