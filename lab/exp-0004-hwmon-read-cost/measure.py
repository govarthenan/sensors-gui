"""Measure how long each hwmon channel takes to read on this machine.

Not every sysfs file costs the same. A file backed by a value the kernel
already holds costs a few microseconds. A file that starts a bus transaction —
an SMBus read of a DDR5 SPD hub, or an NVMe admin command — costs a thousand
times more. The sampler must know which is which.
"""

from __future__ import annotations

import json
import logging
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

from sensors_gui.collectors.hwmon import HwmonCollector, _read_scaled

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "results"
ROUNDS = 50


def main() -> None:
    """Measure each channel, then the whole pass, and write the result."""
    collector = HwmonCollector()
    collector.discover()
    collector.read()  # Warm the caches so that the first read is not counted.

    per_channel = []
    for channel in collector._channels:  # noqa: SLF001 - the experiment looks inside on purpose
        timings = []
        for _ in range(ROUNDS):
            start = time.perf_counter()
            _read_scaled(channel.input_path, channel.divisor)
            timings.append((time.perf_counter() - start) * 1000)
        per_channel.append(
            {
                "driver": channel.spec.id.device.split("@", 1)[0],
                "label": channel.spec.label,
                "channel": channel.spec.id.channel,
                "median_ms": round(statistics.median(timings), 4),
                "min_ms": round(min(timings), 4),
                "max_ms": round(max(timings), 4),
            }
        )

    pass_timings = []
    for _ in range(ROUNDS):
        start = time.perf_counter()
        collector.read()
        pass_timings.append((time.perf_counter() - start) * 1000)

    per_channel.sort(key=lambda row: row["median_ms"], reverse=True)
    for row in per_channel:
        logger.info("%8.4f ms  %-20s %s", row["median_ms"], row["driver"], row["label"])
    logger.info("full pass median: %.3f ms", statistics.median(pass_timings))

    payload = {
        "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rounds": ROUNDS,
        "channels": per_channel,
        "full_pass": {
            "median_ms": round(statistics.median(pass_timings), 3),
            "min_ms": round(min(pass_timings), 3),
            "max_ms": round(max(pass_timings), 3),
        },
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "read-cost.json").write_text(json.dumps(payload, indent=2))
    logger.info("wrote %s", RESULTS_DIR / "read-cost.json")


if __name__ == "__main__":
    main()
