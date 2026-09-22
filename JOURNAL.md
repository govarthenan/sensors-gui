# Journal

Short dated entries. One entry for each session. Details live in `docs/` and
`lab/`.

---

## 2026-09-16 — Session 1: first survey of the machine

**Goal:** start the project, find out what this PC can measure.

**What happened**

- Made the repository, the folder structure and `CLAUDE.md` with a continuity
  framework (`state/STATUS.md` + this journal + `docs/` + `lab/`).
- Surveyed the hardware. The machine is an AMD Ryzen 9 9900X (12 cores, 2 CCDs)
  on an MSI PRO X870-P WIFI, with 61 GiB of DDR5, an NVIDIA RTX 4090, the AMD
  integrated GPU, and one WD_BLACK SN770 1TB NVMe drive.
- Ran `exp-0001`, a full hwmon sweep. Result: 7 devices, 15 channels, all
  readable without root.

**Findings**

1. **The motherboard sensor chip has no driver.** No fan speeds, no PWM control,
   no VRM or chipset temperature, no voltage rails. This is the largest gap.
   The board is expected to use a Nuvoton NCT6687. An out-of-tree DKMS driver
   exists. This needs Gova's decision (Q1).
2. **CPU power needs root.** `k10temp` gives temperatures only. Package power
   comes from RAPL at `/sys/class/powercap/intel-rapl:0/energy_uj`, mode 0400.
   `turbostat` is installed but also needs root.
3. **There is no passwordless sudo.** Every root probe must be handed to Gova.
4. **hwmon indexes are not stable, and two devices share the name `spd5118`**
   (one for each DIMM). Decided ADR 0002: the key is
   `name@device_path:channel`.
5. The Logitech G305 mouse gives a battery level, but as text
   (`capacity_level = Full`), not a percent. The G515 TKL keyboard and the MSI
   MYSTIC LIGHT RGB controller are present as HID devices.
6. The Realtek Ethernet PHY has its own temperature sensor. That was a surprise.
7. `exp-0002`: NVML reads the RTX 4090 in 0.67 ms. `nvidia-smi` needs
   19.91 ms for the same fields, because it starts a process each time.
   NVML also gives the fan count, an energy counter, PCIe throughput,
   NVENC and NVDEC use, and the throttle reasons.
8. Two traps found in NVML. The version 1 memory structure counts 503 MiB
   of driver-reserved memory and disagrees with `nvidia-smi`; use version 2.
   The `*_TLIMIT` fields are headroom in degrees, not temperatures.
9. The RTX 4090 gives the edge temperature only. NVML has no hotspot and no
   GDDR6X temperature on this card.

**Decisions**

- ADR 0001 — all project memory lives in the repository.
- ADR 0002 — identify hwmon sources by name and device path, never by index.
- ADR 0003 — read the NVIDIA GPU through NVML, with the two rules above.

**Next**

Gova must choose the GUI toolkit (Q5) and answer Q1, Q2 and Q6. Then
`exp-0003` (Super-I/O chip identification, needs root) and `exp-0004` (a load
test of every channel).

---

## 2026-09-16 — Session 1, part 2: decisions and the first collector

**Goal:** take Gova's decisions, then start the collection layer.

**Decisions from Gova**

- The interface is **Textual**, a terminal application (ADR 0004). Textual can
  also serve the same screen in a browser later.
- Root-only sensors go through a **small privileged helper service** on a Unix
  socket (ADR 0005). The interface never needs root.
- All the system changes are allowed: the `nct6687d` DKMS driver,
  `sensors-detect`, `smartmontools`, `nvme-cli` and `ddcutil`. Gova also said
  Claude may install and test anything else that it first shows to be safe.
- Gova: *"I'm willing to go to considerable ends to make this project happen."*
  The hard targets are now written in `state/STATUS.md`.

**What happened**

- Wrote `docs/architecture.md`: the collector contract, the core objects, the
  unit table and the rate table.
- Wrote `scripts/root-probe.sh`, so that Gova runs one command instead of ten.
- Built `sensors_gui.model` and `sensors_gui.collectors.hwmon`, test first. 36
  tests pass. The collector reads all 14 channels on this machine.
- Ran `exp-0004`, which measures the cost of each hwmon read.

**Findings**

