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
reference for every other group; the processor and the memory follow at
checkpoint 4. A channel of another group has no description yet, and
`describe` returns None for it, never a guess.
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

# Checkpoint 4: the processor and the memory. The kernel documents are copies
# of tag v7.0, the kernel this machine runs; psutil is the installed 7.2.2.
_CPU_MEM = "data/evidence/cpu-memory-sources-2026-09-23/"
K10TEMP_DOC = _CPU_MEM + "k10temp.rst"
K10TEMP_SOURCE = _CPU_MEM + "k10temp-c-extracts.txt"
SPD5118_DOC = _CPU_MEM + "spd5118.rst"
POWERCAP_DOC = _CPU_MEM + "powercap.rst-extract.txt"
PROC_DOC = _CPU_MEM + "proc-meminfo-loadavg-stat.txt"
CPUFREQ_DOC = _CPU_MEM + "cpufreq.rst-extract.txt"
PSUTIL = _CPU_MEM + "psutil-7.2.2-extracts.txt"
CPU_MEM_PROBE = _CPU_MEM + "probe-cpu-memory-sysfs.txt"
LAYOUT = "data/evidence/ryzen-9900x-package-layout-2026-09-23/README.md"
TOPOLOGY = "data/probes/2026-09-22-cpu-topology.txt"
FREQUENCY_MARGIN = "data/probes/2026-09-23-cpu-frequency-margin.txt"
EXP_0011 = "lab/exp-0011-privileged-helper/README.md"
EXP_0012 = "lab/exp-0012-per-core-energy/README.md"
HELPER = "src/sensors_gui/helper/sensors_guid.py"
SYSTEM_COLLECTOR = "src/sensors_gui/collectors/system.py"
# Memory pressure and page faults, added on Gova's choice of 2026-09-25.
_PRESSURE_SOURCES = "data/evidence/memory-pressure-sources-2026-09-25/"
PSI_DOC = _PRESSURE_SOURCES + "psi.rst"
FAULT_DOC = _PRESSURE_SOURCES + "page-fault-counters.txt"
PRESSURE_PROBE = _PRESSURE_SOURCES + "probe-this-machine.txt"
PRESSURE_COLLECTOR = "src/sensors_gui/collectors/memory_pressure.py"


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


# --- the processor --------------------------------------------------------------

# From the topology probe: the kernel numbers the cores 0-5 on die 1 and 8-13
# on die 2, and a thread's sibling is 12 away.
_DIE_CORES = {1: (0, 1, 2, 3, 4, 5), 2: (8, 9, 10, 11, 12, 13)}
_THREADS = 24
_SIBLING_STEP = 12


def _die_of_core(core: int) -> int | None:
    """Return the die a kernel core number is on, or None for a number this processor does not have."""
    for die, cores in _DIE_CORES.items():
        if core in cores:
            return die
    return None


def _core_of_thread(thread: int) -> int:
    """Return the kernel core number of one thread, from the topology probe's pairs."""
    position = thread % _SIBLING_STEP
    return (*_DIE_CORES[1], *_DIE_CORES[2])[position]


