"""The hwmon collector. It reads `/sys/class/hwmon`.

ADR 0002 fixes the identity rule: a sensor is keyed by the device `name` plus
the real path of its `device` link, never by the `hwmonN` index.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sensors_gui.collectors.cache import ChannelCache
from sensors_gui.model import Group, Reading, SensorId, SensorSpec, Unit

logger = logging.getLogger(__name__)

SYSFS_ROOT = "/sys"
DEFAULT_ROOT = Path(SYSFS_ROOT) / "class" / "hwmon"
SOURCE = "hwmon"

# Channel attributes look like "temp1_input", "fan2_label", "in0_min".
CHANNEL_PATTERN = re.compile(r"^(?P<kind>[a-z]+)(?P<index>\d+)_(?P<attribute>.+)$")

# The divisor that turns the raw sysfs integer into the display unit, from the
# kernel hwmon ABI (Documentation/hwmon/sysfs-interface.rst).
#
# The divisor is an integer on purpose. Multiplying by a float factor loses
# precision: 14000 * 1e-6 gives 0.013999999999999999, but 14000 / 1_000_000
# gives 0.014.
KIND_UNITS: dict[str, tuple[Unit, int]] = {
    "temp": (Unit.CELSIUS, 1000),
    "in": (Unit.VOLT, 1000),
    "curr": (Unit.AMPERE, 1000),
    "power": (Unit.WATT, 1_000_000),
    "energy": (Unit.JOULE, 1_000_000),
    "fan": (Unit.RPM, 1),
    "pwm": (Unit.PWM, 1),
    "freq": (Unit.HERTZ, 1),
    "humidity": (Unit.PERCENT, 1000),
}

# Which part of the machine a driver belongs to.
DRIVER_GROUPS: dict[str, Group] = {
    "k10temp": Group.CPU,
    "zenpower": Group.CPU,
    "coretemp": Group.CPU,
    "amdgpu": Group.GPU,
    "nouveau": Group.GPU,
    "nvme": Group.STORAGE,
    "drivetemp": Group.STORAGE,
    "spd5118": Group.MEMORY,
    "jc42": Group.MEMORY,
    "nct6687": Group.BOARD,
    "nct6683": Group.BOARD,
    "nct6775": Group.BOARD,
    "it87": Group.BOARD,
}

# The shortest time in seconds between two reads of a device, from ADR 0006.
# A read of an SMBus or NVMe channel costs about 1.5 to 2 ms, against 5 us for
# a register-backed channel, and it wakes the device. Measured in
# `lab/exp-0004-hwmon-read-cost/`.
DRIVER_INTERVALS: dict[str, float] = {
    "spd5118": 5.0,
    "jc42": 5.0,
    "nvme": 5.0,
    "drivetemp": 5.0,
}
DEFAULT_INTERVAL = 0.0

# A drive can report a placeholder limit such as 65261850 millidegrees. Any
# limit outside a plausible range for its unit is thrown away.
PLAUSIBLE_LIMITS: dict[Unit, tuple[float, float]] = {
    Unit.CELSIUS: (-50.0, 200.0),
    Unit.VOLT: (0.0, 30.0),
    Unit.AMPERE: (0.0, 200.0),
    Unit.WATT: (0.0, 2000.0),
    Unit.RPM: (0.0, 20000.0),
}


@dataclass(slots=True)
class _Channel:
    """One discovered channel, with the file the collector reads for its value."""

    spec: SensorSpec
    input_path: Path
    divisor: int


def _read_text(path: Path) -> str | None:
    """Read a sysfs file and return its stripped text, or None when it is not readable."""
    try:
        return path.read_text(errors="replace").strip()
    except OSError as exc:
        logger.debug("cannot read %s: %s", path, exc)
        return None


def _read_scaled(path: Path, divisor: int) -> float | None:
    """Read a sysfs file and return the value in the display unit, or None on failure."""
    text = _read_text(path)
    if text is None:
        return None
    try:
        raw = int(text)
    except ValueError:
        logger.debug("not an integer in %s: %r", path, text)
        return None
    return raw / divisor if divisor != 1 else float(raw)


def _plausible(value: float | None, unit: Unit) -> float | None:
    """Return the value when it sits inside a plausible range for its unit, else None."""
    if value is None:
        return None
    low, high = PLAUSIBLE_LIMITS.get(unit, (float("-inf"), float("inf")))
    return value if low <= value <= high else None


def _normalise(path: Path) -> str:
    """Return a device path that starts at `/sys/devices`.

    Every hwmon device sits under `/sys/devices`. The path is cut at that
    component and rebuilt, so that a test tree or a chroot prefix cannot get
    into a sensor key. Without this, the same sensor would get a different key
    in a test than on the machine.
    """
    parts = path.parts
    if "devices" in parts:
        index = len(parts) - 1 - parts[::-1].index("devices")
        return str(Path(SYSFS_ROOT).joinpath(*parts[index:]))
    return str(path)


def _device_path(hwmon_dir: Path) -> str:
    """Return the real path of the device behind a hwmon directory.

    The `device` link is the correct answer. When it is absent, the parent of
    the `hwmon` directory is used, which is where the kernel puts the device
    for a driver that registers through `devm_hwmon_device_register_with_info`.
    """
    device_link = hwmon_dir / "device"
    if device_link.exists():
        return _normalise(device_link.resolve())
    resolved = hwmon_dir.resolve()
    if resolved.parent.name == "hwmon":
        return _normalise(resolved.parent.parent)
    return _normalise(resolved)


class HwmonCollector:
    """Read every temperature, voltage, fan, power and frequency in `/sys/class/hwmon`."""

    name = SOURCE

    def __init__(self, root: Path | str = DEFAULT_ROOT, clock: Callable[[], float] = time.monotonic) -> None:
        """Create the collector.

        Args:
            root: The directory that holds the `hwmonN` entries. Tests point
                this at a temporary tree that copies the shape of sysfs.
            clock: The source of time used for the read intervals. It must
                give seconds and must not go backwards.
        """
        self.root = Path(root)
        self.clock = clock
        self._cache = ChannelCache(lambda: self.clock())
        self._channels: list[_Channel] = []

    def discover(self) -> list[SensorSpec]:
        """Find every readable channel under the root, and remember how to read it.

        A re-scan keeps the cached value of every channel that is still there.
        Throwing the cache away would make a re-scan start a bus transaction on
        every slow device at once, which is what ADR 0006 avoids. The cache is
        keyed by `SensorId`, so it survives a re-scan by itself.
        """
        self._channels = []
        if not self.root.is_dir():
            logger.warning("no hwmon root at %s", self.root)
            return []

        for hwmon_dir in sorted(self.root.iterdir(), key=lambda path: path.name):
            try:
                self._channels.extend(self._discover_device(hwmon_dir))
            except OSError as exc:
                logger.warning("skipping %s: %s", hwmon_dir, exc)

        logger.info("hwmon: found %d channels", len(self._channels))
        return [channel.spec for channel in self._channels]

    def read(self) -> list[Reading]:
        """Read every channel found by the last `discover` call. This never raises.

        A channel whose minimum interval has not passed is served from the
        cache, with the time of the read that first produced the value. See
        ADR 0006.
        """
        return [
            self._cache.serve(
                channel.spec.id,
                channel.spec.min_interval,
                lambda channel=channel: _read_scaled(channel.input_path, channel.divisor),
            )
            for channel in self._channels
        ]

    def close(self) -> None:
        """Release the discovered channels and the cache. The collector holds no open file."""
        self._channels = []
        self._cache.forget()

    def _discover_device(self, hwmon_dir: Path) -> list[_Channel]:
        """Find every channel of one hwmon device."""
        driver_name = _read_text(hwmon_dir / "name")
        if driver_name is None:
            return []

        device = f"{driver_name}@{_device_path(hwmon_dir)}"
        group = DRIVER_GROUPS.get(driver_name, Group.OTHER)
        interval = DRIVER_INTERVALS.get(driver_name, DEFAULT_INTERVAL)
        attributes = self._group_attributes(hwmon_dir)

        channels: list[_Channel] = []
        for (kind, index), files in sorted(attributes.items()):
            if "input" not in files or kind not in KIND_UNITS:
                continue
            unit, divisor = KIND_UNITS[kind]
            channel_name = f"{kind}{index}"
            label = _read_text(files["label"]) if "label" in files else None
            spec = SensorSpec(
                id=SensorId(source=SOURCE, device=device, channel=channel_name),
                label=label or channel_name,
                group=group,
                unit=unit,
                warn=_plausible(_read_scaled(files["max"], divisor), unit) if "max" in files else None,
                critical=_plausible(_read_scaled(files["crit"], divisor), unit) if "crit" in files else None,
                low=_plausible(_read_scaled(files["min"], divisor), unit) if "min" in files else None,
                min_interval=interval,
                origin=str(files["input"]),
            )
            channels.append(_Channel(spec=spec, input_path=files["input"], divisor=divisor))
        return channels

    @staticmethod
    def _group_attributes(hwmon_dir: Path) -> dict[tuple[str, int], dict[str, Path]]:
        """Group the files of one hwmon directory by channel, as `(kind, index) -> {attribute: path}`."""
        grouped: dict[tuple[str, int], dict[str, Path]] = {}
        for entry in hwmon_dir.iterdir():
            match = CHANNEL_PATTERN.match(entry.name)
            if match is None:
                continue
            key = (match["kind"], int(match["index"]))
            grouped.setdefault(key, {})[match["attribute"]] = entry
        return grouped
