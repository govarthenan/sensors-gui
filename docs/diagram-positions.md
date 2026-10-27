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

## The graphics card, wireframe — `src/sensors_gui/web/static/views/card-wireframe.js`

Written 2026-09-23, on Gova's answer at checkpoint 3: *"a wireframe of the
GPU ... the sensors could be shown as pulsating dots on the wireframe - where
the sensors would be ... This is purely cosmetic."* The schematic above is
kept, on a second tab.

### What the drawing is

The card as photograph 02 shows it through the side glass: the backplate face,
the output bracket at the left end, the edge that goes into the motherboard at
the top, and the edge that faces the glass at the bottom.

| Claim | Source |
|---|---|
| Outline 336 x 142 mm, drawn to scale | MSI's own specification pages, SUPRIM and SUPRIM X agree — `data/evidence/rtx4090-suprim-layout-2026-09-23/msi-suprim-air-specification.txt`, `msi-suprimx-specification.txt`; WCCFTech measured the same |
| Three fans, on the far face (not drawn: their positions are not established) | `techpowerup-introduction-specifications.txt`, `wccftech-suprimx-air-teardown.txt` |
| 4 outputs: 3 DisplayPort, 1 HDMI, on the bracket at the left end | all four sources in that folder; the bracket is seen in photographs 02 and 04. The order of the ports on the bracket is not established; they are drawn as four slots. |
| The backplate runs past the end of the circuit board, with vents at its far end | `wccftech-suprimx-air-teardown.txt`. Where the board ends is not established, so no line is drawn for it. |
| The cross-shaped plate with four screws, at about 0.46 of the length and the middle of the height | seen in photograph 02; read on the gridded crop `data/evidence/rtx4090-suprim-layout-2026-09-23/photo-02-card-with-grid.png` |
| The 12VHPWR connector on the near edge, at about 0.84 of the length | seen in photograph 02, same crop. The dual-BIOS switch ("SILENT / GAMING") is visible just before it, which agrees with TheFPSReview: "near the rear of the PCB". |

The photograph is taken at an angle, so every fraction read from it is
**approximate**, to a few per cent.

### The dots

| Dot | Where | Basis |
|---|---|---|
| Graphics chip — edge temperature, use, SM clock, P-state, NVENC, NVDEC | on the cross-shaped plate | **Inferred, and labelled so in its tip.** The chip is under the backplate and cannot be seen; the plate and its four screws are where a cooler is held down over a chip. No source in the repository states it for this card. |
| Power connector — power, energy | on the connector | **Seen**, photograph 02. NVIDIA's power figure is for the whole board, so the dot stands where the power enters it. |
| Memory, VRM, PCIe fingers, fan channel 1, fan channel 2, hotspot | in the dashed row "Position on the card not established" | No source places them. None of the four published sources gives a position for the memory chips or the VRM, and none says which fans each NVML channel drives. |

A dot pulses in the colour of the worst state among its readings. A part that
cannot be read has a hollow dot that does not pulse: nothing is measured
there. The pulse stops when the desktop asks for reduced motion.

### What would place the rest

A photograph of the card's other face (the fans) or of the bare board. Either
would place the memory and the VRM, and a photograph of the fan side would
show the three fans. Which fans each NVML channel drives would still need a
source of its own. Q18 in `state/STATUS.md`.

### CORRECTION, 2026-09-23 — the card is the SUPRIM LIQUID X

The first version of the wireframe drew the **air-cooled** SUPRIM: 336 x 142 mm
and three fans. Gova said the same day that the card is the SUPRIM LIQUID X,
and the label on the backplate (`docs/photos/06-gpu-backplate-label.jpg`)
agrees. The table above is kept as written; this one replaces it.