1. **A hwmon read is not free, and the cost is not equal.** The three NVMe
   channels cost about 2 ms each and the two DIMM channels about 1.5 ms each,
   against 5 microseconds for `k10temp` and `amdgpu`. Five of the 14 channels
   take 99.8 % of the time. The cause is the bus: SMBus for the DDR5 SPD hub,
   and an NVMe admin command for the drive.
2. **The three NVMe temperatures come from one health log**, but the kernel
   fetches that log again for each of the three files. The collector paid 2 ms
   three times for one page of data.
3. Two float traps in the code. `14000 * 1e-6` gives `0.013999999999999999`;
   `14000 / 1_000_000` gives `0.014`. The collector now divides by an integer.
4. A sensor key must not carry a filesystem prefix. The collector now cuts
   every device path at `/devices` and rebuilds it under `/sys`, so that the
   same sensor gets the same key in a test and on the machine.
5. A re-scan must keep the cache. Without that, a re-scan starts a bus
   transaction on every slow device at once.

**Decisions**

- ADR 0006 — each device gets its own read interval, with a cache between
  reads. Built and measured: a pass went from **10.015 ms to 0.199 ms**.

**Next**

Gova runs `sudo ./scripts/root-probe.sh` and installs the three packages. Then
`exp-0003` (the Super-I/O chip) can start, and the NVML collector can be built.

---

## 2026-09-17 — Session 2: the root probe, and a census of the machine

**Goal:** read the root probe that Gova ran, and answer Gova's question about a
component census.

**What happened**

- Read `data/probes/root-probe-20260917T060712Z/` → `exp-0003`.
- Answered Gova's idea: the census experiment **is** worth doing, with one
  change. Started it as `exp-0005`, and built `census.py` for step 1.

**Findings**

1. **`sensors-detect` gave a false negative.** It ended with "no sensors were
   detected", but three lines earlier it printed
   `/dev/port: Operation not permitted`. Secure Boot puts the kernel in
   **integrity lockdown**, which blocks `/dev/port` and `iopl`. **No
   user-space tool can probe the ISA ports on this machine.** The Super-I/O
   chip is still unidentified, and no user-space tool will ever identify it
   here.
2. **A DKMS module still loads.** `sig_enforce=Y`, but a MOK is already
   enrolled and `/var/lib/shim-signed/mok/MOK.priv` exists. DKMS signs each
   module it builds; that is how the NVIDIA module loads. So `nct6687d` needs
   no BIOS change.
3. **The RAPL `core` domain is core 0 only**, not the package cores. It read
   0.269 W while `turbostat` gave 3.71 W for the package and 0.32 W for CPU 0.
   On Zen 5 the core energy register is per core.
4. The drive is healthy: 0 % wear, 9.28 TB written, 320 hours, no throttle
   event ever. But it records **28 unsafe shutdowns** in 144 power cycles.
5. The memory is 2 × 32 GB DDR5 `UD5-6400` in slots **A2** and **B2**, running
   at **6400 MT/s** against a 5200 MT/s rating, so an EXPO profile is on. That
   also names the two `spd5118` sensors: `0x51` is DIMMA2 and `0x53` is DIMMB2.
6. Three I2C clients are unclaimed: `0x49`, `0x4b` and `0x4f`. The first two
   fit the DDR5 power management chips of the two modules. **Those chips set
   the DIMM voltage, so nothing may ever write to 0x48–0x4F.**
7. Both monitors are **MSI MD272QXP**, and both run from the **integrated**
   Radeon graphics, not from the RTX 4090.
8. **ADR 0002 proved itself.** The Logitech battery was `hidpp_battery_2`
   yesterday and is `hidpp_battery_3` after the reboot, with no hardware
   change.

**Census result (exp-0005 step 1)**

111 components, 18 with a known sensor source. Of the 93 without one, 51 are
bridges, buses and root hubs that hold no sensor. Ten real targets remain, and
they are listed in order in `lab/exp-0005-component-census/README.md`.

**Next**

Install `nct6687d` through DKMS. It is the largest gap and the only way to
identify the Super-I/O chip on a locked-down kernel.

---

## 2026-09-21 — Session 3: a correction, and the fan count

**A correction.** Claude reported on 2026-09-17 that both monitors ran from the
integrated Radeon graphics. **That was wrong.** `card1` is the RTX 4090
(PCI `0000:01:00.0`) and `card2` is the integrated graphics
(PCI `0000:74:00.0`). Both monitors are on the graphics card, which is what
Gova said.

