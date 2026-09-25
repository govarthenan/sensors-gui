# exp-0019 — which sources can measure the power of the whole system?

- Date: 2026-09-25
- Asked by: Gova, in `TODO`
- Related: ADR 0007, ADR 0010, ADR 0011, `exp-0005` (component census),
  `exp-0012` (per-core energy), Q10 (unsafe shutdowns)

## Question

Gova, verbatim: *"Explore and identify which other peripherals or sensors let
us measure power draw. So that we may more accurately guage the total power
draw of the system, in addition to what we have from cpu and gpu."*

Today the application has three power sources: CPU package power (RAPL),
twelve per-core powers (MSR `0xc001029a`) and GPU board power (NVML). The power
supply, an NZXT C1200, has no telemetry link. This experiment lists every other
route: what the machine already publishes, what a device could add, and what
only an estimate can give. It is preliminary. Gova decides what to do next.

## Method

Every step only reads. No step wrote to sysfs, to a bus, to an MSR, to the SMU
or to a device. No step used root. No I2C tool ran. No packet was sent to
another host on the network. No load was started.

1. **Sysfs sweep**, as user `gova`. Every `power*`, `curr*`, `in*` and
   `energy*` file under `/sys/class/hwmon/`; every zone under
   `/sys/class/powercap/` with its permissions (root-only files listed, not
   read); `/sys/class/power_supply/`, `/sys/class/typec/`,
   `/sys/class/usb_power_delivery/`; the DRM cards; the network chips; ACPI
   power meters and IPMI. Files: `results/hwmon-power-voltage-current.txt`,
   `results/powercap.txt`, `results/power-supply-typec-pd.txt`,
   `results/network-chips.txt`, `results/acpi-ipmi-upower.txt`.
2. **USB census.** `lsusb`, `lsusb -t` and the sysfs descriptors, including
   `bMaxPower`. File: `results/usb-devices.txt`.
3. **NVMe.** Device permissions, sysfs, and the power-state table copied from
   the root probe of 2026-09-22 (not re-run; it needs root). File:
   `results/nvme-power.txt`.
4. **Side-by-side sample.** `probe.py` reads, at 1 Hz for 30 s: the `amdgpu`
   `power1_input`, the power fields of `gpu_metrics`, NVML (power usage, the
   energy counter, the field values `POWER_INSTANT` and `POWER_AVERAGE` for
   the GPU, module and memory scopes, and the limits as context), and the
   helper's CPU power channels through the application's own client.
   ```bash
   uv run python lab/exp-0019-power-draw-sources/probe.py --samples 30
   ```
   Files: `results/2026-09-25-power-channels-30s.json` and its summary
   `results/2026-09-25-power-channels-30s-summary.txt`.
5. **The amdgpu driver source**, kernel v7.0, to learn what `power1_input`
   and `gpu_metrics` are and what a read of them causes. File:
   `results/web-amdgpu-kernel-source.md`.
6. **Passive network read.** `ip neigh` and `/proc/net/arp` only. File:
   `results/network-neighbours.txt`. **That file is not committed** (2026-09-25): it holds the
   home network's public IPv6 prefix and the router's MAC address, and the sweep before the first
   push found no IP address in the repository. It stays on this machine until Gova decides.
7. **Web research** on the power supply, wall meters, UPS reporting, inline
   DC meters and the parts that no sensor measures. Files: `results/web-*.md`.
   Quotes are copied into the files with the URL and the date.

**The machine was not idle.** Folding@home (`fah-client`, nice 19) was running
on the CPU and the GPU during the whole experiment. This experiment did not
start it. `results/machine-state.txt`. So the numbers below are a steady
medium load (CPU package 161 W, GPU 351 W), not idle. That was useful for
comparing channels, but **idle figures are not established**.

## Result

### 1. The short answer

- **Nothing more on this machine measures power.** Every hwmon power, current
  and energy channel is already in the application (the hwmon collector reads
  every `<kind><n>_input`). The board chip gives voltages only, no currents.
  There is no `psys` or `dram` RAPL zone, no USB PD, no ACPI power meter, no
  UPS and no power supply link.
