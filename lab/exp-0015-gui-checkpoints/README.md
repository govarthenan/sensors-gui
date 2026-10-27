# exp-0015 — The GUI checkpoints

Date opened: 2026-09-22 (session 8). Runs to the end of the GUI stream.

## Question

At each of the seven checkpoints of `docs/gui-goal.md` section 5: what did the
application look like when Gova reviewed it, and what did Gova say?

This folder is the record, not an experiment with one answer. It holds one
screenshot of each screen at each checkpoint, so that a later session can see
what was accepted and what was changed. Gova's words go in `JOURNAL.md`,
verbatim, as the protocol requires.

## Method

At every checkpoint, before Gova is called:

1. Start the application with the one command in `state/STATUS.md`.
2. Open it, maximised at 2560 x 1440, and look at it. Fix what is found first.
3. Save one screenshot of each screen into `results/`, named
   `<date>-checkpoint-<n>-<screen>.png`.
4. Send `notify-send` with the checkpoint name.

The screen is 2560 x 1440. A window is maximised with `wmctrl` and
photographed with `gnome-screenshot -w`, which captures the window alone.

## Result

### Checkpoint 1 — framework ADR and spike, 2026-09-22

| File | What it shows |
|---|---|
| `2026-09-22-checkpoint-1-spike-one-value.png` | the chosen stack: `Tctl` live at 10.00 Hz, a gauge, a line over the last 120 samples, and the cost |
| `2026-09-22-checkpoint-1-spike-all-channels.png` | the same window streaming all **175** channels at 10.00 Hz, with 0.29 ms of paint per frame |
| `2026-09-22-checkpoint-1-qt-alternative.png` | the measured alternative, PySide6, so the comparison in ADR 0012 can be seen and not only read |

**Gova accepted the stack.** The words are in `JOURNAL.md`, verbatim. The
decision is ADR 0012; the numbers are `exp-0014`.

### Component review — the widget set, 2026-09-22

Gova's words at checkpoint 1 were: *"The thermal dial on top and the line
chart look sub par."* A widget that is about to be used 175 times is worth a
review of its own, which `docs/gui-goal.md` section 5 allows inside a
checkpoint.

| File | What it shows |
|---|---|
| `2026-09-22-checkpoint-1-widget-review.png` | the rebuilt set, live: meters, dials, stat tiles, line charts with the crosshair open, and the meaning of each colour |
| `2026-09-22-checkpoint-1b-overhead.json` | what the real application costs, at 1 Hz and at 10 Hz |

Two things were wrong with the old dial, and only one was about appearance.

1. **It was the wrong form.** The `dataviz` skill puts "a single ratio against
   a limit" on a meter. The meter is now the default; a dial is kept for at
   most one hero value in a view.
2. **It was dishonest.** It drew `Tctl` against 0 to 100 °C, and `k10temp`
   publishes no maximum and no threshold for `Tctl`. 66 of 175 channels carry
   a real scale; 5 carry a threshold. The widget set now draws no bar without
   one.

Four more defects were found by opening the page, and none by a test: the
dial's scale labels were drawn under the arc, the minimum was hidden on three
of six dials, the threshold band was as heavy as the fill so a cool DIMM
looked warm, and the scale ends read `480.00` instead of `480`.

### What the application costs

Measured with `measure-overhead.py`, which runs the shipped command, not a
spike. Cost is in cores: CPU seconds for each second of wall time, out of 24
threads.

| Rate | Python | Chrome | Total | Of the machine |
|---|---|---|---|---|
| 1 Hz | 0.0120 | 0.0233 | **0.0353** | 0.15 % |
| 10 Hz | 0.0393 | 0.1400 | **0.1793** | 0.75 % |

The review page is the heaviest thing the application will draw for its size:
it redraws six dials, six meters, six sparklines and four charts on every
frame. A real view draws less.

**Gova's answers, 2026-09-22**: *"Go with the meter. And yes, much better
now."* So the meter is the form for a value against a limit, the line chart is
accepted as it is, and the dial was removed from the widget set. This
screenshot keeps the record of what it looked like.

### Checkpoint 2 — the shell and the summary view, 2026-09-22

