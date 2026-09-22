"""Measure what the real application costs, at every checkpoint.

    uv run python lab/exp-0015-gui-checkpoints/measure-overhead.py --seconds 30

`docs/gui-goal.md` section 4.5 asks for the CPU cost of the running GUI at
1 Hz and at 10 Hz, reported at every checkpoint. This measures the shipped
command, not a spike:

    uv run python -m sensors_gui.web

Cost is in **cores**: CPU seconds used for each second of wall time. This
machine has 24 threads, so 1.0 core is 4.2 % of it. A process is matched by
its command line, because Chrome moves its renderers away from the process
that started them.

Nothing is written to hardware.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import date
from pathlib import Path

import psutil

HERE = Path(__file__).parent
RESULTS = HERE / "results"
ROOT = HERE.parent.parent
PROFILE = Path.home() / ".local/state/sensors-gui/window-profile"
SETTLE_SECONDS = 15.0
GROUPS = {"python (sampler+server)": "sensors_gui.web", "chrome (window)": str(PROFILE)}


def matching(needle: str) -> list[psutil.Process]:
    """Return every live process whose command line holds `needle`."""
    found: list[psutil.Process] = []
    for process in psutil.process_iter(["cmdline"]):
        try:
            if any(needle in part for part in (process.info["cmdline"] or [])):
                found.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found


def usage(processes: list[psutil.Process]) -> tuple[float, float]:
    """Return the CPU seconds used so far and the resident memory in MiB."""
    cpu = 0.0
    rss = 0.0
    for process in processes:
        try:
            times = process.cpu_times()
            cpu += times.user + times.system
            rss += process.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return cpu, rss / (1024 * 1024)


def measure_at(hz: float, page: str, seconds: float) -> dict[str, object]:
    """Start the application at `hz`, let it settle, measure it, and stop it.

    Args:
        hz: The sample rate to run at.
        page: The page the window opens.
        seconds: The length of the measurement window.

    Returns:
        One row for the record.
    """
    command = ["uv", "run", "python", "-m", "sensors_gui.web", "--hz", str(hz), "--page", page]
    print(f"\n=== {hz} Hz, {page}")
    started = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    row: dict[str, object] = {"hz": hz, "page": page, "window_seconds": seconds, "groups": []}
    try:
        time.sleep(SETTLE_SECONDS)
        before = {label: usage(matching(needle)) for label, needle in GROUPS.items()}
        began = time.monotonic()
        time.sleep(seconds)
        elapsed = time.monotonic() - began
        total = 0.0
        for label, needle in GROUPS.items():
            processes = matching(needle)
            cpu, rss = usage(processes)
            cores = round((cpu - before[label][0]) / elapsed, 4)
            total += cores
            row["groups"].append(
                {"label": label, "cores": cores, "rss_mib": round(rss, 1), "processes": len(processes)}
            )
            print(f"    {label:<24}{cores:>8.4f} cores{rss:>9.1f} MiB  ({len(processes)} proc)")
        row["total_cores"] = round(total, 4)
        print(f"    {'TOTAL':<24}{total:>8.4f} cores")
    finally:
        started.terminate()
        try:
            started.wait(timeout=10)
        except subprocess.TimeoutExpired:
            started.kill()
        for needle in ("sensors_gui.web", str(PROFILE)):
            for stray in matching(needle):
                try:
                    stray.terminate()
                except psutil.Error:
                    continue
        time.sleep(3)
    return row


def main() -> None:
    """Measure the application at both rates and write the record."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--page", default="/gallery", help="the page the window opens")
    parser.add_argument("--checkpoint", default="2", help="which checkpoint this belongs to")
    args = parser.parse_args()

    rows = [measure_at(1.0, args.page, args.seconds), measure_at(10.0, args.page, args.seconds)]

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"{date.today().isoformat()}-checkpoint-{args.checkpoint}-overhead.json"
    out.write_text(
        json.dumps(
            {
                "date": date.today().isoformat(),
                "checkpoint": args.checkpoint,
                "command": "uv run python -m sensors_gui.web",
                "cpu_threads": psutil.cpu_count(),
                "note": "cores = CPU seconds used per second of wall time. 1.0 = one thread saturated.",
                "rows": rows,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
