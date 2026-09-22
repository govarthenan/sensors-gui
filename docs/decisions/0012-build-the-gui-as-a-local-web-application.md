# ADR 0012 — Build the desktop GUI as a local web application in a Chrome window

- Date: 2026-09-22
- Status: accepted, waiting for Gova at checkpoint 1
- Supersedes: ADR 0004 (Textual) for the **new** front end. The terminal
  application stays until checkpoint 7 is accepted; see `docs/gui-goal.md`
  section 6.
- Evidence: `lab/exp-0014-gui-framework-spike/`

## Context

`docs/gui-goal.md` asks for a desktop application that does more than print
numbers. It must place each sensor on a diagram of the part it measures, give
every one of about 175 channels a tooltip with five parts, draw a gauge or a
live line for each value, and hold several views. It must update at up to
10 Hz, it must not change what it measures, and it must start with one command
on this machine.

A character grid cannot do that, which is why ADR 0004 is superseded here.

The goal document sets five needs. Every option below is judged against them.

| # | Need |
|---|---|
| 1 | Vector charts, an SVG of the hardware with live overlays, hover tooltips |
| 2 | Low overhead on the machine it measures |
| 3 | 10 Hz for about 200 values with no visible stutter |
| 4 | The Python collection layer stays in Python and runs through `uv` |
| 5 | Starts on this machine, today, with one command |

## The options

Four were considered. Two were built and measured; two were rejected on
properties that can be read from the machine.

### A. A local web application in a Chrome application window — **chosen**

A Python process holds the collectors, serves one page on `127.0.0.1` and
pushes one frame for each sample over a WebSocket. `google-chrome --app=URL`
opens it as a window with no tabs and no address bar. The front end is plain
HTML, CSS, SVG and JavaScript: no Node, no bundler and no build step.

### B. Qt through PySide6 — measured, not chosen

One process, one language. The window is drawn by Qt's own vector painter.

### C. Electron — rejected

It is the same renderer as option A with Node, a bundler, a second runtime and
a packaging step added. It gives no capability the Chrome application window
lacks, and it costs more of everything. `docs/gui-goal.md` also puts packaging
out of scope, which removes the one thing Electron is good at.

### D. Tauri — rejected

`cargo` and `rustc` are installed (`/usr/bin/cargo`, `/usr/bin/rustc`), so the
toolchain is here. But Tauri needs the `webkit2gtk` development packages,
which are a **root** install on this machine, and a compile step before the
application runs. Its webview is WebKitGTK, not Chrome, so the developer tools
that find defects in this project are weaker. It fails need 5 today and buys
nothing that A does not already give.

## What was measured

Full method and output: `lab/exp-0014-gui-framework-spike/README.md`.

Both A and B were built as a real window driven by the **real** sampler, with
the same three things drawn: a large number, an arc gauge and a line over the
last 120 samples. Cost is in **cores**: CPU seconds used for each second of
wall time. This machine has 24 threads, so 1.0 core is 4.2 % of it.

| What is running | CPU, cores | Resident memory |
|---|---|---|
| The collection layer alone, 1 Hz | 0.0117 | 86 MiB |
| The collection layer alone, 10 Hz | 0.0377 | 86 MiB |
| **A. Web window**, 1 channel, 1 Hz | 0.0180 | 108 MiB + 1202 MiB |
| **A. Web window**, 175 channels, 1 Hz | 0.0297 | 108 MiB + 1265 MiB |
| **A. Web window**, 175 channels, 10 Hz | **0.1207** | 109 MiB + 1257 MiB |
| **B. Qt window**, 1 channel, 1 Hz | 0.0120 | 172 MiB |
| **B. Qt window**, 175 channels, 1 Hz | 0.0147 | 174 MiB |
| **B. Qt window**, 175 channels, 10 Hz | **0.0617** | 175 MiB |

Both held 10.00 Hz exactly, with no dropped frame. The web window spent
**0.29 ms** of browser time on each frame of 175 values, so 97 % of each 100 ms
period was idle.

**Qt costs about half of what the web window costs.** That is the one need
where option B wins, and it is recorded here because it is true.

## Decision

**Build the GUI as option A: a local web application, served by a Python
process on `127.0.0.1`, shown in a dedicated Chrome application window.**

The front end is plain HTML, CSS, SVG and JavaScript with **no build step**.
Any library it uses is a file in the repository, not an `npm install`.

### Why, against the five needs

| # | Need | A, web | B, Qt |
|---|---|---|---|
| 1 | SVG diagrams, overlays, tooltips | **native** | every one is bespoke work |
| 2 | Low overhead | 0.1207 cores | **0.0617 cores** |
| 3 | 10 Hz, 200 values | 10.00 Hz, 0.29 ms a frame | 10.00 Hz |
| 4 | Python through `uv` | a socket between two processes | **one process** |
| 5 | One command, today | **works now** | needs a root install |

Three things decide it.