| File | What it shows |
|---|---|
| `2026-09-22-checkpoint-2-summary-2560.png` | the summary, maximised at 2560 x 1440 |
| `2026-09-22-checkpoint-2-summary-1280.png` | the same at half the width, which the brief requires not to break |
| `2026-09-22-checkpoint-2-summary-1000-tabs.png` | narrower still: the navigation becomes a row of tabs |
| `2026-09-22-checkpoint-2-view-not-built-yet.png` | a view that is not built yet, saying which checkpoint builds it |
| `2026-09-22-checkpoint-2-overhead.json` | what the summary costs, at 1 Hz and at 10 Hz |

What is in it: the hottest part of the machine with every temperature beside
it, the power that can be measured with a note on what cannot, the four loads
that publish a real scale, two charts, memory, storage health, every fan with
the reason five headers read zero, the channels that come through the root
helper, and what each colour means.

The status bar carries what section 4.5 asks for: the channel count, the
hidden count, the rate, the median and the maximum pass, the paint time, the
time of the last sample, whether the helper answers, and that the application
is read only.

**Three defects were found by opening it, and none by a test.** The line chart
had a fixed width and ran under the card beside it; the card titles wrapped
because the note beside them would not give way; and the view left a third of
the screen empty, which a second chart now uses.

### What the summary costs

| Rate | Python | Chrome | Total | Of the machine |
|---|---|---|---|---|
| 1 Hz | 0.0107 | 0.0200 | **0.0307** | 0.13 % |
| 10 Hz | 0.0403 | 0.1317 | **0.1720** | 0.72 % |

It was **0.2147 cores** at 10 Hz before one change: the widgets now write text
only when the text is different. At 10 Hz with 175 channels that call happens
about 1750 times a second, and most values do not change between two passes.
Three lines, and a fifth of the cost went away.

### Checkpoint 3 — the graphics card, 2026-09-23

| File | What it shows |
|---|---|
| `2026-09-23-checkpoint-3-gpu-2560.png` | the whole graphics card view, maximised at 2560 x 1440, full page |
| `2026-09-23-checkpoint-3-gpu-tooltip-fan.png` | the tooltip panel open on `GPU fan 2`, with its five parts and its sources |
| `2026-09-23-checkpoint-3-gpu-1280.png` | the same view at half the width |
| `2026-09-23-checkpoint-3-overhead.json` | what the view costs, at 1 Hz and at 10 Hz |

What is in it: the card diagram (`docs/diagram-positions.md`), all 21 card
channels in eight cards, the three temperatures that cannot be read, the two
values NVML gives and the collector does not read, and a tooltip on every
value with the five parts of `docs/gui-goal.md` section 4.2.

The card was idle for every screenshot, so both fans read 0 RPM. The machine
was not loaded for a picture; `HANDOFF.md` section 5.4 (at the time `HANDOFF-gui-stream.md` section 4).

**Six defects were found by opening it, and none by a test.**

1. The fan chart's axis ran from −1 to 1 RPM while both fans stood still: a
   speed below zero. An axis now stops at the low end of the spec's scale
   (`floorAt` in `widgets.js`, with a test).
2. The VRAM chart had two ticks both labelled `1.3 GiB`: a scaled tick kept
   one decimal whatever the step. A tick now takes the decimals its step needs.
3. The SM clock's end label was cut to `570.0 MH`; the right margin was sized
   for `34.0 °C`.
4. A line of text ran out of the dashed box of the diagram.
5. The meter printed the ends of its scale raw. No meter on the summary had a
   large unit, so nobody saw it; `VRAM used` would have read `25757220864`.
   Found by reading the code before it was drawn.
6. After a change, Chrome kept serving the old `widgets.js` from its cache,
   and a reload showed the old page. The static files are now sent with
   `Cache-Control: no-cache`, so the browser revalidates them (with a test).

### What the graphics card view costs

| Rate | Python | Chrome | Total | Of the machine |
|---|---|---|---|---|
| 1 Hz | 0.0127 | 0.0323 | **0.0450** | 0.19 % |
| 10 Hz | 0.0423 | 0.1017 | **0.1440** | 0.60 % |

Lower than the summary at 10 Hz (0.1720), although this view draws more:
seven line charts against two. One 30-second window each, on an idle desktop;
the difference is inside what ordinary desktop use moves, so it is not a
finding.

### Checkpoint 3b — Gova's answer applied, 2026-09-23

