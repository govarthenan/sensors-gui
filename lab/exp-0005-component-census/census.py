"""Enumerate every component of this PC that a bus can report.

This is step 1 of the coverage experiment: build the denominator. The script
walks every enumerable bus and writes one row for each component, with the
sensor sources that are already known for it.

It only reads. It starts no bus transaction that the kernel has not already
made, and it never writes to an I2C address.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "results"
SYS = Path("/sys")


@dataclass
class Component:
    """One component found on a bus.

    Attributes:
        bus: Which enumeration found it, for example `pci` or `i2c`.
        address: Where it sits on that bus.
        name: What it calls itself.
        driver: The kernel driver bound to it, if any.
        kind: A short class, for example `gpu`, `storage`, `dimm`.
        sensor_sources: The sensor paths or tools already known for it.
        notes: Anything else worth keeping.
    """

    bus: str
    address: str
    name: str
    driver: str | None = None
    kind: str = "unknown"
    sensor_sources: list[str] = field(default_factory=list)
    notes: dict[str, str] = field(default_factory=dict)


def _run(command: list[str]) -> str:
    """Run a command and return its output, or an empty string when it fails."""
    try:
        return subprocess.run(command, capture_output=True, text=True, check=False, timeout=20).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("command failed %s: %s", command[0], exc)
        return ""


def _read(path: Path) -> str | None:
    """Read a sysfs file and return its stripped text, or None."""
    try:
        return path.read_text(errors="replace").strip()
    except OSError:
        return None


def _driver_of(device_dir: Path) -> str | None:
    """Return the name of the driver bound to a sysfs device, or None."""
    link = device_dir / "driver"
    return link.resolve().name if link.exists() else None


def _hwmon_index() -> dict[str, list[str]]:
    """Map a real device path to the hwmon names it provides.

    A hwmon node often hangs below the device it belongs to, not on it. The
    `nvme` hwmon sits at `<pci device>/nvme/nvme0`, and the Realtek PHY hwmon
    sits on an MDIO bus below the network card. `_sources_under` matches on the
    path prefix so that those sensors reach the right component.
    """
    index: dict[str, list[str]] = {}
    hwmon_root = SYS / "class" / "hwmon"
    if not hwmon_root.is_dir():
        return index
    for entry in hwmon_root.iterdir():
        name = _read(entry / "name")
        if name is None:
            continue
        device_link = entry / "device"
        device = str(device_link.resolve()) if device_link.exists() else str(entry.resolve().parent.parent)
        index.setdefault(device, []).append(f"hwmon:{name}")
    return index


def _sources_under(index: dict[str, list[str]], device_dir: Path, *, subtree: bool = True) -> list[str]:
    """Return every hwmon source at or below a device path.

    Args:
        index: The map built by `_hwmon_index`.
        device_dir: The device to look under.
        subtree: When False, only an exact match counts. A PCI bridge sits
            above many devices, so a subtree match would credit the bridge with
            every sensor below it, which is true but useless.

    Returns:
        The sorted names of the hwmon sources.
    """
    root = str(device_dir.resolve())
    found: list[str] = []
    for path, names in index.items():
        if path == root or (subtree and path.startswith(root + "/")):
            found.extend(names)
    return sorted(set(found))


# Sensor sources that are not hwmon, keyed by the PCI vendor of the device.
PCI_VENDOR_SOURCES = {
    ("0x10de", "gpu"): ["nvml (nvidia-ml-py)", "nvidia-smi"],
}

PCI_CLASS_KINDS = {
    "0300": "gpu",
    "0302": "gpu",
    "0403": "audio",
    "0108": "storage",
    "0200": "network",
    "0280": "network",
    "0c03": "usb",
    "0604": "bridge",
    "0600": "host-bridge",
    "0500": "memory-controller",
    "0c05": "smbus",
    "1180": "signal-processing",
}


def collect_pci(hwmon_by_device: dict[str, list[str]]) -> list[Component]:
    """List every PCI device, with its class, driver and known sensor sources."""
    components: list[Component] = []
    pci_root = SYS / "bus" / "pci" / "devices"
    if not pci_root.is_dir():
        return components

    verbose = _run(["lspci", "-nn"])
    names: dict[str, str] = {}
    for line in verbose.splitlines():
        match = re.match(r"^(\S+)\s+(.*)$", line)
        if match:
            names[f"0000:{match[1]}"] = match[2]

    for device_dir in sorted(pci_root.iterdir()):
        address = device_dir.name
        pci_class = (_read(device_dir / "class") or "0x000000")[2:6]
        kind = PCI_CLASS_KINDS.get(pci_class, "other")
        vendor = _read(device_dir / "vendor") or ""
        # A bridge is credited only with a sensor of its own, never with the
        # sensors of the devices below it.
        sources = _sources_under(hwmon_by_device, device_dir, subtree=kind not in {"bridge", "host-bridge"})
        sources += PCI_VENDOR_SOURCES.get((vendor, kind), [])
        components.append(
            Component(
                bus="pci",
                address=address,
                name=names.get(address, "unknown"),
                driver=_driver_of(device_dir),
                kind=kind,
                sensor_sources=sources,
                notes={"class": pci_class, "vendor": vendor},
            )
        )
    return components


def collect_i2c(hwmon_by_device: dict[str, list[str]]) -> list[Component]:
    """List every I2C bus and every client the kernel has bound on it."""
    components: list[Component] = []
    i2c_root = SYS / "bus" / "i2c" / "devices"
    if not i2c_root.is_dir():
        return components

    for entry in sorted(i2c_root.iterdir()):
        if entry.name.startswith("i2c-"):
            components.append(
                Component(
                    bus="i2c-adapter",
                    address=entry.name,
                    name=_read(entry / "name") or "unknown",
                    kind="bus",
                )
            )
        else:
            components.append(
                Component(
                    bus="i2c",
                    address=entry.name,
                    name=_read(entry / "name") or "unknown",
                    driver=_driver_of(entry),
                    kind="i2c-client",
                    sensor_sources=_sources_under(hwmon_by_device, entry),
                )
            )
    return components


def collect_usb() -> list[Component]:
    """List every USB device, taken from the sysfs USB tree."""
    components: list[Component] = []
    usb_root = SYS / "bus" / "usb" / "devices"
    if not usb_root.is_dir():
        return components

    for entry in sorted(usb_root.iterdir()):
        vendor = _read(entry / "idVendor")
        if vendor is None:  # an interface, not a device
            continue
        product = _read(entry / "idProduct") or "????"
        components.append(
            Component(
                bus="usb",
                address=entry.name,
                name=f"{_read(entry / 'manufacturer') or '?'} {_read(entry / 'product') or '?'}".strip(),
                driver=_driver_of(entry),
                kind="usb",
                notes={"id": f"{vendor}:{product}", "speed": _read(entry / "speed") or "?"},
            )
        )
    return components


def collect_hid() -> list[Component]:
    """List every HID device, with the battery node when it has one."""
    components: list[Component] = []
    hid_root = SYS / "bus" / "hid" / "devices"
    if not hid_root.is_dir():
        return components

    for entry in sorted(hid_root.iterdir()):
        uevent = _read(entry / "uevent") or ""
        name = next((line.split("=", 1)[1] for line in uevent.splitlines() if line.startswith("HID_NAME=")), "unknown")
        sources = [f"power_supply:{supply.name}" for supply in sorted(entry.glob("power_supply/*")) if supply.is_dir()]
        components.append(
            Component(
                bus="hid", address=entry.name, name=name, driver=_driver_of(entry), kind="hid", sensor_sources=sources
            )
        )
    return components


def collect_block() -> list[Component]:
    """List every whole block device that is not a partition or a loop device."""
    components: list[Component] = []
    block_root = SYS / "class" / "block"
    if not block_root.is_dir():
        return components

    for entry in sorted(block_root.iterdir()):
        if (entry / "partition").exists() or entry.name.startswith(("loop", "ram", "dm-")):
            continue
        model = _read(entry / "device" / "model")
        sources = ["nvme-cli:smart-log", "smartctl"] if entry.name.startswith("nvme") else ["smartctl"]
        components.append(
            Component(
                bus="block",
                address=entry.name,
                name=model or entry.name,
                kind="storage",
                sensor_sources=sources,
                notes={"size_gb": f"{int(_read(entry / 'size') or 0) * 512 / 1e9:.1f}"},
            )
        )
    return components


def collect_drm() -> list[Component]:
    """List every DRM connector and say whether a display is attached."""
    components: list[Component] = []
    drm_root = SYS / "class" / "drm"
    if not drm_root.is_dir():
        return components

    for entry in sorted(drm_root.iterdir()):
        status = _read(entry / "status")
        if status is None:
            continue
        components.append(
            Component(
                bus="drm",
                address=entry.name,
                name=f"connector {entry.name}",
                kind="display-connector",
                sensor_sources=["ddcutil"] if status == "connected" else [],
                notes={"status": status, "enabled": _read(entry / "enabled") or "?"},
            )
        )
    return components


def collect_net() -> list[Component]:
    """List every physical network interface. Virtual interfaces are skipped."""
    components: list[Component] = []
    net_root = SYS / "class" / "net"
    if not net_root.is_dir():
        return components

    for entry in sorted(net_root.iterdir()):
        if not (entry / "device").exists():
            continue
        sources = [f"sysfs:/sys/class/net/{entry.name}/statistics"]
        sources += _sources_under(_hwmon_index(), entry / "device")
        if (entry / "wireless").exists() or (entry / "phy80211").exists():
            sources.append("proc:/proc/net/wireless (signal quality)")
        components.append(
            Component(
                bus="net",
                address=entry.name,
                name=_read(entry / "device" / "modalias") or entry.name,
                driver=_driver_of(entry / "device"),
                kind="network",
                sensor_sources=sources,
                notes={"state": _read(entry / "operstate") or "?", "mac": _read(entry / "address") or "?"},
            )
        )
    return components


def collect_dmi_memory() -> list[Component]:
    """List every fitted memory module, from the DMI data in the last root probe."""
    components: list[Component] = []
    probes = sorted((Path(__file__).parents[2] / "data" / "probes").glob("root-probe-*/dmidecode-memory.txt"))
    if not probes:
        logger.warning("no dmidecode-memory.txt in data/probes; run scripts/root-probe.sh")
        return components

    blocks = probes[-1].read_text().split("Memory Device")
    for block in blocks[1:]:
        fields = dict(
            (key.strip(), value.strip())
            for key, _, value in (line.partition(":") for line in block.splitlines())
            if value
        )
        if fields.get("Size", "No Module Installed") == "No Module Installed":
            continue
        locator = fields.get("Locator", "?")
        # DDR5 puts the SPD hub of slot n at 0x50 + n and the PMIC at 0x48 + n.
        slot_index = {"DIMMA1": 0, "DIMMA2": 1, "DIMMB1": 2, "DIMMB2": 3}.get(locator)
        sources = []
        if slot_index is not None:
            sources.append(f"hwmon:spd5118 at i2c 0-00{0x50 + slot_index:02x}")
            sources.append(f"i2c:PMIC at 0-00{0x48 + slot_index:02x} (read only, never write)")
        components.append(
            Component(
                bus="dmi",
                address=locator,
                name=f"{fields.get('Part Number', '?')} {fields.get('Size', '?')} {fields.get('Type', '?')}",
                kind="dimm",
                sensor_sources=sources,
                notes={
                    "rated": fields.get("Speed", "?"),
                    "configured": fields.get("Configured Memory Speed", "?"),
                    "voltage": fields.get("Configured Voltage", "?"),
                    "rank": fields.get("Rank", "?"),
                },
            )
        )
    return components


def collect_cpu() -> list[Component]:
    """Add the CPU package as one component, with its known sensor sources."""
    model = "unknown"
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            model = line.split(":", 1)[1].strip()
            break
    return [
        Component(
            bus="cpu",
            address="socket-0",
            name=model,
            driver=_read(Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver")),
            kind="cpu",
            sensor_sources=[
                "hwmon:k10temp",
                "powercap:intel-rapl:0 (package, needs root)",
                "powercap:intel-rapl:0:0 (core 0 only, needs root)",
                "sysfs:/sys/devices/system/cpu/cpu*/cpufreq",
                "turbostat (needs root)",
            ],
        )
    ]


def main() -> None:
    """Run every collector and write the census."""
    hwmon_by_device = _hwmon_index()
    components: list[Component] = []
    components += collect_cpu()
    components += collect_dmi_memory()
    components += collect_pci(hwmon_by_device)
    components += collect_i2c(hwmon_by_device)
    components += collect_usb()
    components += collect_hid()
    components += collect_block()
    components += collect_drm()
    components += collect_net()

    with_sensors = [c for c in components if c.sensor_sources]
    logger.info("found %d components, %d with a known sensor source", len(components), len(with_sensors))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "component_count": len(components),
        "with_known_sensor_source": len(with_sensors),
        "components": [asdict(c) for c in components],
    }
    (RESULTS_DIR / "census.json").write_text(json.dumps(payload, indent=2))
    logger.info("wrote %s", RESULTS_DIR / "census.json")


if __name__ == "__main__":
    main()
