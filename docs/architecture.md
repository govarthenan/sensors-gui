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

| Collector | Default rate |
|---|---|
| hwmon | 2 Hz |
| nvidia (NVML) | 2 Hz |
| psutil / procfs | 2 Hz |
| helper (RAPL) | 1 Hz — the power value is a delta and needs a time base |
| helper (SMART) | 1 per 60 s — the values change slowly and the read is costly |
| peripherals (mouse battery) | 1 per 60 s |
