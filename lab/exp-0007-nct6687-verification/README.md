# exp-0007 — verify the nct6687 channels

Date: 2026-09-21. Gova ran the install.

## Question

The `nct6687d` driver loaded and gave 29 new channels. Step 3 of Gova's
experiment asks: is each value **not null and realistic**? Which of the 29 can
we trust, and which are wrong?

## Method

```bash
sudo ./scripts/install-nct6687d.sh
```

Then, without root:
- read every raw attribute of the new hwmon device;
- read the same channel twice, two seconds apart, to see what moves;
- compare the board's "CPU" temperature against `k10temp` over five samples;
- read the driver source in `/usr/src/nct6687d-1/nct6687.c` for the register
  map and the board table.

## Result: the install worked

The module built, was signed with the enrolled MOK, and loaded first time.
No BIOS change and no kernel parameter were needed.

```
signer: localhost.localdomain Secure Boot Module Signature key
[nct6687d] module loaded
```

The chip is a **Nuvoton NCT6687D at ISA 0x0a20**. That answers the open
question from `exp-0003` that no user-space tool could answer.

New hwmon device: `nct6687`, **29 channels** — 8 fans, 14 voltages, 7
temperatures.

## Result: what is trustworthy

| Channel | Value | Verdict | Why |
|---|---|---|---|
| CPU Fan | 1907–2247 RPM | **good** | it moves with the CPU temperature |
| Pump Fan | 1470 RPM | **good** | steady, which is what a pump does; it confirms the AIO |
| System Fan #1 | 1294 RPM | **good** | |
| System Fan #2–6 | 0 RPM | **empty headers** | Gova has 7 case fans, so 6 of them are not on the board |
| +12V | 12.120 V | **good** | |
| +5V | 5.040 V | **good** | |
| +3.3V | 3.332 V | **good** | |
| CPU Vcore | 1.182–1.358 V | **probably good** | it moves, which Vcore does |
| CPU Soc | 1.312 V | **probably good** | steady, which SoC voltage is |
| DRAM | 1.368 V | **probably good** | plausible for DDR5 at 6400 MT/s with EXPO |
| AVCC3 | 3.288 V | **probably good** | |
| System | 38.0 °C | **good** | |
| VRM MOS | 38.5 °C | **good** | |
| PCH | 37.5 °C | **good** | |
| **CPU** | 57.0 °C | **a duplicate** | see below |
| CPU Socket, PCIe x1, M2_1 | 0.0 °C | **empty** | optional thermistor headers with nothing plugged in |
| **CPU 1P8** | 3.332 V | **WRONG** | a 1.8 V rail cannot read 3.33 V |
| **CPU VDDP** | 3.328 V | **suspect** | the same value as three other channels |
| **AVSB** | 3.328 V | **suspect** | the same value again |
| **Chipset** | 0.324 V | **WRONG** | an AM5 chipset rail is about 0.9–1.1 V |
| **VBat** | 2.044 V | **suspect** | a CR2032 gives 3.0 V; 2.04 V would mean a flat cell |
| CPU SA | 0.792 V | unverified | |
| Voltage #2 | 1.526 V | unverified | it has no name |

## Finding 1: `_min` and `_max` are not thresholds

The kernel hwmon ABI says `tempN_max` is a limit. **This driver does not follow
it.** It writes the running minimum and maximum it has seen.

```
first read   temp1_input=58000   temp1_min=58000   temp1_max=58000
2 s later    temp1_input=60000   temp1_min=58000   temp1_max=60000
```

`temp1_max` tracked the input. A collector that reads `_max` as a warning
threshold puts **every channel at its own warning limit**, so the application
alarms for ever, on every board sensor.

Fixed: `DRIVERS_WITH_TRACKING_LIMITS` in `collectors/hwmon.py` now holds
`nct6687`, `nct6686` and `nct6683`, and no limit is taken from them. A driver
with genuine limits, such as `nvme`, is untouched.

## Finding 2: the board "CPU" temperature is `Tctl` again

Five samples, one second apart:

| `k10temp` Tctl | `nct6687` CPU |
|---|---|
| 57 °C | 58 °C |
| 58 °C | 58 °C |
| 57 °C | 57 °C |
| 60 °C | 60 °C |
| 60 °C | 60 °C |

They are the same value. The board reads the CPU's own sensor over the
SVI/SB-TSI link and reports it. It is **not** a second measurement. The user
interface must not show it as one.

## Finding 3: the voltage map is not written for this board

The driver has a board table. Your board is in it:

```c
NCT6687_DMI_BOARD("PRO X870-P WIFI (MS-7E47)"),
```

But that entry carries **fan and temperature** handling only. The driver has
exactly **one** board-specific voltage map:

```c
/* MSI Z890 MS-7E32 voltage mapping adapted from LibreHardwareMonitor. */
static const struct voltage_reg_override nct6687_voltage_ms7e32_overrides[] = { ... };
```

Every other board, including this one, uses the generic default table. That is
why four channels report the same 3.33 V, and why the chipset rail and the CMOS
battery are wrong.

The Z890 map also shows what the right answer looks like: there the CMOS
battery is register **14**, not 13, and there is a real `+1.8V` at register 15.
So the generic map is off by more than a label.

**Do not tell Gova the CMOS battery is flat.** The 2.044 V almost certainly
comes from the wrong register.

## Finding 4: the first read after the module loads gives zeros

The `sensors` output taken by the install script, seconds after `modprobe`,
showed `+3.3V 0.00 V`, `AVSB 0.00 V` and `VBat 0.00 V`. The same three channels
now read 3.332 V, 3.328 V and 2.044 V.

The driver needs one update cycle before its values are valid. **The
application must throw away the first sample after a device appears.**
Unconfirmed: reproducing it needs a module reload, which needs root.

## Correction, from exp-0008

This file first called four voltages "**WRONG**" and implied they were dead.
`exp-0008` showed that **all 14 voltages are live**: every one jitters by at
least one step across 220 samples. The fault is narrower than stated here — it
is a **mapping** fault, not a dead channel. Four names read one register, and
two more are scaled or addressed wrongly. See `exp-0008` for the corrected
table.

## Next

`exp-0008` — a load test. Put a load on the CPU and watch which channels move.
That separates Vcore from SoC, confirms the fan response, and shows which of
the unverified voltages react to anything.