The cause: Claude guessed the DRM card order from the connector names instead
of reading the PCI address behind each card. `docs/hardware-inventory.md`,
`exp-0003` and `exp-0005` are corrected, and the inventory now carries the
command that reads it:

```bash
for c in /sys/class/drm/card[0-9]; do
    echo "$(basename "$c") -> $(basename "$(readlink -f "$c/device")")"
done
```

This is the project rule "do not guess hardware facts" failing in practice. Any
card, bus or slot order must be read from sysfs, never taken from a name.

**Gova answered the three questions from `exp-0005` step 5**

1. **9 fans**: 2 on the graphics card, mounted separately; 3 intake; 3 on the
   top; 1 at the rear.
2. The CPU cooler is a **liquid AIO**, so a pump header should also report.
3. The monitors are on the **RTX 4090**.

Still open, and the photographs should settle it: which of the 7 case fans are
plugged into the motherboard rather than into a hub or a controller, whether the
3 top fans are the AIO radiator fans, and the AIO model.

The MSI PRO X870-P WIFI has 8 headers (`CPU_FAN1`, `PUMP_FAN1`, `SYS_FAN1` to
`SYS_FAN6`), so every case fan and the pump can reach the board.

**Then: the NVIDIA collector**

Built `sensors_gui/collectors/nvidia.py`, 17 channels, test first against the
real card. No mock: for a monitor built for one PC, the hardware is the fixture.

`exp-0006` measured each channel, and found the `exp-0004` pattern again, this
time **inside one device**:

- `nvmlDeviceGetPcieThroughput` costs **20.6 ms** per call, because it samples
  the link over a window and blocks for it. Two of them, transmit and receive,
  took 92 % of a 48.4 ms pass. That is nearly the whole 50 ms budget that the
  architecture gives to every collector together.
- `exp-0002` missed this, because its 13 test fields did not include the PCIe
  throughput. A benchmark of "a typical sample" hides the worst call.

So ADR 0006 was amended: the read interval is **per channel**, not per device,
and the cache moved into one shared module that both collectors use. The NVML
pass fell from **48.4 ms to 0.0227 ms**. hwmon kept its 0.192 ms.

A second bug came out of the same work. The VRAM channels declared `Unit.BYTE`
but reported mebibytes, so the screen showed `1125 B` for 1.1 GiB. The unit was
right and the collector was wrong. `SensorSpec.format` now gives SI and binary
prefixes: `1.1 GiB`, `210.0 MHz`, `485.1 kJ`, `38.9 MB/s`.

89 tests pass.

**Next**

Gova runs `sudo ./scripts/install-nct6687d.sh`. The expected fan count is now
known, which is what makes a `0 RPM` reading readable: 0 will mean a stopped
fan, not a missing one.

---

## 2026-09-21 — Session 3, part 2: the motherboard driver works

**Gova installed `nct6687d`.** It built, was signed with the enrolled MOK and
loaded first time. No BIOS change, no kernel parameter.

- The chip is a **Nuvoton NCT6687D at ISA 0x0a20**. `/proc/ioports` now shows
  `0a20-0a23 : nct6687`.
- **29 new channels**: 8 fans, 14 voltages, 7 temperatures. The project reads
  **60 channels** in total.

**Proof that `sensors-detect` is blind here.** Gova ran the root probe again
with the driver loaded and reading 29 channels from that exact chip.
`sensors-detect` still printed `/dev/port: Operation not permitted` three times
and ended with "Sorry, no sensors were detected." Under Secure Boot lockdown,
no user-space tool can see the Super-I/O chip, even when a kernel driver is
reading it at that moment.

**A serious bug found and fixed.** The hwmon ABI says `tempN_max` is a
threshold. This driver writes the running minimum and maximum it has seen:
`temp1_max` read 58000 and then 60000 two seconds later, tracking the input.
The collector read those as warning limits, which put every board channel at
its own limit. The application would have alarmed for ever. Fixed with
`DRIVERS_WITH_TRACKING_LIMITS`.

**`exp-0008`, the load test.** 60 channels at 2 Hz through idle, load and
cooldown.

- 45 of 60 channels moved. The 15 that did not all have a reason: empty fan
  headers, empty thermistor headers, the GPU fan stopped below 50 °C, no video
  encoding, and a fixed VRAM reservation.