| Claim | Source |
|---|---|
| Outline 280 x 140 mm, to scale | MSI's specification of the Liquid X, `data/evidence/rtx4090-suprim-layout-2026-09-23/msi-suprim-liquidx-specification.txt` |
| Cross-shaped plate, and the chip under it: about 0.45 of the length (0.44 in photograph 06, 0.46 in 02) | photographs 02 and 06, gridded crops in the evidence folder. The chip is **inferred**. |
| 12VHPWR connector on the near edge: about 0.88 (0.84 in photograph 02, 0.91 in 06) | seen, photographs 02 and 06 |
| Two coolant tubes leave the near edge at about 0.35 and 0.44, and go to the radiator at the bottom of the case | seen, photographs 05, 06 and 07 |
| **One fan, on the far face**, centre at about 0.73 of the length, about 90 mm across | seen, photograph 07 (`photo-07-card-with-grid.png`), placed by the "SUPRIM" letters on the edge, which photograph 06 also shows. Drawn dashed, with no dot: no reading belongs to it alone. |
| The two fan channels stay in the unplaced row | the V510 schematic names two headers, FAN A (left) and FAN B (right), one on each GPU fan channel; which fans each drives is not established |

The fractions from photographs are approximate, to a few per cent: all three
photographs are taken at an angle, and the bracket end of the card is out of
frame in 06 and 07.

## The processor — `src/sensors_gui/web/static/views/cpu-diagram.js`

