# exp-0008 — which channels react to load

Date: 2026-09-21

## Question

Step 3 of Gova's coverage experiment asks whether a reading is **realistic**. A
value that looks plausible at idle can still come from the wrong register. The
only honest test is causal: drive the machine, and see which channels move with
it.

## Method

`loadtest.py` reads all 60 channels at 2 Hz through three phases:

```
idle 20 s  ->  load 60 s (24 busy processes)  ->  cooldown 30 s
```

For each channel it records the median of each phase, the whole range, and how
many **distinct values** it gave. The distinct count is the useful one: a live
analogue-to-digital reading always jitters by at least one step. A channel that
gives exactly one value for 220 samples is not measuring.

```bash
uv run python lab/exp-0008-load-response/loadtest.py
```

## A flaw in this run

**The idle phase was not idle.** `Tccd1` had a median of 61.9 °C during "idle"
while `Tccd2` had 35.9 °C. Work was running on the first CCD when the test
started, left over from the session that launched it.

So **the phase medians of this run are not trustworthy**, and one of them is
absurd: `Tctl` appears to fall by 1.1 °C under load.

The range and the distinct count do not depend on the phase split, so those are
the results kept below. The run must be repeated on a quiet machine before the
medians are used.

## Result: the channels that react

| Channel | Distinct values | Range | Verdict |
|---|---|---|---|
| `Tccd1` | 71 | 36.4 → **78.4 °C** | **verified** |
| `Tccd2` | 44 | 32.9 → **64.6 °C** | **verified** |
| `Tctl` | 81 | 54.3 → 76.6 °C | **verified** |
| `CPU` (board) | 20 | 54.0 → 76.0 °C | verified, but a **duplicate** of `Tctl` |
| **`CPU Vcore`** | 33 | **1.042 → 1.376 V** | **verified** — it falls under an all-core load, which is what Vcore does when the CPU leaves its single-core boost |
| `CPU Fan` | 44 | 2030 → **2758 RPM** | **verified** — it follows the coolant temperature |
| `Pump Fan` | 10 | 1461 → 1479 RPM | **verified** — steady, as a pump is |
| `System Fan #1` | 25 | 1263 → 1304 RPM | verified, on a flat curve |
| `VRM MOS` | 7 | 39.5 → 42.5 °C | **verified** |
| `Chipset` | 20 | 0.298 → 0.340 V | **live, but the value is not a chipset rail** |
| NVMe `Sensor 1` | 14 | 50.9 → **66.9 °C** | verified |
| NVMe `Composite` | 9 | 37.9 → 45.9 °C | verified |
| `CPU Soc` | 4 | 1.312 → 1.318 V | live, steady, as SoC voltage is |
| `CPU SA` | 4 | 0.788 → 0.794 V | live |
| `DRAM` | 2 | 1.368 → 1.372 V | live; 1.37 V fits DDR5 at 6400 MT/s with EXPO |
| `+12V` | 3 | 12.096 → 12.144 V | live |
| `+5V` | 2 | 5.040 → 5.050 V | live |
| `AVCC3` | 3 | 3.284 → 3.292 V | live |
| `System` (board) | 2 | 38.0 → 38.5 °C | live |
| `PCH` | 2 | 37.5 → 38.0 °C | live |
| GPU power | 210 | 37.8 → 74.5 W | verified |
| GPU use | 53 | 0 → **97 %** | verified |
| GPU SM clock | 26 | 210 MHz → **2.625 GHz** | verified |
| VRAM used | 125 | 1.04 → 1.41 GiB | verified |
| PCIe receive | 37 | 0.44 → **122.8 MB/s** | verified |
| `edge`, `vddgfx`, `vddnb`, `PPT` (integrated GPU) | 2–27 | all moved | verified |

## Result: the channels that never moved

15 channels gave exactly one value for the whole run. **None of them is a
fault.** Each has a reason:

| Channel | Why it did not move |
|---|---|
| `System Fan #2` to `#6` | empty headers; nothing is wired to them |
| `CPU Socket`, `PCIe x1`, `M2_1` | optional thermistor headers with no thermistor |
| `GPU fan` | the RTX 4090 stops its fans below about 50 °C |
| `NVENC use`, `NVDEC use` | nothing encoded or decoded video |
| `sclk` (integrated GPU) | pinned at 600 MHz; the card drives the displays |
| `VRAM reserved` | the driver reserves a fixed 504 MiB |
| `Graphics processes`, `Compute processes` | the desktop kept exactly 4 open |

## Finding: a correction to exp-0007

`exp-0007` called four voltages "**WRONG**" and suspected they were dead. That
was too strong. **All 14 voltages are live analogue readings** — every one of
them jitters by at least one step across 220 samples.

The real problem is narrower, and it is a **mapping** problem:

| Channel | Range | What is wrong |
|---|---|---|
| `+3.3V` | 3.332 – 3.336 V | one of these four is right |
| `CPU 1P8` | 3.332 – 3.336 V | a 1.8 V rail cannot read 3.33 V |
| `CPU VDDP` | 3.332 – 3.336 V | the same reading again |
| `AVSB` | 3.332 – 3.336 V | the same reading again |
| `Chipset` | 0.298 – 0.340 V | live and it moves with load, but an AM5 chipset rail is about 0.9–1.1 V, so the multiplier or the register is wrong |
| `VBat` | 2.044 – 2.046 V | live, but a CR2032 gives 3.0 V. The MSI Z890 map in the driver puts the CMOS battery at register **14**, not 13 |

Four channels reading the same value means the driver is reading **one**
register four times under four names. The cause is known from `exp-0007`: the
driver has a board-specific voltage map for the MSI Z890 MS-7E32 only, and this
board falls back to the generic table.

**Do not tell Gova the CMOS battery is flat.** The reading almost certainly
comes from the wrong register.

## Finding: the drive heats under a CPU load

NVMe `Sensor 1` went from 50.9 °C to **66.9 °C**. The drive is under the
graphics card, and the case has no bottom intake beneath it, because the AIO
radiator sits there. The drive never throttled (`Thermal Management` counters
are all zero), so this is not a fault, but it is worth watching.

## Next

1. **Repeat this run on a quiet machine**, so the phase medians can be used.
2. **`exp-0009` — map the voltage registers.** The driver takes a `manual`
   module parameter that exposes the raw `in0` to `in13` with no labels. With
   that, plus a load test and the known-good rails as anchors, the true map for
   MS-7E47 can be worked out and contributed back to the driver project.
3. A GPU load test. This run drove the CPU only. The GPU reached 97 % by
   accident, from the desktop, which verified the channels but not on purpose.
