"""Compare two ways to read the NVIDIA RTX 4090: the NVML binding and `nvidia-smi` text.

The experiment measures the time of one full sample with each method, and lists
which fields each method gives.
"""

from __future__ import annotations

import json
import logging
import statistics
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pynvml

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "results"
ROUNDS = 30

SMI_FIELDS = [
    "name",
    "temperature.gpu",
    "power.draw",
    "power.limit",
    "fan.speed",
    "utilization.gpu",
    "utilization.memory",
    "memory.used",
    "memory.total",
    "clocks.current.sm",
    "clocks.current.memory",
    "pcie.link.gen.current",
    "pcie.link.width.current",
]


def sample_nvml(handle: Any) -> dict[str, Any]:  # noqa: ANN401 - NVML handle is opaque
    """Read one full sample of the GPU through NVML."""
    sample: dict[str, Any] = {}
    memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
    sample["name"] = pynvml.nvmlDeviceGetName(handle)
    sample["temperature_gpu_c"] = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
    sample["power_draw_w"] = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000
    sample["power_limit_w"] = pynvml.nvmlDeviceGetEnforcedPowerLimit(handle) / 1000
    sample["fan_speed_pct"] = pynvml.nvmlDeviceGetFanSpeed(handle)
    sample["util_gpu_pct"] = util.gpu
    sample["util_memory_pct"] = util.memory
    sample["memory_used_mib"] = memory.used // 1024**2
    sample["memory_total_mib"] = memory.total // 1024**2
    sample["clock_sm_mhz"] = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
    sample["clock_mem_mhz"] = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
    sample["pcie_gen"] = pynvml.nvmlDeviceGetCurrPcieLinkGeneration(handle)
    sample["pcie_width"] = pynvml.nvmlDeviceGetCurrPcieLinkWidth(handle)
    return sample


