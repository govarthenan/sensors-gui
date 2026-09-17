"""Core model objects: sensor identity, specification, reading and sample.

See `docs/architecture.md` for the design, and ADR 0002 for the rule that a
sensor is keyed by its name and device path, never by its `hwmonN` index.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

KEY_SEPARATOR = ":"
KEY_PART_COUNT = 3


class Unit(StrEnum):
    """The display unit of a sensor value."""

    CELSIUS = "celsius"
    VOLT = "volt"
    AMPERE = "ampere"
    WATT = "watt"
    JOULE = "joule"
    RPM = "rpm"
    PERCENT = "percent"
    HERTZ = "hertz"
    BYTE = "byte"
    BYTE_PER_SECOND = "byte_per_second"
    PWM = "pwm"
    COUNT = "count"
    SECOND = "second"
    NONE = "none"

    @property
    def symbol(self) -> str:
        """Return the short symbol to show after a value."""
        return _UNIT_SYMBOLS[self]

    @property
    def decimals(self) -> int:
        """Return how many decimal places a value of this unit needs."""
        return _UNIT_DECIMALS.get(self, 1)


_UNIT_SYMBOLS: dict[Unit, str] = {
    Unit.CELSIUS: "°C",
    Unit.VOLT: "V",
    Unit.AMPERE: "A",
    Unit.WATT: "W",
    Unit.JOULE: "J",
    Unit.RPM: "RPM",
    Unit.PERCENT: "%",
    Unit.HERTZ: "Hz",
    Unit.BYTE: "B",
    Unit.BYTE_PER_SECOND: "B/s",
    Unit.PWM: "",
    Unit.COUNT: "",
    Unit.SECOND: "s",
    Unit.NONE: "",
}

_UNIT_DECIMALS: dict[Unit, int] = {
    Unit.VOLT: 3,
    Unit.WATT: 2,
    Unit.PERCENT: 0,
    Unit.RPM: 0,
    Unit.PWM: 0,
    Unit.COUNT: 0,
    Unit.HERTZ: 0,
    Unit.BYTE: 0,
}


class Group(StrEnum):
    """Where a sensor belongs in the user interface."""

    CPU = "cpu"
    GPU = "gpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    BOARD = "board"
    PERIPHERAL = "peripheral"
    SYSTEM = "system"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class SensorId:
    """The stable identity of one measurable value.

    Attributes:
        source: The collector that owns the sensor, for example `hwmon`.
        device: The device inside that collector, for example
            `k10temp@/sys/devices/pci0000:00/0000:00:18.3`.
        channel: The channel on that device, for example `temp1`.
    """

    source: str
    device: str
    channel: str

    @property
    def key(self) -> str:
        """Return the text form `source:device:channel`, used in settings files."""
        return KEY_SEPARATOR.join((self.source, self.device, self.channel))

    @classmethod
    def from_key(cls, key: str) -> SensorId:
        """Build a `SensorId` from its text form.

        Args:
            key: A string of the form `source:device:channel`.

        Returns:
            The identity.

        Raises:
            ValueError: If the key does not hold three parts. The device part
                can itself hold colons, because PCI paths do, so the split
                takes the first part and the last part.
        """
        head, _, rest = key.partition(KEY_SEPARATOR)
        device, separator, channel = rest.rpartition(KEY_SEPARATOR)
        if not head or not separator or not device or not channel:
            raise ValueError(f"not a sensor key: {key!r}; expected {KEY_PART_COUNT} parts")
        return cls(source=head, device=device, channel=channel)

    def __str__(self) -> str:
        """Return the text form of the identity."""
        return self.key


@dataclass(frozen=True, slots=True)
class SensorSpec:
    """What a sensor is. Found once, at discovery, and then it does not change.

    Attributes:
        id: The identity of the sensor.
        label: A short name for the user.
        group: Where the sensor belongs in the user interface.
        unit: The unit of every value the sensor gives.
        low: The bottom of a sensible meter scale, if it is known.
        high: The top of a sensible meter scale, if it is known.
        warn: The value above which the user interface warns, if the hardware
            gives one.
        critical: The value above which the state is critical, if the hardware
            gives one.
        min_interval: The shortest time in seconds between two reads of this
            sensor. Zero means "read it on every pass". A value above zero
            protects a sensor whose read starts a bus transaction. See ADR 0006.
        origin: The raw path or call, for the diagnostic view.
    """

    id: SensorId
    label: str
    group: Group
    unit: Unit
    low: float | None = None
    high: float | None = None
    warn: float | None = None
    critical: float | None = None
    min_interval: float = 0.0
    origin: str = ""

    def format(self, value: float | None) -> str:
        """Return the value as text with its unit, or an em dash when it is missing.

        Args:
            value: The value to show, or None.

        Returns:
            Text for the user interface.
        """
        if value is None:
            return "—"
        text = f"{value:.{self.unit.decimals}f}"
        return f"{text} {self.unit.symbol}".rstrip()


@dataclass(frozen=True, slots=True)
class Reading:
    """What a sensor said at one moment.

    A reading either holds a value or holds an error. It never holds both.

    Attributes:
        id: The identity of the sensor.
        value: The value in the display unit, or None when the read failed.
        error: Why the read failed, or None.
        read_at: The clock time of the read that produced this value. A cached
            value keeps the time of the read that first produced it, not the
            time of the pass that served it. See ADR 0006.
    """

    id: SensorId
    value: float | None
    error: str | None = None
    read_at: float | None = None

    @classmethod
    def ok(cls, sensor_id: SensorId, value: float, read_at: float | None = None) -> Reading:
        """Build a reading that holds a value."""
        return cls(id=sensor_id, value=value, error=None, read_at=read_at)

    @classmethod
    def failed(cls, sensor_id: SensorId, error: str, read_at: float | None = None) -> Reading:
        """Build a reading that holds an error."""
        return cls(id=sensor_id, value=None, error=error, read_at=read_at)

    @property
    def is_ok(self) -> bool:
        """Return True when the reading holds a value."""
        return self.value is not None

    def age(self, now: float) -> float | None:
        """Return how many seconds old the value is, or None when the time is unknown.

        Args:
            now: The current clock time, from the same clock as `read_at`.

        Returns:
            The age in seconds.
        """
        return None if self.read_at is None else now - self.read_at


@dataclass(slots=True)
class Sample:
    """Every reading from one pass, with one timestamp.

    Attributes:
        timestamp: Seconds from the epoch, from `time.time()`.
        readings: The readings of that pass.
    """

    timestamp: float
    readings: list[Reading] = field(default_factory=list)

    def value_of(self, sensor_id: SensorId) -> float | None:
        """Return the value of one sensor in this sample, or None if it is absent."""
        for reading in self.readings:
            if reading.id == sensor_id:
                return reading.value
        return None

    def by_id(self) -> dict[SensorId, Reading]:
        """Return the readings as a dictionary keyed by sensor identity."""
        return {reading.id: reading for reading in self.readings}