| File | What it shows |
|---|---|
| `2026-09-23-checkpoint-3b-above-ceiling-test-frame.png` | the view with three readings pushed past their ceiling **inside the page only** (power 528 W, fan 1 duty 104 %, SM clock 3300 MHz): the meter crosses its ceiling mark, the chart turns only the part above the ceiling, the diagram marks the value. The server and the hardware never saw these values. |
| `2026-09-23-checkpoint-3b-alerts.png` | the Alerts screen, with real alerts: the CPU thread frequencies past their kernel limits |
| `2026-09-23-checkpoint-3b-wireframe.png` | the wireframe with the chip dot open |
| `2026-09-23-checkpoint-3b-overhead.json` | the cost with the pulsing wireframe on screen |

**How the test frame was made.** In the browser, `JSON.parse` was wrapped so
that three values in each incoming frame were replaced before the page saw
them. Heating the card to reach 480 W for a screenshot was not an option
(`HANDOFF.md` section 5.4; at the time `HANDOFF-gui-stream.md` section 4), and the alert log, which runs on the
server, correctly logged none of them.

**Two defects found by opening it**: the whole line turned the "above
ceiling" colour, not only the part above the ceiling, and the ceiling's word
sat on top of the end label. An old cached `index.html` also met a new status
bar, and every frame raised an error; the page routes are now revalidated.

### What the view costs with the pulsing wireframe

| Rate | Python | Chrome | Total | Of the machine |
|---|---|---|---|---|
| 1 Hz | 0.0103 | 0.0773 | **0.0876** | 0.37 % |
| 10 Hz | 0.0367 | 0.1503 | **0.1870** | 0.78 % |

Against checkpoint 3 the pulse adds about **0.045 cores**, at either rate:
the animation runs whether or not a frame arrives. It runs only while the
wireframe tab of the graphics card view is on screen. A first 1 Hz run counted
five Python processes because a test server of mine was still stopping; it
was run again with nothing else up, and the second run is the one recorded.

### Checkpoint 3c — the SUPRIM LIQUID X, and a cheaper pulse, 2026-09-23

| File | What it shows |
|---|---|
| `2026-09-23-checkpoint-3c-wireframe-liquid-x.png` | the wireframe redrawn for the SUPRIM LIQUID X: 280 x 140 mm, the tubes, the fan on the far face |
| `2026-09-23-checkpoint-3c-overhead.json` | the pulse moved to compositor-only HTML, 2 s, smooth |
| `2026-09-23-checkpoint-3c-steps-overhead.json` | the same pulse in 12 steps over 3 s: **the version kept** |

| Pulse | 1 Hz Chrome | 1 Hz total | 10 Hz Chrome | 10 Hz total |
|---|---|---|---|---|
| none (checkpoint 3) | 0.0323 | 0.0450 | 0.1017 | 0.1440 |
| SVG, smooth, 2 s (3b) | 0.0773 | 0.0876 | 0.1503 | 0.1870 |
| HTML, smooth, 2 s (3c) | 0.0703 | 0.0840 | 0.1180 | 0.1620 |
| **HTML, 12 steps, 3 s (3c-steps)** | **0.0373** | **0.0503** | **0.1100** | **0.1517** |

**Finding.** Moving the animation to the compositor saved little. The cost was
the frame rate: any smooth animation makes Chrome produce about 60 frames a
second. Twelve steps over three seconds is 4 changes a second, and the pulse
now costs about 0.005 cores at 1 Hz and 0.008 at 10 Hz. One 30-second window
each, so these are rough; the order of the saving is not.

### Checkpoint 3e — the checkpoint 3 standard on the summary, 2026-09-23 (session 10)

`docs/gui-goal.md` 5: the feedback on checkpoint 3 applies to every view
before the next group is built. The summary had no tooltips.

| File | What it shows |
|---|---|
| `2026-09-23-checkpoint-3e-summary-tooltip.png` | the summary at 2560 x 1440, the panel open on `Tctl` |

Checked in the page, not only in the code: of the 47 value elements in the
summary (lines, meters, tiles, chart titles, the hero), **46 carry the panel**.
The 47th is "Measured together", which is no channel: it is the sum of two,
and a short native note says so. The line "Hottest sensor on the machine"
opens the panel of whichever sensor it names at that moment.