_TEMPERATURES: dict[str, Description] = {
    "temp1": Description(
        measures=(
            "The processor's temperature control value, Tctl. AMD's own words, quoted by the kernel: it is used by "
            "the platform to control cooling systems, and it is not an actual physical temperature."
        ),
        call="k10temp, temp1_input",
        neighbours=(
            "Tccd1 and Tccd2 are temperatures of the two core dies; Tctl is not the temperature of a place. The "
            "kernel documentation says Tdie is the real measured temperature and Tctl is used for fan control. "
            "The driver subtracts an offset from Tctl only on a few older processors, and its table has no entry "
            "for this one (family 0x1a), so the value is shown as the processor gives it. k10temp on this machine "
            "publishes no maximum and no critical threshold for Tctl, so no state is judged. The BIOS fan curve "
            "names its source CPU Core; whether that is Tctl is not established."
        ),
        sources=(K10TEMP_DOC, K10TEMP_SOURCE, _CPU_MEM + "FINDINGS.md", CPU_MEM_PROBE, INVENTORY),
    ),
}
for _die in (1, 2):
    _first, _last = _DIE_CORES[_die][0], _DIE_CORES[_die][-1]
    _TEMPERATURES[f"temp{_die + 2}"] = Description(
        measures=f"The temperature of core die {_die} (CCD {_die}), from the processor's own sensor for that die.",
        call=f"k10temp, temp{_die + 2}_input",
        neighbours=(
            f"Core die {_die} holds cores {_first}-{_last}. There is no temperature for each core: k10temp gives "
            f"one for each die, and Tctl. Tccd{3 - _die} is the other die. Tctl is a control value, not the "
            "temperature of a place. The driver's register map for these sensors is not confirmed from AMD's "
            "datasheets, its own source says. k10temp publishes no threshold, so no state is judged."
        ),
        sources=(K10TEMP_DOC, K10TEMP_SOURCE, TOPOLOGY, CPU_MEM_PROBE),
    )

_RAPL: dict[tuple[str, str], Description] = {
    ("package-0", "power"): Description(
        measures=(
            "The power of the whole processor package, from the RAPL package energy counter: the rise of the "
            "counter, divided by the time between two reads."
        ),
        call="/sys/class/powercap/intel-rapl:0/energy_uj, read by sensors-guid once a second",
        neighbours=(
            "CPU Cores Power is the 12 cores alone; the package is more, because it is the whole package and not "
            "only its cores. exp-0012 measured the cores at 17.8 % of the package at idle and 66.1 % under an "
            "all-core load. The board declares no RAPL power limit, so there is no scale and no state."
        ),
        sources=(POWERCAP_DOC, EXP_0011, EXP_0012, HELPER),
    ),
    ("package-0", "energy"): Description(
        measures="The RAPL energy counter of the whole processor package. It only grows, and wraps at its range.",
        call="/sys/class/powercap/intel-rapl:0/energy_uj",
        neighbours="CPU Package Power is the rate of this counter. The helper reads the counter once a second.",
        sources=(POWERCAP_DOC, EXP_0011, HELPER),
    ),
    ("package-0.core", "power"): Description(
        measures=("The power of the RAPL core domain. On this processor that domain is core 0 alone, not every core."),
        call="/sys/class/powercap/intel-rapl:0:0/energy_uj, read by sensors-guid once a second",
        neighbours=(
            "CPU Core 0 Power reads the same core from its own energy register, and the two agreed to 0.001 W "
            "(exp-0012). exp-0011 found this domain follows core 0 and not the twelve cores: 1.69 W against 22.8 "
            "to 28.0 W for all of them. The per-core register channels give every core."
        ),
        sources=(POWERCAP_DOC, EXP_0011, EXP_0012, HELPER),
    ),
    ("package-0.core", "energy"): Description(
        measures="The RAPL energy counter of the core domain, which is core 0 alone on this processor.",
        call="/sys/class/powercap/intel-rapl:0:0/energy_uj",
        neighbours="CPU Core 0 (RAPL) Power is the rate of this counter.",
        sources=(POWERCAP_DOC, EXP_0011, HELPER),
    ),
    ("cpu-cores", "power"): Description(
        measures="The sum of the power of the 12 cores, each from its own energy register.",
        call="MSR 0xc001029a on /dev/cpu/N/msr, one read for each core, by sensors-guid; read only",
        neighbours=(
            "CPU Package Power is the whole package; this is the cores alone. Under an all-core load exp-0012 "
            "measured 103.98 W here against 104.10 W from turbostat."
        ),
        sources=(EXP_0012, HELPER),
    ),
}


