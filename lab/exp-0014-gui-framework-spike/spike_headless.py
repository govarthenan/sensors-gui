"""The collection layer alone, with no user interface, as the cost baseline.

    uv run python lab/exp-0014-gui-framework-spike/spike_headless.py --hz 10

It reads every collector at the given rate and prints nothing until it stops.
Whatever this costs, a front end cannot cost less. Nothing is written to
hardware.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time

from sensors_gui.collectors.hwmon import HwmonCollector
from sensors_gui.collectors.nvidia import NvidiaCollector
from sensors_gui.collectors.power_supply import PowerSupplyCollector
from sensors_gui.collectors.privileged import PrivilegedCollector
from sensors_gui.collectors.system import SystemCollector
from sensors_gui.registry import Registry
from sensors_gui.sampler import Sampler


async def run(hz: float, seconds: float) -> dict[str, float]:
    """Sample at `hz` for `seconds` and return the pass count and the pass-time spread."""
    registry = Registry(
        [
            HwmonCollector(),
            NvidiaCollector(),
            PowerSupplyCollector(),
            PrivilegedCollector(),
            SystemCollector(),
        ]
    )
    registry.discover()
    sampler = Sampler(registry)
    period = 1.0 / hz
    start = time.monotonic()
    passes = 0
    times_ms: list[float] = []
    while time.monotonic() - start < seconds:
        began = time.perf_counter()
        sampler.sample()
        times_ms.append((time.perf_counter() - began) * 1000)
        passes += 1
        await asyncio.sleep(max(start + passes * period - time.monotonic(), 0.0))
    registry.close()
    ordered = sorted(times_ms)
    return {
        "passes": float(passes),
        "mean_ms": sum(ordered) / max(len(ordered), 1),
        "p50_ms": ordered[len(ordered) // 2] if ordered else 0.0,
        "p95_ms": ordered[int(len(ordered) * 0.95)] if ordered else 0.0,
        "max_ms": ordered[-1] if ordered else 0.0,
    }


def main() -> None:
    """Run the baseline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hz", type=float, default=10.0)
    parser.add_argument("--seconds", type=float, default=3600.0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    stats = asyncio.run(run(args.hz, args.seconds))
    print(
        f"headless: {int(stats['passes'])} passes, mean {stats['mean_ms']:.3f} ms, "
        f"p50 {stats['p50_ms']:.3f} ms, p95 {stats['p95_ms']:.3f} ms, max {stats['max_ms']:.3f} ms"
    )


if __name__ == "__main__":
    main()
