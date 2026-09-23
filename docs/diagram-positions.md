# Diagram positions

`docs/gui-goal.md` section 4.3 asks for a diagram of each part with every
sensor placed where it sits, and says: *"a sensor whose physical position is
not established goes in a clearly labelled 'position not established' area,
not on a guessed spot. Record every position claim with its source in a
document under `docs/`."* This is that document.

Each row is one claim a diagram makes. A claim with no source is not drawn.

## The graphics card — `src/sensors_gui/web/static/views/card-diagram.js`

Written 2026-09-23, at checkpoint 3.

### What kind of drawing it is

**A schematic by function, not a picture of the board.** No photograph or
drawing of the bare card is in this repository: `docs/physical-build.md` says
the card's fans are "on the card itself, not visible", and photographs 02 to
04 show the card installed in the case, not its board. So the drawing puts each reading on the
**part** it belongs to, and does not claim where that part sits on the board.
The drawing says this in its own second line, so a reader does not take the
layout for a photograph.

### Which part each reading belongs to

| Reading | Drawn on | Source |
|---|---|---|
| `GPU edge` temperature | the graphics chip | NVIDIA: `temperature.gpu` is the "Core GPU temperature" — `data/evidence/nvidia-field-descriptions-2026-09-23/nvidia-smi-help-query-gpu.txt` |
| GPU use | the graphics chip | NVIDIA: kernels "executing on the GPU" — same file |
| SM clock | the graphics chip | NVIDIA: "Streaming Multiprocessor clock" — same file |
| Performance state | the graphics chip | NVIDIA: "the current performance state for the GPU" — same file |
| NVENC, NVDEC use | the graphics chip, under "video engines" | NVIDIA: the "Encoder Engine" and "Decoder Engine" — same file. **Inference, labelled:** that the two engines are on the chip and not elsewhere on the board is not stated in the file; they are drawn inside the chip region because NVIDIA reports them as engines of the GPU. |
| VRAM used, VRAM bus use, VRAM clock | the memory | NVIDIA: memory "allocated by active contexts", "global (device) memory was being read or written", "memory clock" — same file |
| Memory type GDDR6X, size 24 GiB | the memory, title | `lab/exp-0002-nvidia-access/README.md` (GDDR6X), `docs/hardware-inventory.md` (24564 MiB) |
| Chip name AD102 | the graphics chip, title | `docs/hardware-inventory.md` |
| GPU power, GPU energy | the power input | NVIDIA: "power draw for the entire board" — same file. It is a whole-board figure, so it is drawn where power enters the board, not on the chip. |
| 12VHPWR, 600 W cable | the power input, title | `docs/physical-build.md`, seen in photo 05 |
| Limit 480 W | the power input | `data/probes/2026-09-23-nvidia-smi-q.txt` |
| PCIe transmit, receive | the PCIe edge connector | `lab/exp-0006-nvml-read-cost/README.md`; link x16, PCIe 4.0 at most, from `data/probes/2026-09-23-nvidia-smi-q.txt` |
| Display outputs, both monitors | the outputs | `docs/hardware-inventory.md` (`card1`, DP-1 to DP-3, HDMI-A-1; monitors on HDMI-A-1 and DP-1) |
| Memory temperature, not readable | the memory | the reading is named for the memory — `lab/exp-0013-rtx4090-board-sensors/README.md`, ADR 0011 |
| VRM temperature, not readable | the voltage regulators | the reading is named for the VRM — same sources |

### What is in the "position not established" area

| Reading | Why it is not placed | Source |
|---|---|---|
| GPU fan 1 and fan 2, RPM and duty | NVML reports 2 fans and numbers them 0 and 1. Nothing in this repository says which physical fan is which, or how many physical fans the shroud holds. | `lab/exp-0013-rtx4090-board-sensors/README.md`, `docs/physical-build.md`. Question Q14 in `state/STATUS.md`. |
| GPU hotspot, not readable | "Hotspot" names no part. Where on the chip the card measures it is not in any source here. | `lab/exp-0013-rtx4090-board-sensors/README.md` |

### What would make the drawing physical

A photograph of the card with the shroud and the backplate in view, or MSI's
own drawing of the SUPRIM, saved under `docs/photos/` or `docs/reference/`.
With it the regions could move to where the parts sit, and the fans could
leave the unplaced area. Without it, they stay where they are.
