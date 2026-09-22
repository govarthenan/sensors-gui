# exp-0009 — the BIOS as ground truth

Date: 2026-09-22. Gova photographed the BIOS after an emergency shutdown.

## Question

The `nct6687d` driver reports 14 voltages, and `exp-0008` showed that all 14
are live but several disagree with physics. Which label belongs to which
reading? Only a source that already knows the board can say, and the BIOS is
that source.

## Method

Gova entered the BIOS Hardware Monitor and photographed every page.
Photographs: `docs/photos/bios/`.

## Result 1: the EZ Conn fan exists, and Linux cannot see it

The BIOS fan list has **nine** entries. Linux shows eight.

| BIOS name | BIOS RPM | Linux `nct6687` |
|---|---|---|
| CPU Fan 1 | 3125 / 1986 | `fan1` **CPU Fan** ✓ |
| PUMP SYS Fan 1 | 1445 / 1449 | `fan2` **Pump Fan** ✓ |
| SYS Fan 1 | 1732 / 1213 | `fan3` **System Fan #1** ✓ |
| SYS Fan 2 … 6 | **N/A** | `fan4`–`fan8` = 0 RPM ✓ (they agree: nothing is plugged in) |
| **EZ Conn Fan** | **1612 / 963 RPM** | **nothing. Linux has no channel for it.** |

**This closes the question that three sessions could not.** Gova's case fans
are on the **EZ Conn header (`JAF_1`)**, exactly as the manual suggested. There
was never a fan hub to find, because the EZ Conn connection is a cable. The
BIOS reads that header's tachometer. The Linux driver does not.

The five empty `SYS_FAN` headers are genuinely empty. The BIOS agrees, and
prints `N/A` where Linux prints `0`.

### The driver can already do this

`nct6687.c` holds the answer:

```c
#define NCT6687_NUM_REG_FAN     8
#define NCT6687_NUM_REG_FAN_MAX 9   /* tachometer-only, no PWM */
```

The ninth channel, at register `0x144` in the `msi_alt1` mapping, is enabled
for exactly one board today, the MEG Z890 GODLIKE, where it is a second pump.
This board uses `nct6687_msi_alt_default`, which stops at 8.

Setting `fan_mask` alone is **not** enough: every read loop is bounded by
`nct6687_fan_channels`, which comes from the board entry. The board entry has
to change.

## Result 2: the true voltage map for MS-7E47

BIOS readings, from `docs/photos/bios/01-temps-and-voltages.jpg`, against the
Linux driver at idle.

| BIOS name | BIOS | Linux label | Linux | Verdict |
|---|---|---|---|---|
| System 12V | 12.096 V | `+12V` | 12.120 V | **correct** |
| System 5V | 5.050 V | `+5V` | 5.050 V | **correct, exact** |
| CPU Core | 1.340 V | `CPU Vcore` | 1.340 V | **correct, exact** |
| CPU NB/SOC | 1.312 V | `CPU Soc` | 1.312 V | **correct, exact** |
| **CPU VDDIO** | **1.368 V** | `DRAM` | 1.368 V | right value, **wrong name** |
| **System 3.3V** | **3.288 V** | `AVCC3` | 3.288 V | right value, **wrong name** |
| VDD MISC | 1.097 V | — | — | **Linux does not read it** |
| CPU 1P8 | 1.793 V | — | — | **Linux does not read it** |
| CHIPSET Core | 1.047 V | — | — | **Linux does not read it** |

And the eight Linux channels that match nothing in the BIOS:

| Linux label | Linux value | Verdict |
|---|---|---|
| `+3.3V` | 3.332 V | not the 3.3 V rail; that is `AVCC3` |
| `CPU 1P8` | 3.332 V | the real 1P8 is 1.793 V |
| `CPU VDDP` | 3.328 V | the same reading again |
| `AVSB` | 3.332 V | the same reading again |
| `Chipset` | 0.324 V | the real chipset core is 1.047 V |
| `CPU SA` | 0.792 V | no BIOS equivalent |
| `Voltage #2` | 1.528 V | no BIOS equivalent |
| `VBat` | 2.046 V | **not the CMOS battery** |

So: **4 of 14 are right, 2 are right with the wrong name, and 8 are wrong.**
Four of the wrong ones read the same ~3.33 V, which is one register read four
times.

**Gova's CMOS battery is fine.** `VBat` at 2.046 V does not come from the
battery. The BIOS does not list a battery voltage at all.

Three rails the BIOS reads are missing from Linux. The MSI Z890 override in the
driver uses registers **14** and **15**, which the generic table never touches.
That is where they will be.

## Result 3: the board's own fan curve

From `docs/photos/bios/02-fan-curve.jpg`:

| Setting | Value |
|---|---|
| Mode | Smart Fan, PWM, fan type auto-detect |
| Temperature source | **CPU Core** |
| Curve | 0 °C → 20 %, 45 °C → 35 %, 65 °C → 70 %, 80 °C → 100 % |
| Step up / down | 0.1 s |

This is what the application should draw beside the fan readings, so a speed
can be read against the curve that produced it.

## Result 4: a safety setting that is switched off

`docs/photos/bios/04-board-and-bios-version.jpg`:

```
CPU Fan Fail Warning Control    OFF
```

**That is why the board stayed silent while the CPU fan sat at 0 RPM.** With it
on, the board warns at power-on when the CPU fan does not turn.

**Recommendation for Gova: switch it ON.** It costs nothing and it is exactly
the alarm that was missing yesterday.

## Result 5: small inventory corrections

| Item | Was recorded | BIOS says |
|---|---|---|
| Memory maker | "Unknown", part `UD5-6400` | **TEAM GROUP**, 2 × 32768 MB, DDR5-6400 |
| Slots used | A2 and B2 | confirmed: A1 empty, A2 filled, B1 empty, B2 filled |
| BIOS version | `1.A10`, 2024-08-27 | `E7E47AMSI.1A10`, 2024-08-27 |
| SATA | not checked | all four ports empty |
| Board temperature | — | 41 °C |

## Next

1. Switch `CPU Fan Fail Warning Control` on. (Gova, in the BIOS.)
2. **Read-only** driver work: give this board the 9-channel entry so the EZ Conn
   fan appears in Linux, then confirm `fan9` matches the BIOS. This adds a read
   and changes no output. It needs Gova's agreement first.
3. Map the three missing voltage rails to registers 14 and 15, and correct the
   six wrong labels. Also read-only.
4. Both are worth contributing to the `nct6687d` project, because they apply to
   every MSI PRO X870-P WIFI, not only to this machine.