def _core_power(core: int) -> Description | None:
    """Return the description of one core's power, or None for a core this processor does not have."""
    die = _die_of_core(core)
    if die is None:
        return None
    first_thread = (*_DIE_CORES[1], *_DIE_CORES[2]).index(core)
    second = first_thread + _SIBLING_STEP
    return Description(
        measures=(
            f"The power of core {core}, from its own energy counter: the rise of the counter, divided by the time "
            "between two reads."
        ),
        call=f"MSR 0xc001029a on /dev/cpu/{first_thread}/msr, by sensors-guid once a second; read only",
        neighbours=(
            f"Core {core} is on die {die}, and its threads are cpu{first_thread} and cpu{second}. The register "
            "gives one counter for each core: in exp-0012 one busy thread moved one counter and no other. No "
            "limit for one core is published, so there is no scale."
            + (" CPU Core 0 (RAPL) Power reads the same core another way." if core == 0 else "")
        ),
        sources=(EXP_0012, TOPOLOGY, HELPER),
    )


def _thread(thread: int, kind: str) -> Description | None:
    """Return the description of one thread's use or frequency, or None for a thread this processor lacks."""
    if not 0 <= thread < _THREADS:
        return None
    core = _core_of_thread(thread)
    sibling = thread + _SIBLING_STEP if thread < _SIBLING_STEP else thread - _SIBLING_STEP
    die = _die_of_core(core)
    pair = f"cpu{thread} and cpu{sibling} are the two threads of core {core}, on die {die}."
    if kind == "percent":
        return Description(
            measures=(
                f"The share of time thread cpu{thread} was busy since the last read, from the kernel's CPU time "
                "counters in /proc/stat."
            ),
            call="psutil.cpu_percent(percpu=True)",
            neighbours=(
                f"CPU{thread} is a thread, not a core: {pair} CPU use is all 24 threads together. The frequency "
                f"of this thread is CPU{thread} frequency."
            ),
            sources=(PSUTIL, PROC_DOC, TOPOLOGY, SYSTEM_COLLECTOR),
        )
    return Description(
        measures=(
            f"The frequency of thread cpu{thread}, as the kernel reports it in scaling_cur_freq. The kernel "
            "documentation says this is in most cases the frequency last requested from the hardware, and may not "
            "be the frequency the processor runs at."
        ),
        call=f"psutil.cpu_freq(percpu=True), from /sys/devices/system/cpu/cpu{thread}/cpufreq/scaling_cur_freq",
        neighbours=(
            f"{pair} The scale runs from the lowest frequency the processor can run at, cpuinfo_min_freq "
            "(613.954 MHz), to scaling_max_freq (5662.016 MHz, the same as cpuinfo_max_freq here). The reading "
            "passed the top by up to 2.23 % in 28 800 readings."
        ),
        sources=(CPUFREQ_DOC, PSUTIL, CPU_MEM_PROBE, FREQUENCY_MARGIN, TOPOLOGY, SYSTEM_COLLECTOR),
    )


_CPU_SYSTEM: dict[str, Description] = {
    "percent": Description(
        measures="The share of time all 24 threads together were busy since the last read.",
        call="psutil.cpu_percent()",
        neighbours="CPU0 use to CPU23 use give each thread; this is all of them in one figure.",
        sources=(PSUTIL, PROC_DOC, SYSTEM_COLLECTOR),
    ),
}
for _minutes, _name in ((1, "load1"), (5, "load5"), (15, "load15")):
    _CPU_SYSTEM[_name] = Description(
        measures=f"The load average of the last {_minutes} minutes, as the kernel gives it in /proc/loadavg.",
        call="os.getloadavg(), which psutil uses as it is",
        neighbours=(
            "The three load averages cover 1, 5 and 15 minutes. It is a count, not a percent, so it has no scale; "
            "this processor has 24 threads."
        ),
        sources=(PROC_DOC, PSUTIL, TOPOLOGY),
    )


# --- the memory -----------------------------------------------------------------

_DIMMS = {"0-0051": "A2", "0-0053": "B2"}


