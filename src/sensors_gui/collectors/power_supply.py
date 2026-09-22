"""The power supply collector. It reads `/sys/class/power_supply`.

On this machine that is the battery of the Logitech G305 wireless mouse,
reached through its HID++ receiver. See `docs/hardware-inventory.md`,
section "Peripherals".

ADR 0002 was written for hwmon, but the same problem shows up here: the sysfs
node name is not stable. It was `hidpp_battery_2`, then `_3`, then `_0` across
three reboots with no hardware change (`docs/hardware-inventory.md`). So a
sensor here is keyed by `model_name` and `serial_number`, never by the node
name, and the node is only ever used to find the device during a scan.

`capacity_level` is **text** (`Full`, `High`, `Normal`, `Low`, `Critical`),
not a percent. It is mapped to an approximate number so it fits the `Reading`
model, which only holds a float, and the raw text is kept alongside it,
reachable through `capacity_level_text()`, since nothing in the frozen model
has room for a string value. Some devices give a real `capacity` percent as
well; that is preferred whenever it is present.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sensors_gui.collectors.cache import ChannelCache
from sensors_gui.model import Group, Reading, SensorId, SensorSpec, Unit

logger = logging.getLogger(__name__)

SOURCE = "power_supply"
DEFAULT_ROOT = Path("/sys/class/power_supply")

# Every channel here is a wireless peripheral report, read over a receiver
# radio link. ADR 0006's rate table gives peripherals 60 seconds, the same
# reasoning as the NVMe SMART log: the value changes slowly, and reading it
# more often only wakes the device for nothing.
CHANNEL_INTERVAL = 60.0

# The kernel's `POWER_SUPPLY_CAPACITY_LEVEL_*` enum, mapped to an approximate
# percent. There is no such thing as an exact number behind these words, so
# this is a display convenience, not a measurement. `Unknown` is deliberately
# left unmapped: reporting an invented number for it would be worse than
# reporting nothing.
CAPACITY_LEVEL_PERCENT: dict[str, float] = {
    "Critical": 5.0,
    "Low": 20.0,
    "Normal": 55.0,
    "High": 85.0,
    "Full": 100.0,
}


@dataclass(slots=True)
class _Channel:
    """One discovered channel, with the call that reads its value."""

    spec: SensorSpec
    read_value: Callable[[], float | None]


def _read_text(path: Path) -> str | None:
    """Read a sysfs file and return its stripped text, or None when it is not readable."""
    try:
        return path.read_text(errors="replace").strip()
    except OSError as exc:
        logger.debug("power_supply: cannot read %s: %s", path, exc)
        return None


def _read_int(path: Path) -> float | None:
    """Read a sysfs file and return it as a float, or None when it is not a plain integer."""
    text = _read_text(path)
    if text is None:
        return None
    try:
        return float(int(text))
    except ValueError:
        logger.debug("power_supply: not an integer in %s: %r", path, text)
        return None


def _device_key(node_dir: Path, model_name: str | None) -> str:
    """Return the stable device identity for one power supply node.

    Args:
        node_dir: The node's directory, used only for its name when nothing
            better is available.
        model_name: The device's `model_name`, or None when the file is
            missing or empty.

    Returns:
        `model_name@serial_number` when both are known, `model_name` alone
        when there is no serial, or the node's own name as a last resort -
        which is exactly the unstable identity this function exists to avoid,
        so it is logged.
    """
    if model_name:
        serial = _read_text(node_dir / "serial_number")
        return f"{model_name}@{serial}" if serial else model_name
    logger.warning(
        "power_supply: %s has no model_name; falling back to the node name, "
        "which is not stable across reboots (see ADR 0002)",
        node_dir,
    )
    return node_dir.name


class PowerSupplyCollector:
    """Read every battery and charge state under `/sys/class/power_supply`."""

    name = SOURCE

    def __init__(self, root: Path | str = DEFAULT_ROOT, clock: Callable[[], float] = time.monotonic) -> None:
        """Create the collector.

        Args:
            root: The directory that holds the power supply nodes. A test
                points this at a temporary tree.
            clock: The source of time used for the read interval. It must
                give seconds and must not go backwards.
        """
        self.root = Path(root)
        self.clock = clock
        self._cache = ChannelCache(lambda: self.clock())
        self._channels: list[_Channel] = []
        self._capacity_level_text: dict[SensorId, str] = {}

    def discover(self) -> list[SensorSpec]:
        """Find every power supply node under the root and what it can report.

        A re-scan keeps the cached value of every channel that is still
        there, the same reasoning as `HwmonCollector.discover`: the identity
        does not depend on the node name, so it survives a re-scan by itself.
        """
        self._channels = []
        if not self.root.is_dir():
            logger.info("power_supply: no %s on this machine", self.root)
            return []

        for node_dir in sorted(self.root.iterdir(), key=lambda path: path.name):
            try:
                self._channels.extend(self._discover_node(node_dir))
            except OSError as exc:
                logger.warning("power_supply: skipping %s: %s", node_dir, exc)

        logger.info("power_supply: found %d channels", len(self._channels))
        return [channel.spec for channel in self._channels]

    def read(self) -> list[Reading]:
        """Read every channel found by the last `discover` call. This never raises.

        A channel is served from the cache when it was read less than
        `CHANNEL_INTERVAL` seconds ago.
        """
        return [
            self._cache.serve(channel.spec.id, channel.spec.min_interval, channel.read_value)
            for channel in self._channels
        ]

    def close(self) -> None:
        """Release the discovered channels and the cache. The collector holds no open file."""
        self._channels = []
        self._capacity_level_text = {}
        self._cache.forget()

    def capacity_level_text(self, sensor_id: SensorId) -> str | None:
        """Return the raw `capacity_level` text last read for one battery channel.

        This is not part of the `Collector` protocol. It exists because
        `Reading.value` only holds a float, and `capacity_level` is text
        (`Full`, `High`, ...). The number from `read()` is an approximation;
        this is the real word the device gave.

        Args:
            sensor_id: The identity of the battery channel.

        Returns:
            The most recently read text, or None when nothing has been read
            yet, or the device does not give `capacity_level` at all.
        """
        return self._capacity_level_text.get(sensor_id)

    def _discover_node(self, node_dir: Path) -> list[_Channel]:
        """Find every channel of one power supply node."""
        model_name = _read_text(node_dir / "model_name")
        device = _device_key(node_dir, model_name)

        channels: list[_Channel] = []

        has_capacity = (node_dir / "capacity").is_file()
        has_capacity_level = (node_dir / "capacity_level").is_file()
        if has_capacity or has_capacity_level:
            sensor_id = SensorId(source=SOURCE, device=device, channel="capacity")
            origin = node_dir / ("capacity" if has_capacity else "capacity_level")
            channels.append(
                _Channel(
                    spec=SensorSpec(
                        id=sensor_id,
                        label="Battery",
                        group=Group.PERIPHERAL,
                        unit=Unit.PERCENT,
                        low=0.0,
                        high=100.0,
                        min_interval=CHANNEL_INTERVAL,
                        origin=str(origin),
                    ),
                    read_value=self._capacity_reader(sensor_id, node_dir, has_capacity, has_capacity_level),
                )
            )

        if (node_dir / "online").is_file():
            sensor_id = SensorId(source=SOURCE, device=device, channel="online")
            online_path = node_dir / "online"
            channels.append(
                _Channel(
                    spec=SensorSpec(
                        id=sensor_id,
                        label="Online",
                        group=Group.PERIPHERAL,
                        unit=Unit.COUNT,
                        low=0.0,
                        high=1.0,
                        min_interval=CHANNEL_INTERVAL,
                        origin=str(online_path),
                    ),
                    read_value=lambda path=online_path: _read_int(path),
                )
            )

        return channels

    def _capacity_reader(
        self,
        sensor_id: SensorId,
        node_dir: Path,
        has_capacity: bool,
        has_capacity_level: bool,
    ) -> Callable[[], float | None]:
        """Build the reader for one node's `capacity` channel.

        A real `capacity` percent is preferred when the device gives one.
        `capacity_level` is read either way when it exists, so its text stays
        available through `capacity_level_text` even on a device that also
        gives a real percent.
        """
        capacity_path = node_dir / "capacity"
        capacity_level_path = node_dir / "capacity_level"

        def read_value() -> float | None:
            if has_capacity_level:
                text = _read_text(capacity_level_path)
                if text is not None:
                    self._capacity_level_text[sensor_id] = text

            if has_capacity:
                return _read_int(capacity_path)

            text = self._capacity_level_text.get(sensor_id)
            if text is None:
                return None
            percent = CAPACITY_LEVEL_PERCENT.get(text)
            if percent is None:
                logger.warning("power_supply: unrecognised capacity_level %r for %s", text, sensor_id)
            return percent

        return read_value
