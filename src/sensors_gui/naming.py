"""Give a raw sensor spec a name a person would recognise, and judge it.

The raw labels this machine gives are not usable by a person. Both DIMMs are
labelled `temp1`, and the board's `DRAM` voltage channel is actually CPU
VDDIO. `friendly()` fixes the label and the group. `verdict()` says whether a
channel can be trusted, using the BIOS as ground truth (`exp-0009`).

Both functions take the *raw* spec straight from a collector's `discover()`,
before any renaming, and both can be called on the same raw spec
independently: `friendly()` never needs the result of `verdict()`, or the
reverse. This is the seam `src/sensors_gui/app/sensors_app.py` expects:
`friendly` is its `decorate` callback, and a `keep` callback can be built as
`lambda spec: verdict(spec) != "wrong"`.

The corrections for the `nct6687` voltages and fans come from
`data/evidence/bios-ground-truth-2026-09-22/linux-vs-bios.json`, which this
module loads once, by walking up from its own file to find the repository
root. If that file cannot be found or read, every rule that depends on it
degrades to `verdict() == "unknown"` and an unchanged label - logged once, not
raised - because the application must still run without it. The DIMM names,
the network group, the empty fan headers, the board group, the duplicate CPU
temperature and the empty thermistor headers do not depend on the file at
all, and keep working regardless.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

from sensors_gui.model import Group, SensorSpec

logger = logging.getLogger(__name__)

GROUND_TRUTH_RELATIVE_PATH = Path("data/evidence/bios-ground-truth-2026-09-22/linux-vs-bios.json")

# The five verdicts this module ever returns. A caller can rely on there being
# no sixth value.
Verdict = str
CORRECT: Verdict = "correct"
RENAME: Verdict = "rename"
WRONG: Verdict = "wrong"
UNVERIFIED: Verdict = "unverified"
UNKNOWN: Verdict = "unknown"

# The JSON file's own verdict words, translated to the five above. A fan
# header the BIOS agrees is empty is not a bad reading - the BIOS prints
# "N/A" and Linux prints 0, and they agree - so it counts as "correct", not
# "wrong". "wrong" is reserved for a reading that misleads if taken at face
# value, which is also the one screen-hiding signal the application has: see
# `src/sensors_gui/app/sensors_app.py`, whose `keep` seam is expected to hide
# whatever `verdict()` calls "wrong".
_JSON_VERDICT_MAP: dict[str, Verdict] = {
    "correct": CORRECT,
    "rename": RENAME,
    "wrong": WRONG,
    "unverified": UNVERIFIED,
    "empty header": CORRECT,
}

# The nct6687 driver name, as `hwmon.py` puts it in `SensorId.device`.
NCT6687_DRIVER = "nct6687"
SPD5118_DRIVER = "spd5118"
R8169_DRIVER_PREFIX = "r8169"

# `spd5118` at address 0x51 is slot DIMMA2, and 0x53 is DIMMB2. See
# `docs/hardware-inventory.md`. The match is on the address, not the bus
# number: the kernel numbers the bus at boot, and it was `i2c-0` until
# 2026-09 and `i2c-5` on 2026-10-27 (`data/probes/2026-10-27-spd5118-bus.txt`).
_DIMM_LABELS: dict[str, str] = {
    "0051": "DIMM A2",
    "0053": "DIMM B2",
}
_I2C_CLIENT_PATTERN = re.compile(r"/i2c-\d+/\d+-([0-9a-f]{4})$")

# Proved in exp-0007 (five samples, one second apart, matching every time):
# the nct6687 "CPU" temperature is k10temp's Tctl read a second way, not an
# independent measurement.
_DUPLICATE_TEMP_LABEL = "CPU"
_DUPLICATE_SUFFIX = " (same as Tctl)"

# Optional thermistor headers with nothing plugged in (exp-0007). They read a
# genuine 0.0 C, which is not a temperature, so they are marked empty and
# `verdict()` calls them "wrong" so the screen can hide them by default - the
# same convention as the wrong voltages, but never the fan headers, which
# must stay visible however they read. See docs/physical-build.md.
_EMPTY_THERMISTOR_LABELS: frozenset[str] = frozenset({"CPU Socket", "PCIe x1", "M2_1"})

# `System Fan #2` through `#6` are headers nothing is plugged into (confirmed
# by the BIOS, which prints "N/A" where Linux prints 0). They keep the "SYS_FANn"
# form the board silkscreen and the BIOS use, with "(empty)" for context. A fan
# header must never be hidden for reading 0 RPM - that would hide a fan that
# has STOPPED - so this is a label change only, not a verdict of "wrong".
_EMPTY_FAN_PATTERN = re.compile(r"^System Fan #([2-6])$")

_CHANNEL_KIND_PATTERN = re.compile(r"^([a-z]+)\d+$")


@dataclass(frozen=True, slots=True)
class _VoltageEntry:
    """One row of the ground-truth voltage table."""

    verdict: Verdict
    rename_to: str | None


@dataclass(frozen=True, slots=True)
class _FanEntry:
    """One row of the ground-truth fan table."""

    verdict: Verdict


@dataclass(frozen=True, slots=True)
class GroundTruth:
    """The BIOS correction table, parsed and keyed by the raw Linux label.

    Attributes:
        voltages: Every `nct6687` voltage channel the table covers, keyed by
            its raw `in*_label` text.
        fans: Every `nct6687` fan channel the table covers, keyed by its raw
            `fan*_label` text.
    """

    voltages: dict[str, _VoltageEntry]
    fans: dict[str, _FanEntry]


def friendly(spec: SensorSpec) -> SensorSpec:
    """Return a copy of `spec` with a name and group a person would recognise.

    `spec` must be the raw spec as a collector's `discover()` gives it. The
    input is never modified; a changed field comes back in a new `SensorSpec`,
    and a spec this module has no rule for comes back unchanged (the same
    object, since a frozen dataclass cannot be mutated regardless).

    Args:
        spec: The raw sensor specification.

    Returns:
        A spec with a friendlier `label` and, where it matters, a corrected
        `group`. Every other field is untouched.
    """
    if spec.id.source != "hwmon":
        return spec

    driver = _driver_of(spec)
    kind = _channel_kind(spec.id.channel)
    label = spec.label
    group = spec.group

    if driver == SPD5118_DRIVER:
        label = _dimm_label(spec.id.device, label)
    elif driver.startswith(R8169_DRIVER_PREFIX):
        group = Group.NETWORK
        label = "Ethernet PHY"
    elif driver == NCT6687_DRIVER:
        group = Group.BOARD
        if kind == "in":
            label = _renamed_voltage_label(label)
        elif kind == "fan":
            label = _renamed_fan_label(label)
        elif kind == "temp":
            label = _marked_temp_label(label)

    if label == spec.label and group == spec.group:
        return spec
    return replace(spec, label=label, group=group)


def verdict(spec: SensorSpec) -> str:
    """Judge whether `spec`, as the hardware reports it, can be trusted.

    `spec` must be the raw spec as a collector's `discover()` gives it, the
    same one passed to `friendly()`.

    Args:
        spec: The raw sensor specification.

    Returns:
        One of `"correct"`, `"rename"`, `"wrong"`, `"unverified"` or
        `"unknown"`. `"unknown"` means this module has no evidence either
        way, which is the honest answer for almost everything outside the
        `nct6687` voltages and fans, and for everything when the ground-truth
        file cannot be read.
    """
    if spec.id.source != "hwmon" or _driver_of(spec) != NCT6687_DRIVER:
        return UNKNOWN

    kind = _channel_kind(spec.id.channel)
    if kind == "temp":
        if spec.label == _DUPLICATE_TEMP_LABEL or spec.label in _EMPTY_THERMISTOR_LABELS:
            return WRONG
        return UNKNOWN

    ground_truth = _load_ground_truth()
    if ground_truth is None:
        return UNKNOWN

    if kind == "in":
        entry = ground_truth.voltages.get(spec.label)
        return entry.verdict if entry is not None else UNKNOWN
    if kind == "fan":
        fan_entry = ground_truth.fans.get(spec.label)
        return fan_entry.verdict if fan_entry is not None else UNKNOWN
    return UNKNOWN


# --- label rules -------------------------------------------------------------


def _driver_of(spec: SensorSpec) -> str:
    """Return the driver name from `spec.id.device`, which hwmon.py writes as `driver@path`."""
    driver, _, _ = spec.id.device.partition("@")
    return driver


def _channel_kind(channel: str) -> str:
    """Return the channel kind, for example `in` from `in7` or `temp` from `temp1`."""
    match = _CHANNEL_KIND_PATTERN.match(channel)
    return match.group(1) if match else ""


def _dimm_label(device: str, current_label: str) -> str:
    """Return `DIMM A2` / `DIMM B2` for a known i2c address on any bus, else the label unchanged."""
    match = _I2C_CLIENT_PATTERN.search(device)
    return _DIMM_LABELS.get(match.group(1), current_label) if match else current_label


def _renamed_voltage_label(raw_label: str) -> str:
    """Return the BIOS name for a voltage the ground truth says to rename, else the raw label."""
    ground_truth = _load_ground_truth()
    if ground_truth is None:
        return raw_label
    entry = ground_truth.voltages.get(raw_label)
    if entry is not None and entry.verdict == RENAME and entry.rename_to:
        return entry.rename_to
    return raw_label


def _renamed_fan_label(raw_label: str) -> str:
    """Return `SYS_FANn (empty)` for an empty system fan header, else the label unchanged."""
    match = _EMPTY_FAN_PATTERN.match(raw_label)
    if match is None:
        return raw_label
    return f"SYS_FAN{match.group(1)} (empty)"


def _marked_temp_label(raw_label: str) -> str:
    """Mark the CPU-duplicate temperature and the empty thermistor headers, else leave it."""
    if raw_label == _DUPLICATE_TEMP_LABEL:
        return f"{raw_label}{_DUPLICATE_SUFFIX}"
    if raw_label in _EMPTY_THERMISTOR_LABELS:
        return f"{raw_label} (empty)"
    return raw_label


# --- loading the ground-truth file -------------------------------------------


def _find_repo_root(start: Path | None = None) -> Path | None:
    """Walk upward from `start` (default: this file) to find the repository root.

    The root is recognised by holding both `pyproject.toml` and `data`, which
    is specific enough that an unrelated ancestor directory will not be
    mistaken for it.

    Args:
        start: Where to start looking. Only a test overrides this.

    Returns:
        The repository root, or None when no ancestor matches.
    """
    current = Path(start if start is not None else __file__).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "data").is_dir():
            return candidate
    return None


def _load_ground_truth_from(path: Path) -> GroundTruth | None:
    """Load and parse the ground-truth file at `path`.

    Args:
        path: The file to read.

    Returns:
        The parsed table, or None - with a logged warning, never an
        exception - when the file is missing, unreadable or not valid JSON.
    """
    try:
        raw_text = path.read_text()
    except OSError as exc:
        logger.warning("naming: cannot read the ground-truth file %s: %s", path, exc)
        return None
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("naming: the ground-truth file %s is not valid JSON: %s", path, exc)
        return None
    return _parse_ground_truth(data)


def _parse_ground_truth(data: dict[str, Any]) -> GroundTruth:
    """Turn the raw JSON structure into a `GroundTruth`, keyed by raw Linux label."""
    voltages: dict[str, _VoltageEntry] = {}
    for row in data.get("voltages", []):
        label = row.get("linux_label")
        raw_verdict = row.get("verdict")
        if not label or not raw_verdict:
            continue
        voltages[label] = _VoltageEntry(
            verdict=_JSON_VERDICT_MAP.get(raw_verdict, UNKNOWN),
            rename_to=row.get("rename_to"),
        )

    fans: dict[str, _FanEntry] = {}
    for row in data.get("fans", []):
        label = row.get("linux_label")
        raw_verdict = row.get("verdict")
        if not label or not raw_verdict:
            continue
        fans[label] = _FanEntry(verdict=_JSON_VERDICT_MAP.get(raw_verdict, UNKNOWN))

    return GroundTruth(voltages=voltages, fans=fans)


@lru_cache(maxsize=1)
def _load_ground_truth() -> GroundTruth | None:
    """Load the ground-truth table once and cache it for the life of the process."""
    root = _find_repo_root()
    if root is None:
        logger.warning(
            "naming: could not find the repository root from %s; "
            "voltage and fan corrections are unavailable, everything reports 'unknown'",
            __file__,
        )
        return None
    return _load_ground_truth_from(root / GROUND_TRUTH_RELATIVE_PATH)