def _dimm(hub: str) -> Description | None:
    """Return the description of one module's temperature, or None for a hub address not on this board."""
    slot = _DIMMS.get(hub)
    if slot is None:
        return None
    other_hub, other_slot = next((key, value) for key, value in _DIMMS.items() if key != hub)
    return Description(
        measures=(
            f"The temperature of the memory module in slot {slot}, from the SPD5118 sensor on the module (the SPD hub)."
        ),
        call=f"spd5118, i2c {hub}, temp1_input",
        neighbours=(
            f"The module in {slot} is the one at i2c {hub}; DIMM {other_slot} is the other module, at "
            f"{other_hub}. The kernel driver owns the bus; this application only reads what it publishes. "
            "The chip carries a maximum of 55 °C and a critical threshold of 85 °C, which the scale and the "
            "state use. The driver's documentation says these limits can be configured."
        ),
        sources=(SPD5118_DOC, INVENTORY, CPU_MEM_PROBE),
    )


_MEMORY: dict[str, Description] = {
    "total": Description(
        measures="All the memory the kernel can use: the modules' memory less a few reserved parts and the kernel.",
        call="psutil.virtual_memory().total, MemTotal in /proc/meminfo",
        neighbours="Two modules of 32 GB are fitted; the kernel can use this much of them.",
        sources=(PSUTIL, PROC_DOC, INVENTORY),
    ),
    "available": Description(
        measures=(
            "The kernel's estimate of how much memory can be given to new programs without swapping, MemAvailable."
        ),
        call="psutil.virtual_memory().available, MemAvailable in /proc/meminfo",
        neighbours=(
            "It counts free memory and the cache the kernel can take back, so it is much more than Memory free. "
            "Memory used is Memory total less this."
        ),
        sources=(PSUTIL, PROC_DOC),
    ),
    "used": Description(
        measures="Memory total less Memory available: the memory the kernel cannot give to a new program now.",
        call="psutil.virtual_memory().used, total - available",
        neighbours=(
            "psutil 7.2.2 on Linux computes it as total less available, not total less free. So used, free and "
            "cached do not add up to the total: cached memory is partly in available."
        ),
        sources=(PSUTIL, PROC_DOC),
    ),
    "percent": Description(
        measures="Memory used as a percent of Memory total.",
        call="psutil.virtual_memory().percent, (total - available) / total",
        neighbours="The same figure as Memory used, on a scale of 0 to 100.",
        sources=(PSUTIL,),
    ),
    "free": Description(
        measures="Memory that holds nothing at all, MemFree.",
        call="psutil.virtual_memory().free, MemFree in /proc/meminfo",
        neighbours=("Memory available is larger, because the kernel can take back cache when a program needs memory."),
        sources=(PSUTIL, PROC_DOC),
    ),
    "cached": Description(
        measures=(
            "The cache for files read from the drive, with tmpfs and shared memory, and the part of the kernel's "
            "own caches it can take back."
        ),
        call="psutil.virtual_memory().cached, Cached plus SReclaimable in /proc/meminfo",
        neighbours="Memory shared is part of it. Much of it is also counted in Memory available.",
        sources=(PSUTIL, PROC_DOC),
    ),
    "buffers": Description(
        measures="Temporary storage for raw blocks of the drive, Buffers.",
        call="psutil.virtual_memory().buffers, Buffers in /proc/meminfo",
        neighbours="The kernel documentation says it should stay small, about 20 MB.",
        sources=(PSUTIL, PROC_DOC),
    ),
    "shared": Description(
        measures="Memory used by shared memory and tmpfs, Shmem.",
        call="psutil.virtual_memory().shared, Shmem in /proc/meminfo",
        neighbours="The kernel counts it inside Cached, so it is also inside Memory cached.",
        sources=(PSUTIL, PROC_DOC),
    ),
}

_NO_SWAP = "On 2026-09-23 SwapTotal read 0 kB: this machine had no swap, and every swap reading was 0."

