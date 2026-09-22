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

Waiting for Gova. The decision is ADR 0012; the numbers are `exp-0014`.
