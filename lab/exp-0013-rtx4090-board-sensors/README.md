# exp-0013 — The RTX 4090 board sensors: is there a route that only reads?

- Date: 2026-09-22 (session 7)
- Target 3 of `lab/exp-0005-component-census/README.md`
- Related: ADR 0007, ADR 0010, ADR 0011, `lab/exp-0002-nvidia-access/`

## Question

`exp-0005` target 3 asks for three things the RTX 4090 does not report through
NVML: the **hotspot temperature**, the **speed of each fan** and the **VRM
temperature**. The plan named one route: the card's own I2C buses, read from
the board controller. The plan also marked it "risky".

ADR 0010 says to ask one question before a route is planned: **does it read, or
does it tell the hardware something?** So this experiment has two parts.

1. Does an I2C read of the card write? Answer this on paper, before any
   command touches a bus.
2. If the answer is yes, is there any route that only reads?

## Method

### Part 1 — the I2C question, on paper

No bus was probed. Two sources were read:

- the adapters the card publishes, from sysfs (a directory listing starts no
  bus transaction) → `results/i2c-adapters.txt`;
- what the I2C tools say about themselves, from the manual pages on this
  machine → `results/i2c-tools-warnings.txt`.

### Part 2 — the search for a route that only reads

`results/nvml-fields.json`, from `probe-nvml-fields.py`: every NVML field
constant the binding knows (302 of them), every temperature sensor index from
0 to 7, every temperature threshold, and the fan count with a speed for each
fan. The script calls no `nvmlDeviceSet*` function and touches no bus.

`results/tlimit-under-load.csv`, from `watch-tlimit.py`: 95 samples, one a
second, while `vkcube` loaded the card and then stopped. This tests whether the
three `*_TLIMIT` fields are **live margins** — which would give the hotspot
temperature — or **constants**.

## Result

### 1. The I2C route writes. The target is dropped.

The card publishes five buses: `i2c-3` to `i2c-7`, all on `0000:01:00.0`. What
sits on them is unknown, and the only way to find out is to probe them.

An I2C read is not a read at the bus level. To read a register the master must
first **write** the register number, then restart and read. The tool that would
do it says so in its own manual page:

> i2cget can be extremely dangerous if used improperly. I2C and SMBus are
> designed in such a way that **an SMBus read transaction can be seen as a
> write transaction by certain chips**.
> — `i2cget(8)`

And the tool that would find the addresses first:

> This program can confuse your I2C bus, cause data loss and worse!
> — `i2cdetect(8)`

Both of `i2cdetect`'s probing methods are marked "Not recommended" in the same
page: quick write "is known to corrupt the Atmel AT24RF08 EEPROM", and receive
byte "is known to lock SMBus on various write-only chips".

This is the same shape as the route ADR 0010 already closed. That decision
forbids "writing an address to a PCI configuration index register to read SMN",
because it is a write to a shared register and a second reader can be part-way
through its own transaction. An I2C register pointer **is** such a register,
and on a graphics card there is certainly a second master: the card's own
controller reads these sensors continuously for its fan curve and its power
limit.

What sits on those buses is also unknown, and on a graphics card it includes
the voltage controller. ADR 0007 rule 1, in its original form, named I2C
addresses `0x48` to `0x4F` as forbidden because they set memory voltage. The
same class of part is on the card.

**So the I2C route is dropped, under the closing sentence of ADR 0007: if a
question can only be answered by writing, drop the question.** Written up as
ADR 0011.

### 2. The `*_TLIMIT` fields are constants. There is no hotspot.

This was the one promising lead: `exp-0002` found that the `TLIMIT` fields hold
a **headroom in degrees**, not a temperature, so `threshold − headroom` might
give the sensor the threshold is measured against — the hotspot.

It does not. Over 95 samples, while the edge temperature moved 32 → 40 °C, the
power 43.7 → 132.1 W and the use 2 → 99 %:

| Field | Distinct values in 95 samples |
|---|---|
| `NVML_FI_DEV_TEMPERATURE_SHUTDOWN_TLIMIT` | 1 (always −7) |
| `NVML_FI_DEV_TEMPERATURE_SLOWDOWN_TLIMIT` | 1 (always −2) |
| `NVML_FI_DEV_TEMPERATURE_GPU_MAX_TLIMIT` | 1 (always 0) |

They do not move with the temperature, so they are not a live margin. They are
offsets between the thresholds, fixed in the card's firmware. **NVML on this
card gives one temperature and no hotspot**, which is what `exp-0002` found.
This is the second, and stronger, confirmation.

Every temperature sensor index from 1 to 7 is refused with `Invalid Argument`.
Only index 0, the edge sensor, answers. `threshold_mem_max` is `Not Supported`,
so there is no memory temperature either.

### 3. Found: the speed of each fan, in RPM, with no write. 4 new channels.

`nvmlDeviceGetNumFans` reports **2** fans, and `nvmlDeviceGetFanSpeedRPM` gives
the true speed of each one. Under the same load:

| | Stopped | Under load |
|---|---|---|
| Fan 0 | 0 RPM | 1205 RPM |
| Fan 1 | 0 RPM | 1520 RPM |

**The two fans do not turn at the same speed**, and the single `fan_speed`
channel the collector had reports fan 0 alone, as a percent. So one of the
three things target 3 wanted — the speed of each fan — was available all along
through a plain NVML call, with no bus, no root and no write.

Cost, 30 rounds each: `nvmlDeviceGetFanSpeedRPM` 0.445 ms and 0.410 ms,
`nvmlDeviceGetFanSpeed_v2` 0.596 ms. Four calls on every pass would be 2 ms, so
they take the same one-second interval as the original fan channel (ADR 0006).

Gova decided on 2026-09-22 to add an RPM channel and a percent channel for each
fan and to keep the original one. The screen went from 171 to **175 channels**,
at 1.84 ms per pass.

### What is still missing from the card

| Missing | Why |
|---|---|
| Hotspot temperature | NVML gives one sensor. The board controller holds it, and the only route to it is I2C, which writes. **Dropped, ADR 0011.** |
| Memory (GDDR6X) temperature | the same |
| VRM temperature | the same |

## Files

| File | What |
|---|---|
| `probe-nvml-fields.py` | reads every NVML field, sensor, threshold and fan. Read-only. |
| `watch-tlimit.py` | samples the thermal fields once a second under load. Read-only. |
| `results/nvml-fields.json` | the whole sweep: 302 fields, 58 with a value |
| `results/tlimit-under-load.csv` | 95 samples, idle → 99 % → idle |
| `results/i2c-adapters.txt` | the buses the card publishes, from sysfs |
| `results/i2c-tools-warnings.txt` | what `i2cget` and `i2cdetect` say about themselves |