def probe_extras(handle: Any) -> dict[str, Any]:  # noqa: ANN401 - NVML handle is opaque
    """Try the NVML calls that `nvidia-smi --query-gpu` does not give, and record what works."""
    extras: dict[str, Any] = {}

    def attempt(key: str, call: Any) -> None:  # noqa: ANN401 - any NVML callable
        try:
            extras[key] = call()
        except pynvml.NVMLError as exc:
            extras[key] = f"UNSUPPORTED: {exc}"

    attempt("fan_count", lambda: pynvml.nvmlDeviceGetNumFans(handle))
    attempt("hotspot_temp_c", lambda: pynvml.nvmlDeviceGetTemperature(handle, 1))
    attempt("memory_temp_c", lambda: pynvml.nvmlDeviceGetTemperature(handle, 2))
    attempt("temp_slowdown_c", lambda: pynvml.nvmlDeviceGetTemperatureThreshold(handle, 0))
    attempt("temp_shutdown_c", lambda: pynvml.nvmlDeviceGetTemperatureThreshold(handle, 1))
    attempt("throttle_reasons", lambda: pynvml.nvmlDeviceGetCurrentClocksThrottleReasons(handle))
    attempt("performance_state", lambda: pynvml.nvmlDeviceGetPerformanceState(handle))
    attempt("power_state", lambda: pynvml.nvmlDeviceGetPowerState(handle))
    attempt("encoder_util", lambda: pynvml.nvmlDeviceGetEncoderUtilization(handle)[0])
    attempt("decoder_util", lambda: pynvml.nvmlDeviceGetDecoderUtilization(handle)[0])
    attempt("pcie_tx_kbps", lambda: pynvml.nvmlDeviceGetPcieThroughput(handle, pynvml.NVML_PCIE_UTIL_TX_BYTES))
    attempt("pcie_rx_kbps", lambda: pynvml.nvmlDeviceGetPcieThroughput(handle, pynvml.NVML_PCIE_UTIL_RX_BYTES))
    attempt("total_energy_j", lambda: pynvml.nvmlDeviceGetTotalEnergyConsumption(handle) / 1000)
    attempt("bar1_memory", lambda: pynvml.nvmlDeviceGetBAR1MemoryInfo(handle).bar1Used // 1024**2)
    attempt("compute_processes", lambda: len(pynvml.nvmlDeviceGetComputeRunningProcesses(handle)))
    attempt("graphics_processes", lambda: len(pynvml.nvmlDeviceGetGraphicsRunningProcesses(handle)))
    attempt("vbios_version", lambda: pynvml.nvmlDeviceGetVbiosVersion(handle))
    attempt("serial", lambda: pynvml.nvmlDeviceGetSerial(handle))
    attempt("max_clock_sm_mhz", lambda: pynvml.nvmlDeviceGetMaxClockInfo(handle, pynvml.NVML_CLOCK_SM))
    attempt(
        "memory_used_v2_mib",
        lambda: pynvml.nvmlDeviceGetMemoryInfo(handle, version=pynvml.nvmlMemory_v2).used // 1024**2,
    )
    attempt(
        "memory_reserved_v2_mib",
        lambda: pynvml.nvmlDeviceGetMemoryInfo(handle, version=pynvml.nvmlMemory_v2).reserved // 1024**2,
    )
    # "T.Limit" fields give the headroom in degrees to a limit, not an absolute temperature.
    for field in (
        "NVML_FI_DEV_MEMORY_TEMP",
        "NVML_FI_DEV_TEMPERATURE_GPU_MAX_TLIMIT",
        "NVML_FI_DEV_TEMPERATURE_MEM_MAX_TLIMIT",
        "NVML_FI_DEV_TEMPERATURE_SHUTDOWN_TLIMIT",
        "NVML_FI_DEV_TEMPERATURE_SLOWDOWN_TLIMIT",
    ):
        attempt(field.replace("NVML_FI_DEV_", "").lower(), lambda f=field: field_value(handle, f))
    return extras


def field_value(handle: Any, field_name: str) -> int | str:  # noqa: ANN401 - NVML handle is opaque
    """Read one NVML "field value" and return it, or a note when the driver does not support it."""
    field_id = getattr(pynvml, field_name)
    value = pynvml.nvmlDeviceGetFieldValues(handle, [field_id])[0]
    if value.nvmlReturn != 0:
        return f"UNSUPPORTED: nvmlReturn={value.nvmlReturn}"
    # valueType 5 is a signed int, which the T.Limit fields use.
    return value.value.siVal if value.valueType == 5 else value.value.uiVal


def sample_smi() -> dict[str, str]:
    """Read one full sample of the GPU by running `nvidia-smi`."""
    query = ",".join(SMI_FIELDS)
    proc = subprocess.run(
        ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        check=True,
    )
    values = [v.strip() for v in proc.stdout.strip().split(",")]
    return dict(zip(SMI_FIELDS, values, strict=True))


def time_rounds(func: Any, rounds: int) -> dict[str, float]:  # noqa: ANN401 - any callable
    """Call `func` several times and return timing statistics in milliseconds."""
    timings = []
    for _ in range(rounds):
        start = time.perf_counter()
        func()
        timings.append((time.perf_counter() - start) * 1000)
    return {
        "rounds": rounds,
        "min_ms": round(min(timings), 3),
        "median_ms": round(statistics.median(timings), 3),
        "max_ms": round(max(timings), 3),
    }


def main() -> None:
    """Run the comparison and write the results."""
    pynvml.nvmlInit()
    try:
        count = pynvml.nvmlDeviceGetCount()
        logger.info("NVML sees %d device(s); driver %s", count, pynvml.nvmlSystemGetDriverVersion())
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)

        nvml_sample = sample_nvml(handle)
        extras = probe_extras(handle)
        smi_sample = sample_smi()

        nvml_timing = time_rounds(lambda: sample_nvml(handle), ROUNDS)
        smi_timing = time_rounds(sample_smi, ROUNDS)
    finally:
        pynvml.nvmlShutdown()

    logger.info("NVML   median %s ms", nvml_timing["median_ms"])
    logger.info("smi    median %s ms", smi_timing["median_ms"])

    payload = {
        "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "nvml": {"sample": nvml_sample, "timing": nvml_timing},
        "nvml_extras": extras,
        "nvidia_smi": {"sample": smi_sample, "timing": smi_timing},
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "nvidia-access.json").write_text(json.dumps(payload, indent=2, default=str))
    logger.info("wrote %s", RESULTS_DIR / "nvidia-access.json")


if __name__ == "__main__":
    main()
