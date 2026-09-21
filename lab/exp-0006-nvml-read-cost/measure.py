"""Measure how long each NVML channel takes to read.

`exp-0004` found that hwmon channels differ by a factor of 400. This asks the
same question of NVML, which `exp-0002` had timed only as a whole.
"""

from __future__ import annotations

import contextlib
import json
import logging
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

from sensors_gui.collectors.nvidia import NvidiaCollector

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "results"
ROUNDS = 20


def main() -> None:
    """Measure each channel, then the whole pass, and write the result."""
    collector = NvidiaCollector()
    if not collector.discover():
        logger.error("no NVIDIA GPU found")
        return
    collector.read()  # warm the cache

    per_channel = []
    for channel in collector._channels:  # noqa: SLF001 - the experiment looks inside on purpose
        timings = []
        for _ in range(ROUNDS):
            start = time.perf_counter()
            # An unsupported call is still a measurement, so its cost counts.
            with contextlib.suppress(Exception):
                channel.read_value()
            timings.append((time.perf_counter() - start) * 1000)
        per_channel.append(
            {
                "channel": channel.spec.id.channel,
                "label": channel.spec.label,
                "min_interval": channel.spec.min_interval,
                "median_ms": round(statistics.median(timings), 4),
            }
        )

    pass_timings = []
    for _ in range(ROUNDS):
        start = time.perf_counter()
        collector.read()
        pass_timings.append((time.perf_counter() - start) * 1000)

    per_channel.sort(key=lambda row: row["median_ms"], reverse=True)
    for row in per_channel:
        logger.info("%9.4f ms  %-22s interval %gs", row["median_ms"], row["channel"], row["min_interval"])
    uncached = sum(row["median_ms"] for row in per_channel)
    logger.info("sum of every channel (no cache): %.3f ms", uncached)
    logger.info("warmed pass with the cache:      %.4f ms", statistics.median(pass_timings))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "nvml-read-cost.json").write_text(
        json.dumps(
            {
                "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "rounds": ROUNDS,
                "channels": per_channel,
                "sum_uncached_ms": round(uncached, 3),
                "warmed_pass_median_ms": round(statistics.median(pass_timings), 4),
            },
            indent=2,
        )
    )
    collector.close()


if __name__ == "__main__":
    main()
