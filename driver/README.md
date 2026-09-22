# nct6687 patch — MSI PRO X870-P WIFI (MS-7E47)

Read-only patch to the out-of-tree `nct6687d` driver
(https://github.com/Fred78290/nct6687d, pinned commit `5f12dd1`) that gives
this one board (DMI board name `PRO X870-P WIFI (MS-7E47)`, Gova's machine)
a ninth fan channel and a corrected voltage table. Both changes only add or
relabel **reads**. Neither touches any write path, any PWM code, or
`pwm_enable`. This was verified by building the patched source as a kernel
module (`make modules` against `/lib/modules/$(uname -r)/build`) and
diffing the compiler output against an unpatched build — same two
environment warnings, no new ones, no errors.

File: `driver/nct6687-ms7e47.patch` — unified diff, `patch -p1` format,
against `/usr/src/nct6687d-1/nct6687.c` as pinned above. Apply and rebuild
with `scripts/patch-nct6687.sh` (requires root; Gova runs it, not Claude).

## Why this exists

`lab/exp-0009-bios-ground-truth` compared the BIOS Hardware Monitor pages
against what Linux reports through `nct6687d`. Two problems, both already
described in the driver itself:

1. The BIOS lists nine fans; Linux shows eight. The ninth is the "EZ Conn
   Fan" — Gova's case fans, on header `JAF_1` — and the driver already has a
   tachometer-only ninth channel (`NCT6687_NUM_REG_FAN_MAX`, register
   `0x144` in the `msi_alt1` register mapping), but only wires it up for one
   board, the MEG Z890 GODLIKE (as a second pump).
2. Of the fourteen voltages the driver reports for this board, only four are
   both correctly valued and correctly named. Two more are correctly valued
   but wrongly named. Six are wrong. Three rails the BIOS reads are not read
   by Linux at all.

## Change 1 — the ninth fan channel

`nct6687_board_data` gets a new field, `fan9_label`. It is `NULL` for every
existing board, which keeps their current behaviour: the ninth channel, when
enabled, is labelled from `nct6687_fan_config_msi_alt[8]` ("Pump Fan #2"),
which is correct for the MEG Z890 GODLIKE. A new board struct,
`nct6687_ms7e47`, sets `fan_channels = NCT6687_NUM_REG_FAN_MAX`,
`default_fan_mask = NCT6687_FAN_MASK_ALL` and `fan9_label = "EZ Conn Fan"`,
and the DMI table entry for `"PRO X870-P WIFI (MS-7E47)"` now points its
`driver_data` at it (this is the exact pattern the driver already uses for
the MEG Z890 GODLIKE and the MAG Z890 TOMAHAWK WIFI).

`nct6687_read_string()` picks `nct6687_board->fan9_label` over the shared
array's label only for channel 8 (index `NCT6687_NUM_REG_FAN`) and only when
the board sets one — every other channel, and every other board, is
unaffected. No other code needed to change: `nct6687_fan_channels`,
`nct6687_setup_fans()`, `nct6687_is_visible()` and the `hwmon_fan`
`HWMON_CHANNEL_INFO` block already handle up to nine channels generically
(the array is already sized `[3][NCT6687_NUM_REG_FAN_MAX]`, and the channel
info table already lists nine `NCT6687_FAN_CONFIG` entries) — that
infrastructure was added for the GODLIKE and simply had no board using the
ninth slot on this DMI entry until now.

**Confirmed from evidence:** the channel exists, its register (`0x144`) is
already read by the `msi_alt1` mapping, and the BIOS's RPM range (963–1612)
is a plausible case-fan reading. **Not yet confirmed:** that `fan9` on this
board, after the rebuild, actually tracks the case fans (e.g. moves when you
touch/block one). This needs the physical check below because the file
matches expectations but nothing here can spin a fan to prove it.

Note: the DMI table also lists `"X870 GAMING PLUS WIFI (MS-7E47)"` — a
different retail name that happens to share the MS-7E47 board number. That
entry is **not** touched. There is no BIOS evidence for that specific
product, and DMI matching is by board name string, so it cannot affect
Gova's machine (which reports `PRO X870-P WIFI (MS-7E47)`) either way.

## Change 2 — the voltage table

New override array `nct6687_voltage_ms7e47_overrides`, wired into a new
`nct6687_ms7e47` board_data entry (`voltage_overrides` /
`voltage_override_count`), following the shape of
`nct6687_voltage_ms7e32_overrides`. `hidden_voltage_mask` hides three
channels that are known duplicates (see below), following the shape of how
`nct6687_ms7e32` hides its own bad channel with `BIT(7)`.

| Channel | Old label | New label | Reg | Mult | Status | Evidence |
|---|---|---|---|---|---|---|
| 0 `+12V` | `+12V` | *(unchanged)* | 0 | 12 | correct | BIOS `System 12V` 12.096 V vs Linux 12.120 V |
| 1 `+5V` | `+5V` | *(unchanged)* | 1 | 5 | correct | BIOS `System 5V` 5.050 V, exact |
| 2 `+3.3V` | `+3.3V` | *(hidden)* | 11 | 1 | **CONFIRMED wrong, known duplicate** | Reads ~3.33 V, same as channels 5/6/12 before this patch; the real 3.3 V rail is channel 11 (below) |
| 3 `CPU Soc` | `CPU Soc` | *(unchanged)* | 2 | 1 | correct | BIOS `CPU NB/SOC` 1.312 V, exact |
| 4 `CPU Vcore` | `CPU Vcore` | *(unchanged)* | 4 | 1 | correct | BIOS `CPU Core` 1.340 V, exact |
| 5 `CPU 1P8` | `CPU 1P8` | `CPU 1P8` (reg 9 → 15) | **15** | 1 | **GUESS — unverified** | BIOS shows a real "CPU 1P8" at 1.793 V that Linux never read (old reg 9 duplicated ch. 2/6/12). Reg 15 chosen only because the sibling MS-7E32 override maps reg 15 to a ~1.8 V rail there ("+1.8V") — the only hardware precedent available. Old reg 9 was already confirmed wrong with nothing better known, so nothing working is lost if this guess is wrong. |
| 6 `CPU VDDP` | `CPU VDDP` | *(hidden)* | 10 | 1 | **CONFIRMED wrong, known duplicate** | Same ~3.33 V group as channel 2 |
| 7 `DRAM` | `DRAM` | **`CPU VDDIO`** | 3 | 2 | **CONFIRMED rename only** | BIOS `CPU VDDIO` 1.368 V = Linux value, exact. Register/multiplier unchanged. |
| 8 `Chipset` | `Chipset` | **`CHIPSET Core`** (reg 5 → 14) | **14** | 1 | **GUESS — unverified, and renamed** | Old reg 5 read 0.324 V; BIOS `CHIPSET Core` is 1.047 V, so the old mapping is confirmed wrong. Reg 14 chosen only because it is the other register the generic table never reads (the MS-7E32 override uses it for a different rail, "CMOS Battery" — **not** a precedent for the *value*, only evidence the register exists and is unused generically). This is the weaker of the two guesses. |
| 9 `CPU SA` | `CPU SA` | *(unchanged)* | 6 | 1 | unverified | No BIOS equivalent found; not proven wrong, left alone |
| 10 `Voltage #2` | `Voltage #2` | *(unchanged)* | 7 | 1 | unverified | No BIOS equivalent found; not proven wrong, left alone |
| 11 `AVCC3` | `AVCC3` | **`System 3.3V`** | 8 | 1 | **CONFIRMED rename only** | BIOS `System 3.3V` 3.288 V = Linux value, exact. Register/multiplier unchanged. |
| 12 `AVSB` | `AVSB` | *(hidden)* | 12 | 1 | **CONFIRMED wrong, known duplicate** | Same ~3.33 V group as channel 2 |
| 13 `VBat` | `VBat` | *(unchanged, still wrong)* | 13 | 1 | **confirmed wrong, not remapped** | BIOS explicitly has no CMOS battery voltage reading at all; Linux's 2.046 V is not it. No missing-rail candidate matches this value, and no free register is left (14 and 15 are spent on the two guesses above), so it is left as-is for Stream C's `naming.py` to mark `wrong` in the app. |

**Missing entirely, not mapped:** `VDD MISC` (BIOS 1.097 V). Registers 14
and 15 are the only two the generic table skips, and both are already spent
on the CPU 1P8 / CHIPSET Core guesses above. No register is known for VDD
MISC, so nothing was added for it — guessing a third register with no
remaining unused slot to justify it would be pure speculation.

**Why channels 2, 6 and 12 are hidden, not remapped:** before this patch,
four channels (`+3.3V` reg 11, `CPU 1P8` reg 9, `CPU VDDP` reg 10, `AVSB`
reg 12) all read the same ~3.33 V. That is `exp-0009`'s "one register read
four times" finding. Channel 5 (`CPU 1P8`) is repurposed above to test the
reg-15 guess; the other three keep reading their original, still-duplicate,
still-unidentified registers, so they are hidden with `hidden_voltage_mask`
rather than shown three times over under confident-looking names — the same
pattern `nct6687_ms7e32` uses for its own bad channel (`BIT(7)`). They are
not lost: `nct6687_is_visible()` skips the hide when the module is loaded
with `manual=1`, so `in2`, `in6` and `in12` are still readable in that mode
if anyone ever wants to look at the raw register again.

## What is confirmed vs. guessed — summary

| Confirmed from BIOS (safe) | GUESS (verify after rebuild) |
|---|---|
| Fan channel 9 exists at register `0x144` and the BIOS shows a plausible RPM range for it | Fan9 actually tracks the case fans (needs a physical check, not just a register read) |
| `DRAM` → `CPU VDDIO` (same reg/mult) | `CPU 1P8` now reads register 15 |
| `AVCC3` → `System 3.3V` (same reg/mult) | `Chipset` → `CHIPSET Core` now reads register 14 |
| Channels 2, 6, 12 are mutually duplicate and worth hiding | — |

## How to verify after the rebuild

Run `scripts/patch-nct6687.sh` as root. It prints a before/after table by
itself, but Gova should specifically check:

1. **`fan9` / "EZ Conn Fan" exists and reads roughly 960–1600 RPM** at idle,
   matching the BIOS's 963–1612 RPM range. Then, ideally, unplug or briefly
   touch a case fan and confirm the reading changes — this is the only way
   to confirm the *tachometer* is wired to the *case fans* and not to
   something else that happens to occupy the same register.
2. **The channel labelled `CPU 1P8`** (`grep . /sys/class/hwmon/hwmon*/in*_label`
   or `sensors`, find the file, not by number) should read close to **1.793 V**.
   If it reads 0 V, a saturated/clamped value, or anything else clearly not
   ~1.8 V, the register-15 guess is wrong — revert that one override line
   (put `.reg = 9` back) and treat CPU 1P8 as still unmapped.
3. **The channel labelled `CHIPSET Core`** should read close to **1.047 V**.
   Same test: if it doesn't, revert that line (put `.reg = 5` back and the
   label back to `"Chipset"`) and treat CHIPSET Core as still unmapped. This
   guess has less evidence behind it than CPU 1P8's, so a miss here would
   not be surprising.
4. **`CPU VDDIO` and `System 3.3V`** should be unchanged in value from what
   `DRAM` and `AVCC3` read before the patch (1.368 V and 3.288 V) — these
   are renames only, so a value change here would mean something else broke.
5. **`in2`, `in6`, `in12`** (the hidden duplicates) should simply be absent
   from `sensors` output and from `/sys/class/hwmon/hwmon*/in{2,6,12}_input`
   (or present only when the module is loaded with `manual=1`).
6. Confirm nothing PWM-related changed: `pwm1`..`pwm8` and `pwm*_enable`
   should read exactly as before the patch — the script never writes to a
   `pwm*` file, and neither change touches `nct6687_setup_pwm()` or any
   write path, but it costs nothing to check.

## How to revert

```sh
sudo ./scripts/uninstall-nct6687d.sh   # removes the DKMS package, unloads
                                        # the module, deletes /usr/src/nct6687d-1
sudo ./scripts/install-nct6687d.sh     # re-clones pristine upstream nct6687d
                                        # and rebuilds/reloads it
```

`uninstall-nct6687d.sh` deletes `/usr/src/nct6687d-1` outright, so the patch
cannot linger; `install-nct6687d.sh` re-clones from upstream, which does not
carry this patch. `scripts/patch-nct6687.sh` also keeps a timestamped backup
of the pre-patch `nct6687.c` (see its own output for the path) in case a
narrower revert — restoring just the file without a full DKMS
remove/re-clone — is ever wanted instead.
