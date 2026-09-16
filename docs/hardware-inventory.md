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
| BIOS | AMI 1.A10, 2024-08-27 | `/sys/devices/virtual/dmi/id/bios_*` |
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

## Memory

| Item | Value |
|---|---|
| Total | 60 GiB usable (61 GiB installed, 2 × 32 GB) |
| Swap | none (0 B) |
| SPD hubs | 2 × `spd5118` on SMBus port 0, addresses 0x51 and 0x53 |

DDR5 modules report their own temperature through the SPD5118 hub. Part numbers
and speed need `dmidecode` with root. **Open item.**

Source: `free -h`, `/sys/bus/i2c/devices/0-0051`, `0-0053`.

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
| DRM card | `card2` (outputs DP-4, DP-5, DP-6, HDMI-A-2) |

### 2. AMD Radeon integrated graphics (in the 9900X)

| Item | Value |
|---|---|
| PCI | `74:00.0`, `1002:13c0` rev c2 |
| Audio function | `74:00.1`, `1002:1640` |
| Driver | `amdgpu` |
| DRM card | `card1` (outputs DP-1, DP-2, DP-3, HDMI-A-1) |

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

| Item | Value |
|---|---|
| Logitech device | `hidpp_battery_2` hwmon, UPower `battery_hidpp_battery_2` |

The exact model of the Logitech device is an **open item**.

## Open items

1. DIMM part numbers, speed and slot positions — needs root `dmidecode`.
2. Logitech peripheral model name.
3. Contents of `nvme0n1p4` (359.2 GB, not mounted).
4. Super-I/O chip model on the MSI PRO X870-P WIFI — expected Nuvoton NCT6687,
   not confirmed, because no driver is loaded.
