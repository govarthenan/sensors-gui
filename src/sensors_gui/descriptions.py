"""What each channel measures, in plain sentences, with the source of each fact.

`docs/gui-goal.md` section 4.2 asks for a tooltip on every value, and asks
for its text to live in the Python model, next to the spec, so the terminal
screen and the GUI share it. This module is that text.

**Every sentence here is a hardware fact, and every fact has a source** under
`docs/`, `lab/` or `data/`, named in `sources`. `tests/test_descriptions.py`
checks each source is a file in this repository. Where the machine gives no
answer, the text says "not established" and the question is in
`state/STATUS.md`. Nothing here is guessed.

The graphics card is described first, at checkpoint 3, because it is the
reference for every other group. A channel of another group has no
description yet, and `describe` returns None for it, never a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sensors_gui.model import Group, SensorSpec

NOT_ESTABLISHED = "not established"

# The sources, named once. Each is a file in this repository.
NVIDIA_HELP = "data/evidence/nvidia-field-descriptions-2026-09-23/nvidia-smi-help-query-gpu.txt"
NVIDIA_QUERY = "data/probes/2026-09-23-nvidia-smi-q.txt"
EXP_0002 = "lab/exp-0002-nvidia-access/README.md"
EXP_0006 = "lab/exp-0006-nvml-read-cost/README.md"
EXP_0013 = "lab/exp-0013-rtx4090-board-sensors/README.md"
EXP_0016 = "lab/exp-0016-nvml-new-channels/README.md"
NVML_BINDING = "data/evidence/nvml-binding-2026-09-23/pynvml-extracts.txt"
ADR_0003 = "docs/decisions/0003-use-nvml-for-the-nvidia-gpu.md"
ADR_0011 = "docs/decisions/0011-no-i2c-route-to-the-graphics-card.md"
INVENTORY = "docs/hardware-inventory.md"
PHYSICAL_BUILD = "docs/physical-build.md"
SCHEMATIC = "data/evidence/rtx4090-suprim-layout-2026-09-23/scribd-ms-v510-schematic-extract.txt"
LABEL_PHOTO = "docs/photos/06-gpu-backplate-label.jpg"
COLLECTOR = "src/sensors_gui/collectors/nvidia.py"


@dataclass(frozen=True, slots=True)
class Description:
    """The text of one tooltip, apart from the live parts.

    The live parts — the value, the safe range, the read interval and the age
    — come from the spec and the frame, so they are never written here.

    Attributes:
        measures: What the channel measures, in one or two plain sentences.
        call: The driver call or path the value is read with.
        neighbours: How it differs from the channels next to it, or an empty
            string when nothing next to it could be confused with it.
        sources: The files in this repository the sentences rest on.
    """

    measures: str
    call: str
    neighbours: str
    sources: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Return the description as the front end receives it."""
        return {
            "measures": self.measures,
            "call": self.call,
            "neighbours": self.neighbours,
            "sources": list(self.sources),
        }


