# exp-0018 — which channels leave the scale their spec publishes?

- Date: 2026-09-23 (session 9)
- Related: `src/sensors_gui/web/alerts.py`, Q17 in `state/STATUS.md`,
  `data/probes/2026-09-23-cpu-frequency-margin.txt`

## Question

Gova, 2026-09-23: *"What about other channels, did we see any abnormal
readings above/below ceiling/floor from other channels other than cpu freq?"*
The alert log's first hour saw only CPU frequencies, but those runs were short
and were never counted. Which of the channels with a scale leave it, how
often, and how far?

## Method

`scan.py` builds the same service the GUI runs, with the CPU frequency floor
at the hardware minimum and the 10 % margin in the log, and samples every
channel at 2 Hz for 300 s. For each channel with a `low` or a `high` it counts
the readings above the ceiling and below the floor, and the furthest each went
as a fraction of the limit. It writes nothing to hardware.

```bash
uv run python lab/exp-0018-channels-outside-scale/scan.py --seconds 300
```

## Result

`results/2026-09-23-scan-300s.json`: 575 passes, **120 channels with a
scale**, the desktop in ordinary use and no load run for the test.

| Channels | Above the ceiling | Below the floor | Logged, with the margin |
|---|---|---|---|
| 13 of the 24 CPU thread frequencies | 297 readings, the furthest **+1.23 %** (CPU20) | **none**, with the hardware minimum as the floor | **0** |
| the other 107 channels with a scale | **none** | **none** | 0 |

**Only the CPU frequencies left their scale, and only by a little.** Nothing
else did: not the card's power, clocks, fans or memory, not a temperature with
a threshold, not a load, not a helper channel.

## Limits

One run of five minutes, on an idle desktop. A channel that only leaves its
scale under load — the card's power against its 480 W limit is the obvious
one — cannot be seen here, and the project does not load the machine for a
test (`tmp/HANDOFF-gui-stream.md` section 4). The alert log runs whenever the
application runs, so such a reading would be caught in ordinary use.
