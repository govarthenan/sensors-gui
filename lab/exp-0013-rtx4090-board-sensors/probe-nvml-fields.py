"""Read every NVML field, temperature sensor and fan channel the driver offers.

This script only reads. It calls no `nvmlDeviceSet*` function, and it never
touches an I2C bus. See ADR 0007 and ADR 0010.

Usage: uv run python lab/exp-0013-rtx4090-board-sensors/probe-nvml-fields.py
"""

from __future__ import annotations

import ctypes
import json
import sys
from datetime import UTC, datetime
from typing import Any

import pynvml

FORBIDDEN = "Set"  # no function with this in its name is called anywhere here.


def field_constants() -> dict[int, str]:
    """Every NVML_FI_* constant that pynvml exposes, by value."""
    out: dict[int, str] = {}
    for name in dir(pynvml):
        if name.startswith("NVML_FI_DEV") or name.startswith("NVML_FI_"):
            value = getattr(pynvml, name)
            if isinstance(value, int) and name != "NVML_FI_MAX":
                out.setdefault(value, name)
    return out


def read_fields(handle: Any, fields: dict[int, str]) -> dict[str, Any]:  # noqa: ANN401
    """Read the fields one at a time, so one refusal does not hide the rest."""
    results: dict[str, Any] = {}
    for field_id, name in sorted(fields.items()):
        try:
            values = pynvml.nvmlDeviceGetFieldValues(handle, [field_id])
        except pynvml.NVMLError as error:
            results[name] = {"error": str(error)}
            continue
        value = values[0]
        if value.nvmlReturn != 0:
            results[name] = {"error": f"nvmlReturn={value.nvmlReturn}"}
            continue
        results[name] = {
            "value": _unwrap(value),
            "valueType": value.valueType,
            "latency_us": value.latencyUsec,
        }
    return results


def _unwrap(value: Any) -> Any:  # noqa: ANN401
    """Return the number out of an NVML field value, whatever its type is."""
    kinds = {
        0: "dVal",
        1: "uiVal",
        2: "ulVal",
        3: "ullVal",
        4: "sllVal",
        5: "siVal",
    }
    attribute = kinds.get(value.valueType)
    if attribute is None:
        return None
    return getattr(value.value, attribute)


def read_temperatures(handle: Any) -> dict[str, Any]:  # noqa: ANN401
    """Ask for every temperature sensor index, not only the documented one."""
    out: dict[str, Any] = {}
    for index in range(0, 8):
        try:
            out[f"sensor_{index}"] = pynvml.nvmlDeviceGetTemperature(handle, index)
        except pynvml.NVMLError as error:
            out[f"sensor_{index}"] = {"error": str(error)}
    for name, threshold in (
        ("shutdown", 0),
        ("slowdown", 1),
        ("mem_max", 2),
        ("gpu_max", 3),
        ("acoustic_min", 4),
        ("acoustic_curr", 5),
        ("acoustic_max", 6),
    ):
        try:
            out[f"threshold_{name}"] = pynvml.nvmlDeviceGetTemperatureThreshold(handle, threshold)
        except pynvml.NVMLError as error:
            out[f"threshold_{name}"] = {"error": str(error)}
    return out


def _fan_rpm(handle: Any, index: int) -> Any:  # noqa: ANN401
    """Read one fan's RPM.

    `pynvml.nvmlDeviceGetFanSpeedRPM` fixes the fan number at 0, so this calls
    the same library function through the same pointer with the fan number set.
    It reads only.
    """
    try:
        info = pynvml.c_nvmlFanSpeedInfo_t()
        info.version = pynvml.nvmlFanSpeedInfo_v1
        info.fan = index
        function = pynvml._nvmlGetFunctionPointer("nvmlDeviceGetFanSpeedRPM")
        code = function(handle, ctypes.byref(info))
        if code != 0:
            return {"error": f"nvmlReturn={code}"}
        return info.speed
    except pynvml.NVMLError as error:
        return {"error": str(error)}
    except Exception as error:  # the structure may not match this driver
        return {"error": f"{type(error).__name__}: {error}"}


def read_fans(handle: Any) -> dict[str, Any]:  # noqa: ANN401
    """Read the count, the control percent and the RPM of every fan."""
    out: dict[str, Any] = {}
    try:
        count = pynvml.nvmlDeviceGetNumFans(handle)
    except pynvml.NVMLError as error:
        return {"error": str(error)}
    out["count"] = count
    for index in range(count):
        entry: dict[str, Any] = {}
        try:
            entry["percent"] = pynvml.nvmlDeviceGetFanSpeed_v2(handle, index)
        except pynvml.NVMLError as error:
            entry["percent"] = {"error": str(error)}
        entry["rpm"] = _fan_rpm(handle, index)
        out[f"fan_{index}"] = entry
    return out


def main() -> int:
    """Write the whole report to standard output as JSON."""
    pynvml.nvmlInit()
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        report = {
            "captured": datetime.now(UTC).isoformat(),
            "driver": pynvml.nvmlSystemGetDriverVersion(),
            "nvml": pynvml.nvmlSystemGetNVMLVersion(),
            "device": pynvml.nvmlDeviceGetName(handle),
            "temperatures": read_temperatures(handle),
            "fans": read_fans(handle),
            "fields": read_fields(handle, field_constants()),
        }
    finally:
        pynvml.nvmlShutdown()
    json.dump(report, sys.stdout, indent=2, default=str)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
