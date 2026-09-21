# exp-0006 — the cost of an NVML read

Date: 2026-09-21

## Question

`exp-0004` found that hwmon channels differ in cost by a factor of 400. Does
NVML behave the same way? `exp-0002` timed a 13-field sample as a whole
(0.67 ms), but it never timed one call at a time.

## Method

The NVIDIA collector was built with 17 channels. `measure.py` reads each one 20
times and records the median, then times a full pass.

```bash
uv run python lab/exp-0006-nvml-read-cost/measure.py
```

## Result

The first version of the collector, with no cache, took **48.4 ms for one
pass**. That alone is almost the whole 50 ms budget that
`docs/architecture.md` sets for **every** collector together.

| Channel | Median | Share |
|---|---|---|
| `pcie_tx` | **20.59 ms** | 46 % |
| `pcie_rx` | **20.56 ms** | 46 % |
| `energy` | 3.14 ms | 7 % |
| `fan_speed` | 0.60 ms | 1 % |
| `graphics_processes` | 0.048 ms | |
| `compute_processes` | 0.017 ms | |
| the other 11 channels | 0.0006 ms each | |

Sum with no cache: **44.97 ms**.

## Findings

1. **Two calls take 92 % of the pass.** `nvmlDeviceGetPcieThroughput` does not
   read a counter. It samples the link over a window of about 20 ms and blocks
   for that whole time. Calling it twice, for transmit and for receive, costs
   41 ms.
2. **The pattern from `exp-0004` repeats exactly.** A call that reads a value
   the driver already holds costs 0.0006 ms. A call that starts a measurement,
   or that walks a process list, costs thousands of times more. The rule is not
   about hwmon or NVML. It is about what the call has to do.
3. `exp-0002` missed this, because its 13 fields did not include the PCIe
   throughput. A benchmark of "a typical sample" hides the worst call.

## Decision

Extend ADR 0006 from a per-device interval to a **per-channel** interval, and
put the cache in one shared place, `sensors_gui/collectors/cache.py`, so that
both collectors use the same rule.

| Channel | Interval | Why |
|---|---|---|
| `pcie_tx`, `pcie_rx` | 2 s | 20.6 ms each, and the number is a rate that means little at a higher rate |
| `energy` | 1 s | 3.1 ms, and it is a counter that only grows |
| `fan_speed` | 1 s | 0.6 ms |
| `graphics_processes`, `compute_processes` | 1 s | they walk a process list |
| everything else | every pass | 0.0006 ms |

## Result after the change

| | Before | After |
|---|---|---|
| NVML pass | 48.4 ms | **0.0227 ms** |

A pass is now about **2000 times cheaper**. The hwmon collector moved to the
same shared cache and kept its own result: 0.192 ms per pass.

## A second bug found on the way

The VRAM channels declared `Unit.BYTE` but reported mebibytes, so the user
interface showed `1125 B` for 1.1 GiB. The unit was right and the collector was
wrong. The collector now reports true bytes, and `SensorSpec.format` gained SI
and binary prefixes:

| Raw value | Was shown | Now shown |
|---|---|---|
| 1 179 648 000 B | `1125 B` | `1.1 GiB` |
| 210 000 000 Hz | `210000000 Hz` | `210.0 MHz` |
| 485 100 J | `485100 J` | `485.1 kJ` |
| 38 916 000 B/s | `38916000 B/s` | `38.9 MB/s` |

A byte count takes a binary prefix, because that is what every other tool on
this machine shows for memory. A transfer rate takes a decimal prefix, because
that is what every network tool shows. Degrees, volts, watts, percent and RPM
never take a prefix.
