# CLAUDE.md — sensors-gui

Project instructions for Claude Code. Read this file first in every session.

## 1. What this project is

A GUI sensor monitor application for one specific PC: Gova's desktop
(`dst-gova-pc`). The goal is full coverage of every sensor on this machine and
every connected component. The application is not a general product. It is a
custom tool for this hardware.

Target qualities:
- Show every available sensor. Do not hide a source because it is difficult.
- Correct units and correct labels for this exact hardware.
- Low overhead. The monitor must not change what it measures.
- Usable as a desktop window.

## 2. Continuity framework (IMPORTANT)

Work happens over many sessions. To continue correctly:

0. **If you are picking this up cold, read `HANDOFF.md` first.** It is the one
   file that gives the whole picture: what runs, what the machine is, what is
   still unread, and the rules learned the hard way.
1. Read `state/STATUS.md` — current phase, next actions, open questions.
2. Read `JOURNAL.md` — the last two or three entries.
3. Read `docs/hardware-inventory.md` and `docs/sensor-sources.md` for facts
   about the machine.
4. Do the work.
5. Before the session ends, update `state/STATUS.md` and add a `JOURNAL.md`
   entry. Then commit.

**Never start new work before you read `state/STATUS.md`.**

## 3. Folder structure

```
CLAUDE.md              This file.
README.md              Short description for a human.
JOURNAL.md             Dated log of events, findings and decisions. Short entries.
state/STATUS.md        Live state: phase, next actions, open questions, blockers.
docs/
  hardware-inventory.md  The components of this PC.
  sensor-sources.md      Every sensor source, with path, unit and status.
  architecture.md        Design of the application.
  decisions/             Decision records, one file for each decision (ADR).
lab/                   Experiments. One folder for each experiment.
  exp-NNNN-<slug>/       README.md (question, method, result), code, results/.
data/probes/           Timestamped machine captures from scripts/.
data/evidence/         Material a claim rests on: incidents, external ground
                       truth, third-party source. See data/evidence/README.md.
src/sensors_gui/       Application code.
tests/                 Tests (pytest).
scripts/               Helper scripts for the developer.
```

## 4. Rules for the work

- **Python through uv only.** `uv run ...`, `uv add ...`, `uv sync`. Never the
  system Python.
- **Record everything.** A finding, an experiment or a decision that is not in
  `docs/`, `lab/` or `JOURNAL.md` does not exist.
- **Run the thing and look at it.** Four screen defects were found by rendering
  the application and none by the tests. Use
  `uv run python scripts/preview-screen.py --rows 0 --all`.
- **One experiment, one folder.** Each `lab/exp-NNNN-*` folder has a README.md
  with three parts: Question, Method, Result.
- **Decisions get an ADR.** Use `docs/decisions/NNNN-<slug>.md`.
- **Do not guess hardware facts.** Read the machine. Put the command and its
  output in the document. A claim with no file under `data/` or
  `lab/exp-*/results/` behind it is not established.
- **Copy evidence, never link to it.** A path under `/usr/src`, `/tmp` or
  `/proc` is not evidence; it will be gone. Every evidence file carries the
  command, the date and the source in its first lines.
- **Keep what disproves a claim.** When a later experiment corrects an earlier
  one, both stay, and the correction is written into each.
- **THIS PROJECT WRITES NOTHING TO HARDWARE.** No exceptions, no conditions.
  See ADR 0007 and `data/evidence/2026-09-22-thermal-shutdown/`. A script that
  wrote fan control values stopped the CPU radiator fans, could not start them
  again, and the machine shut itself down at 98 °C. Reading is safe. Writing is
  not. If a question can only be answered by writing, drop the question.
- **Root access:** some sensors need root (RAPL energy, SMART data, Super-I/O).
  Ask Gova before you install a kernel module or change permissions.
- **No mocks in tests** unless Gova asks for them.
- Commits use Conventional Commits. Attribute Govarthenan, never Claude.

## 5. Sensor access, short version

| Source | Path or tool | Needs root |
|---|---|---|
| CPU temperature | `/sys/class/hwmon/hwmon*/` (`k10temp`) | no |
| CPU package power | `/sys/class/powercap/intel-rapl:0/energy_uj`, through `sensors-guid` | the helper, not the screen |
| CPU frequency | `/sys/devices/system/cpu/cpu*/cpufreq/` | no |
| NVIDIA RTX 4090 | `nvidia-smi`, NVML | no |
| AMD iGPU | `/sys/class/hwmon/hwmon*/` (`amdgpu`) | no |
| NVMe temperature | `/sys/class/hwmon/hwmon*/` (`nvme`) | no |
| NVMe SMART | `nvme smart-log`, through `sensors-guid` — 15 channels | the helper, not the screen |
| DIMM temperature | `/sys/class/hwmon/hwmon*/` (`spd5118`) | no |
| Fans, VRM, voltages | `nct6687`, patched 2026-09-22 — 9 fans, 10 voltages, 7 temperatures | no |
| EZ Conn fan (case fans on `JAF_1`) | `fan9`, added by `driver/nct6687-ms7e47.patch` | no |
| CMOS battery | `in13`, 3.116 V, added by the same patch | no |
| CPU use, memory, disk, network | `psutil` and `/proc` — 96 channels | no |
| Mouse battery | `/sys/class/power_supply/` | no |
| The helper itself | `/run/sensors-gui.sock`, group `gova`, read-only. ADR 0005 and 0009. | no |

See `docs/sensor-sources.md` for the complete list.
