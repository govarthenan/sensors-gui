"""exp-0019 probe: sample every power channel this machine already publishes, side by side.

READ ONLY. This script writes nothing to hardware:
- sysfs files are opened for reading only;
- NVML is called only through `nvmlDeviceGet*` functions;
- the helper socket is asked through the application's own client, which sends
  a JSON request to a local process and never touches hardware itself.

One thing the reader must know (see the README, route A2): reading
`amdgpu` `power1_input` or `gpu_metrics` makes the **kernel driver** send the
message `TransferTableSmu2Dram` to the SMU, to copy the metrics table to memory.
The application already does this on every pass through its hwmon collector.
This script does not open the SMU, the MSRs or any bus itself.

Run:
    uv run python lab/exp-0019-power-draw-sources/probe.py --samples 30
"""

from __future__ import annotations

import argparse
import json
import logging
import struct
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pynvml

from sensors_gui.collectors.privileged import PrivilegedCollector

logger = logging.getLogger(__name__)

AMDGPU_DEVICE = Path("/sys/devices/pci0000:00/0000:00:08.1/0000:74:00.0")
UNSUPPORTED = 0xFFFF

# gpu_metrics_v2_1 from include/kgd_pp_interface.h (kernel v7.0). Offsets in bytes.
V2_1_POWER_OFFSET = 40
V2_1_POWER_FORMAT = "<4H8H"  # socket, cpu, soc, gfx, core[8]; all mW


def find_amdgpu_hwmon() -> Path | None:
    """Return the hwmon directory of the amdgpu device, found by name and path (ADR 0002)."""
    for hwmon in Path("/sys/class/hwmon").iterdir():
        name = (hwmon / "name").read_text().strip()
        if name == "amdgpu" and (hwmon / "device").resolve() == AMDGPU_DEVICE:
            return hwmon
    return None


def read_gpu_metrics() -> dict[str, Any]:
    """Decode the power fields of `gpu_metrics`, when it is format 2.1."""
    raw = (AMDGPU_DEVICE / "gpu_metrics").read_bytes()
    size, fmt, content = struct.unpack_from("<HBB", raw, 0)
    result: dict[str, Any] = {"size": size, "format": f"{fmt}.{content}"}
    if (fmt, content) != (2, 1):
        return result
    values = struct.unpack_from(V2_1_POWER_FORMAT, raw, V2_1_POWER_OFFSET)
    names = ["socket_mw", "cpu_mw", "soc_mw", "gfx_mw"] + [f"core{i}_mw" for i in range(8)]
    for name, value in zip(names, values, strict=True):
        result[name] = None if value == UNSUPPORTED else value
    return result


def nvml_field(handle: Any, field_id: int, scope: int = 0) -> Any:  # noqa: ANN401 - opaque NVML types
    """Read one NVML field value by its id, and return the value or the error code."""
    field = pynvml.c_nvmlFieldValue_t()
    field.fieldId = field_id
    field.scopeId = scope
    array = (pynvml.c_nvmlFieldValue_t * 1)(field)
    function = pynvml._nvmlGetFunctionPointer("nvmlDeviceGetFieldValues")  # noqa: SLF001
    ret = function(handle, 1, array)
    if ret != 0:
        return f"call failed: {ret}"
    item = array[0]
    if item.nvmlReturn != 0:
        return f"nvmlReturn {item.nvmlReturn}"
    return {"ullVal": item.value.ullVal, "uiVal": item.value.uiVal, "valueType": item.valueType}


def nvml_context(handle: Any) -> dict[str, Any]:  # noqa: ANN401
    """Read the power context of the card once: limits, source, state."""
    calls = {
        "enforced_limit_mw": pynvml.nvmlDeviceGetEnforcedPowerLimit,
        "management_limit_mw": pynvml.nvmlDeviceGetPowerManagementLimit,
        "default_limit_mw": pynvml.nvmlDeviceGetPowerManagementDefaultLimit,
        "limit_constraints_mw": pynvml.nvmlDeviceGetPowerManagementLimitConstraints,
        "power_management_mode": pynvml.nvmlDeviceGetPowerManagementMode,
        "power_source": pynvml.nvmlDeviceGetPowerSource,
        "power_state": pynvml.nvmlDeviceGetPowerState,
    }
    result: dict[str, Any] = {}
    for key, call in calls.items():
        try:
            result[key] = call(handle)
        except pynvml.NVMLError as exc:
            result[key] = f"error: {exc}"
    return result


def nvml_sample(handle: Any) -> dict[str, Any]:  # noqa: ANN401
    """Read the power values of the card that NVML offers."""
    sample: dict[str, Any] = {}
    try:
        sample["usage_mw"] = pynvml.nvmlDeviceGetPowerUsage(handle)
        sample["total_energy_mj"] = pynvml.nvmlDeviceGetTotalEnergyConsumption(handle)
    except pynvml.NVMLError as exc:
        sample["error"] = str(exc)
    scopes = {
        "gpu": pynvml.NVML_POWER_SCOPE_GPU,
        "module": pynvml.NVML_POWER_SCOPE_MODULE,
        "memory": pynvml.NVML_POWER_SCOPE_MEMORY,
    }
    for scope_name, scope in scopes.items():
        sample[f"fi_power_instant_{scope_name}"] = nvml_field(handle, pynvml.NVML_FI_DEV_POWER_INSTANT, scope)
        sample[f"fi_power_average_{scope_name}"] = nvml_field(handle, pynvml.NVML_FI_DEV_POWER_AVERAGE, scope)
    return sample


def helper_sample(collector: PrivilegedCollector) -> dict[str, float | None]:
    """Ask the helper for its power channels, through the application's own client."""
    wanted = ("CPU Package Power", "CPU Cores Power", "CPU Core 0 (RAPL) Power")
    labels = {spec.id: spec.label for spec in collector.discover()}
    result: dict[str, float | None] = {}
    for reading in collector.read():
        label = labels.get(reading.id, "")
        if label in wanted:
            result[label] = reading.value
    return result


def main() -> None:
    """Sample every power channel at one hertz and write one JSON file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "results")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    collector = PrivilegedCollector()
    amdgpu_hwmon = find_amdgpu_hwmon()
    started = datetime.now(UTC)
    record: dict[str, Any] = {
        "command": f"uv run python lab/exp-0019-power-draw-sources/probe.py --samples {args.samples}",
        "date": started.isoformat(),
        "source": "sysfs amdgpu hwmon and gpu_metrics, NVML Get calls, /run/sensors-gui.sock (helper)",
        "machine_state": "idle desktop, no load started by this script",
        "nvml_driver": pynvml.nvmlSystemGetDriverVersion(),
        "nvml_context": nvml_context(handle),
        "samples": [],
    }
    helper_sample(collector)  # the first read primes the helper's power deltas
    for _ in range(args.samples):
        time.sleep(1.0)
        sample: dict[str, Any] = {"t": time.time()}
        if amdgpu_hwmon is not None:
            sample["amdgpu_power1_input_uw"] = int((amdgpu_hwmon / "power1_input").read_text())
        sample["gpu_metrics"] = read_gpu_metrics()
        sample["nvml"] = nvml_sample(handle)
        sample["helper"] = helper_sample(collector)
        record["samples"].append(sample)
    collector.close()
    pynvml.nvmlShutdown()

    args.out.mkdir(parents=True, exist_ok=True)
    out_file = args.out / f"{started:%Y-%m-%d}-power-channels-{args.samples}s.json"
    out_file.write_text(json.dumps(record, indent=1, default=str))
    logger.info("wrote %s", out_file)


if __name__ == "__main__":
    main()
