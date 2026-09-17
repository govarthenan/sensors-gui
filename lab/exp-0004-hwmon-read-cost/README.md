# exp-0004 — the cost of a hwmon read

Date: 2026-09-16

## Question

Does every hwmon channel cost the same to read? If not, which ones are
expensive, and what does that mean for the sample rate?

## Method

`measure.py` uses the project collector. It discovers the 14 channels, warms
the caches with one pass, then reads each channel 50 times and records the
median. It then times 50 full passes.

```bash
uv run python lab/exp-0004-hwmon-read-cost/measure.py
```

## Result

| Channel | Driver | Median |
|---|---|---|
| Sensor 1 | `nvme` | **2.028 ms** |
| Sensor 2 | `nvme` | **2.013 ms** |
| Composite | `nvme` | **1.981 ms** |
| temp1 (DIMM 0x51) | `spd5118` | **1.470 ms** |
| temp1 (DIMM 0x53) | `spd5118` | **1.469 ms** |
| temp1 (Ethernet PHY) | `r8169` | 0.010 ms |
| Tctl, Tccd1, Tccd2 | `k10temp` | 0.006 ms |
| edge, vddgfx, vddnb, PPT, sclk | `amdgpu` | 0.005 ms |

**Full pass: 10.015 ms.**

## Findings

1. **Two drivers take 99.8 % of the time.** The five NVMe and SPD5118 channels
   cost 9.96 ms of the 10.02 ms. The other nine channels together cost 0.05 ms.
2. **The reason is the bus.** `k10temp` and `amdgpu` read a register the CPU or
   the GPU already holds. `spd5118` starts an SMBus transaction to the DDR5 SPD
   hub on the memory module. `nvme` sends an admin command to the drive and
   waits for the SMART health log.
3. **The NVMe cost is per read, not per log.** All three NVMe temperatures come
   from **one** SMART health log page. The kernel driver fetches that page
   again for each of the three files, so the collector pays 2 ms three times
   for data that one fetch gives.
4. **10 ms is still inside the 50 ms budget**, but it is 2 % of a 2 Hz cycle
   spent waiting on buses, and it wakes the SSD 6 times each second. That is
   waste, and on a drive it may stop a low power state.

## Decision

Give each hwmon device its own read interval, and cache the last value between
reads. See ADR 0006.

Planned intervals:

| Driver | Interval | Why |
|---|---|---|
| `k10temp`, `amdgpu`, `r8169` | 0.5 s (every pass) | almost free |
| `spd5118` | 5 s | DIMM temperature moves slowly, and the read uses the SMBus |
| `nvme` | 5 s | drive temperature moves slowly, and the read wakes the drive |

That brings the average cost of a pass from 10.0 ms to about 1.0 ms.

## Result after the change

The interval cache of ADR 0006 was built and measured over 60 passes at 50 Hz:

| | Before | After |
|---|---|---|
| Median pass | 10.015 ms | **0.199 ms** |
| Mean pass | 10.0 ms | **0.388 ms** |
| Worst pass | — | 0.949 ms (the pass that re-reads the slow devices) |

A pass is now **50 times cheaper**. The worst pass, the one that falls due for
the NVMe and DIMM reads, still costs less than 1 ms, because the two slow
devices no longer fall due together on every pass.

