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
was not loaded for a picture; `HANDOFF-gui-stream.md` section 4.

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
