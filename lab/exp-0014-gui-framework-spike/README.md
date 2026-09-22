# exp-0014 — The GUI framework spike

Date: 2026-09-22 (session 8). Feeds ADR 0012 and checkpoint 1 of
`docs/gui-goal.md`.

## Question

Which framework should the desktop GUI be built on, and what does it cost this
machine to run it?

`docs/gui-goal.md` section 3 sets five needs and asks for a spike before the
application is built: a throw-away window showing one live value from the
**real** sampler, with the idle cost measured.

Three sub-questions:

1. Can a candidate stack hold **10 Hz** with about 200 values and not stutter?
2. What does it cost, in CPU and in memory?
3. Does the window **change what it measures**? A browser composites through
   the graphics card that this application displays.

## Method

Two stacks were built as real windows, driven by the real
`Registry` + `Sampler` + all five collectors. No mock, no replayed data.

| File | What it is |
|---|---|
| `spike_web.py` + `spike_web.html` | FastAPI on `127.0.0.1`, one frame per sample over a WebSocket, shown by `google-chrome --app=` in its own profile |
| `spike_qt.py` | The same window in PySide6, sampler on a `QThread` |
| `spike_headless.py` | The collection layer with no window: the cost floor |
| `pass-profile.py` | Times each collector separately over 600 passes |
| `measure.py` | Runs each scenario, lets it settle 12 s, then counts CPU time for 30 s |
| `gpu-cost.py` | Watches the card's power, clock and temperature under each front end |

Both windows draw the same three things: a large number, an arc gauge and a
line over the last 120 samples. With `--all` they also show every channel, so
the 10 Hz test is done against the real channel count and not against one
value.

`measure.py` finds a process by its **command line**, not by its parent,
because Chrome moves its renderers away from the process that started them.
Cost is reported in **cores**: CPU seconds used for each second of wall time.
This machine has 24 threads, so 1.0 core is 4.2 % of it.

```bash
uv run python lab/exp-0014-gui-framework-spike/pass-profile.py --hz 10 --seconds 60
uv run python lab/exp-0014-gui-framework-spike/measure.py --seconds 30 --qt-libs <dir>
uv run python lab/exp-0014-gui-framework-spike/gpu-cost.py --seconds 40 --qt-libs <dir>
```

### PySide6 is not in the project

It was added with `uv add --dev pyside6` for this measurement and removed
afterwards, because the option was not chosen and the wheels are about 250 MB.

It also **did not start**: PySide6 needs `libxcb-cursor0`, which this machine
does not have (`apt-cache policy libxcb-cursor0` → `Installed: (none)`), and
the Qt platform plugin `xcb` refused to load. Rather than install a system
package with root for a measurement, the package was fetched and unpacked
into a temporary directory as an ordinary user, and the spike was run with
`LD_LIBRARY_PATH` pointed at it. **Nothing on the machine was changed.**

```bash
apt-get download libxcb-cursor0          # no root
dpkg-deb -x libxcb-cursor0_*.deb .       # no root
uv add --dev pyside6
LD_LIBRARY_PATH=<dir>/usr/lib/x86_64-linux-gnu uv run python lab/exp-0014-gui-framework-spike/spike_qt.py --hz 10 --all
```

## Result

### 1. Both stacks hold 10 Hz. Neither stutters.

Both reported a measured rate of **10.00 Hz** with all 175 channels on screen.
The web window spent **0.29 ms** of browser time on each frame, so it used
0.3 % of each 100 ms period to repaint 175 values, a gauge and a chart.

### 2. Cost

| What is running | CPU, cores | Resident memory |
|---|---|---|
| Collection layer alone, 1 Hz | 0.0117 | 86 MiB |
| Collection layer alone, 10 Hz | 0.0377 | 86 MiB |
| Web window, 1 channel, 1 Hz | 0.0180 | 108 MiB + 1202 MiB |
| Web window, 1 channel, 10 Hz | 0.0663 | 109 MiB + 1221 MiB |
| Web window, 175 channels, 1 Hz | 0.0297 | 108 MiB + 1265 MiB |
| Web window, 175 channels, 10 Hz | **0.1207** | 109 MiB + 1257 MiB |
| Qt window, 1 channel, 1 Hz | 0.0120 | 172 MiB |
| Qt window, 1 channel, 10 Hz | 0.0467 | 173 MiB |
| Qt window, 175 channels, 1 Hz | 0.0147 | 174 MiB |
| Qt window, 175 channels, 10 Hz | **0.0617** | 175 MiB |

