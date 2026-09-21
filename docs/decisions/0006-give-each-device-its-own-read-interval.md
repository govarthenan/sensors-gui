# ADR 0006 — Give each device its own read interval, and cache between reads

- Date: 2026-09-16
- Status: accepted
- Evidence: `lab/exp-0004-hwmon-read-cost/`

## Context

A measurement of the 14 hwmon channels on this machine showed that the cost of
a read is not the same for every channel:

| Driver | Median cost of one read |
|---|---|
| `nvme` | 2.0 ms |
| `spd5118` | 1.5 ms |
| `r8169` | 0.010 ms |
| `k10temp` | 0.006 ms |
| `amdgpu` | 0.005 ms |

Five of the 14 channels take 99.8 % of the 10 ms that a full pass costs. The
cause is the bus: `spd5118` starts an SMBus transaction to the memory module,
and `nvme` sends an admin command to the drive and waits for the health log.

At 2 Hz, a plain "read everything each pass" design wakes the SSD six times a
second for data that changes by less than a degree in a minute.

## Decision

Every sensor specification carries a **minimum read interval**. The sampler
keeps the last value and its timestamp, and it re-reads a channel only when the
interval has passed. Between reads the sampler gives the cached value and marks
it with its age.

Default intervals:

| Source | Interval |
|---|---|
| `k10temp`, `amdgpu`, `r8169`, and any other register-backed channel | every pass |
| `spd5118` (DIMM temperature) | 5 s |
| `nvme` (drive temperature) | 5 s |
| NVMe SMART through the helper | 60 s |
| Peripheral battery | 60 s |

The user can shorten an interval in the settings, with a warning that a short
interval on a bus-backed sensor costs time and wakes the device.

## Consequences

- A pass costs about 1 ms instead of 10 ms.
- The user interface must show the age of a value, so that a five second old
  DIMM temperature does not look like a live one.
- The history store must record the time of the **read**, not the time of the
  pass, or a graph will show steps that the hardware did not make.
- The collector interface gains a cache. `read()` must stay the shape it is;
  the cache lives inside the collector.

---

## Amendment, 2026-09-21

- Evidence: `lab/exp-0006-nvml-read-cost/`

`exp-0006` found the same pattern in NVML, but **inside one device**, not
between devices:

| NVML channel | Median cost |
|---|---|
| `pcie_tx`, `pcie_rx` | 20.6 ms each |
| `energy` | 3.1 ms |
| `fan_speed` | 0.6 ms |
| the other 11 channels | 0.0006 ms each |

`nvmlDeviceGetPcieThroughput` samples the link over a window of about 20 ms and
blocks for that whole time. Two of those calls took 92 % of a 48.4 ms pass,
which is nearly the whole 50 ms budget for every collector together.

So the decision changes in two ways:

1. **The interval is per channel, not per device.** A device can hold one
   expensive channel among ten cheap ones.
2. **The cache lives in one shared place**, `sensors_gui/collectors/cache.py`,
   and every collector uses it. The first version of this ADR said the cache
   lives inside the collector. That led to two copies of the same rule, so the
   rule moved out.

The shared cache also holds a failure for the same interval as a success.
Retrying a dead device on every pass costs as much as reading a live one.

Result: the NVML pass fell from 48.4 ms to 0.0227 ms, and the hwmon pass kept
its 0.192 ms.

