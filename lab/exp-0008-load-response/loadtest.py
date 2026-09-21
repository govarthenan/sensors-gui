"""Put a load on the CPU and record which sensor channels react.

Step 3 of Gova's coverage experiment asks whether a reading is realistic. A
value that looks plausible at idle can still come from the wrong register. The
test here is causal, not cosmetic: drive the machine, and see which channels
move with it.

The run has three phases:
    idle  -> load (every core busy) -> idle

A channel that should react and does not is suspect. A channel that reacts and
should not is also suspect.
"""

from __future__ import annotations

import json
import logging
import multiprocessing
import statistics
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sensors_gui.collectors.hwmon import HwmonCollector
from sensors_gui.collectors.nvidia import NvidiaCollector
from sensors_gui.model import Reading, SensorSpec

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "results"
SAMPLE_INTERVAL = 0.5
IDLE_SECONDS = 20.0
LOAD_SECONDS = 60.0
COOLDOWN_SECONDS = 30.0


def _burn(stop_at: float) -> None:
    """Keep one core busy until the wall clock passes `stop_at`."""
    value = 0.0
    while time.time() < stop_at:
        for index in range(200_000):
            value += index * 1.000001
    _ = value


@dataclass
class Series:
    """Every value one channel gave, split by phase."""

    spec: SensorSpec
    idle: list[float]
    load: list[float]
    cooldown: list[float]

    def summary(self) -> dict[str, float | str | None]:
        """Return the medians, the change under load, and a verdict."""
        idle_median = statistics.median(self.idle) if self.idle else None
        load_median = statistics.median(self.load) if self.load else None
        cool_median = statistics.median(self.cooldown) if self.cooldown else None
        delta = None if idle_median is None or load_median is None else load_median - idle_median
        relative = None
        if delta is not None and idle_median not in (None, 0.0):
            relative = abs(delta) / abs(idle_median) * 100
        everything = self.idle + self.load + self.cooldown
        return {
            "label": self.spec.label,
            "key": self.spec.id.key,
            "unit": self.spec.unit.value,
            "idle_median": idle_median,
            "load_median": load_median,
            "cooldown_median": cool_median,
            "delta": delta,
            "percent_change": relative,
            "min": min(everything) if everything else None,
            "max": max(everything) if everything else None,
            "distinct_values": len(set(everything)),
        }


def _collect(collectors: list, specs: dict) -> list[Reading]:  # noqa: ANN001 - a list of collectors
    """Read every collector once."""
    readings: list[Reading] = []
    for collector in collectors:
        readings.extend(collector.read())
    return readings


def _sample_for(seconds: float, collectors: list, into: dict) -> None:  # noqa: ANN001
    """Sample every collector for a period, and append each value to `into`."""
    end = time.time() + seconds
    while time.time() < end:
        for reading in _collect(collectors, {}):
            if reading.value is not None:
                into.setdefault(reading.id, []).append(reading.value)
        time.sleep(SAMPLE_INTERVAL)


def main() -> None:
    """Run the three phases and write the result."""
    collectors = [HwmonCollector(), NvidiaCollector()]
    specs: dict = {}
    for collector in collectors:
        for spec in collector.discover():
            specs[spec.id] = spec
    for collector in collectors:
        collector.read()  # the first sample after a device appears can be wrong

    logger.info(
        "%d channels; idle %.0fs, load %.0fs, cooldown %.0fs", len(specs), IDLE_SECONDS, LOAD_SECONDS, COOLDOWN_SECONDS
    )

    idle: dict = {}
    load: dict = {}
    cooldown: dict = {}

    logger.info("phase 1: idle")
    _sample_for(IDLE_SECONDS, collectors, idle)

    logger.info("phase 2: load on %d cores", multiprocessing.cpu_count())
    stop_at = time.time() + LOAD_SECONDS
    workers = [multiprocessing.Process(target=_burn, args=(stop_at,)) for _ in range(multiprocessing.cpu_count())]
    for worker in workers:
        worker.start()
    _sample_for(LOAD_SECONDS, collectors, load)
    for worker in workers:
        worker.join()

    logger.info("phase 3: cooldown")
    _sample_for(COOLDOWN_SECONDS, collectors, cooldown)

    for collector in collectors:
        collector.close()

    rows = [
        Series(
            spec=specs[sensor_id],
            idle=idle.get(sensor_id, []),
            load=load.get(sensor_id, []),
            cooldown=cooldown.get(sensor_id, []),
        ).summary()
        for sensor_id in specs
    ]
    rows.sort(key=lambda row: abs(row["percent_change"] or 0.0), reverse=True)

    logger.info("%-22s %12s %12s %12s  %s", "channel", "idle", "load", "change", "unit")
    for row in rows:
        logger.info(
            "%-22s %12s %12s %12s  %s",
            row["label"][:22],
            "-" if row["idle_median"] is None else f"{row['idle_median']:.3f}",
            "-" if row["load_median"] is None else f"{row['load_median']:.3f}",
            "-" if row["delta"] is None else f"{row['delta']:+.3f}",
            row["unit"],
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "load-response.json").write_text(
        json.dumps(
            {
                "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "phases": {"idle_s": IDLE_SECONDS, "load_s": LOAD_SECONDS, "cooldown_s": COOLDOWN_SECONDS},
                "sample_interval_s": SAMPLE_INTERVAL,
                "cores_loaded": multiprocessing.cpu_count(),
                "channels": rows,
            },
            indent=2,
        )
    )
    logger.info("wrote %s", RESULTS_DIR / "load-response.json")


if __name__ == "__main__":
    main()
