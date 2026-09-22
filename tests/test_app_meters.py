"""Tests for the pure drawing helpers of the screen.

These have no Textual dependency and no hardware. They decide how a value
becomes a bar and a colour, which is the part most likely to be wrong in a way
a person would notice.
"""

from __future__ import annotations

import pytest

from sensors_gui.app.meters import Level, bar, fraction, level_of
from sensors_gui.model import Group, SensorId, SensorSpec, Unit


def _spec(**kwargs: object) -> SensorSpec:
    """Build a spec with sensible defaults for a temperature channel."""
    defaults = {
        "id": SensorId(source="test", device="d@/sys/x", channel="temp1"),
        "label": "test",
        "group": Group.CPU,
        "unit": Unit.CELSIUS,
    }
    defaults.update(kwargs)
    return SensorSpec(**defaults)  # type: ignore[arg-type]


# --- fraction ---------------------------------------------------------------


def test_fraction_uses_low_and_high_when_both_are_known() -> None:
    spec = _spec(low=0.0, high=100.0)
    assert fraction(spec, 25.0) == 0.25


def test_fraction_uses_critical_as_the_top_when_high_is_missing() -> None:
    spec = _spec(critical=100.0)
    assert fraction(spec, 50.0) == 0.5


def test_fraction_is_none_when_there_is_no_scale_to_draw() -> None:
    # A frequency with no known maximum cannot be drawn as a proportion.
    assert fraction(_spec(unit=Unit.HERTZ), 3.2e9) is None


def test_fraction_is_none_for_a_missing_value() -> None:
    assert fraction(_spec(low=0.0, high=100.0), None) is None


def test_fraction_is_clamped_so_an_over_range_value_cannot_overflow_the_bar() -> None:
    spec = _spec(low=0.0, high=100.0)
    assert fraction(spec, 150.0) == 1.0
    assert fraction(spec, -20.0) == 0.0


def test_a_percent_channel_needs_no_declared_scale() -> None:
    assert fraction(_spec(unit=Unit.PERCENT), 40.0) == 0.4


def test_a_zero_width_scale_does_not_divide_by_zero() -> None:
    assert fraction(_spec(low=50.0, high=50.0), 50.0) is None


# --- level ------------------------------------------------------------------


def test_level_is_normal_below_the_warning_threshold() -> None:
    assert level_of(_spec(warn=80.0, critical=95.0), 50.0) is Level.NORMAL


def test_level_is_warn_at_and_above_the_warning_threshold() -> None:
    assert level_of(_spec(warn=80.0, critical=95.0), 80.0) is Level.WARN
    assert level_of(_spec(warn=80.0, critical=95.0), 90.0) is Level.WARN


def test_level_is_critical_at_and_above_the_critical_threshold() -> None:
    assert level_of(_spec(warn=80.0, critical=95.0), 95.0) is Level.CRITICAL


def test_level_is_unknown_for_a_missing_value() -> None:
    assert level_of(_spec(warn=80.0), None) is Level.UNKNOWN


def test_level_is_normal_when_the_hardware_gives_no_threshold() -> None:
    # The nct6687 driver gives no usable limits. A channel without thresholds
    # must never look like an alarm. See ADR 0006 and exp-0007.
    assert level_of(_spec(), 98.0) is Level.NORMAL


def test_a_critical_threshold_alone_still_works() -> None:
    assert level_of(_spec(critical=95.0), 96.0) is Level.CRITICAL


# --- bar --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "width", "expected"),
    [
        (0.0, 10, "          "),
        (1.0, 10, "██████████"),
        (0.5, 10, "█████     "),
    ],
)
def test_bar_fills_in_proportion(value: float, width: int, expected: str) -> None:
    assert bar(value, width) == expected


def test_bar_uses_a_partial_block_for_a_fraction_of_a_cell() -> None:
    # 0.55 of 10 cells is 5.5 cells: five full blocks and one half block.
    drawn = bar(0.55, 10)
    assert drawn.startswith("█████")
    assert drawn[5] == "▌"
    assert len(drawn) == 10


def test_bar_of_none_is_blank_but_keeps_its_width() -> None:
    assert bar(None, 8) == " " * 8


def test_bar_never_exceeds_its_width() -> None:
    assert len(bar(1.5, 12)) == 12


def test_a_zero_width_bar_is_empty_and_does_not_raise() -> None:
    assert bar(0.5, 0) == ""


# --- display conventions ----------------------------------------------------


def test_a_temperature_gets_a_bar_even_when_the_hardware_gives_no_limits() -> None:
    # k10temp declares no minimum or maximum, but 0-100 C is what every PC tool
    # draws a CPU temperature against. Without this, most of the screen has no
    # bar at all.
    assert fraction(_spec(unit=Unit.CELSIUS), 50.0) == 0.5


