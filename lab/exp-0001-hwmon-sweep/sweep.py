"""Sweep every hwmon device in sysfs and record all readable attributes.

The script answers one question: which sensor channels does this machine expose
through the standard Linux hwmon interface, and which of them need root?

Output:
    results/hwmon-sweep.json  - machine readable dump
    results/hwmon-sweep.md    - human readable table
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

HWMON_ROOT = Path("/sys/class/hwmon")
RESULTS_DIR = Path(__file__).parent / "results"

# Channel attributes look like "temp1_input", "fan2_label", "in0_min".
CHANNEL_RE = re.compile(r"^(?P<kind>[a-z]+)(?P<index>\d+)_(?P<attr>.+)$")

# Scale factors from raw sysfs integers to the unit a human wants.
UNIT_BY_KIND: dict[str, tuple[str, float]] = {
    "temp": ("degC", 1e-3),
    "in": ("V", 1e-3),
    "fan": ("RPM", 1.0),
    "pwm": ("0-255", 1.0),
    "power": ("W", 1e-6),
    "energy": ("J", 1e-6),
    "curr": ("A", 1e-3),
    "humidity": ("%RH", 1e-3),
    "freq": ("Hz", 1.0),
}


@dataclass
class Channel:
    """One measurable channel of a hwmon device, for example `temp1`."""

    kind: str
    index: int
    label: str | None = None
    unit: str = ""
    raw_input: int | None = None
    value: float | None = None
    attributes: dict[str, str] = field(default_factory=dict)
    unreadable: list[str] = field(default_factory=list)


@dataclass
class HwmonDevice:
    """One `/sys/class/hwmon/hwmonN` device."""

    path: str
    name: str
    driver: str | None
    device_path: str | None
    channels: list[Channel] = field(default_factory=list)
    extra_files: dict[str, str] = field(default_factory=dict)


def read_text(path: Path) -> str | None:
    """Read a sysfs file and return its stripped text, or None if it is not readable."""
    try:
        return path.read_text(errors="replace").strip()
    except (OSError, PermissionError) as exc:
        logger.debug("cannot read %s: %s", path, exc)
        return None


def scale(kind: str, raw: str) -> tuple[str, float | None, int | None]:
    """Convert a raw sysfs value to (unit, scaled value, raw integer)."""
    unit, factor = UNIT_BY_KIND.get(kind, ("", 1.0))
    try:
        raw_int = int(raw)
    except ValueError:
        return unit, None, None
    return unit, raw_int * factor, raw_int


def collect_device(hwmon_dir: Path) -> HwmonDevice:
    """Read every attribute of one hwmon device."""
    name = read_text(hwmon_dir / "name") or "unknown"
    driver_link = hwmon_dir / "device" / "driver"
    driver = os.path.basename(os.path.realpath(driver_link)) if driver_link.exists() else None
    device_link = hwmon_dir / "device"
    device_path = os.path.realpath(device_link) if device_link.exists() else None

    device = HwmonDevice(path=str(hwmon_dir), name=name, driver=driver, device_path=device_path)
    channels: dict[tuple[str, int], Channel] = {}

    for entry in sorted(hwmon_dir.iterdir()):
        if entry.is_dir() or entry.name in {"name", "uevent", "subsystem", "device", "power"}:
            continue
        match = CHANNEL_RE.match(entry.name)
        if not match:
            text = read_text(entry)
            if text is not None:
                device.extra_files[entry.name] = text
            continue

        kind = match["kind"]
        index = int(match["index"])
        attr = match["attr"]
        key = (kind, index)
        channel = channels.setdefault(key, Channel(kind=kind, index=index))

        text = read_text(entry)
        if text is None:
            channel.unreadable.append(entry.name)
            continue
        channel.attributes[attr] = text
        if attr == "label":
            channel.label = text
        elif attr == "input":
            channel.unit, channel.value, channel.raw_input = scale(kind, text)

    device.channels = [channels[key] for key in sorted(channels)]
    return device


def collect_all() -> list[HwmonDevice]:
    """Read every hwmon device on the system."""
    if not HWMON_ROOT.exists():
        logger.error("no hwmon root at %s", HWMON_ROOT)
        return []
    devices = [collect_device(p) for p in sorted(HWMON_ROOT.iterdir(), key=lambda p: p.name)]
    logger.info("read %d hwmon devices", len(devices))
    return devices


def render_markdown(devices: list[HwmonDevice], captured_at: str) -> str:
    """Build a markdown report of the sweep."""
    lines = [
        "# hwmon sweep",
        "",
        f"Captured: {captured_at}",
        f"Run as: uid {os.getuid()}",
        "",
    ]
    for device in devices:
        lines.append(f"## `{Path(device.path).name}` — {device.name}")
        lines.append("")
        lines.append(f"- driver: `{device.driver}`")
        lines.append(f"- device: `{device.device_path}`")
        lines.append("")
        if device.channels:
            lines.append("| channel | label | value | unit | other attributes | unreadable |")
            lines.append("|---|---|---|---|---|---|")
            for channel in device.channels:
                other = ", ".join(f"{k}={v}" for k, v in channel.attributes.items() if k not in {"input", "label"})
                value = "-" if channel.value is None else f"{channel.value:g}"
                lines.append(
                    f"| `{channel.kind}{channel.index}` | {channel.label or '-'} | {value} | "
                    f"{channel.unit or '-'} | {other or '-'} | {', '.join(channel.unreadable) or '-'} |"
                )
            lines.append("")
        if device.extra_files:
            lines.append("Other files: " + ", ".join(f"`{k}`={v}" for k, v in device.extra_files.items()))
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    """Run the sweep and write both result files."""
    captured_at = datetime.now(UTC).isoformat(timespec="seconds")
    devices = collect_all()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    payload = {"captured_at": captured_at, "uid": os.getuid(), "devices": [asdict(d) for d in devices]}
    (RESULTS_DIR / "hwmon-sweep.json").write_text(json.dumps(payload, indent=2))
    (RESULTS_DIR / "hwmon-sweep.md").write_text(render_markdown(devices, captured_at))
    logger.info("wrote results to %s", RESULTS_DIR)


if __name__ == "__main__":
    main()