**Three defects found by opening it**, none by a test:

1. The place of each temperature ("SN770, sensor 1") was in a native `title`.
   The panel replaces the title, and these channels have no description yet,
   so the place would have gone from the screen. It is now written beside the
   name.
2. The colour legend gave no meaning for "above ceiling" and "below floor".
   The two states were added in checkpoint 3b and the legend was not.
3. The fan note said "three of the nine case fans". The case has 7 fans and
   the machine 10 (`docs/physical-build.md`, correction of 2026-09-23).

Overhead not measured again: the change adds four event listeners to each
value and no work on a frame.

### Checkpoint 4 — the processor and the memory, 2026-09-23 (session 10)

| File | What it shows |
|---|---|
| `2026-09-23-checkpoint-4-cpu-2560.png` | the processor view, maximised |
| `2026-09-23-checkpoint-4-cpu-column-tooltip.png` | the panel of one frequency column, reached with the keyboard |
| `2026-09-23-checkpoint-4-cpu-1280.png` | the processor view at half width |
| `2026-09-23-checkpoint-4-memory-2560.png` | the memory view, with the panel of DIMM A2 |
| `2026-09-23-checkpoint-4-memory-1280.png` | the memory view at half width |
| `2026-09-23-checkpoint-4-cpu-overhead.json`, `…-memory-overhead.json` | the cost of each view |

Checked in the page: every value element of both views opens the panel (18
in each), the arrow keys move the panel from column to column, and the card
wireframe still opens its dot panel after the dots moved into
`views/dots.js`.

**Seven defects found by opening the views**, none by a test:

1. The three temperature tiles ran out of their card: a tile's own minimum
   width, 170 px, was kept inside a row of three.
2. The unit of each column display ("W", "%", "GHz") was drawn on top of its
   highest tick.
3. The power axis had ticks at 0.8, 1.5 and 2.2 W: a following top cut into
   quarters. The ticks are now whole round steps; `barTicks` has a test.
4. At 2560 px a fifth grid column stayed empty, because every wide card
   spanned two. The column displays span three now.
5. **At 1280 px the page scrolled sideways** and the right column was cut:
   a card that spans three cells in a grid of two makes the browser add a
   third. A container query now gives it the whole row below 1240 px of view.
6. The memory drawing was scaled up so far that one line of text ran over
   another.
7. The panel said "not described yet" after the descriptions were written:
   the server loads them at start, and the test server was the old one.
   Nothing to fix in the code; the trap is in the handoff.

**One screen text was withdrawn for want of a source.** The load card said
"tasks running or waiting". The copy of `proc.rst` says only "Load average of
last 1, 5 & 15 minutes", so the card now says that.

