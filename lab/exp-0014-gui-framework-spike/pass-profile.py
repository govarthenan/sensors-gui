"""Where does the long pass go? Time every collector separately.

    uv run python lab/exp-0014-gui-framework-spike/pass-profile.py --hz 10 --seconds 60

The median pass of the collection layer is about 2 ms, but the tail is far
longer. This says which collector owns the tail, which decides whether the
front end can call `sample()` on its event loop or must call it on a thread.

Nothing is written to hardware.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

from sensors_gui.collectors.hwmon import HwmonCollector
from sensors_gui.collectors.nvidia import NvidiaCollector
from sensors_gui.collectors.power_supply import PowerSupplyCollector
from sensors_gui.collectors.privileged import PrivilegedCollector
from sensors_gui.collectors.system import SystemCollector

RESULTS = Path(__file__).parent / "results"


def percentile(ordered: list[float], fraction: float) -> float:
    """Return the value at `fraction` through an already sorted list."""
    if not ordered:
        return 0.0
    return ordered[min(int(len(ordered) * fraction), len(ordered) - 1)]


def main() -> None:
    """Time each collector over many passes and write the spread."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hz", type=float, default=10.0)
    parser.add_argument("--seconds", type=float, default=60.0)
    args = parser.parse_args()

    collectors = [
        HwmonCollector(),
        NvidiaCollector(),
        PowerSupplyCollector(),
        PrivilegedCollector(),
        SystemCollector(),
    ]
    for collector in collectors:
        collector.discover()
        collector.read()

    times: dict[str, list[float]] = {collector.name: [] for collector in collectors}
    period = 1.0 / args.hz
    start = time.monotonic()
    passes = 0
    while time.monotonic() - start < args.seconds:
        for collector in collectors:
            began = time.perf_counter()
            collector.read()
            times[collector.name].append((time.perf_counter() - began) * 1000)
        passes += 1
        time.sleep(max(start + passes * period - time.monotonic(), 0.0))

    rows = []
    for name, samples in times.items():
        ordered = sorted(samples)
        rows.append(
            {
                "collector": name,
                "mean_ms": round(sum(ordered) / len(ordered), 3),
                "p50_ms": round(percentile(ordered, 0.50), 3),
                "p95_ms": round(percentile(ordered, 0.95), 3),
                "p99_ms": round(percentile(ordered, 0.99), 3),
                "max_ms": round(ordered[-1], 3),
                "over_20ms": sum(1 for value in ordered if value > 20.0),
            }
        )
    rows.sort(key=lambda row: row["max_ms"], reverse=True)

    for collector in collectors:
        collector.close()

    header = f"{'collector':<12}{'mean':>9}{'p50':>9}{'p95':>9}{'p99':>9}{'max':>9}{'>20ms':>8}"
    print(header)
    for row in rows:
        print(
            f"{row['collector']:<12}{row['mean_ms']:>9.3f}{row['p50_ms']:>9.3f}"
            f"{row['p95_ms']:>9.3f}{row['p99_ms']:>9.3f}{row['max_ms']:>9.3f}{row['over_20ms']:>8}"
        )

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"pass-profile-{date.today().isoformat()}.json"
    out.write_text(json.dumps({"hz": args.hz, "passes": passes, "collectors": rows}, indent=2) + "\n")
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
