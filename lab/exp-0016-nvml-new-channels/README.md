# exp-0016 — the cost of the card channels Gova asked for at checkpoint 3

- Date: 2026-09-23 (session 9)
- Related: ADR 0006, `lab/exp-0006-nvml-read-cost/`, Q13 and Q16 in `state/STATUS.md`

## Question

Gova answered "yes" to Q13 (read the clock event reasons and the PCIe link)
and to Q16 (give the VRAM clock its maximum). `exp-0006` found that two NVML
calls cost 20 ms each and must not run on every pass. Do any of the new calls
cost that much?

## Method

`measure.py` times each call 30 times on the RTX 4090 and records the median
and the maximum. Every call is an `nvmlDeviceGet*` function; nothing is set.

```bash
uv run python lab/exp-0016-nvml-new-channels/measure.py
```

## Result

`results/read-cost.json`, 2026-09-23:

| Call | Value | Median | Max |
|---|---|---|---|
| `nvmlDeviceGetCurrentClocksEventReasons` | 1 (GPU idle) | 0.0005 ms | 0.0051 ms |
| `nvmlDeviceGetCurrPcieLinkGeneration` | 2 | 0.0005 ms | 0.0015 ms |
| `nvmlDeviceGetCurrPcieLinkWidth` | 16 | 0.0039 ms | 0.0078 ms |
| `nvmlDeviceGetMaxPcieLinkGeneration` | 4 | 0.0004 ms | 0.0007 ms |
| `nvmlDeviceGetMaxPcieLinkWidth` | 16 | 0.0004 ms | 0.0006 ms |
| `nvmlDeviceGetMaxClockInfo(NVML_CLOCK_MEM)` | 10501 MHz | **2.08 ms** | 3.98 ms |

## Decision

- The three live channels — clock event reasons, PCIe generation, PCIe width
  — cost under 0.01 ms and are read **on every pass**.
- The two link maximums and the memory clock maximum become the `high` of
  their channels, read **once, at discovery**. The memory clock maximum costs
  2 ms, which would be the largest single call on a pass if it were read there.
- The link generation moved between two runs of the same day: 1 in the probe,
  2 here. So it is a live value, not a constant, which is why it is a channel
  and not a fact on the page.

The card now has **24 channels**, and the machine 178.
