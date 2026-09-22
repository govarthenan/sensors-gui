# Phase 3 plan — the collection layer and the Textual screen

Written 2026-09-22, at the start of parallel work. This file fixes the
contracts, so that four streams can run at once without treading on each other.

## Streams and file ownership

**Nothing outside your list may be edited.** If you need a change elsewhere,
write it in your report instead of making it.

| Stream | Owns | Must not touch |
|---|---|---|
| A — driver patch | `driver/`, `scripts/patch-nct6687.sh` | everything else |
| B — registry and sampler | `src/sensors_gui/registry.py`, `src/sensors_gui/sampler.py`, `tests/test_registry.py`, `tests/test_sampler.py` | `collectors/`, `model.py`, `app/` |
| C — naming and new collectors | `src/sensors_gui/naming.py`, `src/sensors_gui/collectors/power_supply.py`, `src/sensors_gui/collectors/system.py`, `src/sensors_gui/collectors/__init__.py`, `tests/test_naming.py`, `tests/test_power_supply.py`, `tests/test_system.py` | `model.py`, `registry.py`, `sampler.py`, `app/` |
| D — the screen | `src/sensors_gui/app/`, `src/sensors_gui/__main__.py` | everything else |

`pyproject.toml`, `model.py`, `collectors/base.py`, `collectors/cache.py`,
`collectors/hwmon.py` and `collectors/nvidia.py` are **frozen** for this round.
`textual`, `psutil` and `nvidia-ml-py` are already added.

## Fixed contracts

### What already exists and does not change

```python
from sensors_gui.model import SensorId, SensorSpec, Reading, Sample, Unit, Group
from sensors_gui.collectors import Collector          # Protocol
from sensors_gui.collectors.cache import ChannelCache
from sensors_gui.collectors.hwmon import HwmonCollector
from sensors_gui.collectors.nvidia import NvidiaCollector
```

- `SensorId(source, device, channel)`, `.key`, `.from_key()`
- `SensorSpec(id, label, group, unit, low, high, warn, critical, min_interval, origin)`,
  `.format(value)`
- `Reading(id, value, error, read_at)`, `.ok()`, `.failed()`, `.is_ok`, `.age(now)`
- `Sample(timestamp, readings)`, `.value_of(id)`, `.by_id()`
- A collector has `name`, `discover() -> list[SensorSpec]`,
  `read() -> list[Reading]`, `close()`. **`read()` must never raise.**

### Stream B builds

```python
class Registry:
    """Holds every SensorSpec from every collector, and finds them again."""
    def __init__(self, collectors: list[Collector]) -> None: ...
    def discover(self) -> None: ...
    def specs(self) -> list[SensorSpec]: ...
    def spec(self, sensor_id: SensorId) -> SensorSpec | None: ...
    def by_group(self) -> dict[Group, list[SensorSpec]]: ...
    def close(self) -> None: ...

class Sampler:
    """Reads every collector on a schedule and keeps a short history."""
    def __init__(self, registry: Registry, history: int = 120) -> None: ...
    def sample(self) -> Sample: ...                       # one synchronous pass
    async def run(self, hz: float = 2.0) -> None: ...     # loop until cancelled
    def latest(self) -> Sample | None: ...
    def history(self, sensor_id: SensorId) -> list[float | None]: ...
    def subscribe(self, callback: Callable[[Sample], None]) -> None: ...
```

Rules for B:
- **Throw away the first sample after discovery.** `exp-0007` finding 4: the
  `nct6687` driver gives zeros until it has updated once.
- A collector that raises during `discover` is logged and skipped, not fatal.
- `sample()` must stay inside the 50 ms budget of `docs/architecture.md`.
- History is a ring buffer per sensor, holding the value only, aligned with the
  sample index, so a graph can be drawn from it.

### Stream C builds

```python
def friendly(spec: SensorSpec) -> SensorSpec:
    """Return the spec with a name and group a person would recognise."""

def verdict(spec: SensorSpec) -> str:
    """'correct' | 'rename' | 'wrong' | 'unverified' | 'unknown'."""
```

`naming.py` loads
`data/evidence/bios-ground-truth-2026-09-22/linux-vs-bios.json` and applies it:

| Case | What to do |
|---|---|
| verdict `rename` | use the BIOS name: `DRAM` → `CPU VDDIO`, `AVCC3` → `System 3.3V` |
| verdict `wrong` | keep the channel, mark it, and let the screen hide it by default |
| `spd5118` at `0-0051` | `DIMM A2` |
| `spd5118` at `0-0053` | `DIMM B2` |
| `r8169_0_b00:00` | group `NETWORK`, label `Ethernet PHY` |
| `nct6687` | group `BOARD` |
| `System Fan #2`–`#6` | label `SYS_FAN2 (empty)` … and mark as an empty header |

Also for C:
- `power_supply.py` reads `/sys/class/power_supply/*` for the Logitech G305.
  `capacity_level` is **text** (`Full`), not a percent. Map it to a number and
  keep the text. Interval 60 s. The node number changes across reboots
  (`hidpp_battery_2` → `_3` → `_0`), so key by `model_name`.
- `system.py` uses `psutil` and `/proc` for CPU use per core, frequency, memory,
  swap, disk I/O and network counters. Intervals: 0 for the cheap ones.

### Stream D builds

The Textual screen (ADR 0004). It may assume B and C exist and import them, but
must not edit their files. If they are not finished, build against
`HwmonCollector` and `NvidiaCollector` directly and leave a clear seam.

## Rules for every stream

1. **Tests first.** Write the test, see it fail, then write the code.
2. **No mocks.** Use a real temporary directory tree, a fake clock that is a
   real callable, or the real hardware. `tests/conftest.py` shows the pattern.
3. `uv run ruff format . && uv run ruff check . && uv run pytest -q` must be
   clean before you report.
4. Type hints on everything. Google docstrings. Lines under 120 characters.
5. **Write nothing to hardware.** Read only. See ADR 0007.
6. Do not commit. Report what you changed, and the parent session commits.
