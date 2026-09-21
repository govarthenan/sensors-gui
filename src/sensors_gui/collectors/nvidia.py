"""The NVIDIA collector. It reads the RTX 4090 through NVML.

ADR 0003 fixes three rules, each of which came from a measurement in
`lab/exp-0002-nvidia-access/`:

1. Use NVML, not `nvidia-smi`. NVML costs 0.67 ms for a full sample against
   19.91 ms, and it gives fields that `--query-gpu` does not.
2. Read memory with `nvmlMemory_v2`. The version 1 structure counts about
   500 MiB of driver-reserved memory and disagrees with every other tool.
3. The `*_TLIMIT` fields are headroom in degrees, not temperatures, and in NVML
   `SHUTDOWN = 0` and `SLOWDOWN = 1`, which is the opposite of the order a
   reader expects.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sensors_gui.collectors.cache import ChannelCache
from sensors_gui.model import Group, Reading, SensorId, SensorSpec, Unit

logger = logging.getLogger(__name__)

SOURCE = "nvidia"
MIB = 1024**2
MHZ = 1_000_000
KB = 1000

# The shortest time in seconds between two reads of a channel, from ADR 0006.
# Measured on this machine with 20 rounds per channel:
#   pcie_tx / pcie_rx  20.6 ms each  (NVML samples over a window)
#   energy              3.0 ms
#   fan_speed           0.58 ms
#   everything else     under 0.05 ms
# The two PCIe calls alone took 92 % of a 44.8 ms pass.
CHANNEL_INTERVALS: dict[str, float] = {
    "pcie_tx": 2.0,
    "pcie_rx": 2.0,
    "energy": 1.0,
    "fan_speed": 1.0,
    "graphics_processes": 1.0,
    "compute_processes": 1.0,
}

# NVML enumeration values, written out so that the code does not depend on the
# binding exposing a constant by name.
TEMPERATURE_THRESHOLD_SHUTDOWN = 0
TEMPERATURE_THRESHOLD_SLOWDOWN = 1


@dataclass(slots=True)
class _Channel:
    """One discovered channel, with the call that reads its value."""

    spec: SensorSpec
    read_value: Callable[[], float]


class NvidiaCollector:
    """Read every NVIDIA GPU in this machine through NVML."""

    name = SOURCE

    def __init__(self, library_name: str | None = None) -> None:
        """Create the collector.

        Args:
            library_name: Force a library file name. Only a test uses this, to
                check that a collector which cannot start stays quiet.
        """
        self._library_name = library_name
        self._nvml: Any = None
        self._channels: list[_Channel] = []
        self._cache = ChannelCache()

    def discover(self) -> list[SensorSpec]:
        """Find every GPU and build a channel for each value NVML gives.

        A failure to start NVML is not an error. The collector reports zero
        sensors and stays quiet, as rule 3 of the collector contract requires.
        """
        if self._channels:
            return [channel.spec for channel in self._channels]
        if not self._start():
            return []

        self._channels = []
        try:
            count = self._nvml.nvmlDeviceGetCount()
        except Exception as exc:  # noqa: BLE001 - NVML raises its own error class
            logger.warning("nvidia: cannot count devices: %s", exc)
            return []

        for index in range(count):
            try:
                handle = self._nvml.nvmlDeviceGetHandleByIndex(index)
                self._channels.extend(self._discover_device(handle))
            except Exception as exc:  # noqa: BLE001 - one bad GPU must not stop the rest
                logger.warning("nvidia: skipping device %d: %s", index, exc)

        logger.info("nvidia: found %d channels on %d device(s)", len(self._channels), count)
        return [channel.spec for channel in self._channels]

    def read(self) -> list[Reading]:
        """Read every channel. This never raises.

        An expensive channel is served from the cache between its reads. See
        `CHANNEL_INTERVALS` and ADR 0006.
        """
        return [
            self._cache.serve(channel.spec.id, channel.spec.min_interval, channel.read_value)
            for channel in self._channels
        ]

    def close(self) -> None:
        """Shut NVML down. The channels stay, so that `read` can report the failure."""
        self._cache.forget()
        if self._nvml is not None:
            try:
                self._nvml.nvmlShutdown()
            except Exception as exc:  # noqa: BLE001 - shutting down must not raise
                logger.debug("nvidia: shutdown failed: %s", exc)
            self._nvml = None

    def _start(self) -> bool:
        """Import the binding and start NVML. Return False when that is not possible."""
        if self._nvml is not None:
            return True
        try:
            import pynvml
        except ImportError as exc:
            logger.info("nvidia: the nvidia-ml-py package is not installed: %s", exc)
            return False
        try:
            if self._library_name is not None:
                pynvml.nvmlLib = None
                pynvml.__dict__["NVML_LIB_NAME"] = self._library_name
                raise OSError(f"forced library {self._library_name}")
            pynvml.nvmlInit()
        except Exception as exc:  # noqa: BLE001 - no driver is a normal state, not an error
            logger.info("nvidia: NVML did not start: %s", exc)
            return False
        self._nvml = pynvml
        return True

    def _discover_device(self, handle: Any) -> list[_Channel]:  # noqa: ANN401 - the handle is opaque
        """Build every channel of one GPU."""
        nvml = self._nvml
        bus_id = nvml.nvmlDeviceGetPciInfo(handle).busId
        if isinstance(bus_id, bytes):
            bus_id = bus_id.decode()
        name = nvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode()
        device = f"{name}@{bus_id}"
        logger.info("nvidia: found %s", device)

        memory_total = float(nvml.nvmlDeviceGetMemoryInfo(handle, version=nvml.nvmlMemory_v2).total)
        power_limit = nvml.nvmlDeviceGetEnforcedPowerLimit(handle) / 1000
        max_clock = nvml.nvmlDeviceGetMaxClockInfo(handle, nvml.NVML_CLOCK_SM) * MHZ

        # ADR 0003 rule 3: SHUTDOWN is 0 and SLOWDOWN is 1, so a reader that
        # trusts the order gets a slowdown limit above the shutdown limit.
        slowdown = nvml.nvmlDeviceGetTemperatureThreshold(handle, TEMPERATURE_THRESHOLD_SLOWDOWN)
        shutdown = nvml.nvmlDeviceGetTemperatureThreshold(handle, TEMPERATURE_THRESHOLD_SHUTDOWN)
        warn, critical = float(min(slowdown, shutdown)), float(max(slowdown, shutdown))

        def channel(
            key: str,
            label: str,
            unit: Unit,
            read_value: Callable[[], float],
            **limits: float | None,
        ) -> _Channel:
            """Build one channel of this GPU."""
            return _Channel(
                spec=SensorSpec(
                    id=SensorId(source=SOURCE, device=device, channel=key),
                    label=label,
                    group=Group.GPU,
                    unit=unit,
                    min_interval=CHANNEL_INTERVALS.get(key, 0.0),
                    origin=f"nvml:{key}@{bus_id}",
                    **limits,  # type: ignore[arg-type]
                ),
                read_value=read_value,
            )

        # ADR 0003 rule 2: the version 2 memory structure, always.
        def memory(field: str) -> Callable[[], float]:
            """Return a reader for one field of the version 2 memory structure, in bytes."""
            return lambda: float(getattr(nvml.nvmlDeviceGetMemoryInfo(handle, version=nvml.nvmlMemory_v2), field))

        return [
            channel(
                "temperature",
                "GPU edge",
                Unit.CELSIUS,
                lambda: float(nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)),
                low=0.0,
                high=critical,
                warn=warn,
                critical=critical,
            ),
            channel(
                "power",
                "GPU power",
                Unit.WATT,
                lambda: nvml.nvmlDeviceGetPowerUsage(handle) / 1000,
                low=0.0,
                high=power_limit,
            ),
            channel(
                "energy",
                "GPU energy",
                Unit.JOULE,
                lambda: nvml.nvmlDeviceGetTotalEnergyConsumption(handle) / 1000,
            ),
            channel(
                "fan_speed",
                "GPU fan",
                Unit.PERCENT,
                lambda: float(nvml.nvmlDeviceGetFanSpeed(handle)),
                low=0.0,
                high=100.0,
            ),
            channel(
                "utilization",
                "GPU use",
                Unit.PERCENT,
                lambda: float(nvml.nvmlDeviceGetUtilizationRates(handle).gpu),
                low=0.0,
                high=100.0,
            ),
            channel(
                "memory_utilization",
                "VRAM bus use",
                Unit.PERCENT,
                lambda: float(nvml.nvmlDeviceGetUtilizationRates(handle).memory),
                low=0.0,
                high=100.0,
            ),
            channel("memory_used", "VRAM used", Unit.BYTE, memory("used"), low=0.0, high=memory_total),
            channel("memory_reserved", "VRAM reserved", Unit.BYTE, memory("reserved")),
            channel(
                "clock_sm",
                "SM clock",
                Unit.HERTZ,
                lambda: float(nvml.nvmlDeviceGetClockInfo(handle, nvml.NVML_CLOCK_SM) * MHZ),
                low=0.0,
                high=max_clock,
            ),
            channel(
                "clock_memory",
                "VRAM clock",
                Unit.HERTZ,
                lambda: float(nvml.nvmlDeviceGetClockInfo(handle, nvml.NVML_CLOCK_MEM) * MHZ),
            ),
            channel(
                "encoder_utilization",
                "NVENC use",
                Unit.PERCENT,
                lambda: float(nvml.nvmlDeviceGetEncoderUtilization(handle)[0]),
                low=0.0,
                high=100.0,
            ),
            channel(
                "decoder_utilization",
                "NVDEC use",
                Unit.PERCENT,
                lambda: float(nvml.nvmlDeviceGetDecoderUtilization(handle)[0]),
                low=0.0,
                high=100.0,
            ),
            channel(
                "pcie_tx",
                "PCIe transmit",
                Unit.BYTE_PER_SECOND,
                lambda: float(nvml.nvmlDeviceGetPcieThroughput(handle, nvml.NVML_PCIE_UTIL_TX_BYTES) * KB),
            ),
            channel(
                "pcie_rx",
                "PCIe receive",
                Unit.BYTE_PER_SECOND,
                lambda: float(nvml.nvmlDeviceGetPcieThroughput(handle, nvml.NVML_PCIE_UTIL_RX_BYTES) * KB),
            ),
            channel(
                "performance_state",
                "P-state",
                Unit.COUNT,
                lambda: float(nvml.nvmlDeviceGetPerformanceState(handle)),
            ),
            channel(
                "graphics_processes",
                "Graphics processes",
                Unit.COUNT,
                lambda: float(len(nvml.nvmlDeviceGetGraphicsRunningProcesses(handle))),
            ),
            channel(
                "compute_processes",
                "Compute processes",
                Unit.COUNT,
                lambda: float(len(nvml.nvmlDeviceGetComputeRunningProcesses(handle))),
            ),
        ]
