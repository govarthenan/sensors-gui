"""exp-0018: which channels leave the scale their spec publishes, and by how much?

Read only. It builds the same service the GUI runs, samples every channel at
2 Hz for the given time, and counts, for every channel with a scale, the
readings above its ceiling (`high`) and below its floor (`low`), and the
furthest each went, as a fraction of the limit.

    uv run python lab/exp-0018-channels-outside-scale/scan.py --seconds 300
"""

from __future__ import annotations

import argparse
import json
import socket
import time
from pathlib import Path

from sensors_gui.web.service import alert_margin, build_service

RESULTS = Path(__file__).parent / "results"


def main() -> None:
    """Sample for the given time and write one JSON record."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=300.0)
    arguments = parser.parse_args()

    service = build_service(hz=2.0)
    service.discover()
    channels = [
        channel for channel in service.channels() if channel.spec.low is not None or channel.spec.high is not None
    ]
    by_id = {channel.spec.id: channel for channel in channels}
    rows = {
        channel.spec.id.key: {
            "label": channel.spec.label,
            "low": channel.spec.low,
            "high": channel.spec.high,
            "hidden": channel.hidden,
            "margin": alert_margin(channel.spec),
            "readings": 0,
            "above": 0,
            "below": 0,
            "furthest_above": 0.0,
            "furthest_below": 0.0,
        }
        for channel in channels
    }
    began = time.monotonic()
    passes = 0
    while time.monotonic() - began < arguments.seconds:
        service.sample_once()
        passes += 1
        for reading in service.latest_readings().values():
            channel = by_id.get(reading.id)
            if channel is None or reading.value is None:
                continue
            row = rows[channel.spec.id.key]
            row["readings"] += 1
            spec = channel.spec
            if spec.high is not None and reading.value > spec.high:
                row["above"] += 1
                past = (reading.value - spec.high) / abs(spec.high) if spec.high else float("inf")
                row["furthest_above"] = max(row["furthest_above"], past)
            if spec.low is not None and reading.value < spec.low:
                row["below"] += 1
                past = (spec.low - reading.value) / abs(spec.low) if spec.low else float("inf")
                row["furthest_below"] = max(row["furthest_below"], past)
        time.sleep(0.5)
    service.stop()
    alerts = service.alerts.entries()
    record = {
        "command": f"uv run python lab/exp-0018-channels-outside-scale/scan.py --seconds {arguments.seconds:g}",
        "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "host": socket.gethostname(),
        "passes": passes,
        "channels_with_a_scale": len(rows),
        "outside": {key: row for key, row in rows.items() if row["above"] or row["below"]},
        "alerts_logged_with_the_margin": len(alerts),
        "alerts": alerts,
    }
    out = RESULTS / f"{time.strftime('%Y-%m-%d')}-scan-{int(arguments.seconds)}s.json"
    out.write_text(json.dumps(record, indent=2, default=str))
    print(f"passes {passes}, channels with a scale {len(rows)}, outside: {len(record['outside'])}")
    for row in record["outside"].values():
        print(
            f"  {row['label']:24s} above {row['above']:4d} (max +{row['furthest_above'] * 100:.2f} %)  "
            f"below {row['below']:4d} (max -{row['furthest_below'] * 100:.2f} %)  margin {row['margin']}"
        )
    print(f"alerts logged with the margin: {len(alerts)}")
    print(f"written: {out}")


if __name__ == "__main__":
    main()
