# Hardware inventory — `dst-gova-pc`

Recorded 2026-09-16. All facts come from the machine. The command is given with
each fact.

## System

| Item | Value | Source |
|---|---|---|
| Hostname | `dst-gova-pc` | `uname -n` |
| OS | Linux Mint 22.3 "Zena" (Ubuntu 24.04 base) | `/etc/os-release` |
| Kernel | 7.0.0-31-generic, x86_64 | `uname -r` |
| Motherboard | MSI PRO X870-P WIFI (MS-7E47), rev 1.1 | `/sys/devices/virtual/dmi/id/` |
| BIOS | AMI `E7E47AMSI.1A10`, 2024-08-27 | `/sys/devices/virtual/dmi/id/bios_*`, BIOS screen |
| Chipset | AMD X870 (socket AM5) | board model |

## CPU

| Item | Value |
|---|---|
| Model | AMD Ryzen 9 9900X (Zen 5, "Granite Ridge") |
| Family / Model / Stepping | 26 / 68 / 0 |
| Cores / Threads | 12 / 24 |
| CCDs | 2 (`Tccd1`, `Tccd2` both present) |
| Frequency range | 613.95 MHz – 5662.02 MHz, boost enabled |
| Cache | L1d 576 KiB, L1i 384 KiB, L2 12 MiB, L3 64 MiB (2 instances) |
| Scaling driver | `amd-pstate-epp`, governor `performance` |
| NUMA | 1 node, CPUs 0–23 |

Source: `lscpu`, `/sys/devices/system/cpu/cpu0/cpufreq/`.

### Which thread belongs to which core, and which core to which CCD

Read from the machine on 2026-09-22, not inferred. Full output and the
command: `data/probes/2026-09-22-cpu-topology.txt`.

| CCD | `die_id` | `core_id` | The two threads of that core | Its temperature | Its power channel |
|---|---|---|---|---|---|
| CCD 1 | 0 | 0 | `cpu0`, `cpu12` | `Tccd1` | `CPU Core 0 Power` |
| CCD 1 | 0 | 1 | `cpu1`, `cpu13` | `Tccd1` | `CPU Core 1 Power` |
| CCD 1 | 0 | 2 | `cpu2`, `cpu14` | `Tccd1` | `CPU Core 2 Power` |
| CCD 1 | 0 | 3 | `cpu3`, `cpu15` | `Tccd1` | `CPU Core 3 Power` |
| CCD 1 | 0 | 4 | `cpu4`, `cpu16` | `Tccd1` | `CPU Core 4 Power` |
| CCD 1 | 0 | 5 | `cpu5`, `cpu17` | `Tccd1` | `CPU Core 5 Power` |
| CCD 2 | 1 | 8 | `cpu6`, `cpu18` | `Tccd2` | `CPU Core 8 Power` |
| CCD 2 | 1 | 9 | `cpu7`, `cpu19` | `Tccd2` | `CPU Core 9 Power` |
| CCD 2 | 1 | 10 | `cpu8`, `cpu20` | `Tccd2` | `CPU Core 10 Power` |
| CCD 2 | 1 | 11 | `cpu9`, `cpu21` | `Tccd2` | `CPU Core 11 Power` |
| CCD 2 | 1 | 12 | `cpu10`, `cpu22` | `Tccd2` | `CPU Core 12 Power` |
| CCD 2 | 1 | 13 | `cpu11`, `cpu23` | `Tccd2` | `CPU Core 13 Power` |

Three things this settles, all of which the application needed:

1. **A thread's sibling is 12 away, not next to it.** `cpu0` and `cpu12` are
   one core. Pairing `cpu0` with `cpu1` would put two different cores side by
   side and make a core look half idle when it is busy.
2. **The gap in the core numbers is real.** The kernel numbers the cores 0-5
   and 8-13, which is exactly how the per-core energy registers of `exp-0012`
   are labelled, so `CPU Core 8 Power` is the seventh core and the first on
   CCD 2.
3. **`Tccd1` covers `core_id` 0-5 and `Tccd2` covers 8-13.** A core's
   temperature is the temperature of its die, and the application can now say
   which die a core is on.

## Memory

| Item | Value |
|---|---|
| Total | 60 GiB usable (2 × 32 GB) |
| Swap | none (0 B) |

| Slot | Fitted | Size | Type | Rated | Configured | Voltage | Part | Rank | SPD hub | PMIC |
|---|---|---|---|---|---|---|---|---|---|---|
| DIMMA1 | no | — | — | — | — | — | — | — | — | — |
| **DIMMA2** | yes | 32 GB | DDR5 | 5200 MT/s | **6400 MT/s** | 1.1 V | TEAM GROUP `UD5-6400` | 2 | i2c `0-0051` | i2c `0-0049` |
| DIMMB1 | no | — | — | — | — | — | — | — | — | — |
| **DIMMB2** | yes | 32 GB | DDR5 | 5200 MT/s | **6400 MT/s** | 1.1 V | TEAM GROUP `UD5-6400` | 2 | i2c `0-0053` | i2c `0-004b` |

