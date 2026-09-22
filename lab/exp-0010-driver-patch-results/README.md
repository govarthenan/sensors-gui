# exp-0010 — what the driver patch actually found

Date: 2026-09-22. Gova ran the install; Claude ran the correction.

## Question

`exp-0009` read the BIOS and found two gaps: a fan Linux cannot see, and a
voltage map that is mostly wrong. The patch built from that reading carried two
**guesses**, on registers 14 and 15, because no evidence could settle them
without a rebuild. Are they right?

## Method

Two rounds. Each one: patch, rebuild through DKMS, reload, read the machine.

```bash
sudo ./scripts/patch-nct6687.sh
```

## Round 1 — the guesses were wrong, and one was wrong in a useful way

| Target | Expected | Measured | Verdict |
|---|---|---|---|
| `fan9` at register `0x144` | 963–1612 RPM | **0 RPM**, constant | wrong register |
| `CPU 1P8` at register 15 | 1.793 V | **0.000 V**, constant | nothing is there |
| `CHIPSET Core` at register 14 | 1.047 V | **3.116 V**, steady | wrong label, **real reading** |
| `CPU VDDIO` (rename) | 1.368 V | 1.368 V | **confirmed** |
| `System 3.3V` (rename) | 3.288 V | 3.292 V | **confirmed** |
| `in2`, `in6`, `in12` gone | — | gone | **confirmed** |

Both renames were right. Both guesses were wrong. But register 14 was reading
**something**, steadily, and 3.116 V is exactly what a healthy CR2032 gives —
and the MS-7E32 map in this same driver puts the **CMOS battery** on register
14.

## The fan: the answer was a comment in the driver

The patch used register `0x144`, following the only precedent — the MEG Z890
GODLIKE, where that register is a second pump. On this board it reads zero.

The driver's own **default** fan table has the answer, in a comment:

```c
{.reg_rpm = 0x146, ... .label = "System Fan #2"}, // SYS Fan 2, EZConn on others
```

`0x146` is free in the `msi_alt1` mapping, because the system fans moved to
`0x154`–`0x15E`. The register is board-specific, so `board_data` gained an
optional `fan9_reg_rpm` and this board gets its own copy of the table with that
one register changed. The GODLIKE is untouched.

## Round 2 — both fixes confirmed on the machine

| Channel | Ten samples | BIOS said |
|---|---|---|
| `fan9` **EZ Conn Fan** | 988, 988, 966, 988, 988, 966, 964, 986, 986, **963** | 963 and 1612 |
| `in13` **CMOS Battery** | 3116, 3116, 3120, 3116, 3116 mV | not reported |

**963 RPM against the BIOS's 963 RPM.** The case fans on header `JAF_1` are
readable in Linux for the first time.

## The board channels now

| | Before any patch | Now |
|---|---|---|
| Fan channels | 8 | **9** |
| Voltages shown | 14, of which 4 correct | **10**, of which 7 correct or renamed |
| Duplicate rails shown | 4 (one rail, four names) | **0** |
| CMOS battery | wrong (2.046 V) | **3.116 V, healthy** |

```
fan1  CPU Fan          1488 RPM      in0   +12V          12.120 V
fan2  Pump Fan         1461 RPM      in1   +5V            5.050 V
fan3  System Fan #1    1295 RPM      in3   CPU Soc        1.310 V
fan4-8 System Fan #2-6    0 RPM      in4   CPU Vcore      0.966 V
fan9  EZ Conn Fan       986 RPM      in7   CPU VDDIO      1.368 V
                                     in8   Chipset        0.296 V  (wrong, kept)
                                     in9   CPU SA         0.812 V  (unverified)
                                     in10  Voltage #2     1.528 V  (unverified)
                                     in11  System 3.3V    3.292 V
                                     in13  CMOS Battery   3.116 V
```

## What is still unmapped

Three rails the BIOS reads and Linux does not: `VDD MISC` 1.097 V,
`CPU 1P8` 1.793 V, `CHIPSET Core` 1.047 V. Both untried registers are now
accounted for — 15 is empty and 14 is the battery — so these are not in this
chip's voltage block at all. The BIOS must read them some other way.

`Chipset` at 0.296 V is left **visible and wrong on purpose**. It is a live
reading of something real, and the driver hiding it would destroy information.
The application marks it instead.

## Findings

1. **A guess that is labelled as a guess costs nothing and can pay.** Both
   guesses were wrong, and one of them found the CMOS battery, which nobody was
   looking for. Neither cost anything, because each reused a channel already
   proven wrong.
2. **Read the code's comments before guessing from precedent.** The fan
   register was documented in the driver's own default table. The first patch
   guessed from a sibling board instead, and lost a round.
3. **A steady wrong number is information.** Register 14 reading a constant
   3.116 V was more useful than a zero. `exp-0008` made the same point about
   the distinct-value count.
