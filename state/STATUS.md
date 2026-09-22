# STATUS

Last update: 2026-09-22 (end of session 6)

## Phase

**Phase 2 — Coverage repair. Done for the root-only sources.** The privileged
helper of ADR 0005 runs, and the three sources that need root are on the
screen. What is left of phase 2 is the sensor target list of `exp-0005`, which
is one item shorter: the Ryzen SMU is closed by ADR 0010.

Phases 0, 1 and 3 are done. Phase 4 (history and alarms) is next.

Planned phases:

| Phase | Name | Goal |
|---|---|---|
| 0 | Exploration | Complete sensor catalogue for this machine. |
| 1 | Collection layer | A Python library that reads all sources at a set rate. |
| 2 | Coverage repair | Get the missing sources (Super-I/O fans, RAPL, SMART). **RAPL, SMART and the fans are done.** |
| 3 | TUI | The Textual monitor screen. **Working.** |
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
| ~~Per-core power~~ | ~~needs `ryzen_smu` or `zenpower3`~~ | **DONE 2026-09-22.** It needed neither. `0xc001029a` holds one energy counter for each core and reading it writes nothing. 13 channels. `exp-0012`, ADR 0010. |
| ~~SoC power and the real VID~~ | needs a **write** to the SMU mailbox | **DROPPED, ADR 0010.** ADR 0007 has no exceptions. |
| RTX 4090 hotspot temperature | NVML does not give it; it needs an I2C read of the board controller | the temperature that limits a 4090 |
| ~~SSD wear, TBW and throttle state~~ | ~~needs NVMe admin commands as root~~ | **DONE 2026-09-22**, 15 channels through the helper. `exp-0011`. |
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
- **Session 4.** A script that wrote fan control values caused a **thermal
  shutdown** at 98 °C. It is deleted, ADR 0007 is reverted, and the project now
  writes nothing to hardware. Full record in
  `data/evidence/2026-09-22-thermal-shutdown/`.
- `exp-0009`: Gova's BIOS photographs gave **ground truth**. The case fans are
  on the **`JAF_1` EZ Conn header**, which the BIOS reads and Linux does not.
  Of 14 board voltages, 4 are correct, 2 are misnamed and 8 are wrong; 3 rails
  the BIOS reads are missing from Linux. The correction table is at
  `data/evidence/bios-ground-truth-2026-09-22/linux-vs-bios.json`.
- `data/evidence/` created, with an index and rules. `CLAUDE.md` updated.
- **Phase 3 started.** `docs/phase-3-plan.md` fixes the file ownership and the
  interfaces for four parallel streams.
- **Stream D done**: the Textual screen. 60 channels render, 1.06 ms per pass,
  140 tests pass. Group panels, bars only where a real scale exists,
  temperature and fan display conventions, a status bar, and a seam for hiding
  channels the BIOS proved wrong.
- Gova offered the `run-as-root` skill, so privileged commands can be run with
  Gova approving each one at the desktop password prompt.
- **All four phase 3 streams landed.** The application runs:
  `uv run python -m sensors_gui`. **152 channels on screen, 6 hidden,
  2.22 ms per pass, 283 tests pass.** The machine now reads **158 channels**
  in total: 43 hwmon, 17 NVML, 2 battery, 96 system.
- ADR 0008 accepted: the discard of the first pass after discovery lives in the
  registry.
- **The driver patch is installed and confirmed.** The board gives **9 fans and
  10 voltages**. `EZ Conn Fan` reads 963–988 RPM, matching the BIOS exactly,
  and the **CMOS battery is healthy at 3.116 V**. See `exp-0010`.
- **Session 3.** Corrected the GPU and monitor error. Gova gave the fan count.
- **The motherboard driver is installed and working.** Gova ran
  `scripts/install-nct6687d.sh`. It built, was signed with the enrolled MOK and
  loaded first time. The chip is a **Nuvoton NCT6687D at ISA 0x0a20**.
  **29 new channels**: 8 fans, 14 voltages, 7 temperatures. The project now
  reads **60 channels** in total.
- `exp-0007` verified them. Fans and temperatures are good. **Four voltages are
  wrong**, because the driver has a board-specific voltage map for the MSI Z890
  only. Fixed a serious collector bug: this driver's `_min` and `_max` files
  hold a running minimum and maximum, not a threshold, so the application would
  have alarmed for ever on every board channel.
- Gova sent photographs. `docs/physical-build.md` written. The power supply is
  an NZXT C1200 with no telemetry. The radiator is at the bottom with 2 fans.
  The card is an MSI RTX 4090 SUPRIM.
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
- **Session 5. Phase 2 landed: the privileged helper.** `sensors-guid` runs as
  a systemd service, reads the RAPL energy counters and the NVMe SMART log, and
  publishes them on `/run/sensors-gui.sock` (`srw-rw---- root:gova`). The screen
  reads that socket and never needs root. **19 new channels, all live.**
  ADR 0009 written. 326 tests pass. See `exp-0011`.
- The RAPL `core` domain was confirmed a second time to be **core 0 only**: it
  read 2.534 W where `turbostat` read 2.55 W for CPU 0, against 22.8-28.0 W for
  all twelve cores.