Both modules run above their JEDEC rating, so an EXPO or XMP profile is on.

DDR5 puts the SPD hub of slot *n* at `0x50 + n` and the power management chip
at `0x48 + n`. **Never write to an address from 0x48 to 0x4F.** Those chips set
the voltage of the memory modules.

Source: `free -h`, `dmidecode -t memory`, `/sys/bus/i2c/devices/`.

## Graphics

Two GPUs are present.

### 1. NVIDIA GeForce RTX 4090 (discrete)

| Item | Value |
|---|---|
| PCI | `01:00.0`, AD102, `10de:2684` |
| Audio function | `01:00.1`, `10de:22ba` |
| Driver | NVIDIA 595.84 |
| VRAM | 24564 MiB |
| Power limit | 480.00 W |
| DRM card | **`card1`** (outputs DP-1, DP-2, DP-3, HDMI-A-1) |
| Displays | **both monitors run from this card** |

### 2. AMD Radeon integrated graphics (in the 9900X)

| Item | Value |
|---|---|
| PCI | `74:00.0`, `1002:13c0` rev c2 |
| Audio function | `74:00.1`, `1002:1640` |
| Driver | `amdgpu` |
| DRM card | **`card2`** (outputs DP-4, DP-5, DP-6, HDMI-A-2, Writeback-1) |
| Displays | none |

## Storage

| Item | Value |
|---|---|
| Device | `nvme0n1`, WD_BLACK SN770 1TB, 931.5 GB, non-rotational |
| Partitions | p1 94M `/boot/efi`, p2 286.1G `/`, p3 286.1G `/home`, p4 359.2G (not mounted) |
| Temperature sensors | Composite, Sensor 1, Sensor 2 |

Only one drive is present.

## Network

| Interface | Type | State | Note |
|---|---|---|---|
| `enp11s0` | Realtek `r8169` wired | DOWN (no carrier) | has a temperature sensor |
| `wlp8s0` | Wi-Fi (board module) | UP | |
| `virbr0`, `docker0`, `br-*`, `veth*` | virtual | mixed | libvirt and Docker |

## Audio

| Device | PCI |
|---|---|
| NVIDIA HDMI audio | `01:00.1` |
| AMD Rembrandt HDMI audio | `74:00.1` |
| AMD Family 17h/19h HD Audio (analogue) | `74:00.6` |

## Peripherals

| Item | Model | Sensor |
|---|---|---|
| Mouse | Logitech G305 Lightspeed, wireless | battery through `/sys/class/power_supply/hidpp_battery_N/` |
| Keyboard | Logitech G515 TKL | none found yet |
| Receiver | Logitech USB Receiver `046D:C53F` | — |
| RGB controller | MSI MYSTIC LIGHT, HID `0DB0:0076` | none found yet |

The battery node was `hidpp_battery_2` on 2026-09-16 and `hidpp_battery_3`
after the reboot on 2026-09-17, with no change to the hardware. This is why
ADR 0002 forbids keying a sensor by its index.

## Displays

| Display | Connector | Bus | Model | Serial |
|---|---|---|---|---|
| 1 | `card1-HDMI-A-1` | `/dev/i2c-4` | MSI MD272QXP | PB1H824600444 |
| 2 | `card1-DP-1` | `/dev/i2c-5` | MSI MD272QXP | PB1H824600465 |

`card1` is the **RTX 4090**. Both monitors are plugged into the graphics card,
which Gova confirmed on 2026-09-21.

Do not guess which card is which. Read the PCI address behind it:

```bash
for c in /sys/class/drm/card[0-9]; do
    echo "$(basename "$c") -> $(basename "$(readlink -f "$c/device")")"
done
# card1 -> 0000:01:00.0   NVIDIA RTX 4090
# card2 -> 0000:74:00.0   AMD integrated graphics
```

`xrandr --listproviders` gives one provider, `NVIDIA-0`, with 7 outputs. The
two connectors read `enabled=disabled` in sysfs, because the NVIDIA driver does
its own mode setting and does not use the DRM path that sysfs reports.

Source: `ddcutil detect`, `/sys/class/drm/card*/device`, `xrandr`.

## Firmware state

