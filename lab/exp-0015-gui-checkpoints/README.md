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

**Two questions are open for Gova**: a meter or a dial for a headline value,
and whether the line chart is right now.