_SWAP: dict[str, Description] = {
    "total": Description(
        measures="The swap space the kernel has, SwapTotal.",
        call="psutil.swap_memory().total, SwapTotal in /proc/meminfo",
        neighbours=_NO_SWAP,
        sources=(PSUTIL, PROC_DOC, CPU_MEM_PROBE),
    ),
    "used": Description(
        measures="Swap space in use: SwapTotal less SwapFree.",
        call="psutil.swap_memory().used",
        neighbours=_NO_SWAP,
        sources=(PSUTIL, PROC_DOC, CPU_MEM_PROBE),
    ),
    "free": Description(
        measures="Swap space not in use, SwapFree.",
        call="psutil.swap_memory().free, SwapFree in /proc/meminfo",
        neighbours=_NO_SWAP,
        sources=(PSUTIL, PROC_DOC, CPU_MEM_PROBE),
    ),
    "percent": Description(
        measures="Swap used as a percent of Swap total.",
        call="psutil.swap_memory().percent",
        neighbours=_NO_SWAP,
        sources=(PSUTIL, CPU_MEM_PROBE),
    ),
    "sin_rate": Description(
        measures=(
            "The rate at which memory comes back in from swap: the rise of the kernel's pswpin counter between two "
            "reads, in bytes each second."
        ),
        call="psutil.swap_memory().sin, from pswpin in /proc/vmstat",
        neighbours="Swap out is the other direction. " + _NO_SWAP,
        sources=(PSUTIL, SYSTEM_COLLECTOR, CPU_MEM_PROBE),
    ),
    "sout_rate": Description(
        measures=(
            "The rate at which memory goes out to swap: the rise of the kernel's pswpout counter between two "
            "reads, in bytes each second."
        ),
        call="psutil.swap_memory().sout, from pswpout in /proc/vmstat",
        neighbours="Swap in is the other direction. " + _NO_SWAP,
        sources=(PSUTIL, SYSTEM_COLLECTOR, CPU_MEM_PROBE),
    ),
}

_PRESSURE_KIND = {
    "some": "at least one task waited for memory",
    "full": "every task that had work to do waited for memory at the same time",
}


def _pressure(kind: str, window: str) -> Description:
    """Return the description of one memory pressure average."""
    other = "full" if kind == "some" else "some"
    return Description(
        measures=f"The part of the last {window} s in which {_PRESSURE_KIND[kind]}, as a running average in percent.",
        call=f"/proc/pressure/memory, the {kind} line, avg{window}",
        neighbours=(
            f"The {other} line is the other measure: {_PRESSURE_KIND[other]}. "
            "The kernel documentation calls a long time in full thrashing. The 10, 60 and 300 s averages are the "
            "same measure over three windows. Memory use says how much memory is in use; this says whether tasks "
            "had to wait for it. The file can also take a write, to set a trigger; this application only reads it."
        ),
        sources=(PSI_DOC, PRESSURE_PROBE, PRESSURE_COLLECTOR),
    )


_FAULTS: dict[str, Description] = {
    "pgfault_rate": Description(
        measures=(
            "Page faults each second: the rise of the kernel's pgfault counter between two reads. A page fault "
            "occurs when a program uses a page of memory that is not yet mapped for it."
        ),
        call="/proc/vmstat, pgfault",
        neighbours=(
            "Most page faults are minor: the page is already in memory. Major page faults are the part that had to "
            "be read from the drive. The counter includes faults that failed."
        ),
        sources=(FAULT_DOC, PRESSURE_PROBE, PRESSURE_COLLECTOR),
    ),
    "pgmajfault_rate": Description(
        measures=(
            "Major page faults each second: the rise of the kernel's pgmajfault counter between two reads. A major "
            "fault had to read the page from the drive, from a file not in the page cache or from swap."
        ),
        call="/proc/vmstat, pgmajfault",
        neighbours=(
            "Page faults counts all faults, minor and major. A high rate here, with memory pressure above 0, means "
            "the machine reads memory back from the drive."
        ),
        sources=(FAULT_DOC, PRESSURE_PROBE, PRESSURE_COLLECTOR),
    ),
}