def test_a_fan_gets_a_bar_from_the_conventional_scale() -> None:
    assert fraction(_spec(unit=Unit.RPM), 1500.0) == 0.5


def test_a_declared_scale_always_beats_the_convention() -> None:
    # The drive declares crit 87.85 C. That is a real fact and must win over
    # the 0-100 convention.
    spec = _spec(unit=Unit.CELSIUS, critical=87.85)
    assert fraction(spec, 43.925) == pytest.approx(0.5)


def test_a_unit_with_no_convention_still_refuses_to_invent_one() -> None:
    # A clock speed or a voltage rail has no universal scale. Drawing one would
    # be a lie about the hardware.
    assert fraction(_spec(unit=Unit.HERTZ), 3.2e9) is None
    assert fraction(_spec(unit=Unit.VOLT), 1.3) is None
    assert fraction(_spec(unit=Unit.WATT), 40.0) is None


def test_the_convention_is_still_clamped() -> None:
    assert fraction(_spec(unit=Unit.CELSIUS), 130.0) == 1.0


# --- ordering ---------------------------------------------------------------


def test_sort_key_puts_temperature_and_power_above_the_rest() -> None:
    from sensors_gui.app.meters import sort_key

    units = [Unit.VOLT, Unit.CELSIUS, Unit.HERTZ, Unit.WATT, Unit.RPM, Unit.PERCENT]
    specs = [_spec(unit=unit, label=unit.value) for unit in units]
    ordered = [spec.unit for spec in sorted(specs, key=sort_key)]
    assert ordered[0] is Unit.CELSIUS
    assert ordered[1] is Unit.WATT
    assert ordered.index(Unit.RPM) < ordered.index(Unit.VOLT)


def test_sort_key_reads_a_number_in_a_label_as_a_number() -> None:
    # Found by rendering the screen after exp-0012 put twelve cores on it:
    # plain text order gave Core 0, 1, 10, 11, 12, 13, 2, 3.
    from sensors_gui.app.meters import sort_key

    labels = ["CPU Core 10 Power", "CPU Core 2 Power", "CPU Core 1 Power", "CPU Core 0 Power"]
    specs = [_spec(unit=Unit.WATT, label=label) for label in labels]

    assert [spec.label for spec in sorted(specs, key=sort_key)] == [
        "CPU Core 0 Power",
        "CPU Core 1 Power",
        "CPU Core 2 Power",
        "CPU Core 10 Power",
    ]


def test_sort_key_orders_by_label_inside_one_unit() -> None:
    from sensors_gui.app.meters import sort_key

    specs = [_spec(label="Tctl"), _spec(label="Tccd1"), _spec(label="CPU")]
    assert [spec.label for spec in sorted(specs, key=sort_key)] == ["CPU", "Tccd1", "Tctl"]


# --- sparkline --------------------------------------------------------------


def test_a_sparkline_is_drawn_from_a_history_of_values() -> None:
    from sensors_gui.app.meters import sparkline

    drawn = sparkline([0.0, 50.0, 100.0], width=3)
    assert len(drawn) == 3
    assert drawn[0] == "▁"
    assert drawn[2] == "█"


def test_a_sparkline_shows_only_the_most_recent_values_that_fit() -> None:
    from sensors_gui.app.meters import sparkline

    drawn = sparkline([0.0] * 50 + [100.0], width=8)
    assert len(drawn) == 8
    assert drawn[-1] == "█"


def test_a_flat_history_draws_a_flat_line_rather_than_dividing_by_zero() -> None:
    from sensors_gui.app.meters import sparkline

    drawn = sparkline([42.0, 42.0, 42.0], width=3)
    assert len(drawn) == 3
    assert len(set(drawn)) == 1


def test_a_gap_in_the_history_is_blank_not_zero() -> None:
    # A failed read must not look like a reading of zero.
    from sensors_gui.app.meters import sparkline

    drawn = sparkline([0.0, None, 100.0], width=3)
    assert drawn[1] == " "


def test_a_history_too_short_to_fill_the_width_is_padded_on_the_left() -> None:
    from sensors_gui.app.meters import sparkline

    drawn = sparkline([10.0, 20.0], width=6)
    assert len(drawn) == 6
    assert drawn.startswith("    ")


def test_an_empty_history_is_blank_but_keeps_its_width() -> None:
    from sensors_gui.app.meters import sparkline

    assert sparkline([], width=5) == " " * 5
    assert sparkline([None, None], width=5) == " " * 5


def test_a_sparkline_scales_to_the_declared_range_when_one_is_given() -> None:
    # Against a fixed scale, a small wobble stays visually small instead of
    # being stretched to fill the whole height.
    from sensors_gui.app.meters import sparkline

    drawn = sparkline([40.0, 41.0, 42.0], width=3, low=0.0, high=100.0)
    assert len(set(drawn)) <= 2
