# Sensor sources

The catalogue of every sensor source found on `dst-gova-pc`. Updated 2026-09-16.

Status values:
- **OK** — the value is readable now, as user `gova`.
- **ROOT** — the value exists but needs root.
- **MISSING** — the hardware has the sensor, but Linux does not expose it yet.
- **TODO** — not yet examined.

## A. hwmon (sysfs) — `/sys/class/hwmon/`

The index `hwmonN` is **not stable** across boots. Always match on the `name`
file, and on the real device path. See ADR 0002.

| Device | Name | Channel | Label | Unit | Status |
|---|---|---|---|---|---|
| hwmon0 | `r8169_0_b00:00` | `temp1` | (none) Ethernet PHY | °C | OK |
| hwmon1 | `nvme` | `temp1` | Composite | °C | OK |
| hwmon1 | `nvme` | `temp2` | Sensor 1 | °C | OK |
| hwmon1 | `nvme` | `temp3` | Sensor 2 | °C | OK |
| hwmon2 | `k10temp` | `temp1` | Tctl | °C | OK |
| hwmon2 | `k10temp` | `temp3` | Tccd1 | °C | OK |
| hwmon2 | `k10temp` | `temp4` | Tccd2 | °C | OK |
| hwmon3 | `spd5118` | `temp1` | DIMM at i2c 0-0051 | °C | OK |
| hwmon4 | `spd5118` | `temp1` | DIMM at i2c 0-0053 | °C | OK |
| hwmon5 | `amdgpu` | `temp1` | edge | °C | OK |
| hwmon5 | `amdgpu` | `in0` | vddgfx | V | OK |
| hwmon5 | `amdgpu` | `in1` | vddnb | V | OK |
| hwmon5 | `amdgpu` | `power1` | PPT | W | OK |
| hwmon5 | `amdgpu` | `freq1` | sclk | Hz | OK |
| hwmon6 | `hidpp_battery_2` | (no channels) | — | — | see section E |

Notes:
- `k10temp` has no `temp2`. Zen 5 gives `Tctl`, and one `Tccd` for each of the
  two CCDs. There is no `Tdie` channel and no current or voltage channel.
- The `spd5118` thresholds (`max` 55 °C, `crit` 85 °C) are set by the module.
- The NVMe `Sensor 1` and `Sensor 2` limits (65261.85 °C) are placeholders from
  the drive firmware. Do not show them.

## B. CPU package power — RAPL

| Path | Contents | Status |
|---|---|---|
| `/sys/class/powercap/intel-rapl:0/energy_uj` | package energy counter, µJ | **ROOT** (mode 0400) |
| `/sys/class/powercap/intel-rapl:0:0/energy_uj` | core domain energy, µJ | **ROOT** |

The name is `intel-rapl` on AMD too. The kernel uses the same powercap
framework. Power in watts = delta(energy) / delta(time). The counter wraps, so
the reader must handle the wrap with `max_energy_range_uj`.

`turbostat` is installed (`/usr/bin/turbostat`) and also needs root.

## C. CPU frequency and state

| Path | Contents | Status |
|---|---|---|
| `/sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq` | current kHz, per thread | OK |
| `/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor` | `performance` | OK |
| `/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver` | `amd-pstate-epp` | OK |
| `/proc/stat` | per core use | OK |
| `/proc/loadavg` | load average | OK |

## D. GPUs

### NVIDIA RTX 4090 — NVML (`nvidia-ml-py`)

Decided in ADR 0003 after `exp-0002`, and built on 2026-09-21. All fields
read as a normal user. A warmed pass of all 17 channels costs **0.023 ms**.
See `exp-0006` for why the two PCIe channels need their own interval.

Collector: `sensors_gui/collectors/nvidia.py`. 17 channels, 89 tests pass.

