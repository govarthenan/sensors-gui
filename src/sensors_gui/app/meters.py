"""Turning a sensor value into something a person can read at a glance.

These helpers hold no Textual dependency on purpose. They are the part of the
screen most likely to be wrong in a way a person would notice, so they are
plain functions with plain tests.
"""

from __future__ import annotations

from enum import Enum, auto

from sensors_gui.model import SensorSpec, Unit

# Blocks for the fractional part of a bar cell, from 1/8 to 8/8.
_PARTIAL_BLOCKS = " ▏▎▍▌▋▊▉█"
_FULL_BLOCK = "█"

# Units whose scale is fixed by the unit itself. These are facts.
_IMPLIED_SCALE: dict[Unit, tuple[float, float]] = {
    Unit.PERCENT: (0.0, 100.0),
    Unit.PWM: (0.0, 255.0),
}

# Units with a scale that every PC tool draws against, used only when the
# hardware declares none of its own. These are display CONVENTIONS, not facts
# about the machine, so a declared limit always wins.
#
# Without them most of this screen has no bar at all: k10temp declares no
# limits, and the nct6687 limits are not usable (ADR 0006).
_CONVENTIONAL_SCALE: dict[Unit, tuple[float, float]] = {
    Unit.CELSIUS: (0.0, 100.0),
    Unit.RPM: (0.0, 3000.0),
}

# Which units matter most, top of a panel first. A temperature or a power
# reading is what a person looks for; a voltage rail is reference detail.
_UNIT_PRIORITY: dict[Unit, int] = {
    Unit.CELSIUS: 0,
    Unit.WATT: 1,
    Unit.RPM: 2,
    Unit.PERCENT: 3,
    Unit.PWM: 4,
    Unit.HERTZ: 5,
    Unit.BYTE: 6,
    Unit.BYTE_PER_SECOND: 7,
    Unit.JOULE: 8,
    Unit.VOLT: 9,
    Unit.AMPERE: 10,
    Unit.COUNT: 11,
}
_UNIT_PRIORITY_LAST = 99


class Level(Enum):
    """How a value stands against the thresholds the hardware gave."""

    UNKNOWN = auto()
    NORMAL = auto()
    WARN = auto()
    CRITICAL = auto()


def fraction(spec: SensorSpec, value: float | None) -> float | None:
    """Return where a value sits on its scale, from 0.0 to 1.0.

    A bar may only be drawn when there is a real scale to draw it against.
    Inventing one would make an unbounded reading, such as a clock speed with
    no known maximum, look like a proportion of something.

    Args:
        spec: The sensor, which carries `low`, `high` and `critical`.
        value: The reading, or None.

    Returns:
        The position on the scale, clamped to 0.0–1.0, or None when the sensor
        has no scale or the value is missing.
    """
    if value is None:
        return None

    low, high = _IMPLIED_SCALE.get(spec.unit, (spec.low, spec.high))
    if high is None:
        # A critical threshold is a sensible top of scale when nothing else is.
        high = spec.critical
    if high is None:
        # Nothing was declared. Fall back to the display convention, if the
        # unit has one, and keep whatever low the hardware did give.
        conventional = _CONVENTIONAL_SCALE.get(spec.unit)
        if conventional is not None:
            low, high = (low if low is not None else conventional[0]), conventional[1]
    if low is None:
        low = 0.0
    if high is None or high <= low:
        return None

    return max(0.0, min(1.0, (value - low) / (high - low)))


def sort_key(spec: SensorSpec) -> tuple[int, str]:
    """Return the key that orders sensors inside a panel.

    Temperature first, then power, then fan speed, and reference detail such as
    voltage rails last. Inside one unit, by label.

    Args:
        spec: The sensor.

    Returns:
        A tuple to sort on.
    """
    return (_UNIT_PRIORITY.get(spec.unit, _UNIT_PRIORITY_LAST), spec.label.lower())


def level_of(spec: SensorSpec, value: float | None) -> Level:
    """Return how a value stands against its thresholds.

    A sensor with no threshold is always `NORMAL`, however high it reads. The
    `nct6687` driver gives no usable limits, so a channel without thresholds
    must never be drawn as an alarm. See ADR 0006 and `exp-0007`.

    Args:
        spec: The sensor, which carries `warn` and `critical`.
        value: The reading, or None.

    Returns:
        The level.
    """
    if value is None:
        return Level.UNKNOWN
    if spec.critical is not None and value >= spec.critical:
        return Level.CRITICAL
    if spec.warn is not None and value >= spec.warn:
        return Level.WARN
    return Level.NORMAL


def bar(value: float | None, width: int) -> str:
    """Draw a horizontal bar of a given width.

    Args:
        value: A position from 0.0 to 1.0, or None for a blank bar.
        width: How many character cells the bar occupies.

    Returns:
        A string of exactly `width` characters.
    """
    if width <= 0:
        return ""
    if value is None:
        return " " * width

    filled = max(0.0, min(1.0, value)) * width
    whole = int(filled)
    remainder = filled - whole

    if whole >= width:
        return _FULL_BLOCK * width

    partial = _PARTIAL_BLOCKS[int(remainder * 8)]
    drawn = _FULL_BLOCK * whole + partial
    return drawn.ljust(width)[:width]