| Item | Value | Effect |
|---|---|---|
| Secure Boot | **enabled** | |
| Kernel lockdown | **integrity** | `/dev/port` and `iopl` are blocked, so no user-space tool can probe the ISA ports |
| `sig_enforce` | `Y` | an unsigned kernel module cannot load |
| Enrolled MOK | `CN=aipc03-MS-7E47 Secure Boot Module Signature key` | DKMS signs each module it builds, so a DKMS module still loads |

Source: `mokutil --sb-state`, `/sys/kernel/security/lockdown`, `dkms status`.

## Storage health (2026-09-17)

| Field | Value |
|---|---|
| Wear (`percentage_used`) | 0 % |
| Spare | 100 %, threshold 10 % |
| Written | 9.28 TB |
| Read | 2.57 TB |
| Power-on hours | 320 |
| Power cycles | 144 |
| **Unsafe shutdowns** | **28** |
| Media errors | 0 |
| Thermal throttle events | 0 |

Source: `nvme smart-log /dev/nvme0`.

## Cooling and power (from photographs, 2026-09-21)

| Item | Model |
|---|---|
| Power supply | NZXT C1200 — **no telemetry link**, so total system power cannot be measured |
| CPU cooler | MSI liquid cooler (AIO), radiator at the bottom of the case with 2 fans |
| Case fans | 3 front intake, 3 top, 1 rear, plus the 2 radiator fans = **9** |
| Pump | reports 1470 RPM on the `PUMP_FAN` header |
| Graphics card | MSI GeForce RTX 4090 **SUPRIM**, on a 600 W rated 12VHPWR cable |

Only 3 of the 8 board headers carry a tachometer signal. See
`docs/physical-build.md`.

## Motherboard sensors (nct6687, from 2026-09-21)

The Super-I/O chip is a **Nuvoton NCT6687D at ISA 0x0a20**, read by the
out-of-tree `nct6687d` DKMS driver. `/proc/ioports` confirms it:

```
0a20-0a2f : PNP0C02:02
  0a20-0a23 : nct6687
```

**Patched 2026-09-22** with `driver/nct6687-ms7e47.patch`, which adds reads
only. The board now gives **9 fans**, **10 voltages** and 7 temperatures.

| Channel | Value | Note |
|---|---|---|
| `fan9` **EZ Conn Fan** | 963–988 RPM | the case fans on header `JAF_1`. Register `0x146`. |
| `in13` **CMOS Battery** | **3.116 V** | healthy. Register 14. |
| `CPU VDDIO`, `System 3.3V` | | renamed in the driver; they were `DRAM` and `AVCC3` |
| four duplicates of the 3.3 V rail | | hidden; one rail had four names |

Before the patch: 8 fans and 14 voltages, of which only 4 voltages were right.

**The BIOS reads more than Linux does.** Checked against the BIOS on
2026-09-22 (`exp-0009`):

- ~~A ninth fan channel Linux has no channel for.~~ **ANSWERED 2026-09-22: the
  patch reads it. `EZ Conn Fan` gives 963–988 RPM, matching the BIOS.**
- Of the 14 voltages, **4 are correct**, 2 are correct with the wrong name
  (`DRAM` is really `CPU VDDIO`, `AVCC3` is really `System 3.3V`), and **8 are
  wrong**. Three rails the BIOS shows — `VDD MISC` 1.097 V, `CPU 1P8` 1.793 V
  and `CHIPSET Core` 1.047 V — are not read by Linux at all.
- ~~`VBat` at 2.046 V is not the CMOS battery.~~ **ANSWERED 2026-09-22: the
  battery is on register 14 and reads 3.116 V. It is healthy.**

The board's own fan curve: source **CPU Core**; 0 °C → 20 %, 45 °C → 35 %,
65 °C → 70 %, 80 °C → 100 %; step 0.1 s.

**`CPU Fan Fail Warning Control` is OFF in the BIOS.** It should be on.

## Open items

1. Contents of `nvme0n1p4` (359.2 GB, not mounted).
2. ~~Super-I/O chip model.~~ **ANSWERED 2026-09-21: Nuvoton NCT6687D at
   ISA 0x0a20.**
3. The I2C client at `0x4f` is not identified.
4. ~~The USB device `1-11`.~~ **ANSWERED: a Foxconn Bluetooth adapter**
   (`0489:e10a`, driver `btusb`, `hci0`). It is the Bluetooth half of the
   Qualcomm WCN7850 Wi-Fi card.
5. **Unsafe shutdowns: now 29 of 145 power cycles.** Between the two probes the
   machine went through **one** power cycle, and the unsafe count rose by
   **one**. One sample is not a pattern, but it is worth watching.
6. ~~Which headers the 9 fans are wired to.~~ **ANSWERED 2026-09-22: the case
   fans are on the `JAF_1` EZ Conn header**, which the BIOS reads and Linux
   does not. See `exp-0009`.
7. The exact model of the MSI liquid cooler.