- Four defects were found by running the helper, not by the tests. The worst:
  a failed socket bind made the **root** process delete the ordinary file in its
  way, because `socketserver` calls `server_close()` when `server_bind()`
  raises. Same shape as fault 1 of the thermal shutdown. Fixed, with a test.

- **Session 6. Per-core power, with no write.** `exp-0012`: the processor holds
  one energy counter for each core at MSR `0xc001029a`, and `pread()` on
  `/dev/cpu/N/msr` reads it. All twelve cores are live, the sum matched
  `turbostat` to **0.1 %** under load (103.98 W against 104.10 W), and one sweep
  of 24 threads costs **0.070 ms**. 13 new channels.
- **The route the plan named would have broken ADR 0007.** `ryzen_smu` and
  `zenpower3` **write** a command word into the SMU mailbox to get the same
  numbers. ADR 0010 writes the distinction down: a register may be read, a
  mailbox may not be written, and the three unmapped voltage rails are dropped
  for that reason.
- Two defects found by looking at the screen, neither by the tests: two rows
  both labelled `CPU Core 0 Power`, and rows ordered as text, so `Core 10` came
  between `Core 1` and `Core 2`. Both fixed; the sort now reads a number as a
  number, which also repairs `CPU0 use` to `CPU23 use`.
- The two readings of core 0 — powercap and the register — agree to
  **0.001 W**, which is a third confirmation that the powercap `core` domain is
  core 0 alone.
- The screen: **166 channels, 5 hidden, 1.95 ms per pass. 350 tests pass.**

- **Published.** The project is at <https://github.com/govarthenan/sensors-gui>,
  **private**, 32 signed commits, 223 files. A sweep for credentials and
  personal data ran first and found nothing critical. The 8 hardware
  identifiers it did find are kept on purpose, because the repository is
  private; that decision must be made again before it is ever made public.
- `HANDOFF.md` is purged from the whole history and is in `.gitignore`. It
  stays on this machine.
- Three root scripts were leaving their output owned by root, because they read
  `SUDO_USER` and the `run-as-root` skill sets `PKEXEC_UID`. Fixed in
  `patch-nct6687.sh`, `install-nct6687d.sh` and `root-probe.sh`.

## Waiting for Gova

Nothing. Gova approved three more root commands on 2026-09-22 through the
`run-as-root` skill: the read-only core-energy probe and two helper installs.

Verified on the machine at the end of session 6, not assumed:

- `sensors-guid.service` is **enabled and active**, and it answers **32 of 32
  channels** with a value.
- The socket is `srw-rw---- root:gova`, and the user `gova` reads all 32
  channels from it **with no password**.
- The installed helper and the repository copy have the same SHA-256.
- The application runs: **166 channels, 1.95 ms per pass, 5 hidden.**
- `CPU Core 0 (RAPL) Power` and `CPU Core 0 Power` read **1.624 W each**, from
  two different parts of the processor.
- The `msr` module now loads at boot, from
  `/etc/modules-load.d/sensors-gui.conf`. **This is untested across a reboot**;
  the next session should check it first.
- From the earlier reboot, still true: the patched driver loads by itself and
  is signed, `fan/pwm mask=0x1ff` (9 channels), `EZ Conn Fan` 963 RPM,
  `CMOS Battery` 3.116 V, and all eight fan headers are at `enable=2`.

## Next actions

The list was renumbered on 2026-09-22. It had two items numbered 4 and two
numbered 5, and one of them was already done.

1. **Offer the driver patch upstream.** `driver/nct6687-ms7e47.patch` applies to
   every MSI PRO X870-P WIFI, not only this one. It adds the EZ Conn fan channel
   and corrects the voltage map, both proved on hardware (`exp-0010`). The
   project is <https://github.com/Fred78290/nct6687d>.

2. **Phase 4: history and alarms.** The sampler's ring buffer lives in memory
   only, so nothing survives a restart. Every threshold is already in the specs,
   and the hardware-given ones are marked, so an alarm never has to invent a
   limit.

3. `exp-0005` steps 2 and 3 — work down the target list in
   `lab/exp-0005-component-census/README.md`. Target 2, the Ryzen SMU, is
   **closed** by ADR 0010. The next one is the RTX 4090 board over I2C, then the
   DDR5 PMICs, then the unknown client `0x4f`, then the Wi-Fi chip, then MYSTIC
   LIGHT. Read `data/evidence/` before the I2C work: an I2C write near the DDR5
   power management chips is in the same family of risk as the fan write.

4. ~~**Fix the remaining wrong voltages.**~~ **DROPPED 2026-09-22, ADR 0010.**
   `exp-0010` proved `VDD MISC`, `CPU 1P8` and `CHIPSET Core` are not in the
   board chip's voltage block. The only remaining route is the SMU or SMN, and
   both need a write. ADR 0007: if a question can only be answered by writing,
   drop the question.

5. **Gova looks inside the case** (about 5 minutes). Three questions, in
   `lab/exp-0005-component-census/README.md`, section "Step 5". It would say
   which physical fans sit on the three headers that report.

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
| Q10 | **The screen now shows this live**: on 2026-09-22 it read 31 unsafe shutdowns in 150 power cycles, about one in five. One of them was the thermal shutdown of 2026-09-22. Does Gova know what causes the rest? (This row no longer holds a copy of the number. `HANDOFF.md` said 29 and this file said 28; both were true when written, at 145 and 144 power cycles.) | health | Gova |

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