- **Measured now, as DC:** CPU package (RAPL) + GPU board (NVML) = **512 W**
  mean over the 30 s sample. Everything else is not measured: the board and
  chipset, the memory, the drive, the fans and pump, USB and Wi-Fi, the CPU's
  voltage regulator loss, and the power supply's own loss.
- **To measure the whole system, a device is needed.** The cheapest and
  simplest is a smart plug with a local API between the wall and the PC.

### 2. Every route

Status: **IN APP** (already read), **AVAILABLE NOW**, **NEEDS A DEVICE**,
**NEEDS ROOT**, **DROPPED** (the route writes, or cannot give power).

"Does it write?" asks ADR 0010's question: does it only ask, or does it tell
the hardware something?

#### A. Sources on this machine

| # | Source | What it gives | Unit | Kind | Read path | Root? | Does it write? | Status |
|---|---|---|---|---|---|---|---|---|
| A1 | RAPL `package-0` | CPU package power | W | measured by the CPU | `/sys/class/powercap/intel-rapl:0/energy_uj` via the helper | helper | no | **IN APP** |
| A2 | RAPL `core` | core 0 only (known trap) | W | measured | `intel-rapl:0:0` via the helper | helper | no | **IN APP** |
| A3 | MSR `0xc001029a` | 12 core powers and their sum | W | measured | `/dev/cpu/N/msr`, `pread` via the helper | helper | no (ADR 0010) | **IN APP** |
| A4 | Other RAPL zones (`psys`, `dram`) | — | — | — | not present: only `package-0` and `core` exist | — | — | **not present** |
| A5 | NVML `nvmlDeviceGetPowerUsage` | GPU **whole board** power, 1 s average, "+/- 5 watts" | W | measured | `pynvml` | no | no (Get call) | **IN APP** |
| A6 | NVML total energy counter | GPU board energy since the driver loaded | J | measured | `pynvml` | no | no | **IN APP** |
| A7 | NVML field `POWER_INSTANT`, GPU scope | GPU board power, instantaneous (210–408 W while the average was 330–386 W) | W | measured | `nvmlDeviceGetFieldValues` | no | no (Get call) | **AVAILABLE NOW** (new, optional) |
| A8 | NVML field power, MODULE and MEMORY scopes | — | — | — | returns `NVML_ERROR_NOT_SUPPORTED` (3) | — | — | **not supported** on this card |
| A9 | NVML power limits | 480 W enforced and default; 150–530 W range | W | declared | `pynvml` Get calls | no | no | context only; 480 W already used as the scale |
| A10 | `nct6687` `+12V`, `+5V`, `System 3.3V` | rail **voltages** only; the driver has no `curr` or `power` type | V | measured | hwmon | no | no | **IN APP**, but **cannot give power** |
| A11 | `amdgpu` `power1_input` "PPT" | 0.026–0.059 W while RAPL read 158–162 W. The kernel says "power used by the SoC ... On APUs this includes the CPU". It does not track the CPU here. Meaning and scale **not established** | W | unclear | hwmon | no | **the kernel driver** sends `TransferTableSmu2Dram` to the SMU on each read (1 ms cache). This project writes nothing. See finding 4 | **IN APP, NOT USABLE** for total power |
| A12 | `amdgpu` `gpu_metrics` v2.1 | `socket` 104–233 "mW", `soc` 20.4–24.1 W, `gfx` 1.9–64.4 W; `cpu` and per-core fields empty. `socket` and `gfx` do not follow RAPL (correlation +0.26 and −0.07). Meaning **not established** | mW | unclear | `/sys/class/drm/card2/device/gpu_metrics`, world-readable | no | the same driver message, with no cache | **AVAILABLE NOW**, not recommended |
| A13 | `/sys/class/power_supply/` | the G305 mouse battery only; no UPS, no mains | — | — | sysfs | no | no | **IN APP**; nothing new |
| A14 | USB Type-C / USB PD | no `typec` class, no `usb_power_delivery` class, no UCSI module | — | — | — | — | — | **not present** |
| A15 | USB `bMaxPower` | declared maximum for 6 devices: 1398 mA at 5 V, **7.0 W at most**. The webcam (500 mA) and the Bluetooth are suspended | mA | **declared**, not measured | `/sys/bus/usb/devices/*/bMaxPower` | no | no (cached descriptor) | **AVAILABLE NOW**, an upper bound only |
| A16 | NVMe power-state table | PS0 5.00 W, PS1 3.30 W, PS2 2.20 W, sleep 0.0150–0.0033 W | W | **declared** maxima | `nvme id-ctrl` (copied from 2026-09-22) | yes | no (Identify is a read command; the helper already sends Get Log Page) | **NEEDS ROOT**, already captured |
| A17 | NVMe current power state | which of PS0–PS5 the drive is in; × the table = a declared figure | — | declared | `nvme get-feature /dev/nvme0 -f 2` through the helper | yes | no (Get Features reads). **Not run** | **NEEDS ROOT** |
| A18 | DDR5 PMIC (`0x49`, `0x4b`) | module input power | — | — | I2C | — | **yes**: an I2C read writes the register pointer | **DROPPED**, ADR 0011 |
| A19 | SMU mailbox (SoC power, VID) | — | — | — | `ryzen_smu`, `zenpower3` | — | **yes**: a command word | **DROPPED**, ADR 0010 |
| A20 | Monitors (DDC/CI) | no power field in MCCS anyway | — | — | `ddcutil` | — | **yes**: DDC/CI is I2C | **DROPPED**, ADR 0011. The monitors are not on the PC's supply (declared 16.1 W each, **not verified**) |
| A21 | Wi-Fi `ath12k`, Ethernet `r8169` | no power, current or energy file | — | — | sysfs | — | — | **not present** |
| A22 | ACPI power meter (`ACPI000D`), IPMI | none on this board | — | — | — | — | — | **not present** |
| A23 | MSI MYSTIC LIGHT `0db0:0076` | an RGB controller; no power data is known | — | — | HID feature reports | — | a feature report is a request **to** the device | **DROPPED**; no known value |
| A24 | NZXT C1200 | no USB, no CAM, no reading (maker's page) | — | — | none | — | — | **not possible** |
| A25 | Network: existing smart plug or UPS | `ip neigh` shows only the router and Docker containers. A plug the PC never talked to would not show | — | — | passive read only | no | no | **not established**; `avahi-browse -a -t -r -p` would query the LAN, **not run** |

#### B. Devices that could be added

| # | Device | What it measures | Kind | Read path on Linux | Root? | Does it write? | Cost | Status |
|---|---|---|---|---|---|---|---|---|
| B1 | **Smart plug with a local API**, for example Shelly Plus Plug UK (Type G, 13 A) | **AC at the wall**: the whole PC, supply loss included; also V, A, power factor, energy | measured; about ±2 % per a reseller and one review, **not from the maker** | HTTP GET `http://<plug>/rpc/Switch.GetStatus?id=0`, field `apower` | no | nothing to this machine. A GET to a device that **holds the PC's power**: the same API can switch it off. Use GET only; set the plug so it cannot turn off by itself | not checked | **NEEDS A DEVICE** |
| B2 | Tasmota plug (third-party firmware) | AC at the wall | measured; must be **calibrated** by the user | HTTP or MQTT, local | no | as B1 | not checked | **NEEDS A DEVICE** |
| B3 | TP-Link Tapo P110 | AC at the wall | measured | local KLAP protocol with account login; open issues in `python-kasa` | no | as B1 | not checked | **NEEDS A DEVICE**, weaker software support |
| B4 | **UPS with USB HID** (NUT `usbhid-ups`) | the UPS **output**: the PC plus anything else on it. `ups.realpower` (W) on some models, only `ups.load` (%) on others | measured; coarse on load-% models; accuracy **not established** | NUT `upsc` | **yes**, once: install NUT, udev rule | the driver asks for HID reports. NUT's **instant commands** (`load.off`, `shutdown`) tell the UPS to act: give the NUT user no command rights | not checked | **NEEDS A DEVICE + NEEDS ROOT** |
| B5 | ElmorLabs PMD2X | **DC** on EPS 8-pin ×2, PCIe ×3, ATX 24-pin, 12V-2x6. ±0.1 V at 12 V, ±0.5 A at 10 A | measured | USB serial, 115200 baud; the host sends command byte **4** to get values | once: add `gova` to `dialout` | sends a read command to the **meter**. The same protocol has calibration, reset and bootloader commands: never send them. The meter sits **in the CPU and GPU cables** | US$109 | **NEEDS A DEVICE**; not recommended (see below) |
| B6 | BENCHLAB | DC on ATX 24-pin, EPS ×2, PCIe ×3, 12VHPWR ×2 | measured; accuracy not stated | USB; Linux support and protocol **not established** | not established | it also **controls fans**: that part must never be used | US$199 (+ US$40 slot adapter) | **NEEDS A DEVICE**; not recommended |
| B7 | A power supply with telemetry (Corsair HXi/RMi) | the supply's own power, rails, input voltage | measured by the supply; accuracy **not established** | in-kernel `corsair-psu` hwmon driver; the application would read it with no change | no | the **kernel driver** sends HID requests (as `spd5118` does) | a new PSU | listed for completeness only |
| B8 | A current-clamp meter in the wiring (Shelly EM, PZEM-004T) | AC at the circuit | measured | Wi-Fi or USB-serial (Modbus) | varies | the PZEM needs a Modbus read request; it also has an energy-reset command | not researched | **not researched**; needs an electrician; no evidence file |

#### C. The software estimate

| # | Part | Kind | Source |
|---|---|---|---|
| C1 | CPU package | **measured** (RAPL) | A1 |
| C2 | GPU board, with its shroud fan and its 2 radiator fans (they connect to the card); whether the card also powers its pump is not established | **measured** (NVML, "+/- 5 watts") | A5; the radiator fans connect to the card (`data/evidence/rtx4090-liquidx-fans-2026-09-23/`) |
| C3 | CPU voltage regulator loss (EPS 12 V in, package out) | **not measured, not established** | no source found |
| C4 | Board, X870 chipset (one Promontory 21), 2 DDR5 modules, Wi-Fi, audio | **not measured, not established** | no published figure found (`results/web-other-parts.md`) |
| C5 | NVMe drive | **declared**: 5.00 W maximum | A16 |
| C6 | USB devices | **declared**: 7.0 W maximum | A15 |
| C7 | 7 case fans, CPU radiator fans, CPU pump | **not measured**; the fan models are not known | — |
| C8 | Power supply loss | **estimated** from the Cybenetics curve at 230 V | `results/web-nzxt-c1200.md` |

The estimate is:

```
P_wall ≈ (P_RAPL + P_NVML + R) / η(load)
```

- `P_RAPL + P_NVML` is measured: 512 W in the sample.
- `R` is C3 to C7, the part no sensor sees. **It is not established.** A rough
  guess of 40 to 80 W (regulator loss plus board, memory, drive, fans and
  USB) is Claude's guess, with no source, and must not be shown as a fact.
- `η` comes from the Cybenetics report 24PS2447A at 230 V: 92.7 % at 40–50 %
  load, 90.4 % at 20 %, 85.4 % at 10 %, 74.0 % at 2 %. At light load the loss
  is large in proportion. **Which C1200 revision is in this PC is not
  established**, so the curve may not be the right one.
- For the sample: (512 + 40…80) / 0.927 ≈ **595 to 640 W at the wall**. This
  is an estimate with a wide range. It is **not** a measurement.

The way to fix `R`: measure the wall once with a meter (B1), at idle and under
a known load, and solve for `R`. After that, the estimate is calibrated for
this machine, and the application could show it all the time, labelled as an
estimate.

### 3. Findings on the way

1. **The `amdgpu` "PPT" channel in the application is not a usable power
   reading on this machine.** Under a 161 W CPU package load it read
   0.026–0.059 W. The kernel documents `power1_input` as SoC power that
   "on APUs ... includes the CPU", but here it does not follow the CPU. The
   kernel converts the SMU field (in mW) with `(x << 8) / 1000` and then
   `(q >> 8) * 1e6 + (q & 0xff) * 1000` µW, so the hwmon value is 0.256 × the
   raw field for values under 1 W. `exp-0001` wrote "plausible but needs a
   load test to confirm the scale"; this is that test, and the scale is **not
   confirmed**. What the raw field measures is not established.
2. **`gpu_metrics` has a `soc` field that holds steady at 20.4–24.1 W.** It
   may be the SoC rail of the processor. RAPL package minus the core sum was
   59 W in the same sample. The two do not match and the meaning of the field
   is **not established**.
3. **NVML instantaneous power swings much more than the average**: 210 to
   408 W against 330 to 386 W. Only the average is in the application. The
   energy counter gave 343 W over the run, which agrees with the average.
4. **The application already causes a message to the SMU.** Each read of
   `amdgpu` `power1_input` makes the kernel driver send
   `SMU_MSG_TransferTableSmu2Dram` (at most once per millisecond), and the
   hwmon collector reads `amdgpu` at interval 0, on every pass. The driver
   owns this and serialises it, so by ADR 0011 section 2 it is "reading what a
   kernel driver publishes". But ADR 0010 closed the SMU route for this
   project, and Gova should decide whether this indirect case is acceptable,
   now that it is known. `results/web-amdgpu-kernel-source.md`.
5. **A webcam is connected** that the inventory does not list: Sonix
   `0c45:6366` "USB 2.0 Camera" behind a Genesys `05e3:0608` hub, on bus 9.
   `results/usb-devices.txt`.

### 4. Recommendation for Gova, ranked

1. **A smart plug with a local API (B1), Type G, between the wall and the
   PC.** It is the only low-cost route to the **whole** system's power,
   supply loss included. It needs no root and sends nothing to this machine's
   hardware. The application would call one HTTP GET. Before it is used:
   set it to power-on default ON, turn off its schedules, its cloud control
   and its button, and set its power limit well above the PC's peak. It is a
   relay in the PC's power path, and a relay that opens under load is an
   unsafe shutdown.
2. **In software, now: add a "CPU + GPU (measured)" sum channel** from RAPL
   and NVML, both measured, and label it as the measured DC part. After a
   wall meter gives `R` once, an **"estimated wall power"** channel can follow,
   always labelled as an estimate.
3. **A UPS with `ups.realpower` (B4)**, only if Gova wants a UPS for its own
   sake. Q10 counts 29 unsafe shutdowns in 145 power cycles; if some of those
   are mains cuts, a UPS answers two questions. It needs root once to install
   NUT, and NUT must be set so the application can read but never command.

Not recommended: the inline DC meters (B5, B6). They put a new board and two
new connectors into the 12V-2x6 cable of the RTX 4090, they repeat a number
NVML already gives within 5 W, and they do not see the supply's loss. They
are worth it only if Gova wants the board and CPU-input split specifically.

### 5. Open questions for Gova

1. **Where does "the system" end?** The PC alone, or the PC and the two
   monitors and anything else on the same strip? A wall meter measures what
   is plugged into it.
2. **Which C1200 is it?** The label on the side of the supply gives the model
   number (PA-...). The efficiency curve depends on it.
3. **What is the wall socket?** Type G, or an older Type D or M? The plug must
   fit without an adapter; an adapter on a 600 W load is a poor idea.
4. **Is there a UPS now, and are mains cuts common?** This bears on Q10 and
   on recommendation 3.
5. **The `amdgpu` "PPT" channel**: keep it, relabel it as "not a calibrated
   power figure", or hide it? And is the driver's SMU message on every read
   acceptable (finding 4), or should its interval be longer?
6. **May a smart plug be put in the PC's power path at all?** It is the one
   recommended route that adds a switch between the wall and the machine.
7. **May `avahi-browse -a -t -r -p` be run once?** It sends an mDNS query to
   the local network and would show any plug or UPS already there. It was not
   run.

## Limits

- The machine was under a Folding@home load. No idle figure was taken.
- One sample of 30 s.
- Prices of the smart plugs and the UPS were not checked. Accuracy figures for
  the smart plug are from a reseller and a review, not the maker.
- The web quotes from WebFetch come through a summarising tool; the files say
  so. The kernel source, the NUT variable table, the `corsair-psu` document
  and the ElmorLabs code were fetched raw and are verbatim.
- The amdgpu source is the upstream v7.0 tag. This machine runs Ubuntu's
  7.0.0-31 build, which can differ.
