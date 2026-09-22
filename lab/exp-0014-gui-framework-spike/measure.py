"""Measure what a running front end costs this machine.

    uv run python lab/exp-0014-gui-framework-spike/measure.py --seconds 30

For each scenario it starts the processes, waits for them to settle, and then
counts the CPU time every matching process uses over a fixed window. The
result is given in **cores**: 0.01 cores is one hundredth of one of the 24
threads of this processor.

A process is matched by its command line, not by its parent, because Chrome
re-parents its renderers away from the process that started it.

The output goes to `results/overhead-<date>.json` and to the screen.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import psutil

HERE = Path(__file__).parent
RESULTS = HERE / "results"
PROFILE = Path.home() / ".local/state/sensors-gui/spike-profile"
SETTLE_SECONDS = 12.0


@dataclass(frozen=True, slots=True)
class Cost:
    """What one group of processes cost over the measurement window."""

    label: str
    processes: int
    cpu_cores: float
    rss_mib: float


@dataclass(frozen=True, slots=True)
class Scenario:
    """One measured configuration."""

    name: str
    hz: float
    channels: str
    window_seconds: float
    costs: list[Cost]

    @property
    def total_cores(self) -> float:
        """Return the CPU cost of every group together, in cores."""
        return sum(cost.cpu_cores for cost in self.costs)


def matching(needle: str) -> list[psutil.Process]:
    """Return every live process whose command line holds `needle`."""
    found: list[psutil.Process] = []
    for process in psutil.process_iter(["cmdline"]):
        try:
            cmdline = process.info["cmdline"] or []
            if any(needle in part for part in cmdline):
                found.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found


def cpu_seconds(processes: list[psutil.Process]) -> tuple[float, float]:
    """Return the total CPU seconds used so far and the resident memory, in MiB."""
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


def measure(groups: dict[str, str], seconds: float) -> list[Cost]:
    """Measure the CPU cost of each named group of processes over `seconds`.

    Args:
        groups: A label for each group, and the command-line text that finds it.
        seconds: How long the window is.

    Returns:
        One `Cost` for each group.
    """
    before = {label: cpu_seconds(matching(needle)) for label, needle in groups.items()}
    began = time.monotonic()
    time.sleep(seconds)
    elapsed = time.monotonic() - began

    costs: list[Cost] = []
    for label, needle in groups.items():
        processes = matching(needle)
        after_cpu, rss = cpu_seconds(processes)
        costs.append(
            Cost(
                label=label,
                processes=len(processes),
                cpu_cores=round((after_cpu - before[label][0]) / elapsed, 4),
                rss_mib=round(rss, 1),
            )
        )
    return costs


def run_scenario(
    name: str,
    command: list[str],
    groups: dict[str, str],
    hz: float,
    channels: str,
    seconds: float,
    env: dict[str, str] | None = None,
) -> Scenario:
    """Start `command`, let it settle, measure it, and stop it.

    Args:
        name: The name of the scenario.
        command: The command to start.
        groups: The process groups to measure.
        hz: The sample rate under test.
        channels: How many channels are streamed, as text for the record.
        seconds: The length of the measurement window.
        env: Extra environment for the command, added to this process's own.

    Returns:
        The measured scenario.
    """
    print(f"\n=== {name}: {' '.join(command)}")
    environment = {**os.environ, **(env or {})}
    process = subprocess.Popen(
        command, cwd=HERE.parent.parent, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        time.sleep(SETTLE_SECONDS)
        costs = measure(groups, seconds)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        # `uv run` starts python as a child, so stopping the wrapper is not
        # enough. Everything this scenario started is found by its command line
        # and stopped, or the next scenario measures two applications at once.
        script = next(part for part in command if part.endswith(".py"))
        for stray in [*matching(script), *matching(str(PROFILE))]:
            try:
                stray.terminate()
            except psutil.Error:
                continue
        time.sleep(3)

    scenario = Scenario(name=name, hz=hz, channels=channels, window_seconds=seconds, costs=costs)
    for cost in costs:
        print(f"    {cost.label:<22} {cost.cpu_cores:>7.4f} cores  {cost.rss_mib:>8.1f} MiB  ({cost.processes} proc)")
    print(f"    {'TOTAL':<22} {scenario.total_cores:>7.4f} cores")
    return scenario


def main() -> None:
    """Measure every scenario and write the results."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument(
        "--qt-libs",
        default="",
        help="a directory holding libxcb-cursor.so.0, which this machine does not have installed",
    )
    args = parser.parse_args()

    uv = ["uv", "run", "python"]
    headless = "spike_headless.py"
    web = "spike_web.py"
    qt = "spike_qt.py"
    chrome_group = {"chrome (window)": str(PROFILE)}
    both = {"python (sampler+server)": web, **chrome_group}
    qt_group = {"python+qt (one process)": qt}
    qt_env = {"LD_LIBRARY_PATH": args.qt_libs} if args.qt_libs else {}

    scenarios = [
        run_scenario(
            "headless collection layer, 1 Hz",
            [*uv, f"lab/exp-0014-gui-framework-spike/{headless}", "--hz", "1"],
            {"python (sampler only)": headless},
            1.0,
            "175 read",
            args.seconds,
        ),
        run_scenario(
            "headless collection layer, 10 Hz",
            [*uv, f"lab/exp-0014-gui-framework-spike/{headless}", "--hz", "10"],
            {"python (sampler only)": headless},
            10.0,
            "175 read",
            args.seconds,
        ),
        run_scenario(
            "web window, 1 channel, 1 Hz",
            [*uv, f"lab/exp-0014-gui-framework-spike/{web}", "--hz", "1"],
            both,
            1.0,
            "1 shown",
            args.seconds,
        ),
        run_scenario(
            "web window, 1 channel, 10 Hz",
            [*uv, f"lab/exp-0014-gui-framework-spike/{web}", "--hz", "10"],
            both,
            10.0,
            "1 shown",
            args.seconds,
        ),
        run_scenario(
            "web window, every channel, 1 Hz",
            [*uv, f"lab/exp-0014-gui-framework-spike/{web}", "--hz", "1", "--all"],
            both,
            1.0,
            "175 shown",
            args.seconds,
        ),
        run_scenario(
            "web window, every channel, 10 Hz",
            [*uv, f"lab/exp-0014-gui-framework-spike/{web}", "--hz", "10", "--all"],
            both,
            10.0,
            "175 shown",
            args.seconds,
        ),
        run_scenario(
            "Qt window, 1 channel, 1 Hz",
            [*uv, f"lab/exp-0014-gui-framework-spike/{qt}", "--hz", "1"],
            qt_group,
            1.0,
            "1 shown",
            args.seconds,
            qt_env,
        ),
        run_scenario(
            "Qt window, 1 channel, 10 Hz",
            [*uv, f"lab/exp-0014-gui-framework-spike/{qt}", "--hz", "10"],
            qt_group,
            10.0,
            "1 shown",
            args.seconds,
            qt_env,
        ),
        run_scenario(
            "Qt window, every channel, 1 Hz",
            [*uv, f"lab/exp-0014-gui-framework-spike/{qt}", "--hz", "1", "--all"],
            qt_group,
            1.0,
            "175 shown",
            args.seconds,
            qt_env,
        ),
        run_scenario(
            "Qt window, every channel, 10 Hz",
            [*uv, f"lab/exp-0014-gui-framework-spike/{qt}", "--hz", "10", "--all"],
            qt_group,
            10.0,
            "175 shown",
            args.seconds,
            qt_env,
        ),
    ]

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"overhead-{date.today().isoformat()}.json"
    out.write_text(
        json.dumps(
            {
                "date": date.today().isoformat(),
                "machine": "dst-gova-pc",
                "cpu_threads": psutil.cpu_count(),
                "note": "cpu_cores is CPU seconds used per second of wall time. 1.0 = one thread saturated.",
                "scenarios": [{**asdict(scenario), "total_cores": scenario.total_cores} for scenario in scenarios],
            },
            indent=2,
        )
        + "\n"
    )
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
