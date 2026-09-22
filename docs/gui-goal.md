# Goal: a desktop GUI for sensors-gui

Written 2026-09-22 by Govarthenan. This is the brief for the next stream of
work. Paste it, or point Claude Code at it, as the first message of the
session. It is written for Claude Code and it is complete on its own.

---

## 0. Before you start

Read these files, in this order, before you write any code or any plan:

1. `CLAUDE.md` — the rules of this project. They all apply.
2. `HANDOFF.md` — the whole picture, and section 6, "Rules learned the hard way".
3. `state/STATUS.md` — the current phase.
4. `docs/sensor-sources.md` — every sensor, its path, its unit, its status.
5. `docs/hardware-inventory.md` and `docs/physical-build.md` — what the
   machine is and where each part sits inside the case.
6. `docs/architecture.md` and `src/sensors_gui/model.py` — the objects the
   collection layer already gives you.

Then run the current application and look at it. It is the baseline you
replace:

```bash
uv sync
uv run python -m sensors_gui                              # the terminal screen
uv run python scripts/preview-screen.py --rows 0 --all    # the same, to a file
```

## 1. The goal in one paragraph

Replace the terminal screen with a **desktop GUI application** that presents
every sensor this machine reads. The GUI must do more than show numbers. It
must **explain** the machine: group the sensors by the physical part they
measure, place them on a picture of the hardware, show how each value moves,
and tell the user, on every sensor, what the value means and how it differs
from its neighbours. The result will be shown to Gova's internal team as a
finished piece of work, not as a toy. It runs on this PC only.

## 2. Scope

### In scope

- A new front end. It reads from the **existing** collection layer:
  `Registry`, `Sampler`, the collectors and the `sensors-guid` helper. That
  layer is finished and tested. **Do not rewrite it.** Add to it only where the
  GUI needs a field the model does not carry yet, for example a long
  description for a tooltip or a position on a diagram.
- Every channel the terminal screen shows today, and the five it hides. The
  count is in `HANDOFF.md`; at the time of writing it is 170 shown and 5
  hidden, 194 read in total.
- Meaningful grouping, visualisation, tooltips and hardware diagrams, as
  section 4 defines them.
- Multiple screens or views. There is no limit on the design. Go to any length
  that makes the machine clearer to the user.
- The tests, the documents, the ADRs, the JOURNAL entries and the STATUS
  updates that `CLAUDE.md` requires.

### Out of scope, for now

- **Packaging, installers, portability and running on another PC.** Do not
  spend one minute on it. The application must start from a single command on
  this machine and nothing more.
- **Writing to hardware.** Not in scope now and never in scope. `CLAUDE.md`
  section 4 and ADR 0007, 0010 and 0011. This includes fan control, RGB, and
  any I2C or SMU route. A GUI button that writes is a defect, not a feature.
- **History storage and alarms.** Dropped by Gova on 2026-09-22 and not to be
  offered again. The ring buffer in `Sampler` is all the history there is. A
  live graph over that ring buffer is fine and wanted; a store on disk is not.
- **Autostart, tray icon, settings file.** Phase 5, later.
- **New sensor sources.** The catalogue is closed for this stream. If the GUI
  work shows a gap in the data, write it in `state/STATUS.md` as an open
  question and carry on.

## 3. Framework

The framework is your choice, but the choice must be made **before** the GUI
work starts and it must be recorded as an ADR in `docs/decisions/`. Electron
is acceptable. So are Qt through PySide6, Tauri, or a local web application in
a dedicated window. The ADR must compare at least three options against these
needs, and the winner must satisfy all of them:

| Need | Why |
|---|---|
| Rich, smooth graphics: vector charts, an image or SVG of the hardware with live overlays, hover tooltips | Section 4 needs all of these. A character grid does not give them, which is why ADR 0004 is being superseded. |
| Low overhead on the machine it measures | The monitor must not change what it measures. Measure the idle CPU cost of the running GUI and record it in a `lab/exp-NNNN-*` folder. Report it at the first checkpoint. |
| Updates at up to 10 Hz for about 200 values without visible stutter | The sampler already runs at 0.25 Hz to 10 Hz. |
| The Python collection layer stays in Python and runs through `uv` | It is done, tested and it talks to a root helper over a Unix socket. If the front end is not Python, it talks to a small Python process over a local socket or WebSocket on `127.0.0.1`, and that process is the only thing that imports the collectors. Nothing listens on any other address. |
| Starts on this machine, today, with one command | Scope, section 2. |

Write ADR `0012-<slug>.md`. Include a **spike**: a throw-away window that
shows one live value from the real sampler through the chosen stack, with the
measured idle cost. Do not build the full application on an unproven stack.

If the choice is a JavaScript stack, `node` and `npm` are installed through
nvm on this machine; check the versions before you decide. Keep the JavaScript
tooling inside the repository, under one folder, and keep all Python through
`uv`.

## 4. What "presented properly" means

These are the requirements the human-in-the-loop checkpoints (section 5) test
against.

### 4.1 Grouping follows the hardware, not the driver

