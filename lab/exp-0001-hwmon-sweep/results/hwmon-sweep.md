# hwmon sweep

Captured: 2026-09-16T11:09:02+00:00
Run as: uid 1000

## `hwmon0` — r8169_0_b00:00

- driver: `Realtek Internal NBASE-T PHY`
- device: `/sys/devices/pci0000:00/0000:00:02.1/0000:03:00.0/0000:04:06.0/0000:0b:00.0/mdio_bus/r8169-0-b00/r8169-0-b00:00`

| channel | label | value | unit | other attributes | unreadable |
|---|---|---|---|---|---|
| `temp1` | - | 35.5 | degC | max=120000 | - |

## `hwmon1` — nvme

- driver: `None`
- device: `/sys/devices/pci0000:00/0000:00:01.2/0000:02:00.0/nvme/nvme0`

| channel | label | value | unit | other attributes | unreadable |
|---|---|---|---|---|---|
| `temp1` | Composite | 32.85 | degC | alarm=0, crit=87850, max=83850, min=-40150 | - |
| `temp2` | Sensor 1 | 45.85 | degC | max=65261850, min=-273150 | - |
| `temp3` | Sensor 2 | 32.85 | degC | max=65261850, min=-273150 | - |

## `hwmon2` — k10temp

- driver: `k10temp`
- device: `/sys/devices/pci0000:00/0000:00:18.3`

| channel | label | value | unit | other attributes | unreadable |
|---|---|---|---|---|---|
| `temp1` | Tctl | 41 | degC | - | - |
| `temp3` | Tccd1 | 33.5 | degC | - | - |
| `temp4` | Tccd2 | 29.25 | degC | - | - |

## `hwmon3` — spd5118

- driver: `spd5118`
- device: `/sys/devices/pci0000:00/0000:00:14.0/i2c-0/0-0051`

| channel | label | value | unit | other attributes | unreadable |
|---|---|---|---|---|---|
| `temp1` | - | 30.25 | degC | crit=85000, crit_alarm=0, enable=1, lcrit=0, lcrit_alarm=0, max=55000, max_alarm=0, min=0, min_alarm=0 | - |

## `hwmon4` — spd5118

- driver: `spd5118`
- device: `/sys/devices/pci0000:00/0000:00:14.0/i2c-0/0-0053`

| channel | label | value | unit | other attributes | unreadable |
|---|---|---|---|---|---|
| `temp1` | - | 28.75 | degC | crit=85000, crit_alarm=0, enable=1, lcrit=0, lcrit_alarm=0, max=55000, max_alarm=0, min=0, min_alarm=0 | - |

## `hwmon5` — amdgpu

- driver: `amdgpu`
- device: `/sys/devices/pci0000:00/0000:00:08.1/0000:74:00.0`

| channel | label | value | unit | other attributes | unreadable |
|---|---|---|---|---|---|
| `freq1` | sclk | 6e+08 | Hz | - | - |
| `in0` | vddgfx | 1.305 | V | - | - |
| `in1` | vddnb | 1.305 | V | - | - |
| `power1` | PPT | 0.014 | W | - | - |
| `temp1` | edge | 38 | degC | - | - |

## `hwmon6` — hidpp_battery_2

- driver: `None`
- device: `/sys/devices/pci0000:00/0000:00:02.1/0000:03:00.0/0000:04:0c.0/0000:0e:00.0/usb1/1-5/1-5:1.2/0003:046D:C53F.0012/0003:046D:4074.0013/power_supply/hidpp_battery_2`