_PRESSURE_PATTERN = re.compile(r"^(?P<kind>some|full)_avg(?P<window>10|60|300)$")
_THREAD_PATTERN = re.compile(r"^core(?P<thread>\d+)_(?P<kind>percent|frequency)$")
_CORE_DEVICE_PATTERN = re.compile(r"^cpu-cores\.core-(?P<core>\d+)$")


def _describe_hwmon(spec: SensorSpec) -> Description | None:
    """Return the description of a processor or memory channel read through hwmon, or None."""
    driver, _, path = spec.id.device.partition("@")
    if driver == "k10temp":
        return _TEMPERATURES.get(spec.id.channel)
    if driver == "spd5118" and spec.id.channel == "temp1":
        return _dimm(path.rsplit("/", 1)[-1])
    return None


def _describe_privileged(spec: SensorSpec) -> Description | None:
    """Return the description of a RAPL or core energy channel, or None."""
    matched = _CORE_DEVICE_PATTERN.match(spec.id.device)
    if matched and spec.id.channel == "power":
        return _core_power(int(matched["core"]))
    return _RAPL.get((spec.id.device, spec.id.channel))


def _describe_system(spec: SensorSpec) -> Description | None:
    """Return the description of a processor, memory or swap channel read through psutil, or None."""
    if spec.id.device == "cpu":
        matched = _THREAD_PATTERN.match(spec.id.channel)
        if matched:
            return _thread(int(matched["thread"]), matched["kind"])
        return _CPU_SYSTEM.get(spec.id.channel)
    if spec.id.device == "memory":
        return _MEMORY.get(spec.id.channel)
    if spec.id.device == "swap":
        return _SWAP.get(spec.id.channel)
    return None


def _describe_proc(spec: SensorSpec) -> Description | None:
    """Return the description of a memory pressure or page fault channel, or None."""
    if spec.id.device == "pressure/memory":
        matched = _PRESSURE_PATTERN.match(spec.id.channel)
        return _pressure(matched["kind"], matched["window"]) if matched else None
    if spec.id.device == "vmstat":
        return _FAULTS.get(spec.id.channel)
    return None


def describe(spec: SensorSpec) -> Description | None:
    """Return the description of one channel, or None when it has none yet.

    Args:
        spec: The channel. It is matched on its identity, which the naming
            layer never changes, and not on its label.

    Returns:
        The description, or None. None is an honest answer: the tooltip then
        says the channel is not described yet, and nothing is guessed.
    """
    if spec.id.source == "hwmon":
        return _describe_hwmon(spec)
    if spec.id.source == "privileged":
        return _describe_privileged(spec)
    if spec.id.source == "system":
        return _describe_system(spec)
    if spec.id.source == "proc":
        return _describe_proc(spec)
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

# --- values a view makes from channels, and says so ------------------------------

# Gova, 2026-09-25: the memory view shows one bar, divided into the memory in
# use, the cache the kernel can take back, and the free memory. The middle part
# is no channel; the page makes it from two. Its text lives here, with every
# other tooltip, and the catalogue sends it by this key.
DERIVED: dict[str, Description] = {
    "memory_reclaimable": Description(
        measures=(
            "The memory the kernel can take back for a new program: file cache and other caches it can empty. "
            "It is Memory available less Memory free."
        ),
        call="Memory available - Memory free",
        neighbours=(
            "MemAvailable is the kernel's estimate, from MemFree, SReclaimable, the file lists and the low "
            "watermarks, so this part is an estimate too. Memory cached can be larger: the kernel documentation says "
            "the system needs some page cache to work well, and that not all reclaimable slab can be taken back. "
            "What the estimate leaves out is in Memory used, which is Memory total less Memory available. So Memory "
            "used, this part and Memory free add up to Memory total."
        ),
        sources=(PROC_DOC, PSUTIL),
    ),
}

# Q13 is answered: the clock event reasons and the PCIe link are channels now
# (Gova, 2026-09-23). The list stays, empty, so a later group can use it.
NOT_COLLECTED: tuple[Missing, ...] = ()