@dataclass(frozen=True, slots=True)
class Missing:
    """A value a person would expect on this part, which the application does not show.

    Attributes:
        label: The name a person would look for.
        group: The part of the machine it belongs to.
        reason: Why it is not shown, in one sentence.
        sources: The files in this repository the reason rests on.
    """

    label: str
    group: Group
    reason: str
    sources: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Return the entry as the front end receives it."""
        return {
            "label": self.label,
            "group": str(self.group),
            "reason": self.reason,
            "sources": list(self.sources),
        }


# --- the graphics card ---------------------------------------------------------

_EDGE_NEIGHBOURS = (
    "It is the only temperature this card gives: NVML refuses every other sensor index. "
    "The hotspot, memory (GDDR6X) and VRM temperatures are not readable on this machine, because the card's "
    "board controller holds them behind I2C, and an I2C read writes a register pointer first, which ADR 0011 "
    "forbids. The card slows its clocks at 99 °C, shuts down at 104 °C, and reports a target temperature of 84 °C."
)

_CARD: dict[str, Description] = {
    "temperature": Description(
        measures=(
            "The temperature of the graphics chip. NVIDIA names it the core GPU temperature; this application "
            "calls it the edge sensor, to keep it apart from the hotspot sensor the card does not report."
        ),
        call="nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)",
        neighbours=_EDGE_NEIGHBOURS,
        sources=(NVIDIA_HELP, NVIDIA_QUERY, EXP_0002, EXP_0013, ADR_0011),
    ),
    "power": Description(
        measures=(
            "The power drawn by the entire graphics card. NVIDIA states that on Ampere or newer cards the value "
            "is the average over 1 second, accurate to within 5 W; this card reports itself as Ada Lovelace."
        ),
        call="nvmlDeviceGetPowerUsage(handle)",
        neighbours=(
            "The scale runs to the enforced power limit, 480 W: the card's power management keeps the board under "
            "it. This application only reads the limit. This is the card alone; the power of the whole machine "
            "cannot be measured, because the NZXT C1200 has no telemetry link."
        ),
        sources=(NVIDIA_HELP, NVIDIA_QUERY, PHYSICAL_BUILD),
    ),
    "energy": Description(
        measures="The energy the card has used since the driver was last loaded. The counter only grows.",
        call="nvmlDeviceGetTotalEnergyConsumption(handle)",
        neighbours=(
            "GPU power is a rate; this is a total. The call costs about 3 ms, so it is read once a second, "
            "not on every pass."
        ),
        sources=(EXP_0002, EXP_0006),
    ),
    "fan_speed": Description(
        measures=(
            "The speed the card asks of fan 1, as a percent of the product's maximum noise-tolerance speed. It is "
            "the intended speed, not the measured one, and it can exceed 100 %."
        ),
        call="nvmlDeviceGetFanSpeed(handle)",
        neighbours=(
            "This is the original single fan channel, and it reports fan 1 only. GPU fan 1 duty reads the same "
            "fan through the call for each fan. Both are kept, on Gova's decision of 2026-09-22."
        ),
        sources=(NVIDIA_HELP, EXP_0013, COLLECTOR),
    ),
    "utilization": Description(
        measures=(
            "The percent of time in the last sample period during which one or more kernels ran on the graphics "
            "chip. The period is between 1/6 s and 1 s, depending on the product."
        ),
        call="nvmlDeviceGetUtilizationRates(handle).gpu",
        neighbours=(
            "It measures time, not how much of the chip was busy: by this definition one small kernel that runs "
            "all the time reads 100 %."
        ),
        sources=(NVIDIA_HELP,),
    ),
    "memory_utilization": Description(
        measures=(
            "The percent of time in the last sample period during which the card's memory was being read or written."
        ),
        call="nvmlDeviceGetUtilizationRates(handle).memory",
        neighbours="It is how busy the memory bus was, not how full the memory is. VRAM used gives how full.",
        sources=(NVIDIA_HELP,),
    ),
    "memory_used": Description(
        measures="The card memory allocated by active contexts, read with the version 2 memory structure.",
        call="nvmlDeviceGetMemoryInfo(handle, version=nvmlMemory_v2).used",
        neighbours=(
            "The scale is the card's total memory, 24564 MiB. VRAM reserved is kept apart: the version 1 "
            "structure counts it as used, and then disagrees with every other tool by about 500 MiB."
        ),
        sources=(NVIDIA_HELP, INVENTORY, EXP_0002, ADR_0003),
    ),
    "memory_reserved": Description(
        measures="The card memory reserved by the NVIDIA driver and firmware.",
        call="nvmlDeviceGetMemoryInfo(handle, version=nvmlMemory_v2).reserved",
        neighbours="About 503 MiB on this card. It is not part of VRAM used.",
        sources=(NVIDIA_HELP, EXP_0002, ADR_0003),
    ),
    "clock_sm": Description(
        measures="The current frequency of the SM (streaming multiprocessor) clock.",
        call="nvmlDeviceGetClockInfo(handle, NVML_CLOCK_SM)",
        neighbours=(
            "The scale runs to the card's maximum SM clock, 3165 MHz. At idle the card drops it to about 210 MHz."
        ),
        sources=(NVIDIA_HELP, NVIDIA_QUERY, EXP_0002),
    ),
    "clock_memory": Description(
        measures="The current frequency of the memory clock.",
        call="nvmlDeviceGetClockInfo(handle, NVML_CLOCK_MEM)",
        neighbours=(
            "The scale runs to the card's maximum memory clock, 10501 MHz, read once when the application starts. "
            "At idle the card drops it to about 405 MHz."
        ),
        sources=(NVIDIA_HELP, NVIDIA_QUERY, EXP_0016),
    ),
    "clock_event_reasons": Description(
        measures=(
            "Which reasons are holding the card's clocks down now, as a bit field: GPU idle, a software power cap, "
            "a software or hardware thermal slowdown, a hardware power brake, and others. None set means the clocks "
            "run as high as they can."
        ),
        call="nvmlDeviceGetCurrentClocksEventReasons(handle)",
        neighbours=(
            "NVIDIA says a hardware slowdown cuts the core clock by a factor of 2 or more, and the power brake "
            "is set from outside the card, for example by the power supply. At idle only the idle bit is set. "
            "Older tools call these the throttle reasons."
        ),
        sources=(NVIDIA_HELP, NVML_BINDING, NVIDIA_QUERY, EXP_0016),
    ),
    "pcie_link_gen": Description(
        measures="The PCIe generation the card's link runs at now.",
        call="nvmlDeviceGetCurrPcieLinkGeneration(handle)",
        neighbours=(
            "The ceiling is the most this link can run at with this card in this board: PCIe 4.0. The card lowers "
            "the generation when it is not in use, so 1 or 2 at idle is expected. PCIe width is the other half of "
            "the link."
        ),
        sources=(NVIDIA_HELP, NVIDIA_QUERY, EXP_0016),
    ),
    "pcie_link_width": Description(
        measures="The number of PCIe lanes the card's link uses now.",
        call="nvmlDeviceGetCurrPcieLinkWidth(handle)",
        neighbours=(
            "The ceiling is the most lanes this link can use, 16. NVIDIA says the width may be reduced when the "
            "card is not in use. PCIe generation is the other half of the link."
        ),
        sources=(NVIDIA_HELP, NVIDIA_QUERY, EXP_0016),
    ),
    "encoder_utilization": Description(
        measures=(
            "The percent of time in the last sample period during which the video encoder engine, NVENC, was working."
        ),
        call="nvmlDeviceGetEncoderUtilization(handle)",
        neighbours="NVDEC use is the decoder engine, the other half of the pair.",
        sources=(NVIDIA_HELP, EXP_0002),
    ),
    "decoder_utilization": Description(
        measures=(
            "The percent of time in the last sample period during which the video decoder engine, NVDEC, was working."
        ),
        call="nvmlDeviceGetDecoderUtilization(handle)",
        neighbours="NVENC use is the encoder engine, the other half of the pair.",
        sources=(NVIDIA_HELP, EXP_0002),
    ),
    "pcie_tx": Description(
        measures="The rate at which the card transmits data over its PCIe link.",
        call="nvmlDeviceGetPcieThroughput(handle, NVML_PCIE_UTIL_TX_BYTES)",
        neighbours=(
            "PCIe receive is the other direction. NVML measures the link for about 20 ms on each call, so this "
            "channel is read every 2 s. PCIe generation and PCIe width give the state of the link itself."
        ),
        sources=(EXP_0006, NVIDIA_QUERY),
    ),
    "pcie_rx": Description(
        measures="The rate at which the card receives data over its PCIe link.",
        call="nvmlDeviceGetPcieThroughput(handle, NVML_PCIE_UTIL_RX_BYTES)",
        neighbours=(
            "PCIe transmit is the other direction. NVML measures the link for about 20 ms on each call, so this "
            "channel is read every 2 s."
        ),
        sources=(EXP_0006, NVIDIA_QUERY),
    ),
    "performance_state": Description(
        measures=("The current performance state of the card, from P0, the maximum performance, to P12, the minimum."),
        call="nvmlDeviceGetPerformanceState(handle)",
        neighbours="A lower number is a faster state. At idle this card sits in P8.",
        sources=(NVIDIA_HELP, NVIDIA_QUERY),
    ),
    "graphics_processes": Description(
        measures="The number of processes that hold a graphics context on the card.",
        call="nvmlDeviceGetGraphicsRunningProcesses(handle)",
        neighbours=(
            "Both monitors run from this card, so the desktop itself is always on this list: on 2026-09-23 it "
            "held Xorg, cinnamon, VS Code and Chrome. Walking the list costs more than a plain read, so it is read "
            "once a second."
        ),
        sources=(INVENTORY, NVIDIA_QUERY, EXP_0006),
    ),
    "compute_processes": Description(
        measures="The number of processes that hold a compute context on the card.",
        call="nvmlDeviceGetComputeRunningProcesses(handle)",
        neighbours=(
            "Graphics processes counts the other kind of context. On 2026-09-23 no process held a compute "
            "context. Read once a second."
        ),
        sources=(NVIDIA_QUERY, EXP_0006),
    ),
}

_FAN_PATTERN = re.compile(r"^fan(?P<index>\d+)_(?P<kind>rpm|percent)$")

# exp-0013: NVML reports 2 fans on this card. A text that names "the other
# fan" is only true for these two, so a third fan gets no description.
_CARD_FANS = 2


def _fan(index: int, kind: str) -> Description | None:
    """Return the description of one fan channel, or None for a fan this card does not have."""
    if index >= _CARD_FANS:
        return None
    number, other = index + 1, 2 - index
    where = (
        "The card has one fan and its radiator two; the card's board, MS-V510, has two fan headers, A and B, one "
        f"on each GPU fan channel. Which fans channel {number} drives is {NOT_ESTABLISHED}."
    )
    if kind == "rpm":
        return Description(
            measures=f"The measured speed of fan {number} of the graphics card, in revolutions per minute.",
            call=f"nvmlDeviceGetFanSpeedRPM(handle, fan={index})",
            neighbours=(
                f"NVML reports 2 fans on this card, and they do not turn at the same speed: exp-0013 measured "
                f"1205 and 1520 RPM under one load. GPU fan {other} is the other one. Both stop at idle. "
                f"GPU fan {number} duty is what the card asks of this fan; this is what the fan does. {where}"
            ),
            sources=(EXP_0013, COLLECTOR, SCHEMATIC, LABEL_PHOTO, PHYSICAL_BUILD),
        )
    return Description(
        measures=(
            f"The speed the card asks of fan {number}, as a percent of the product's maximum noise-tolerance "
            f"speed. It can exceed 100 %."
        ),
        call=f"nvmlDeviceGetFanSpeed_v2(handle, {index})",
        neighbours=(
            f"GPU fan {number} gives the measured speed. NVIDIA says that when a fan is blocked, the intended "
            f"speed and the measured one do not agree, so the two are shown together. {where}"
        ),
        sources=(NVIDIA_HELP, EXP_0013, COLLECTOR, SCHEMATIC, LABEL_PHOTO, PHYSICAL_BUILD),
    )


def describe(spec: SensorSpec) -> Description | None:
    """Return the description of one channel, or None when it has none yet.

    Args:
        spec: The channel. It is matched on its identity, which the naming
            layer never changes, and not on its label.

    Returns:
        The description, or None. None is an honest answer: the tooltip then
        says the channel is not described yet, and nothing is guessed.
    """
    if spec.id.source != "nvidia":
        return None
    matched = _FAN_PATTERN.match(spec.id.channel)
    if matched:
        return _fan(int(matched["index"]), matched["kind"])
    return _CARD.get(spec.id.channel)


# --- what the application does not show, and why ------------------------------

UNREACHABLE: tuple[Missing, ...] = (
    Missing(
        label="GPU hotspot",
        group=Group.GPU,
        reason=(
            "NVML refuses every temperature sensor but the edge sensor; the board controller holds this one behind "
            "I2C, and an I2C read writes a register pointer first, which ADR 0011 forbids."
        ),
        sources=(EXP_0013, ADR_0011),
    ),
    Missing(
        label="GPU memory (GDDR6X)",
        group=Group.GPU,
        reason="NVML says the memory temperature is not supported on this card, and the only other route is I2C, "
        "which ADR 0011 forbids.",
        sources=(EXP_0002, EXP_0013, ADR_0011),
    ),
    Missing(
        label="GPU VRM",
        group=Group.GPU,
        reason="NVML never gives it, and the only route is I2C to the board controller, which ADR 0011 forbids.",
        sources=(EXP_0013, ADR_0011),
    ),
)

# Q13 is answered: the clock event reasons and the PCIe link are channels now
# (Gova, 2026-09-23). The list stays, empty, so a later group can use it.
NOT_COLLECTED: tuple[Missing, ...] = ()
