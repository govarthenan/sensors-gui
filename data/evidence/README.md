# Evidence

Raw material that a claim in `docs/` or `lab/` rests on. If a statement about
this machine cannot be traced to a file here, to a file in `data/probes/`, or to
a `lab/exp-*/results/` file, it is not established.

## What lives where

| Directory | Contents |
|---|---|
| `data/evidence/` | Material that is not the output of one experiment: incidents, external ground truth, third-party source. |
| `data/probes/` | Timestamped machine captures from `scripts/root-probe.sh`, `scripts/probe-privileged.sh` and `scripts/install-nct6687d.sh`. |
| `lab/exp-NNNN-*/results/` | The output of one experiment. It belongs to that experiment. |
| `docs/photos/` | Photographs of the machine and of the BIOS. |
| `docs/reference/` | Pages rendered from the motherboard manual. |

## Index

### `2026-09-22-thermal-shutdown/`

The machine shut itself down at about 98 °C because a script written by Claude
stopped the CPU radiator fans and could not start them again.

| File | Contents |
|---|---|
| `README.md` | Timeline, cause, why the safety rules failed, outcome. |
| `kernel-nct6687-messages.txt` | Every `nct6687` line from the boot that died. |
| `kernel-final-messages.txt` | The last 60 kernel messages before the power cut. |
| `observed-state.txt` | The sysfs state and temperatures read afterwards, kept because a reboot destroyed them. |

Supports: ADR 0007 amendment 2, the `JOURNAL.md` entry for 2026-09-22.

### `bios-ground-truth-2026-09-22/`

What the BIOS reports, photographed by Gova. This is the only independent
source on this machine that already knows the board, so it settles every
question about what a sensor really is.

| File | Contents |
|---|---|
| `bios-readings.json` | Every value the BIOS showed: temperatures, voltages, fans, the fan curve, memory, storage, the board and BIOS version. |
| `linux-vs-bios.json` | **The correction table.** Each `nct6687` channel against what the BIOS says it really is, with a verdict of correct, rename, wrong or unverified. The application reads this. |

Photographs: `docs/photos/bios/`.
Supports: `lab/exp-0009-bios-ground-truth/`, and the corrections in
`docs/hardware-inventory.md` and `docs/physical-build.md`.

### `nvidia-field-descriptions-2026-09-23/`

NVIDIA's own sentence for each field `nvidia-smi` can query, from the driver
installed on this machine (595.91.07). `nvidia-smi` reads through NVML, the
same library the collector calls, so the meanings are the same.

| File | Contents |
|---|---|
| `nvidia-smi-help-query-gpu.txt` | `nvidia-smi --help-query-gpu`, whole, with the command, the date and the version in its first lines. |

Supports: the card tooltips in `src/sensors_gui/descriptions.py`, and
`docs/diagram-positions.md`. The full query report of the same day is a probe:
`data/probes/2026-09-23-nvidia-smi-q.txt`.

### `nct6687-driver-source/`

Extracts from the out-of-tree driver, pinned to the commit that is installed, so
that later work does not depend on `/usr/src` still holding this version.

| File | Contents |
|---|---|
| `COMMIT.txt` | The exact commit installed. |
| `nct6687-c-extracts.txt` | The fan channel constants, the board table, the generic voltage table, the one board-specific override, this board's DMI entry, and the `pwm_enable` modes. |
| `dkms.conf` | The DKMS build description. |

Supports: `lab/exp-0007-nct6687-verification/`, `lab/exp-0009-bios-ground-truth/`.

## Rules

1. **Copy, do not link.** A path under `/usr/src` or `/tmp` is not evidence. It
   will be gone.
2. **Say where it came from.** Every file carries the command, the date and the
   source in its first lines.
3. **Keep what disproves a claim too.** `exp-0008` corrected `exp-0007`, and
   both are kept, with the correction written in each.
4. **Large files stay out of git.** `.gitignore` excludes `*.raw`, `*.bin` and
   bulk sample files. Photographs are reduced to about 1400 pixels before they
   are committed.