1. **Need 1 is the whole point of the work, and it is where the two options
   differ most.** `docs/gui-goal.md` section 4.3 asks for "an SVG with named
   regions" for four parts of the machine, and section 4.2 asks for a
   five-part tooltip on every one of 175 channels. In a browser both are what
   the platform already does. In Qt widgets both are written by hand.
2. **The cost difference does not matter at this size.** The gap is 0.059
   cores, which is **0.25 % of this machine**. Both options are far below any
   level that could move a reading, and the measurement in the next section
   shows neither one moved the card it displays. A monitor that is 0.5 % of
   the machine is not changing what it measures.
3. **Option B does not start on this machine today.** PySide6 needs
   `libxcb-cursor0`, and `apt-cache policy` says it is not installed. The Qt
   spike would not open its window until the library was supplied. Option A
   needs nothing that is not already here: Chrome 153 is installed.

A fourth reason is about how this project works. Four screen defects were
found by rendering the application and none by the tests (`HANDOFF.md`
section 6). A page in Chrome can be opened, read, hovered and photographed
with the browser tools in the session, and its console can be read. A Qt
window can only be photographed. The method that finds the defects in this
project works better on option A.

### Does the window change what it measures?

A browser composites through the graphics card, and this application displays
that card. So it was measured: the card's power, SM clock and temperature, for
40 s in each state, with everything else on the desktop left alone.

| Front end | Power, mean | Power, max | SM clock | Temperature |
|---|---|---|---|---|
| Nothing open | 44.41 W | 81.9 W | 724.7 MHz | 36.3 °C |
| Web window, 175 channels, 10 Hz | 40.28 W | 41.0 W | 328.2 MHz | 36.0 °C |
| Qt window, 175 channels, 10 Hz | 41.75 W | 78.0 W | 388.6 MHz | 36.1 °C |

**The measurement does not support the worry.** With nothing of ours open the
card read the *highest* power of the three, because the desktop was doing its
own work at the time. The difference between the two front ends is smaller
than the noise of ordinary desktop use, so the honest reading is that neither
window moved the card, and that this test cannot separate them. It is kept
because it is the test that would have disproved the decision.

## Consequences

### What is built

- A new package, `src/sensors_gui/web/`, holding the server and the static
  front end. It is the **only** new thing that imports the collectors.
- The collection layer is not rewritten. ADR 0002, 0006 and 0008 stand. The
  model gains fields the GUI needs, for example a long description and a
  position on a diagram, and nothing else.
- The terminal application keeps working until checkpoint 7 is accepted, and
  shares the model with the GUI.

### The sampler runs on a worker thread, not on the event loop

`pass-profile.py` measured each collector over 600 passes at 10 Hz:

| Collector | p50 | p95 | p99 | max | passes over 20 ms |
|---|---|---|---|---|---|
| **nvidia** | 0.102 ms | 21.158 ms | 47.553 ms | **68.523 ms** | 31 of 600 |
| hwmon | 0.595 ms | 3.032 ms | 12.423 ms | 18.566 ms | 0 |
| system | 1.137 ms | 1.352 ms | 1.625 ms | 1.754 ms | 0 |
| privileged | 0.245 ms | 0.293 ms | 0.311 ms | 0.405 ms | 0 |
| power_supply | 0.003 ms | 0.004 ms | 0.006 ms | 0.023 ms | 0 |

The median pass is 2.157 ms, but the p95 is 26.4 ms and the longest is
56.8 ms. The NVIDIA collector owns the tail: it is the two PCIe calls of
`exp-0006`, each costing about 20 ms, which run only when their own interval
expires (ADR 0006). One of those passes is longer than a whole 10 Hz period.

So `sample()` is called on a worker thread and the event loop only serialises
and sends. This also corrects a claim that has been repeated: the terminal
application's status bar prints the time of the **last** pass, which is the
median, and the tail was never on the screen. `docs/architecture.md` gives a
50 ms budget for one pass, and the longest measured pass **exceeds it**.

### The protocol

- The specification of each channel is static, so it is fetched once from
  `GET /api/catalogue`. The 10 Hz frames then carry only an array of values in
  catalogue order, which keeps a frame small.
- Control, such as the rate or a re-scan, goes over the same WebSocket or a
  small `POST`. **No route writes to hardware**, now or ever. ADR 0007.
- The server binds `127.0.0.1` only. Nothing listens on any other address.

### Cost of the choice, written down plainly

- The GUI costs about **0.12 cores at 10 Hz** with every channel on screen,
  against 0.06 for the Qt alternative. At 1 Hz it is 0.03 cores.
- Chrome's resident memory is about **1.2 GiB across ten processes**, of which
  a large part is shared. The machine has 60 GiB.
- There are two processes and a socket between them, instead of one process.
- The window uses its own Chrome profile directory, so it does not touch
  Gova's browser and carries no extension.

### If Gova rejects this at checkpoint 1

The Qt spike, `lab/exp-0014-gui-framework-spike/spike_qt.py`, is kept and
runs. To use it again: `uv add --dev pyside6`, and install `libxcb-cursor0`
with root, or extract it into a directory and set `LD_LIBRARY_PATH`, as the
experiment README records.
