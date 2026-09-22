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

**Read since 2026-09-22, through the helper of ADR 0005.** The files still need
root; the screen does not. See section I.

| Path | Contents | Channel | Status |
|---|---|---|---|
| `/sys/class/powercap/intel-rapl:0/energy_uj` | package energy counter, µJ | `CPU Package Power`, `CPU Package Energy` | OK, through the helper |
| `/sys/class/powercap/intel-rapl:0:0/energy_uj` | core domain energy, µJ | `CPU Core 0 Power`, `CPU Core 0 Energy` | OK, through the helper |

The name is `intel-rapl` on AMD too. The kernel uses the same powercap
framework. Power in watts = delta(energy) / delta(time).

Three traps, all measured on this machine:

1. **The `core` domain is core 0, not the cores.** On 2026-09-22 it gave
   1.69 W while `turbostat` gave 2.07–3.68 W for CPU 0 and 22.8–28.0 W for all
   twelve. `exp-0003` found this and `exp-0011` confirmed it with fresh
   numbers. The label says `Core 0` for that reason.
2. **The counter wraps, and often.** `max_energy_range_uj` is 65 532 610 987,
   which at the 70 W this machine idles near fills in about **15 minutes**. A
   reader that ignores the wrap reports a large negative power four times an
   hour.
3. **`enabled` reads 0 on both domains, and the counters count anyway.** Do not
   use it as a health check.

There is no power constraint file on this board, so there is no declared
maximum and the channel gets no meter bar.

`turbostat` is installed (`/usr/bin/turbostat`) and also needs root. It is the
independent check, not a source the application uses.

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
| SMART / NVMe log page 0x02 | wear, written bytes, power-on hours, throttle state | OK since 2026-09-22, through the helper. 15 channels, see section I. |

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

## I. The privileged helper — `sensors-guid`

ADR 0005 and ADR 0009. A small root service reads the two sources above that
need root and publishes them on `/run/sensors-gui.sock`, mode `0660`, group
`gova`. The screen reads that socket and never needs root.

| Source | Channels | Interval the helper reads at |
|---|---|---|
| RAPL, 2 domains | 4: power and energy for each | 1 s |
| NVMe SMART, 1 drive | 15 | 60 s |

The 15 SMART channels, from `nvme smart-log -o json` under nvme-cli 2.8:

| Channel | Field in the log | Unit | Note |
|---|---|---|---|
| SSD Wear | `percent_used` | % | |
| Spare Available | `avail_spare` | % | the drive's own threshold is 10 % |
| Data Written | `data_units_written` | B | × 512 000; one data unit is 1000 blocks of 512 B |
| Data Read | `data_units_read` | B | the same |
| Power-On Hours | `power_on_hours` | h | |
| Power Cycles | `power_cycles` | | |
| Unsafe Shutdowns | `unsafe_shutdowns` | | see open question Q10 |
| Media Errors | `media_errors` | | |
| Critical Warning | `critical_warning` | | a bit field; 0 is healthy |
| Throttle T1 / T2 Count | `thm_temp1_trans_count`, `thm_temp2_trans_count` | | |
| Throttle T1 / T2 Time | `thm_temp1_total_time`, `thm_temp2_total_time` | s | the log counts these in **seconds** |
| Warning Temp Time | `warning_temp_time` | s | the log counts this in **minutes**; converted |
| Critical Temp Time | `critical_comp_time` | s | the log counts this in **minutes**; converted |

**Without the helper the channels still appear**, with a dash and the reason
"needs the helper". The catalogue is built from `name`, `model` and `serial`,
which any user can read; only the values need root.

Install: `sudo ./scripts/install-helper.sh`. Remove:
`sudo ./scripts/uninstall-helper.sh`.

## J. Other, to examine later

| Source | Note | Status |
|---|---|---|
| AMD SMU / SVI2 telemetry (`zenpower3`, `ryzen_smu`) | per-core power, SoC power, VID | TODO |
| `/dev/i2c-*` (15 buses) | SMBus, DDC on the monitors | TODO |
| Monitors through DDC/CI (`ddcutil`) | brightness, and some panel data | TODO |
| Chassis intrusion, board LEDs | needs Super-I/O | TODO |
| `psutil` general metrics (CPU, RAM, disk, net, processes) | portable fallback | TODO |
