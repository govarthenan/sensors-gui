# STATUS

Last update: 2026-09-21 (session 3)

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
- **Session 2.** Gova ran `scripts/root-probe.sh` and installed
  `smartmontools`, `nvme-cli` and `ddcutil`.
- `exp-0003` root probe done. RAPL, SMART, DMI and `ddcutil` all work. The
  Super-I/O question is **not** answered: Secure Boot puts the kernel in
  integrity lockdown, which blocks `/dev/port`, so `sensors-detect` is blind
  on this machine. A DKMS module still loads, because a MOK is enrolled.
- `exp-0005` started, from Gova's idea: a census of every component, then a
  coverage matrix. Step 1 done: 111 components, 18 with a known source.
- **Session 3.** Corrected the GPU and monitor error. Gova gave the fan count.
- `collectors/nvidia.py` built: 17 channels through NVML, with the two rules
  of ADR 0003. `exp-0006` found that two PCIe calls cost 20.6 ms each and
  took 92 % of a 48.4 ms pass. ADR 0006 amended: the interval is now per
  channel, and the cache moved to one shared place. The pass fell to
  0.0227 ms.
- `SensorSpec.format` gained SI and binary prefixes. `1125 B` now reads
  `1.1 GiB`, and `210000000 Hz` reads `210.0 MHz`.
- 89 tests pass.
- `exp-0004` read cost done → NVMe and SPD5118 reads cost 1.5–2 ms each and
  take 99.8 % of a pass. ADR 0006 accepted and built: a per-device read
  interval with a cache. A pass went from 10.015 ms to 0.199 ms.

## Next actions

1. **Install the `nct6687d` DKMS driver.** This is the largest gap: 8 fans, the
   VRM temperature and 10 voltage rails. Secure Boot does not block it, because
   DKMS signs each module with the enrolled MOK, which is how the NVIDIA module
   loads. This also answers which Super-I/O chip is fitted, which no user-space
   tool can do on this machine.

2. `exp-0005` step 2 and 3 — work down the target list in
   `lab/exp-0005-component-census/README.md`, in order:
   Super-I/O, then the Ryzen SMU (`ryzen_smu` or `zenpower3`), then the RTX 4090
   board over I2C, then the DDR5 PMICs, then the unknown clients `0x4f` and
   USB `1-11`, then the Wi-Fi chip, then MYSTIC LIGHT.

3. **Gova looks inside the case** (about 5 minutes). Three questions, in
   `lab/exp-0005-component-census/README.md`, section "Step 5".

4. Phase 1, next parts of the collection layer:
   - `collectors/power_supply.py` — the Logitech G305 battery.
   - `collectors/system.py` — CPU use and frequency, memory, disk and network
     counters.
   - `collectors/nvme_smart.py` and the RAPL reader, through the helper of
     ADR 0005.
   - `registry.py` and `sampler.py`.
   - Friendly names: `spd5118@...0-0051` must show as "DIMM A2", and the
     `r8169` PHY must sit in the `network` group, not in `other`.

5. `exp-0006` — load test, once the fan and power sensors work.

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
| ~~Q8~~ | ~~How many fans, and is the cooler air or liquid?~~ **ANSWERED: 9 fans** (2 on the GPU, 3 intake, 3 top, 1 rear) and a **liquid AIO**. Which fans reach the board is still open; photographs are expected. | — | part-closed 2026-09-21 |
| ~~Q9~~ | ~~Monitors on the integrated graphics?~~ **ANSWERED: no, they are on the RTX 4090.** Claude guessed the DRM card order instead of reading it. `card1` is the 4090. | — | closed 2026-09-21 |
| Q10 | 28 unsafe shutdowns in 144 power cycles on the SSD. Does Gova know the cause? | health | Gova |

## Expected fan count (Gova, 2026-09-21)

This is the number that makes a `0 RPM` reading readable.

| Location | Count | Reaches the motherboard? |
|---|---|---|
| Graphics card | 2 | no — the card controls its own fans, and NVML reports them |
| Case intake | 3 | to be confirmed |
| Case top | 3 | to be confirmed; they may be the AIO radiator fans |
| Case rear | 1 | to be confirmed |
| AIO pump | 1 | to be confirmed; it should be on a `PUMP_FAN` header |
| **Total** | **9 fans plus a pump** | |

The MSI PRO X870-P WIFI has 8 four-pin headers: `CPU_FAN1`, `PUMP_FAN1` and
`SYS_FAN1` to `SYS_FAN6`. So all 7 case fans and the pump can reach the board.

## Blockers

- No passwordless `sudo`. Any command that needs root must be given to Gova to
  run, with the `! <command>` prefix in the session. All such commands are
  gathered into `scripts/root-probe.sh` so that Gova runs one command, not ten.

## Notes for the next session

Read `CLAUDE.md`, then this file, then the last `JOURNAL.md` entry.