The user must never need to know what `hwmon`, `nct6687` or NVML are. Group
by the physical part:

- **CPU** — AMD Ryzen 9 9900X. Temperatures (`Tctl`, `Tccd1`, `Tccd2`), package
  power, the 12 per-core powers and their sum, frequency per core, use per
  core, load average.
- **Graphics card** — MSI RTX 4090 SUPRIM. Temperature, power and its 480 W
  limit, the two fans (RPM and control percent each), clocks, memory,
  PCIe link, encoder and decoder, performance state, throttle reasons.
- **Integrated graphics** — the AMD iGPU. Show it, and say that both monitors
  run from the RTX 4090, not from this part.
- **Memory** — the two DDR5 DIMMs and their temperatures, system memory use.
- **Storage** — the WD_BLACK SN770: three temperatures, the 15 SMART health
  channels, I/O counters.
- **Motherboard** — MSI PRO X870-P WIFI: the 9 fans, the 10 voltages, the 7
  board temperatures, the CMOS battery.
- **Cooling** — a view that brings together every fan and pump on the machine
  with the temperature it acts on, whatever driver reads it. This crosses the
  groups above on purpose.
- **Network** — Ethernet PHY temperature, Wi-Fi signal, byte and packet
  counters per interface.
- **Peripherals** — the Logitech G305 battery.
- **System** — anything from `psutil` or `/proc` that fits nowhere above.

The existing `Group` enum in `model.py` is a starting point, not the final
answer. Change it if the hardware view needs it, and keep the tests green.

### 4.2 Every sensor has a tooltip that explains it

Hovering any value shows, at minimum:

1. **What it measures**, in one or two plain sentences.
2. **Where it is read from**: the driver or tool, and the path or call.
   Example: "`k10temp`, `/sys/class/hwmon/.../temp1_input`".
3. **How it differs from its neighbours** when a part has more than one
   reading of the same kind. This is the requirement Gova called out. The
   known cases on this machine:
   - CPU: `Tctl` is the control temperature the fan curve uses and it can carry
     an offset; `Tccd1` and `Tccd2` are the two core dies.
   - NVMe: `Composite` is the drive's own summary; `Sensor 1` and `Sensor 2`
     are two points on the drive.
   - DIMMs: the sensor at `i2c 0-0051` and at `0-0053` are the sticks in slots
     A2 and B2. Say which is which, from `docs/hardware-inventory.md`.
   - RTX 4090: the one temperature NVML gives is the **edge** sensor. Hotspot,
     memory and VRM temperatures are **not readable** on this machine and the
     tooltip must say so and say why, in one sentence, with a pointer to
     ADR 0011. Do not leave a silent gap.
   - RAPL "Core 0" against the per-core energy registers: the RAPL core domain
     is core 0 alone; the 12 register channels are one per core.
   - The two GPU fans turn at different speeds under the same load. Show both.
   - Board voltages: which rail each one is, from the BIOS ground truth in
     `data/evidence/bios-ground-truth-2026-09-22/`.
4. **The safe range** where a threshold exists in the spec, and where the
   value sits in it.
5. **The read interval and the age of the value**, because the helper samples
   SMART once a minute and RAPL once a second.

Write the descriptions once, in the Python model, next to the spec, so the
terminal app and the GUI share them. **Do not guess a description.** Every
sentence about the hardware must come from `docs/`, `lab/` or `data/`. If a
fact is not there, say "not established" in the tooltip and add the question
to `state/STATUS.md`.

### 4.3 Diagrams of the hardware with the sensors placed on them

For at least the CPU, the graphics card, the motherboard and the case
airflow, draw a diagram of the part and place each sensor on it where it
physically sits, with its live value. The material is there:

- `docs/physical-build.md` and `docs/photos/` — what is inside the case, and
  which fan is where: 3 front, 3 top, 1 rear, 2 on the radiator at the
  bottom, and the pump.
- `docs/reference/` — pages from the motherboard manual, with header positions.
- `docs/hardware-inventory.md` — slots, PCI addresses, DIMM slots.

An SVG with named regions is the expected form. A photograph with overlays is
also acceptable. The diagram must be honest: a sensor whose physical position
is not established goes in a clearly labelled "position not established" area,
not on a guessed spot. Record every position claim with its source in a
document under `docs/`.

### 4.4 Visualisation that gives a picture, not a list

- **Every value has a shape**, not only a number: a gauge or bar where a real
  scale exists, a live line over the ring buffer where the value moves, a
  state badge where the value is a state (P-state, throttle reasons, critical
  warning bits, battery level).
- **Scales are honest.** A bar runs from a real minimum to a real maximum from
  the spec, never from zero to "whatever it is now". A line chart's axis must
  not make a quarter-degree wobble look violent; the terminal app had exactly
  that defect. Follow the `dataviz` skill if it is available in the session.
- **Related values sit together**: power next to its limit, a fan next to the
  temperature it responds to, a clock next to its maximum, memory used next
  to total.
- **A summary view** exists that gives the state of the whole machine on one
  screen: the hottest part, total measured power (and a note that total
  system power cannot be measured because the NZXT C1200 has no telemetry
  link), memory, storage health, all fans. This is the screen a team member
  sees first.
