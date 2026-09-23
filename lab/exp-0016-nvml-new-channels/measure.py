"""exp-0016: what the channels of Q13 and Q16 cost to read.

Read only: every call is an nvmlDeviceGet* function. Run with
`uv run python lab/exp-0016-nvml-new-channels/measure.py`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pynvml

ROUNDS = 30
RESULTS = Path(__file__).parent / "results" / "read-cost.json"


def main() -> None:
    """Time each call ROUNDS times and write the medians."""
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    calls = {
        "nvmlDeviceGetCurrentClocksEventReasons": lambda: pynvml.nvmlDeviceGetCurrentClocksEventReasons(handle),
        "nvmlDeviceGetCurrPcieLinkGeneration": lambda: pynvml.nvmlDeviceGetCurrPcieLinkGeneration(handle),
        "nvmlDeviceGetCurrPcieLinkWidth": lambda: pynvml.nvmlDeviceGetCurrPcieLinkWidth(handle),
        "nvmlDeviceGetMaxPcieLinkGeneration": lambda: pynvml.nvmlDeviceGetMaxPcieLinkGeneration(handle),
        "nvmlDeviceGetMaxPcieLinkWidth": lambda: pynvml.nvmlDeviceGetMaxPcieLinkWidth(handle),
        "nvmlDeviceGetMaxClockInfo(MEM)": lambda: pynvml.nvmlDeviceGetMaxClockInfo(handle, pynvml.NVML_CLOCK_MEM),
    }
    rows = {}
    for name, call in calls.items():
        value = call()
        times = []
        for _ in range(ROUNDS):
            began = time.perf_counter()
            call()
            times.append((time.perf_counter() - began) * 1000)
        times.sort()
        rows[name] = {"value": value, "median_ms": round(times[ROUNDS // 2], 4), "max_ms": round(times[-1], 4)}
        print(f"{name:42s} value={value!r:8} median={rows[name]['median_ms']} ms max={rows[name]['max_ms']} ms")
    pynvml.nvmlShutdown()
    RESULTS.write_text(
        json.dumps({"date": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "rounds": ROUNDS, "calls": rows}, indent=2)
    )


if __name__ == "__main__":
    main()