Written 2026-09-23, at checkpoint 4. The sources are in
`data/evidence/ryzen-9900x-package-layout-2026-09-23/` (called "the layout
folder" below); its `README.md` answers six questions and marks two of them
"not established".

### What the drawing is

A drawing of the package by its dies, **not to scale inside the package**: the
dies at their true size, about 11 and 8 mm across in a 40 mm square, would not
hold a dot for each core. The die areas are written on them. The drawing says
both things in its own two lines of notes.

### The claims

| Claim | Source |
|---|---|
| The package is square, 40 x 40 mm | `wikipedia-socket-am5.txt`, layout folder |
| An I/O die, "centrally located" | TechPowerUp: "a centrally located client I/O die (cIOD)", `techpowerup-granite-ridge-annotated.txt` |
| Two core dies, close together | TechPowerUp: the "Zen 5" CCDs "snuck up closer to each other"; Guru3D says the same, `guru3d-annotated-die-shots.txt` |
| **The I/O die above, the two core-die seats side by side below it** | **Observation, not text.** The research agent's description of the annotated package photograph in the TechPowerUp article, recorded under "OBSERVATION" in `techpowerup-granite-ridge-annotated.txt`. The photograph is of a one-die part (a 9600X) with the second seat empty. |
| I/O die 6 nm, 122 mm²; core die 70.6 mm² | `techpowerup-die-sizes.txt`, from AMD through HardwareLuxx |
| Two core dies; cores 0-5 on die 1, 8-13 on die 2; `cpuN` and `cpuN+12` are one core | this machine, `data/probes/2026-09-22-cpu-topology.txt` |
| `Tccd1` on die 1, `Tccd2` on die 2 | the same probe, and `docs/hardware-inventory.md` |
| Inside a die, cores in two columns either side of the shared L3 | TechPowerUp's text: "a centrally located 32 MB L3 cache", with each core's L2 "facing the shared L3 cache"; the two columns are an **observation** of the annotated die photograph, in the same file |
| 6 of 8 cores on, in each die | 12 cores on 2 dies (`docs/hardware-inventory.md`); 8 cores to a die (TechPowerUp) |
| `Tctl` in a box of its own, "Not a place" | the k10temp documentation, quoting AMD: "a non-physical temperature on an arbitrary scale", `linux-k10temp-hwmon-doc.txt` |
| The package readings on the package outline | RAPL's package domain is the whole package; see the tooltip sources in `src/sensors_gui/descriptions.py` |

### Not established, and drawn so

| Question | Why not | How the drawing shows it |
|---|---|---|
| Which seat holds die 1 | The k10temp driver takes `Tccd1` from a loop index over register slots, and its own header says the register map "is not confirmed from chip datasheets" (`linux-k10temp-driver-source.txt`). No source ties a die number to a seat. | The dies are drawn in the kernel's order; the note line says so, and the tooltip of each die says so. |
| Which 6 of the 8 core places on a die are on | Set by eFuses when the chip is binned (`xda-developers-disabled-cores.txt`); no map is published | The 6 cores are drawn in the kernel's order, 3 either side of the L3; the tooltip of each core says so. |
| How the package turns in the socket | No text source names the corner mark | Not claimed. |
| Where on a die its temperature sensor is | No source | The die's dot is at its corner, and the tooltip says the place is not established. |

## The memory — `src/sensors_gui/web/static/views/memory-diagram.js`

Written 2026-09-23, at checkpoint 4.

| Claim | Source |
|---|---|
| Four slots, in the order DIMMA1, DIMMA2, DIMMB1, DIMMB2 from the processor socket outward, to the right of the socket | the manual, "Overview of Components", page 27, `docs/reference/mobo-board-layout.png` |
| Modules in DIMMA2 and DIMMB2; A1 and B1 empty | `docs/hardware-inventory.md`, from `dmidecode -t memory` |
| The sensor of A2 is at i2c `0-0051`, of B2 at `0-0053` | `docs/hardware-inventory.md`: DDR5 puts the SPD hub of slot *n* at `0x50 + n` |

**Not established:** where on the module its SPD hub sits. The dot marks the
module, halfway along it, and the tooltip says it does not mark the chip. The
drawing is not to scale.

The system memory readings (used, cached, available and the rest) are the
kernel's account across both modules together, so no dot carries them: no
channel says how much of it is on one module.

**2026-09-25 (checkpoint 4b), on Gova's choice.** Each fitted module carries
its temperature on a plate across its middle, in the colour of its state, and
the dot moved up the module to make room. The slots are wider and further
apart. Neither change is a new claim: the plate is on the module whose sensor
it reads, and the drawing is still not to scale.

## The case and its air — `src/sensors_gui/web/static/views/airflow-diagram.js`

Written 2026-10-27, at checkpoint 5a. A schematic of the case from the side,
not to scale.

| Claim | Source |
|---|---|
| 3 fans at the front, air in; 1 at the rear, air out; 3 at the top on the CPU cooler's radiator, air out through the top; 2 on the graphics card's radiator at the bottom, air down through the drive bay; 1 on the card's underside, air down; the pump on the processor | Gova's trace with a string, the CORRECTION table of `docs/physical-build.md` (a test holds the drawing's copy equal to it) |
| The rear is on the left and the front on the right | Photograph 04, `docs/photos/04-full-interior.jpg`: the rear fan and the card's output bracket are on the left of the frame, the 3 front fans on the right |
| The card's radiator sits on the shroud at the bottom | Photographs 02 and 04 |
| The power supply is under the shroud, at the rear | **Inferred**, not seen: photograph 04 shows the shroud and a vented plate at its rear end, not the power supply itself |
| The CPU cooler's tubes run to the top radiator | Photograph 05, and `docs/physical-build.md` |
| One dot for the card's two NVML fan channels, between the card's fan and its radiator | Both channels drive the card's three fans (`lab/exp-0017-gpu-fan-channels/README.md`); which channel drives which fans is not established (Q14), so the dot sits between the two groups and on neither |

**Not established, so not placed:** which fans each board header drives
(Q20). The four live headers, `CPU_FAN1`, `PUMP_SYS1`, `SYS_FAN1` and `JAF_1`,
are in the dashed box under the case. That includes `PUMP_SYS1`: the header's
name does not say what is plugged into it, and `lab/exp-0020-case-cooler-identity`
found that the pump may be on `CPU_FAN1`. When Q20 is settled, `HEADERS` in the
drawing names the group of each header and its dot moves onto the drawing.

The places of the fans, the radiators and the parts inside the case are
approximate: the drawing shows the order and the direction of the air, not
sizes.
