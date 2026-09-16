# exp-0001 — hwmon sweep

Date: 2026-09-16

## Question

Which sensor channels does `dst-gova-pc` expose through the Linux hwmon
interface, what are their labels and units, and which of them need root?

## Method

`sweep.py` walks `/sys/class/hwmon/hwmon*`. For each device it reads the `name`
file, follows the `device` symlink to get the driver and the real device path,
then reads every attribute file. It groups files by the hwmon naming pattern
`<kind><index>_<attribute>` (for example `temp1_input`), applies the standard
hwmon scale factor for each kind, and records any file it cannot read.

Run:

```bash
uv run python lab/exp-0001-hwmon-sweep/sweep.py
```

Results go to `results/hwmon-sweep.json` and `results/hwmon-sweep.md`.

## Result

7 hwmon devices, 15 channels. All 15 are readable as user `gova` (uid 1000).
No file gave a permission error.

| hwmon | name | channels |
|---|---|---|
| hwmon0 | `r8169_0_b00:00` | 1 temperature (Ethernet PHY) |
| hwmon1 | `nvme` | 3 temperatures |
| hwmon2 | `k10temp` | 3 temperatures (Tctl, Tccd1, Tccd2) |
| hwmon3 | `spd5118` | 1 temperature (DIMM at 0x51) |
| hwmon4 | `spd5118` | 1 temperature (DIMM at 0x53) |
| hwmon5 | `amdgpu` | 1 temperature, 2 voltages, 1 power, 1 frequency |
| hwmon6 | `hidpp_battery_2` | 0 — it is a `power_supply`, not a hwmon channel |

## Findings

1. **No Super-I/O device.** There is no fan, PWM, or board voltage channel
   anywhere in hwmon. The motherboard sensor chip has no driver. This is the
   largest gap in coverage.
2. **`hwmon6` is empty.** The Logitech G305 battery registers a hwmon node with
   no channels. The real data is at
   `/sys/class/power_supply/hidpp_battery_2/`. The application must read the
   `power_supply` class as well as hwmon.
3. **`k10temp` gives no power or voltage.** Only `Tctl`, `Tccd1` and `Tccd2`.
   CPU package power must come from RAPL, which needs root.
4. **The hwmon index is not stable.** The application must match on `name` plus
   the device path, not on `hwmonN`. See ADR 0002.
5. **Some limits are nonsense.** The NVMe `Sensor 1` and `Sensor 2` report
   `max = 65261.85 °C`. These are firmware placeholders. The user interface must
   not draw a scale from them.
6. **The `amdgpu` PPT reads 0.014 W.** That is the integrated GPU at idle. The
   value is plausible but needs a load test to confirm the scale.
