# STATUS

Last update: 2026-09-16 (session 1)

## Phase

**Phase 0 — Exploration.** Find every sensor. Write down what the machine has,
what Linux exposes, and what is missing. No application code yet, only probes.

Planned phases:

| Phase | Name | Goal |
|---|---|---|
| 0 | Exploration | Complete sensor catalogue for this machine. |
| 1 | Collection layer | A Python library that reads all sources at a set rate. |
| 2 | Coverage repair | Get the missing sources (Super-I/O fans, RAPL, SMART). |
| 3 | TUI | The Textual monitor screen. |
| 4 | History and alarms | Store samples, show graphs, give warnings. |
| 5 | Polish | Autostart, tray icon, settings, packaging. |

## Ambition level

Gova said on 2026-09-16: *"I'm willing to go to considerable ends to make this
project happen."*

So the project aims at **complete coverage**, not at what is easy. The list
below holds the hard targets. None of them is out of scope because of effort.

| Target | Why it is hard | Value |
|---|---|---|
| Motherboard fans, VRM temperature and voltage rails | needs the out-of-tree `nct6687d` DKMS driver | the largest gap; 8 fans and 10 voltages |
| Per-core and SoC power, and the real VID | needs `ryzen_smu` or `zenpower3`, which read the AMD SMU mailbox | the true CPU power picture on Zen 5 |
| RTX 4090 hotspot temperature | NVML does not give it; it needs an I2C read of the board controller | the temperature that limits a 4090 |
| SSD wear, TBW and throttle state | needs NVMe admin commands as root | drive health |
| Monitor data through DDC/CI | needs `ddcutil` and i2c group access | model, brightness, input |
| Fan control (write, not read) | needs PWM write access and a safety design | a custom fan curve |
| RGB state (MSI MYSTIC LIGHT, Logitech) | HID protocol work | completeness |
| History storage and alarms | design work, not hardware | trends and warnings |

Fan control is a **write** operation. It gets its own ADR and its own safety
rules before any code is written. Reading comes first.

## Done

- Git repository started. Project structure made. `CLAUDE.md` written.
- Hardware inventory recorded → `docs/hardware-inventory.md`.
- `exp-0001` hwmon sweep done → 7 devices, 15 channels, all readable as user.
- Sensor catalogue started → `docs/sensor-sources.md`.
- ADR 0001 (keep records) and ADR 0002 (hwmon keys) accepted.
- `exp-0002` NVIDIA access done → NVML is 30 times faster and gives more
  fields. ADR 0003 accepted. Two traps recorded: the v1 memory structure and
  the `TLIMIT` fields.
- Gova answered Q1, Q2, Q5 and Q6. ADR 0004 (Textual) and ADR 0005 (helper
  service) accepted.
- `scripts/root-probe.sh` written. It collects every root-only fact in one
  run. Gova must run it with `sudo`.
- `docs/architecture.md` written: the collector contract, the core objects,
  the unit table and the rate table.
- **Phase 1 started.** `sensors_gui.model` and `sensors_gui.collectors.hwmon`
  are written and tested. 36 tests pass. The collector reads all 14 channels
  on this machine.
- `exp-0004` read cost done → NVMe and SPD5118 reads cost 1.5–2 ms each and
  take 99.8 % of a pass. ADR 0006 accepted and built: a per-device read
  interval with a cache. A pass went from 10.015 ms to 0.199 ms.

## Next actions

1. **Gova runs the root probe.** One command, from the project root:

   ```bash
   ! sudo ./scripts/root-probe.sh
   ```

   It writes to `data/probes/root-probe-<timestamp>/`. It reads only, except
   that `sensors-detect --auto` can add lines to `/etc/modules`; the script
   backs that file up and writes a diff.

2. **Gova installs the two safe packages** (approved, Q6):

   ```bash
   ! sudo apt install -y smartmontools nvme-cli ddcutil
   ```

3. `exp-0003` — read the root probe output. Identify the Super-I/O chip. Then
   plan the `nct6687d` DKMS install (approved, Q1).

4. `exp-0004` — load test. Put a load on the CPU and on both GPUs, then record
   how each channel moves. This confirms the scale factors and finds the
   channels that never change.

5. Phase 1, next parts of the collection layer:
   - `collectors/nvidia.py` — NVML, with the two rules of ADR 0003.
   - `collectors/power_supply.py` — the Logitech G305 battery.
   - `collectors/system.py` — CPU use and frequency, memory, disk and network
     counters, through `psutil` and `/proc`.
   - `registry.py` and `sampler.py` — hold every spec, and run the passes.
   - Friendly names: `spd5118@...0-0051` must show as "DIMM 1", and the
     `r8169` PHY must sit in the `network` group, not in `other`.
   - Value formatting with SI prefixes: `sclk` shows 600000000 Hz; it must show
     600 MHz.

## Open questions

| ID | Question | Blocks | Who answers |
|---|---|---|---|
| ~~Q1~~ | ~~Install `nct6687d`?~~ **ANSWERED: yes.** Also `sensors-detect`, `smartmontools`, `nvme-cli`, `ddcutil`, and anything else that Claude first shows to be safe. | — | closed 2026-09-16 |
| ~~Q2~~ | ~~Root-only sensors?~~ **ANSWERED: a privileged helper service.** See ADR 0005. | — | closed 2026-09-16 |
| ~~Q3~~ | ~~NVIDIA access method?~~ **ANSWERED**: NVML. See ADR 0003. | — | closed 2026-09-16 |
| Q4 | Mouse battery: the sysfs `capacity_level` gives text ("Full") only. Does HID++ (Solaar) give a percent, and is that worth a dependency? | phase 2 | Claude, then Gova |
| ~~Q5~~ | ~~GUI toolkit?~~ **ANSWERED: Textual (a terminal UI).** See ADR 0004. | — | closed 2026-09-16 |
| ~~Q6~~ | ~~Install `smartmontools` and `nvme-cli`?~~ **ANSWERED: yes.** `ddcutil` too. | — | closed 2026-09-16 |
| Q7 | What is on `nvme0n1p4` (359.2 GB, not mounted)? | inventory | Gova |

## Blockers

- No passwordless `sudo`. Any command that needs root must be given to Gova to
  run, with the `! <command>` prefix in the session. All such commands are
  gathered into `scripts/root-probe.sh` so that Gova runs one command, not ten.

## Notes for the next session

Read `CLAUDE.md`, then this file, then the last `JOURNAL.md` entry.