| Field | Unit | Status | Note |
|---|---|---|---|
| GPU temperature (edge) | °C | OK | |
| Power draw | W | OK | limit 480 W |
| Total energy counter | J | OK | since the driver loaded |
| Fan speed | % | OK | 2 fans; both report one value |
| GPU / memory use | % | OK | |
| Memory used / total | MiB | OK | **use `nvmlMemory_v2`**, see ADR 0003 |
| Memory reserved | MiB | OK | v2 only, about 503 MiB |
| SM / memory clock | MHz | OK | maximum SM clock 3165 MHz |
| PCIe generation / width | — | OK | drops to gen 1 at idle |
| PCIe transmit / receive | kB/s | OK | |
| Encoder / decoder use | % | OK | NVENC, NVDEC |
| Performance state | P-state | OK | |
| Throttle reasons | bit field | OK | |
| BAR1 memory | MiB | OK | |
| Compute / graphics processes | count | OK | |
| VBIOS version | text | OK | 95.02.3C.40.D1 |
| Temperature thresholds | °C | OK | 99 °C slowdown, 104 °C shutdown |
| **Hotspot temperature** | °C | **MISSING** | NVML says "Invalid Argument" |
| **Memory (GDDR6X) temperature** | °C | **MISSING** | NVML says "not supported" |
| Serial number | text | MISSING | not on a consumer card |

### AMD integrated GPU — `amdgpu`

Sensors are in hwmon5, section A. The integrated GPU gives a small set: edge
temperature, two voltages, PPT and sclk. There is no junction or memory
temperature, and no fan.

## E. Peripherals

| Device | Path | Fields | Status |
|---|---|---|---|
| Logitech G305 mouse | `/sys/class/power_supply/hidpp_battery_2/` | `capacity_level`, `status`, `online`, `model_name` | OK |
| Logitech G515 TKL keyboard | HID `046D:C358` | no battery reported (wired or not exposed) | TODO |
| MSI MYSTIC LIGHT | HID `0DB0:0076` | RGB controller, not a sensor | note only |

The mouse gives `capacity_level` = `Full` as text, not a percent. The HID++
protocol can give a percent. **Open question Q4.**

## F. Storage

| Source | Contents | Status |
|---|---|---|
| hwmon `nvme` | 3 temperatures | OK |
| `/proc/diskstats` | read and write counters, I/O time | OK |
| SMART / NVMe log page 0x02 | wear, written bytes, power on hours, throttle state | **ROOT**, and `nvme-cli` and `smartmontools` are **not installed** |

## G. Network

| Source | Contents | Status |
|---|---|---|
| hwmon `r8169_0_b00:00` | Ethernet PHY temperature | OK |
| `/sys/class/net/*/statistics/` | byte and packet counters | OK |
| `/proc/net/wireless` | Wi-Fi signal quality for `wlp8s0` | OK |

## H. Missing — motherboard Super-I/O

**This is the biggest gap.** No Super-I/O hwmon device is present. There is no
`nct6775`, `nct6683` or `it87` module loaded, and no such device in hwmon.

That means these values are **not available now**:
- All fan speeds (CPU fan, pump, 6 chassis fans).
- All fan control (PWM).
- VRM / MOS temperature.
- Chipset temperature.
- Motherboard voltage rails (+12 V, +5 V, +3.3 V, VCore, VSOC, DRAM).
- The "System" / board temperature sensor.

The MSI PRO X870-P WIFI is expected to use a Nuvoton NCT6687-family chip. The
out-of-tree `nct6687d` driver exists as a DKMS module. It is not confirmed on
this board yet.

Action: experiment `exp-0002`. See open question Q1.

## I. Other, to examine later

| Source | Note | Status |
|---|---|---|
| AMD SMU / SVI2 telemetry (`zenpower3`, `ryzen_smu`) | per-core power, SoC power, VID | TODO |
| `/dev/i2c-*` (15 buses) | SMBus, DDC on the monitors | TODO |
| Monitors through DDC/CI (`ddcutil`) | brightness, and some panel data | TODO |
| Chassis intrusion, board LEDs | needs Super-I/O | TODO |
| `psutil` general metrics (CPU, RAM, disk, net, processes) | portable fallback | TODO |