- **Colour means something.** Use colour for state (normal, warm, hot,
  unavailable, stale), and use the same meaning everywhere. A value that
  "needs the helper" or is unreachable is shown as unavailable with its
  reason, never as zero and never hidden.
- **The window resizes.** The screen is 2560 x 1440. The layout must be
  usable at that size maximised and must not break at half that width.

### 4.5 Low overhead and honesty

- Measure the CPU cost of the running GUI at 1 Hz and at 10 Hz on this machine
  and record it in a `lab/exp-NNNN-*` folder. The number is reported at every
  checkpoint.
- The status bar or an "about" view shows the channel count, the hidden count,
  the sample rate, the time of the last sample and whether the helper is
  connected.

## 5. Human-in-the-loop checkpoints

Gova reviews the work at fixed checkpoints. This is how the stream is run:

**The protocol at a checkpoint**

1. Stop. Do not start the next stage.
2. Make sure the application starts from one command and that the command is
   written in `state/STATUS.md`.
3. Launch the application yourself and inspect it in the browser or window
   tools available in the session, maximised at 2560 x 1440. Fix what you
   find first. `CLAUDE.md`: "Run the thing and look at it."
4. Save a screenshot of each screen under `lab/exp-NNNN-gui-checkpoints/results/`
   with the date and the checkpoint number in the file name.
5. Send `notify-send` with the checkpoint name.
6. Write, in the reply, what was built, what to look at, what you are unsure
   about, and the measured overhead. Keep it short.
7. Wait for Gova's feedback. Record the feedback **verbatim** in `JOURNAL.md`
   and the resulting changes as a list under it. Then implement it, verify it
   yourself the same way, and only then move on. If the feedback changes a
   decision, update the ADR.

**The checkpoints, in order**

| # | Checkpoint | What Gova inspects |
|---|---|---|
| 1 | Framework ADR and spike | The ADR, the spike window with one live value, the measured idle cost. Gova approves the stack or sends it back. |
| 2 | Shell and summary view | The window, navigation between views, the whole-machine summary, the colour meaning, the status bar. No detail views yet. |
| 3 | One complete component: the graphics card | Every RTX 4090 channel, grouped, visualised, with tooltips and the card diagram. This is the reference for every other group; Gova's feedback here is applied to all later groups before they are built. |
| 4 | CPU and memory | The same standard as 3. Includes the 12 per-core powers and the two DIMMs. |
| 5 | Motherboard and cooling | The 9 fans, 10 voltages, 7 temperatures, CMOS battery, the airflow diagram and the cooling view that crosses groups. |
| 6 | Storage, network, peripherals, system | The remaining groups. |
| 7 | Whole application | Everything together, a full walk-through, the overhead numbers at 1 Hz and 10 Hz, a review of every tooltip against `docs/`. |

Inside a checkpoint you may also stop for a **component review** when a single
widget is new and reused many times, for example the gauge, the line chart or
the tooltip panel. Build the widget, show it with real data, and ask before
you stamp it across 170 channels. That is cheaper than 170 corrections.

## 6. Rules that apply to this stream, repeated because they matter

- **Python through `uv` only.** Never the system Python.
- **This project writes nothing to hardware.** Reading what the collectors
  give is the only contact with the machine.
- **No mocks in tests** unless Gova asks. Test the presentation layer against
  the real registry and real readings, or against a `Sample` built by hand
  from the real dataclasses, as `tests/conftest.py` shows.
- **Do not guess hardware facts.** A sentence in a tooltip or a position on a
  diagram is a hardware fact. It needs a source under `docs/`, `lab/` or
  `data/`.
- **Record everything.** ADR for the framework. One `lab/exp-NNNN-*` folder
  for the overhead measurement and one for the checkpoint screenshots.
  `JOURNAL.md` entry per session with Gova's feedback verbatim.
  `state/STATUS.md` updated before every checkpoint and at the end of every
  session.
- **Conventional Commits, attributed to Govarthenan.** Commit at every
  checkpoint at the latest. Run `uv run ruff format . && uv run ruff check .
  && uv run pytest -q` before each commit, plus the lint of the front-end
  stack if it is not Python.
- **Keep the terminal app working** until checkpoint 7 is accepted. It is the
  fallback and it shares the model. After checkpoint 7 Gova decides whether
  it stays.

## 7. Definition of done

The stream is done when Gova accepts checkpoint 7 and all of these are true:

- Every channel the collection layer reads is on screen, in the right group,
  with the right unit, the right label and a tooltip that meets section 4.2.
- Every unreachable or helper-dependent value is shown as unavailable with
  its reason.
- The four diagrams of section 4.3 exist, every placed sensor has a recorded
  source for its position, and unplaced sensors are marked as such.
- The summary view gives the state of the machine on one screen.
- The idle overhead is measured and recorded, and Gova has accepted it.
- The ADR, the experiments, the JOURNAL and STATUS are up to date, and the
  tree is committed.
- The application starts on this machine with the one command in
  `state/STATUS.md`.