**Cost** (30 s each, on Gova's desktop in use):

| View | Rate | Python | Chrome | Total | Of the machine |
|---|---|---|---|---|---|
| Processor | 1 Hz | 0.0113 | 0.0630 | **0.0743 cores** | 0.31 % |
| Processor | 10 Hz | 0.0417 | 0.1573 | **0.1990 cores** | 0.83 % |
| Memory | 1 Hz | 0.0117 | 0.0203 | **0.0320 cores** | 0.13 % |
| Memory | 10 Hz | 0.0417 | 0.0503 | **0.0920 cores** | 0.38 % |

The processor view is the most costly view so far. Against the memory view
it has 16 pulsing dots, where the card has 8, and three column displays that
redraw on every frame. Which of the two costs more is not measured.

### Checkpoint 4b — the memory view rebuilt, and fixed rate steps, 2026-09-25 (session 11)

**Gova's words, verbatim**, on checkpoint 4:

> had a look. The memory view is subpar imo. Can't pinpoint what to improve
> though.

The view was opened at 2560 x 1440 beside the processor view
(`2026-09-25-checkpoint-4b-memory-before-2560.png`) and five defects were
named: two thirds of the screen empty; the kernel's account a list of eight
numbers, with nothing to show how the 60 GiB divides; the swap card six rows
of zero; a large drawing with no value on it; and no large figures. Gova chose
three changes from four: **the composition bar with large figures**, **the
values on the drawing** and **memory pressure**. He did not choose to fold the
swap card into one line, so it stays.

**What changed**

- One bar for the memory the kernel can use, divided into **in use**, **what
  the kernel can take back** (available less free, made in the page) and
  **free**, with four large figures above it. The three parts add up to the
  total because psutil 7.2.2 gives used as total less available. The middle
  part is no channel; its tooltip text is in `descriptions.py` (`DERIVED`) and
  says it is made from two channels and is an estimate.
- Each module on the drawing carries its temperature, in its state colour.
- **8 new channels** from `/proc`, readable without root: memory pressure,
  `some` and `full` over 10, 60 and 300 s, with the kernel's two decimals, and
  the rates of page faults and major page faults. The pressure file is
  writable by every user (a write sets a trigger); the collector only reads it.
- The drawing is one row high, not two, and the temperature and pressure cards
  are two cells wide: the grid of five cells is full at 2560 px.
- **Rate steps** (Gova: "Fixed steps. 10hz, 5 hz, 2 hz, 1 hz, 0.5 hz, 0.25 hz,
  0.2 hz, 0.1 hz"): each click moves one step. Checked in the page: 2 → 0.1 Hz
  and 0.1 → 10 Hz stop at the ends with the button disabled, and at 0.1 Hz a
  frame arrived every 10 s for 27 s (the session 10 freeze does not return).

**Defects found by opening the view**, none by a test: the drawing's two-row
span left an empty space under it; the "Memory use" meter repeated the bar's
first part; the pressure cells showed whole percents, so 0.40 % would read
0 % (a spec now carries `decimals` when its unit's number is wrong for it);
and the tooltip of the derived part said "made in this page" twice.

Screenshots: `2026-09-25-checkpoint-4b-memory-2560.png`,
`2026-09-25-checkpoint-4b-memory-1280.png` and `-1280-lower.png`. At 1280
every card takes the whole row and the page does not scroll sideways.

**Cost** (30 s each, `2026-09-25-checkpoint-4b-memory-overhead.json`; the
machine was close to idle, load 1.05 over 1 min):

| View | Rate | Python | Chrome | Total | Before (checkpoint 4) |
|---|---|---|---|---|---|
| Memory | 1 Hz | 0.0123 | 0.0303 | **0.0426 cores** | 0.0320 |
| Memory | 10 Hz | 0.0413 | 0.0627 | **0.1040 cores** | 0.0920 |

The rise is 0.011 cores at 1 Hz and 0.012 at 10 Hz, for 8 more channels, two
more charts and the bar. The script counted 4 Python processes where it
counted 2 before (the `uv` wrapper is one); the Python cores barely moved.

### Checkpoint 5a — the airflow drawing and the first cooling view, 2026-10-27 (session 13)

Gova chose to stop at the airflow drawing before the rest of checkpoint 5.
Built: `views/airflow-diagram.js` (the case from the side, every fan, the
air, one dot for the card's two fan channels, the four live board headers in
a dashed "not established (Q20)" box, values on the drawing) and the first
`views/cooling.js` (the drawing, the board headers with two charts and the
five empty headers, the card's fans with duty meters and a chart).

**Defects found by opening the view**, none by a test:

- In two grid cells the drawing rendered at about 0.6 of its size, so its
  12 px words were about 7 px. It now spans three cells; at 1280 it takes the
  whole row.
- Four tiles in one narrow card cut the values to "2281 RPI". The tiles are
  now two to a row.
- The label "3 front fans · in" sat on the top radiator. It is now outside
  the case, between the arrows.
- The end labels of the board charts were cut ("CPU_FAN1 2051 R"). The line
  names are now short (`CPU`, `pump`, `SYS1`, `JAF_1`), and the chart titles
  give the header names.

The hover panel of the card's fan dot was checked: four readings and the
basis text. At the time the card's fans read 1201 and 1517 RPM: the card was
under load.

Screenshots: `2026-10-27-checkpoint-5a-cooling-2560.png`, `-1280.png` and
`-hover-card-fans.png`.

**Cost** (30 s each, `2026-10-27-checkpoint-5a-overhead.json`):

| View | Rate | Python | Chrome | Total |
|---|---|---|---|---|
| Cooling | 1 Hz | 0.0093 | 0.0427 | **0.0520 cores** |
| Cooling | 10 Hz | 0.0363 | 0.0557 | **0.0920 cores** |

Below the processor view (0.199 cores at 10 Hz). The machine was not idle:
the graphics card's fans were turning.
