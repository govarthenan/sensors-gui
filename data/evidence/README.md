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

### `nvml-binding-2026-09-23/`

| File | Contents |
|---|---|
| `pynvml-extracts.txt` | The clock event reason bits and the PCIe link and maximum clock calls, from the installed `nvidia-ml-py`, with its version and SHA-256. |

Supports: `CLOCK_EVENT_REASONS` in `src/sensors_gui/collectors/nvidia.py`,
`lab/exp-0016-nvml-new-channels/`.

### `rtx4090-suprim-layout-2026-09-23/`

Published sources on the card's size, fan count, outputs, board and power
connector: MSI's own specification pages, TechPowerUp, WCCFTech,
TheFPSReview, and one parts retailer. Web research only; each file gives its
URL, the date and the tool in its first lines, and quotes the text. Its own
`README.md` lists every fact, every disagreement between sources, and what
was not found. Also `photo-02-card-with-grid.png`: photograph 02 cropped to
the card, with a grid, used to read where the connector and the plate sit.

Supports: `docs/diagram-positions.md`, the wireframe of the card.

### `ryzen-9900x-package-layout-2026-09-23/`

Published sources on the physical layout of the AM5 package and the Zen 5
CCD/IOD dies, for the processor diagram: package outline size, where the IOD
and CCDs sit on the substrate, CCD and IOD die sizes, the core layout inside a
CCD, and whether the k10temp `Tccd1`/`Tccd2` index or the `Tctl` reading ties
to a physical location. Web research only (TechPowerUp, Guru3D, WCCFTech,
Wikipedia, the Linux kernel's k10temp documentation and driver source); each
file gives its URL, the date and the tool in its first lines, and quotes the
text. Its own `README.md` lists every question, its answer, the exact quote,
and what was not established (which physical cores are disabled on the
9900X; whether Tccd1/Tccd2 maps to a physical CCD position; which side of
the package the pin-1 mark faces).

Supports: the future card diagram work in `docs/diagram-positions.md` (not
yet written into that file — this folder is the source material for it).

### `nct6687-driver-source/`

Extracts from the out-of-tree driver, pinned to the commit that is installed, so
that later work does not depend on `/usr/src` still holding this version.

| File | Contents |
|---|---|
| `COMMIT.txt` | The exact commit installed. |
| `nct6687-c-extracts.txt` | The fan channel constants, the board table, the generic voltage table, the one board-specific override, this board's DMI entry, and the `pwm_enable` modes. |
| `dkms.conf` | The DKMS build description. |

Supports: `lab/exp-0007-nct6687-verification/`, `lab/exp-0009-bios-ground-truth/`.

### `cpu-memory-sources-2026-09-23/`

The primary texts behind the PROCESSOR and MEMORY tooltip sentences: kernel
documentation and driver source at tag v7.0, the installed psutil 7.2.2's
own docstrings and Linux implementation, and a same-day read-only probe of
this machine's CPU and DIMM sysfs state.

| File | Contents |
|---|---|
| `k10temp.rst` | What Tctl and Tccd are, whole file. |
| `k10temp-c-extracts.txt` | `drivers/hwmon/k10temp.c`: the `tctl_offset_table`, the temp label table, and the family/model switch that decides Tctl offset and CCD support. |
| `spd5118.rst` | The DIMM temperature sensor and its RW limit attributes, whole file. |
| `proc-meminfo-loadavg-stat.txt` | `Documentation/filesystems/proc.rst`: the `/proc/meminfo` field table, the `/proc/loadavg` format, and the `/proc/stat` cpu time fields. |
| `cpufreq.rst-extract.txt` | `Documentation/admin-guide/pm/cpufreq.rst`: the `scaling_cur_freq`, `cpuinfo_min_freq`, `cpuinfo_max_freq`, `scaling_min_freq`, `scaling_max_freq` sysfs attributes. |
| `amd-pstate.rst-extract.txt` | `Documentation/admin-guide/pm/amd-pstate.rst`: the CPPC performance levels, the per-policy frequency/perf sysfs attributes, and `amd_pstate_epp` (this machine's driver). |
| `powercap.rst-extract.txt` | `Documentation/power/powercap/powercap.rst`: the RAPL `energy_uj` interface, package and core zones. |
| `psutil-7.2.2-extracts.txt` | The installed psutil's docstrings and Linux implementation for `cpu_percent`, `cpu_freq`, `virtual_memory`, `swap_memory` and `getloadavg`. |
| `probe-cpu-memory-sysfs.txt` | A read-only probe of this machine: `/proc/meminfo`, `/proc/loadavg`, cpu0's cpufreq attributes, `amd_pstate/status`, and the k10temp/spd5118 hwmon readings. |
| `FINDINGS.md` | The answers this folder settles, each quoted from the file above it, plus a table citing `src/sensors_gui/collectors/system.py` by line for every CPU/memory channel. |

Supports: the PROCESSOR and MEMORY tooltips (does not itself write tooltip
text).

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
