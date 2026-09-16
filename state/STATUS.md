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
| 3 | GUI | The monitor window. |
| 4 | History and alarms | Store samples, show graphs, give warnings. |
| 5 | Polish | Autostart, tray icon, settings, packaging. |

## Done

- Git repository started. Project structure made. `CLAUDE.md` written.
- Hardware inventory recorded → `docs/hardware-inventory.md`.
- `exp-0001` hwmon sweep done → 7 devices, 15 channels, all readable as user.
- Sensor catalogue started → `docs/sensor-sources.md`.
- ADR 0001 (keep records) and ADR 0002 (hwmon keys) accepted.

## Next actions

1. **Q5 first** — Gova must choose the GUI toolkit. It changes everything after
   phase 1.
2. `exp-0002` — confirm the Super-I/O chip model on the MSI PRO X870-P WIFI.
   Read the chip ID, then decide about the `nct6687d` DKMS module (needs Q1).
3. `exp-0003` — NVIDIA: compare NVML through `nvidia-ml-py` against
   `nvidia-smi` text. Measure the read time of a full sample.
4. `exp-0004` — load test. Put a load on the CPU and on both GPUs, then record
   how each channel moves. This confirms the scale factors and finds the
   channels that never change.
5. Write the `SensorSource` model and the first collector for hwmon
   (phase 1 start).

## Open questions

| ID | Question | Blocks | Who answers |
|---|---|---|---|
| Q1 | May Claude install the out-of-tree `nct6687d` DKMS kernel module? Without it there are no fan speeds and no board voltages. | exp-0002, phase 2 | Gova |
| Q2 | How does the application read root-only sensors (RAPL energy, NVMe SMART)? Options: (a) udev rule that relaxes the file mode, (b) a small privileged helper service with a socket, (c) polkit, (d) run the whole application as root (not liked). | phase 2 | Gova + ADR |
| Q3 | NVIDIA access: the `nvidia-ml-py` binding, or parse `nvidia-smi --query-gpu`? | exp-0003 | Claude, with a measurement |
| Q4 | Mouse battery: the sysfs `capacity_level` gives text ("Full") only. Does HID++ (Solaar) give a percent, and is that worth a dependency? | phase 2 | Claude, then Gova |
| Q5 | **GUI toolkit.** Qt (PySide6), GTK4 (native to Cinnamon), a web UI in a local browser, or a terminal UI (Textual)? | phase 3 | Gova |
| Q6 | May Claude install `smartmontools` and `nvme-cli`? Both need `apt` and root. | phase 2 | Gova |
| Q7 | What is on `nvme0n1p4` (359.2 GB, not mounted)? | inventory | Gova |

## Blockers

- No passwordless `sudo`. Any command that needs root must be given to Gova to
  run, with the `! <command>` prefix in the session.

## Notes for the next session

Read `CLAUDE.md`, then this file, then the last `JOURNAL.md` entry.
