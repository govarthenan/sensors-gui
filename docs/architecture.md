# Architecture

Status: draft, written 2026-09-16 at the start of phase 1.

## Shape

```
                    +--------------------------+
                    |  sensors-guid (root)     |   ADR 0005
                    |  RAPL, NVMe SMART        |
                    +------------+-------------+
                                 | Unix socket, JSON lines
                                 v
+----------+   +----------+   +--------------+   +---------+   +-----------+
| hwmon    |   | nvidia   |   | helper       |   | psutil  |   | procfs    |  collectors
| sysfs    |   | NVML     |   | client       |   |         |   |           |
+----+-----+   +----+-----+   +------+-------+   +----+----+   +-----+-----+
     |              |                |                |              |
     +--------------+----------------+----------------+--------------+
                                 v
                        +------------------+
                        |     Registry     |   holds every SensorSpec
                        +--------+---------+
                                 v
                        +------------------+
                        |     Sampler      |   reads at a set rate, per collector
                        +--------+---------+
                                 v
                        +------------------+
                        |     History      |   ring buffer for each sensor
                        +--------+---------+
                                 v
                        +------------------+
                        |   Textual app    |   ADR 0004
                        +------------------+
```

Since 2026-09-22 there is a second front end beside it, and it is the one
being built (ADR 0012):

```
   Registry + Sampler  --(worker thread)-->  SensorService
                                                  |
                                    catalogue once, frames at up to 10 Hz
                                                  |
                            FastAPI on 127.0.0.1  |  WebSocket
                                                  v
                          a page in a Chrome application window
```

The page is plain HTML, CSS, SVG and JavaScript, with no build step. The
server binds `127.0.0.1` only, and no route writes to hardware.

## The helper, as built on 2026-09-22

The dashed part of the diagram above is now real. `exp-0011` has the numbers.

| Part | Where | What it is |
|---|---|---|
| The service | `src/sensors_gui/helper/sensors_guid.py` | One file, standard library only, run as root by `sensors-guid.service`. Installed to `/usr/local/lib/sensors-gui/` (ADR 0009). |
| The socket | `/run/sensors-gui.sock` | `srw-rw---- root:gova`. No network socket exists. |
| The client | `src/sensors_gui/collectors/privileged.py` | An ordinary collector. It keeps the contract below like every other one. |

The protocol is newline-delimited JSON with three commands, `describe`, `read`
and `ping`. None of them takes a path: the catalogue is built on the root side,
from the machine, and a client may have all of it or none of it.

The helper samples on **its own** clock, not the client's — RAPL every second,
SMART every minute — and reports the age of each value. So the screen can ask
ten times a second and the hardware pays nothing. One request costs 0.034 to
0.080 ms. That is ADR 0006's per-channel interval, moved across the socket,
and it is why `PrivilegedCollector` sets `min_interval` to zero: a second
interval on the client side would only add staleness on top of the first.

When the socket is absent the collector still reports all 19 specs, each
reading carrying the error "needs the helper". ADR 0005 rule 3.

## Core objects

### `SensorId`

The stable key of one measurable value. ADR 0002 says the key must not use the
`hwmonN` index.

```python
SensorId(source="hwmon", device="k10temp@/sys/devices/pci0000:00/0000:00:18.3", channel="temp1")
```

Its text form is `source:device:channel`. That form goes into the settings file.

### `SensorSpec`

What a sensor **is**. Found once, at discovery. It does not change while the
application runs.

| Field | Meaning |
|---|---|
| `id` | the `SensorId` |
| `label` | a short name for the user, for example "CPU Tctl" |
| `group` | where it belongs: `cpu`, `gpu`, `memory`, `storage`, `network`, `board`, `peripheral` |
| `unit` | `Unit.CELSIUS`, `Unit.WATT`, ... |
| `low` / `high` | the sensible scale for a meter, when it is known |
| `warn` / `critical` | thresholds from the hardware, when the hardware gives them |
| `origin` | the raw path or call, for the diagnostic view |

### `Reading`

What a sensor **says**, at one moment.

| Field | Meaning |
|---|---|
| `id` | the `SensorId` |
| `value` | a float in the unit of the spec, or `None` if the read failed |
| `error` | text, when `value` is `None` |

### `Sample`

Every `Reading` from one pass, with one timestamp.

## Collector contract

```python
class Collector(Protocol):
    name: str

    def discover(self) -> list[SensorSpec]: ...
    def read(self) -> list[Reading]: ...
    def close(self) -> None: ...
```

Rules:

1. `discover` runs once at start, and again only when the user asks for a
   re-scan.
2. `read` must never raise. A failure becomes a `Reading` with `value=None` and
   an `error`, so that one dead sensor cannot stop the application.
3. A collector that cannot start at all (for example NVML with no driver)
   reports zero specs and stays quiet. It does not stop the program.
4. `read` must be quick. The budget for one full pass of all collectors is
   **50 ms**. NVML takes 0.67 ms and a hwmon pass takes about 1 ms, so the
   budget is generous, but the helper client must not block.

   **Corrected 2026-09-22 (`exp-0014`, ADR 0012). The budget is met at the
   median and broken at the tail.** Over 600 passes at 10 Hz:

   | | |
   |---|---|
   | median pass | **2.157 ms** |
   | p95 | 26.448 ms |
   | longest | **56.839 ms** — past the budget |

   All of the tail belongs to the NVIDIA collector, whose own maximum is
   **68.523 ms**: the two PCIe calls of `exp-0006` cost about 20 ms each and
   run only when their read interval expires (ADR 0006). Thirty-one passes of
   600 went past 20 ms.

   The budget is **not** raised and those two channels are **not** slowed
   down, because both would cost something real. Instead the rule for a
   caller changes: **a front end calls `sample()` on a worker thread, never on
   the thread that draws**. The terminal screen predates this and calls it on
   its own loop, which is why it has always printed the *last* pass — a number
   close to the median, that hides the tail. The web front end reports the
   median and the maximum. See `src/sensors_gui/web/service.py`.

## Units

The raw values from sysfs use fixed scale factors, given in the kernel hwmon
ABI:

| Kind | Raw unit | Factor to the display unit |
|---|---|---|
| `temp` | millidegree Celsius | 1e-3 |
| `in` | millivolt | 1e-3 |
| `curr` | milliampere | 1e-3 |
| `power` | microwatt | 1e-6 |
| `energy` | microjoule | 1e-6 |
| `fan` | RPM | 1 |
| `pwm` | 0 to 255 | 1 |
| `freq` | hertz | 1 |
| `humidity` | millipercent | 1e-3 |

Every collector converts to the display unit. Nothing after the collector deals
with a raw value.

## Rate

The default sample rate is **2 Hz**. It can be set per collector, because some
sources are slow or change slowly:

Rates are per collector. On top of that, each **channel** carries its own
minimum read interval, because one device can hold an expensive channel among
cheap ones. See ADR 0006 and its amendment.

| Collector | Default rate |
|---|---|
| hwmon | 2 Hz |
| nvidia (NVML) | 2 Hz |
| psutil / procfs | 2 Hz |
| helper (RAPL) | 1 Hz — the power value is a delta and needs a time base |
| helper (SMART) | 1 per 60 s — the values change slowly and the read is costly |
| peripherals (mouse battery) | 1 per 60 s |
