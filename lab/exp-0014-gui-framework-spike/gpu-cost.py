"""Does the window change what it measures? Watch the card while each front end runs.

    uv run python lab/exp-0014-gui-framework-spike/gpu-cost.py --seconds 40

A sensor monitor must not move its own readings. A browser window composites
through the graphics card; a Qt widget window paints on the processor. This
measures the card's power, clock and temperature with no window, with the web
window and with the Qt window, all at 10 Hz and every channel.

Nothing is written to hardware. NVML is read only.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import date
from pathlib import Path

import psutil
import pynvml

HERE = Path(__file__).parent
RESULTS = HERE / "results"
PROFILE = Path.home() / ".local/state/sensors-gui/spike-profile"
SETTLE_SECONDS = 12.0


def watch(handle: object, seconds: float) -> dict[str, float]:
    """Sample the card every 200 ms for `seconds` and return the means."""
    powers: list[float] = []
    clocks: list[float] = []
    temperatures: list[float] = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        powers.append(pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0)
        clocks.append(float(pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)))
        temperatures.append(float(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)))
        time.sleep(0.2)
    return {
        "samples": float(len(powers)),
        "power_w": round(sum(powers) / len(powers), 2),
        "power_max_w": round(max(powers), 2),
        "sm_clock_mhz": round(sum(clocks) / len(clocks), 1),
        "temperature_c": round(sum(temperatures) / len(temperatures), 1),
    }


def stop(script: str) -> None:
    """Stop every process of one scenario, found by its command line."""
    for needle in (script, str(PROFILE)):
        for process in psutil.process_iter(["cmdline"]):
            try:
                if any(needle in part for part in (process.info["cmdline"] or [])):
                    process.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    time.sleep(3)


def main() -> None:
    """Measure the card under each front end and write the result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=40.0)
    parser.add_argument("--qt-libs", default="")
    args = parser.parse_args()

    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)

    rows: list[dict[str, object]] = []
    print("measuring the card with no window open")
    rows.append({"front_end": "nothing open", **watch(handle, args.seconds)})

    for name, script, extra_env in (
        ("web window (Chrome)", "spike_web.py", {}),
        ("Qt window (PySide6)", "spike_qt.py", {"LD_LIBRARY_PATH": args.qt_libs} if args.qt_libs else {}),
    ):
        print(f"measuring the card with the {name}, every channel at 10 Hz")
        command = ["uv", "run", "python", f"lab/exp-0014-gui-framework-spike/{script}", "--hz", "10", "--all"]
        process = subprocess.Popen(
            command,
            cwd=HERE.parent.parent,
            env={**os.environ, **extra_env},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(SETTLE_SECONDS)
            rows.append({"front_end": name, **watch(handle, args.seconds)})
        finally:
            process.terminate()
            stop(script)

    pynvml.nvmlShutdown()

    print(f"\n{'front end':<22}{'power W':>10}{'max W':>9}{'SM MHz':>9}{'temp C':>9}")
    for row in rows:
        print(
            f"{row['front_end']:<22}{row['power_w']:>10}{row['power_max_w']:>9}"
            f"{row['sm_clock_mhz']:>9}{row['temperature_c']:>9}"
        )

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"gpu-cost-{date.today().isoformat()}.json"
    out.write_text(json.dumps({"date": date.today().isoformat(), "rows": rows}, indent=2) + "\n")
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