- `Tccd1` reached 78.4 °C, `CPU Vcore` fell from 1.376 V to 1.042 V under an
  all-core load, and the CPU fan rose from 2030 to 2758 RPM. Those three
  confirm each other.
- **A flaw in the run:** the idle phase was not idle, so the phase medians are
  not usable and one of them is absurd. The ranges and the distinct-value
  counts do not depend on the phase split, so those are what was kept. The run
  must be repeated on a quiet machine.

**A correction to my own earlier claim.** `exp-0007` called four voltages
"wrong" and implied they were dead. They are not. All 14 board voltages are
live analogue readings; every one jitters by at least one step. The fault is
narrower: four names read the **same** register, and two more are scaled or
addressed wrongly. It is a mapping fault, and the cause is that the driver
carries a board-specific voltage map for the MSI Z890 only.

**Gova's photographs.** `docs/physical-build.md` written.

- Power supply: **NZXT C1200**, with no telemetry link. Total system power
  cannot be measured, only estimated.
- The AIO radiator is at the **bottom** of the case with 2 fans. The "2 fans
  from the GPU" are those.
- 9 case fans exist; only 3 headers report. Every USB device is accounted for,
  so it is not a USB controller. It is a splitter or a hub.
- The drive reached 66.9 °C under load. It sits under the graphics card with
  the radiator below it. It has never throttled.

**Two open items closed.** USB `1-11` is a Foxconn Bluetooth adapter. The
Super-I/O chip is named.

**Next**

Map the voltage registers (`exp-0009`), using the driver's `manual` parameter,
and contribute the map back. Repeat the load test on a quiet machine.

---

## 2026-09-22 — Session 4: a thermal shutdown, and the answer from the BIOS

### The incident

**`scripts/map-fans.sh` caused a thermal shutdown of Gova's machine.** It set
the `CPU_FAN1` header to manual mode at zero, which stopped the radiator fans.
The restore ran and **the chip rejected it**:

```
nct6687: The device rejected new configuration as invalid
```

The header stayed at `pwm1 = 0, enable = 1`. `Tctl` reached 98 °C and the board
shut the machine down to protect itself. Gova rebooted, and everything came
back under BIOS control.

Four faults in my design, not one:

1. **The restore was never verified.** It wrote the value and moved on. It
   never read it back. On this board the driver's writes fail often, so an
   unchecked restore was a coin toss.
2. **The watchdog's only action was the action that was failing.** It would
   have restored through the same rejected write path.
3. **Mode and speed were written separately.** The mode change succeeded and
   the speed change did not, which is the worst of both: manual control, at
   zero.
4. **The radiator fan header was in scope at all.** Rule 2 protected the pump.
   On a liquid-cooled machine the radiator fan is just as critical, and it was
   the one that stopped.

**`scripts/map-fans.sh` is deleted, not fixed.** ADR 0007 is reverted: this
project writes nothing to hardware, with no exceptions. The 2026-09-21
amendment argued that a rule too strict to do its job gets worked around. True
in general; wrong here. The right answer to "this rule blocks the work" was to
**drop the work**. It was chasing a label on a fan.

### The answer arrived for free

Gova photographed the BIOS. It closes the question three sessions could not:

**The BIOS fan list has NINE entries. Linux shows eight.** The ninth is
`EZ Conn Fan`, turning at 963–1612 RPM. The case fans are on the `JAF_1` EZ
Conn header, exactly as the manual hinted. There was never a hub to find,
because an EZ Conn connection is a **cable**. The five empty `SYS_FAN` headers
really are empty; the BIOS prints `N/A` where Linux prints `0`.

The driver can already do 9 channels (`NCT6687_NUM_REG_FAN_MAX`), but enables
the ninth only for the MEG Z890 GODLIKE. `fan_mask` alone will not do it: the
read loops are bounded by the board entry's `fan_channels`.

### The true voltage map

The BIOS gave the ground truth. Of 14 Linux voltages:

- **4 are correct**: `+12V`, `+5V`, `CPU Vcore`, `CPU Soc`.
- **2 are correct with the wrong name**: `DRAM` is really **CPU VDDIO**;
  `AVCC3` is really **System 3.3V**.
- **8 are wrong.** Four of them read the same ~3.33 V, which is one register
  read under four names.