Raw output: `results/overhead-2026-09-22.json`.

**Qt costs about half of what the web window costs**, and a tenth of the
memory. The gap at the worst setting is 0.059 cores, which is **0.25 % of this
machine**. ADR 0012 records why the capability difference outweighed it.

The second column of the web rows is the Python process and then Chrome. The
Chrome figure is the sum over ten processes and counts shared memory more than
once, so it is an upper bound.

### 3. The window did not move the card it measures

| Front end | Power, mean | Power, max | SM clock | Temperature |
|---|---|---|---|---|
| Nothing open | 44.41 W | 81.9 W | 724.7 MHz | 36.3 °C |
| Web window, 175 channels, 10 Hz | 40.28 W | 41.0 W | 328.2 MHz | 36.0 °C |
| Qt window, 175 channels, 10 Hz | 41.75 W | 78.0 W | 388.6 MHz | 36.1 °C |

Raw output: `results/gpu-cost-2026-09-22.json`.

**This test failed to separate the two, and it must be read that way.** With
nothing of ours running, the card read the *highest* power of the three,
because the rest of the desktop was working at the time. The differences are
inside the noise of ordinary desktop use. What can be said is that neither
window pushed the card above what the desktop already does, and that the worry
about browser compositing is not supported by this measurement. A clean
version of this test needs an idle desktop, which was not available.

### 4. The finding that changes the design: the pass has a long tail

The terminal application's status bar has been reporting about **2 ms** per
pass for six sessions. That is the **last** pass, and it is close to the
median. Over 600 passes at 10 Hz the whole distribution is:

```
mean 5.748 ms   p50 2.157 ms   p95 26.448 ms   max 56.839 ms
```

Timing each collector separately says where it goes:

| Collector | mean | p50 | p95 | p99 | max | passes over 20 ms |
|---|---|---|---|---|---|---|
| **nvidia** | 3.202 | 0.102 | 21.158 | 47.553 | **68.523** | 31 of 600 |
| hwmon | 1.069 | 0.595 | 3.032 | 12.423 | 18.566 | 0 |
| system | 1.155 | 1.137 | 1.352 | 1.625 | 1.754 | 0 |
| privileged | 0.244 | 0.245 | 0.293 | 0.311 | 0.405 | 0 |
| power_supply | 0.003 | 0.003 | 0.004 | 0.006 | 0.023 | 0 |

Raw output: `results/pass-profile-2026-09-22.json`.

The NVIDIA collector owns the tail. This is the two PCIe calls of `exp-0006`,
about 20 ms each, which run only when their own read interval expires
(ADR 0006). On the pass where both expire, the pass is longer than a whole
10 Hz period.

Three consequences:

1. **The front end must call `sample()` on a worker thread**, never on the
   event loop, or one pass in twenty arrives late. Both spikes already do
   this; ADR 0012 writes it down.
2. **`docs/architecture.md` sets a 50 ms budget for one pass, and the longest
   measured pass exceeds it** (56.8 ms). The budget is not being kept.
3. **A status bar that prints the last pass hides the tail.** The GUI reports
   the median and the maximum, not one number.

### 5. Two defects in the spike, both found by looking at the window

Neither would have been found by a test.

1. **The gauge arc was cut off.** The path was a half circle of radius 110
   inside a box only 90 tall, so its top was outside the picture, and the
   fraction used a path length of 345 that was **guessed**. The window showed
   two disconnected pieces. The box now fits the arc, and the length is read
   with `getTotalLength()`. Same lesson as register 14 in `exp-0010`: a guess
   that is not labelled a guess costs something.
2. **The chart axis needed a floor.** Tctl moves by a quarter of a degree at
   idle, which filled the whole box — exactly the defect
   `HANDOFF.md` records in the terminal sparklines. The axis now keeps a
   minimum span of one unit, or a tenth of the value.

## Files

| File | What |
|---|---|
| `spike_web.py`, `spike_web.html` | the chosen stack, a throw-away window |
| `spike_qt.py` | the measured alternative, kept as evidence |
| `spike_headless.py` | the cost floor |
| `pass-profile.py` | per-collector timing |
| `measure.py` | the CPU and memory harness |
| `gpu-cost.py` | the card under each front end |
| `results/overhead-2026-09-22.json` | the cost table |
| `results/pass-profile-2026-09-22.json` | the per-collector table |
| `results/gpu-cost-2026-09-22.json` | the card table |

Screenshots of both windows are with the checkpoint record,
`lab/exp-0015-gui-checkpoints/results/`.
