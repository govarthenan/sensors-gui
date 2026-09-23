# exp-0017 — the RTX 4090 Suprim Liquid X's two NVML fan channels, at idle

- Date: 2026-09-23 (session 9)
- Related: `lab/exp-0013-rtx4090-board-sensors/README.md` (found the two fan channels and their
  under-load RPMs), `docs/physical-build.md` (the card is the SUPRIM LIQUID X: one fan on the
  card, a 240 mm radiator with 2 fans as its own, not the CPU cooler's),
  `data/evidence/rtx4090-liquidx-fans-2026-09-23/` (the published-source half of this same
  question), ADR 0007, ADR 0010, ADR 0011

## Question

Gova asked: can we read the RPM of the fan that sits ON the card (underneath, blowing down)?
`exp-0013` already showed that NVML reports 2 fans with independent RPMs (1205 and 1520 under
load), so the fan on the card is almost certainly already one of those two channels. The open
question is **which one**, and what the other channel drives — the two radiator fans, wired
together, or something else. This experiment asks whether NVML itself, read only, gives any
further fact — beyond the two RPM numbers already known — that could tell the two channels
apart: a cooler-target label, a field name, a control-policy difference, a speed range.

## Method

`probe.py` reads, with `pynvml` (nvidia-ml-py), and calls no `nvmlDeviceSet*` function and no
I2C route (ADR 0007, ADR 0010, ADR 0011):

Once, at the start:
- `nvmlDeviceGetNumFans`
- `nvmlDeviceGetMinMaxFanSpeed` (the legacy, non-per-fan percent range)
- for each fan index: `nvmlDeviceGetFanControlPolicy_v2`, `nvmlDeviceGetTargetFanSpeed`, and
  `nvmlDeviceGetCoolerInfo` — the pynvml binding's own wrapper for the last of these hardcodes
  `index = 0`, so this script repeats the binding's own approach (a raw `ctypes` struct and
  function-pointer call) with the index set, the same way `exp-0013` already does for
  `nvmlDeviceGetFanSpeedRPM` to reach fan 1.
- every `NVML_FI_*` field constant in this pynvml binding whose name contains `FAN` or
  `COOLER`, read with `nvmlDeviceGetFieldValues` if any exist.

Then, a 60-second series at 2 Hz (120 samples): timestamp, edge temperature, power,
utilization, `fan0`/`fan1` RPM (via the same raw-pointer route as `exp-0013`), `fan0`/`fan1`
percent (`nvmlDeviceGetFanSpeed_v2`), and the legacy single-value `nvmlDeviceGetFanSpeed`.

No stress tool was run. The machine was left idle; the GPU was doing ordinary desktop
compositor work only (`nvidia-smi` immediately before the run: 19 % utilization, 35 °C,
40 W — background load, not a synthetic one).

```bash
uv run python lab/exp-0017-gpu-fan-channels/probe.py
```

## Result

`results/probe.json` and `results/probe-series.csv`, captured 2026-09-23 on `dst-gova-pc`,
driver 595.91.07, NVML 13.595.91.07.

### The series: both fans are stopped at idle, exactly as exp-0013 found

Across all 120 samples (60 s at 2 Hz): `fan0_rpm`, `fan1_rpm`, `fan0_pct`, `fan1_pct` and
`legacy_fan_speed_pct` are **all 0, every sample, no exceptions**. Edge temperature held at
35 °C throughout; power drifted 38.2-45.2 W with the desktop's own background load (peak
utilization spike 60 % on one sample, from something other than this script — this script
does no rendering or compute). Confirms `exp-0013`'s idle reading (0 RPM on both channels)
under a fresh, longer, higher-rate sample, and adds that the **percent** readings are 0 too,
not just RPM — the fans are commanded off, not merely spinning too slowly to register.

### The once-off reads: no field distinguishes the two channels

| Call | fan 0 | fan 1 |
|---|---|---|
| `nvmlDeviceGetFanControlPolicy_v2` | `0` (`NVML_FAN_POLICY_TEMPERATURE_CONTINOUS_SW`) | `0` (same) |
| `nvmlDeviceGetTargetFanSpeed` | `30` % | `30` % (same) |
| `nvmlDeviceGetCoolerInfo` → `coolerControlType` | `2` (`NVML_THERMAL_COOLER_SIGNAL_VARIABLE`) | `2` (same) |
| `nvmlDeviceGetCoolerInfo` → `coolerTarget` | `14` = GPU + MEMORY + POWER_SUPPLY | `14` (same) |

`nvmlDeviceGetMinMaxFanSpeed` (the one non-per-fan legacy call) gave `[30, 100]` percent —
a single range, not one per fan.

**`nvmlDeviceGetCoolerInfo` exists on this driver and answers without error for both
indices — but it gives the identical answer for both.** The task description hoped this call
would "say what each fan cools"; it does carry a target label (`NVML_THERMAL_COOLER_TARGET_*`),
but on this card and driver **both fan 0 and fan 1 report the same composite target**, the
`GPU_RELATED` bitmask (GPU + memory + power supply combined), not a distinct label such as
"this one is the shroud fan, that one is the radiator". So this call does not resolve the
question; it was worth checking, and the answer is a clean **no distinguishing information**,
not a missing capability.

**No `NVML_FI_*` field constant in this pynvml binding (`nvidia-ml-py`) has `FAN` or
`COOLER` in its name.** `fan_or_cooler_field_constants_found` in the JSON is `{}`. This
binding has 305 `NVML_FI_*` constants in total (counted separately, not part of this script's
output); none of them name a fan or cooler field. This is a real, checked result, not an
oversight — the field-based route that worked for other channels (`exp-0013`'s `TLIMIT`
fields) has nothing to offer here.

### What this experiment does and does not establish

- **Confirms** (again, independently of `exp-0013`): 2 fans, both fully stopped at idle, both
  percent and RPM.
- **Established, new here**: `nvmlDeviceGetCoolerInfo` works on this driver for both cooler
  indices, and returns identical, generic values for both — it does not name a physical fan.
- **Does NOT establish** which index is the on-card fan. Every once-off NVML call that could
  plausibly carry a distinguishing label returned the same value for fan 0 and fan 1. The
  distinguishing fact this experiment already has is still only the pair of RPM numbers from
  `exp-0013` under load (1205 and 1520), which this experiment could not reproduce or extend
  because the owner's rule against heating the machine for a test means this run stayed idle.
  A load-bearing repeat of `exp-0013` (or watching the machine by eye, see below) is the next
  step, not a further NVML field search — this experiment used up the read-only NVML surface
  that could plausibly answer the question, and it came up empty.

## Files

| File | What |
|---|---|
| `probe.py` | reads the once-off fan/cooler facts and a 60 s / 2 Hz series. Read-only. |
| `results/probe.json` | the full report: meta, once-off reads, all 120 samples |
| `results/probe-series.csv` | the 120-row series alone, for a quick look or a plot |