- **3 rails the BIOS shows are missing from Linux**: `VDD MISC` 1.097 V,
  `CPU 1P8` 1.793 V, `CHIPSET Core` 1.047 V. The MSI Z890 override uses
  registers 14 and 15, which the generic table never reads. They will be there.

**Gova's CMOS battery is fine.** `VBat` at 2.046 V is not the battery; the BIOS
lists no battery voltage.

### A safety setting that was off

`CPU Fan Fail Warning Control` is **OFF** in the BIOS. That is why the board
stayed silent while the CPU fan sat at 0 RPM. It should be on.

### Also from the BIOS

- The memory is **TEAM GROUP**, not "Unknown".
- The board's own fan curve: source **CPU Core**; 0 °C → 20 %, 45 °C → 35 %,
  65 °C → 70 %, 80 °C → 100 %; step 0.1 s.
- All four SATA ports are empty.

### Next

Two read-only driver changes, both worth contributing upstream because they
apply to every MSI PRO X870-P WIFI:

1. Give this board the 9-channel entry, so the EZ Conn fan appears in Linux.
2. Map the three missing rails and correct the six wrong labels.

Neither writes anything to the hardware. Both need Gova's agreement first,
given what happened.

---

## 2026-09-22 — Session 4, part 2: evidence in order, then phase 3 begins

**Gova asked for the records to be in order before the next phase.** Three gaps
were open, and all three are now closed:

1. **The thermal shutdown had no record outside the conversation**, and the
   machine had rebooted, so the state was gone. Recovered from the journal of
   the boot that died and written up in
   `data/evidence/2026-09-22-thermal-shutdown/`. The last thing the kernel ever
   logged in that boot was another write rejection, and the journal then stops
   four minutes before the boot officially ends — which is what a hard power cut
   looks like.
2. **The BIOS ground truth existed only as prose.** It is now structured data
   the application can read: `bios-readings.json`, and `linux-vs-bios.json`,
   which gives every `nct6687` channel a verdict of correct, rename, wrong or
   unverified.
3. **The driver source was quoted from `/usr/src`**, which is not evidence
   because it will be gone. The extracts are copied and pinned to the commit.

`data/evidence/README.md` is the index, with four rules: copy rather than link,
say where it came from, keep what disproves a claim, and keep large files out of
git. `CLAUDE.md` now carries all of it, including the rule in capitals that this
project writes nothing to hardware.

**Phase 3 started, with four streams in parallel.** Gova agreed to parallel
agents. `docs/phase-3-plan.md` fixes the file ownership and the interfaces
first, so the streams cannot tread on each other. `model.py`, the collector
protocol, the cache and the two existing collectors are frozen for the round.

**Stream D, the Textual screen, is done and committed.**

- `app/meters.py` holds the drawing decisions as plain functions with plain
  tests, because that is the part most likely to be wrong in a way a person
  notices. A bar is only drawn when there is a real scale; a clock speed with
  no known maximum gets none, rather than a made-up proportion.
- Temperature and fan speed get a display **convention** (0–100 °C, 0–3000 RPM)
  used only when the hardware declares nothing, because `k10temp` declares no
  limits and the `nct6687` limits are not usable. A declared limit always wins.
  Without this, most of the screen had no bar at all.
- A sensor with no threshold is never drawn as an alarm, however high it reads.
  That is the direct lesson of the `nct6687` min/max bug.
- The first reading after discovery is taken and thrown away (`exp-0007`
  finding 4).
- The status bar shows what is hidden as a **number**, reachable with one key.
  A channel kept out of the way must never be silently lost — the same
  reasoning as the rule that a 0 RPM fan header stays on the screen.
- A real bug the tests caught: Textual's `remove()` is asynchronous, so
  rebuilding the panels mounted a second panel with the same id before the first
  had gone. The rebuild now awaits the removal.

Verified headless against the real machine: 60 channels, **1.06 ms per pass**.

**Gova offered the `run-as-root` skill**, which escalates one command through
the desktop's own password prompt. That unblocks installing the driver patch.
It does **not** change ADR 0007: installing a driver that adds sensor reads is
not writing to hardware, and the fan control question stays closed.

**Next**

Collect the three running streams — the driver patch, `Registry` and `Sampler`,
and the naming layer with two new collectors — then integrate. The driver
install waits until Gova is back at the keyboard.

