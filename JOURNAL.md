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

**Stream A, the driver patch, is done and committed. Not installed.**

Two read-only changes to `nct6687d`, both from the BIOS ground truth:

- A board entry for MS-7E47 with 9 fan channels and a new `fan9_label` field,
  so this board can name register `0x144` "EZ Conn Fan" without disturbing the
  MEG Z890 GODLIKE, which is the only other board using that register.
- A voltage override table: two confirmed renames (`DRAM` → `CPU VDDIO`,
  `AVCC3` → `System 3.3V`, both exact value matches), three duplicate channels
  hidden, and **two guesses** — register 15 as `CPU 1P8` and register 14 as
  `CHIPSET Core`.

The two guesses are the only risk, and they are labelled `GUESS` in the source,
in `driver/README.md` and in the script's output, each with the value to expect
and the one line to revert. Each reuses a channel already proven wrong, so
nothing that worked is lost either way.

I verified the patch myself rather than trusting the report: it applies cleanly
to a copy of the pinned source and builds a real `nct6687.ko` against this
kernel's headers. `/usr/src` is untouched. The install script requires root,
backs the source up, dry-runs before applying, and **never opens a `pwm` file
at all**.

**All four streams landed, and the application runs.**

- **Stream B**: `Registry` and `Sampler`. ADR 0008 accepted — the discard of
  the first pass after discovery lives in the registry, not the sampler,
  because it belongs to a hardware event rather than to a particular reader.
  The sampler's loop computes each deadline from a fixed monotonic start, so it
  does not drift, and skips a missed deadline instead of firing catch-up
  passes.
- **Stream C**: the naming layer and two new collectors. The machine went from
  60 channels to **158**: 43 hwmon, 17 NVML, 2 battery, 96 system.
- **Integration**: 152 channels on screen, 6 hidden, **2.22 ms per pass**.

**Four defects that only running it could find**

1. **The hide filter never fired.** The screen applied the naming layer and
   *then* asked the filter, but `verdict()` matches on the label, so a renamed
   sensor came back `unknown` instead of `wrong`. Four channels the BIOS proved
   wrong sat on screen while the status bar claimed they were hidden. The
   filter now judges the sensor as the driver reported it.
2. **Sparklines lied about scale.** Auto-scaling to the window made a quarter
   of a degree of DIMM wobble fill the full height, so a rock-steady sensor
   looked violent. A sparkline now uses the same scale as its bar.
3. **A label was 27 characters in a 24-character column** and was shown cut in
   half.
4. **Twenty snap `loop` devices buried the one real drive** under forty rows of
   zeros. Storage went from 29 rows to 13.

None of these would have been caught by a unit test. They needed the thing to
be run and looked at.

**One integration trap worth remembering:** Textual's `App` already owns an
attribute called `_registry`, so naming ours the same silently broke `compose`
with "Registry object is not iterable".

**Next**

The driver install waits until Gova is back at the keyboard, because
`run-as-root` needs a person there to type the password.

---

## 2026-09-22 — Session 4, part 3: the driver patch, and what it found

Gova installed the patch and the machine answered both open questions. Two
rounds were needed.

**Round 1: both guesses were wrong, and one was wrong usefully.**

- `fan9` at register `0x144` read a constant **0 RPM**, while the BIOS showed
  the EZ Conn fan turning.
- `CPU 1P8` at register 15 read a constant **0.000 V**. Nothing is there.
- `CHIPSET Core` at register 14 read a steady **3.116 V** — not a 1.047 V
  chipset rail, but exactly what a healthy **CR2032** gives. And the MS-7E32
  map in this same driver puts the **CMOS battery** on register 14.
- Both renames were confirmed exactly, and the four duplicate 3.33 V channels
  were gone.

**The fan answer was a comment in the driver's own code.** The default fan
table says of register `0x146`: `// SYS Fan 2, EZConn on others`. The patch had
guessed `0x144` from the one precedent, a sibling board where it is a second
pump. `0x146` is free in the `msi_alt1` mapping because the system fans moved
to `0x154`–`0x15E`.

**Round 2, both fixes confirmed on the machine:**

| Channel | Measured | The BIOS said |
|---|---|---|
| `fan9` **EZ Conn Fan** | 963–988 RPM | 963 and 1612 |
| `in13` **CMOS Battery** | 3.116–3.120 V | not reported |

**963 RPM against the BIOS's 963 RPM.** Gova's case fans are readable in Linux
for the first time, and the CMOS battery turns out to be healthy — I had
earlier warned that a 2.046 V reading was probably the wrong register, and it
was.

**The board now gives 9 fans and 10 voltages**, of which 7 are right, against
8 fans and 14 voltages of which 4 were right.

**Three lessons worth keeping**

1. **A guess labelled as a guess costs nothing and can pay.** Both were wrong,
   and one found the CMOS battery, which nobody was looking for. Each reused a
   channel already proven wrong, so nothing that worked was at risk.
2. **Read the code's own comments before guessing from precedent.** The fan
   register was documented in the driver, and the first patch lost a round by
   reasoning from a sibling board instead.
3. **A steady wrong number is information.** Register 14 reading a constant
   3.116 V was far more useful than the zero at register 15. `exp-0008` made
   the same point with its distinct-value count.

The correction table was rewritten to describe the patched driver, with the
pre-patch state kept under `history_before_patch` so the reasoning can still be
followed. The naming tests moved with it, and say why in the file.

`scripts/patch-nct6687.sh` is now re-runnable: it restores the pristine backup
when the source is already patched, which is what made round 2 possible without
a full uninstall.

**The application, live:** 134 channels, 5 hidden, 2.28 ms per pass,
`EZ Conn Fan 964 RPM` on screen.

---

## 2026-09-22 — End of session 4: verified after a reboot, and handed off

**Gova rebooted and set `CPU Fan Fail Warning Control`.** That was the last
thing outstanding.

**Verified on the machine after that reboot**, not assumed:

- The patched `nct6687` loads by itself at boot and is signed with the enrolled
  MOK.
- `fan/pwm mask=0x1ff` — nine channels, so the ninth survived.
- `fan9 EZ Conn Fan` 963 RPM. `in13 CMOS Battery` 3.116 V.
- **All eight fan headers are at `enable=2`**, under the board's own control.
  No manual mode is left anywhere, and `/etc/modprobe.d/nct6687-force.conf`
  does not exist. The machine carries nothing from the thermal shutdown.
- The application runs: **134 channels, 1.94 ms per pass.**

**`HANDOFF.md` written.** It is the one file to read to pick this up cold: what
runs and how, what the machine is, the 158 channels read and the seven things
still unread, where every document lives, and the rules learned the hard way —
the writing rule, the Secure Boot trap, the two times guessing beat reading,
and why the screen has to be rendered and looked at.

**`scripts/preview-screen.py` added.** The reboot cleared the scratchpad and
took the throwaway preview script with it, which was a good argument for making
it permanent. A terminal application cannot be looked at from a session with no
terminal, and every screen defect that mattered was found by looking rather
than by testing.

**Where the project stands at the end of session 4**

| | |
|---|---|
| Channels read | **158** — 43 hwmon, 17 NVML, 2 battery, 96 system |
| Channels on screen | 134, with 5 hidden and one key to reveal them |
| Cost of a pass | about 2 ms |
| Tests | 279, no mocks |
| Experiments | 10 |
| Decision records | 8 |

**The one big gap left** is the privileged helper of ADR 0005: CPU package
power from RAPL, and SSD wear, TBW and power-on hours from NVMe SMART. Both
need root, both are read-only, and the design is already written down.

Session 4 covered a lot of ground and cost Gova one thermal shutdown, caused by
my own script. The rule that came out of it — this project writes nothing to
hardware — is now in `CLAUDE.md` in capitals, and the answer that script was
chasing came from a photograph of the BIOS a few hours later, for free.


---

## 2026-09-22 — Session 5: phase 2, the privileged helper

**The last big gap is closed.** CPU package power and the drive's SMART health
are on the screen, and the screen still never needs root.

**Read the machine first, then write the code.** `scripts/probe-privileged.sh`
captured both sources before a line of the helper was written, so every field
name comes from this machine under nvme-cli 2.8 and not from memory. Raw:
`data/probes/privileged-20260922T051641Z/`.

Three facts came out of that capture and shaped the code:

1. **The RAPL `core` domain is core 0, not the cores.** It gave 1.69 W while
   `turbostat` gave 2.07–3.68 W for CPU 0 and 22.8–28.0 W for all twelve.
   `exp-0003` found this in September; here it is again with fresh numbers. The
   channel is labelled `CPU Core 0 Power`. Later, live, the helper read
   **2.534 W** where `turbostat` had read **2.55 W** for CPU 0.
2. **The energy counter wraps about every 15 minutes** at this machine's idle
   power. `max_energy_range_uj` is 65 532 610 987 µJ. A reader that ignored
   that would report a large negative power four times an hour.
3. **The `warning_temp_time` fields are in minutes and the `thm_*_total_time`
   fields are in seconds.** Both leave the helper in seconds.

**What was built**

| Part | What |
|---|---|
| `src/sensors_gui/helper/sensors_guid.py` | The service. One file, standard library only, because every import is code that runs as root. |
| `src/sensors_gui/collectors/privileged.py` | The client. An ordinary collector. |
| `scripts/sensors-guid.service` | The systemd unit. |
| `scripts/install-helper.sh` / `uninstall-helper.sh` | Install, enable, **and check**. Re-runnable. |
| `docs/decisions/0009-rules-for-the-privileged-helper.md` | The rules the root code keeps. |

**ADR 0009**, the four decisions worth writing down:

- **No NVMe passthrough ioctl.** The SMART log is read by running a fixed
  `nvme smart-log -o json` argument list, with no shell. The ioctl carries an
  opcode, and the same call that reads log page 02h can, with a different
  opcode, write to the drive. `nvme smart-log` cannot become a write however
  wrong the surrounding code is. On a machine that has already had one
  hardware incident, that is worth 3 ms and a process.
- **Root does not run code from a directory the user can write.** The install
  script copies the helper to `/usr/local/lib/sensors-gui/` and records its
  SHA-256; the client compares versions and logs a warning on drift.
- **The unit enforces the read-only rule.** `ProtectSystem=strict` with
  `ReadWritePaths=/run` makes the whole filesystem read-only for this process
  except the socket's own directory, plus `PrivateNetwork=yes`,
  `RestrictAddressFamilies=AF_UNIX` and a five-capability bounding set. A rule
  the machine keeps is stronger than a rule a person must remember.
- **The protocol has no way to name a path.** Three commands, none of which
  takes a path, a device or a file name.

**Four defects, and the tests found only two of them.**

1. The label read `CPU Package 0 Power`. There is one package.
2. A failed `nvme` call reported nvme-cli's bold usage banner instead of
   `Permission denied`, which is the one word that tells a person what to do.
3. **A failed bind made the root process delete the file in its way.**
   `socketserver` calls `server_close()` when `server_bind()` raises, and the
   override unlinked the socket path without asking what was there. Pointed at
   an ordinary file, as root, it deleted it. **This is the same shape as fault
   1 of the thermal shutdown: a clean-up path that acted without checking what
   it was acting on.** A test now proves it does not.
4. `nvme_command=None` searched the PATH, so "nvme-cli is not installed" could
   not be tested on a machine that has it, and that branch never ran.

**Measured, with the service running** (`exp-0011`):

| | |
|---|---|
| New channels | **19** — 4 RAPL, 15 SMART. All gave a value. |
| Cost of one request over the socket | **0.034–0.080 ms** |
| Cost of one SMART read from the drive | 3.0 ms, so the helper reads it once a minute |
| The screen | **153 channels, 2.02 ms per pass** |
| Socket | `srw-rw---- root:gova`, read by the user with no password |
| Tests | **326**, up from 279. No mocks: real sysfs trees, a real `nvme` process, real Unix sockets. |

**The drive, as the screen now shows it live:** 0 % worn, 100 % spare, 9.2 TiB
written, 331 power-on hours, **31 unsafe shutdowns in 150 power cycles**, no
media errors, and all six throttle counters at zero — it has never throttled.

That also settles a small disagreement between two documents. `HANDOFF.md`
said 29 unsafe shutdowns and `state/STATUS.md` said 28. Both were right when
they were written, at 145 and 144 power cycles. The number is now a live
channel, so no document needs to hold a copy of it. Q10 is rewritten to ask
about the **rate**, which is the part that does not change.

**Still missing after this:** per-core power for all twelve cores, which needs
the Ryzen SMU mailbox, and total system power, which nothing can measure
because the NZXT C1200 has no telemetry link.

---

## 2026-09-22 — Session 5, part 2: the first push

**The project is on GitHub, privately**: <https://github.com/govarthenan/sensors-gui>.
32 commits, 223 files, every commit signed.

**A sweep for credentials and personal data ran first.** It found nothing
critical: no keys, no tokens, no `.env`, no IP addresses, no Wi-Fi names, and
no machine UUID — `dmidecode` was never run with `-t system`, so it was never
captured. It also settled a question I could not answer myself, because
`exiftool` is not installed here: **all 12 photographs carry no EXIF data**.
They were re-encoded at some point, which stripped it.

It found **8 unique hardware identifiers** in tracked files: the motherboard
serial, two DIMM serials, the NVMe serial and its EUI-64, two monitor serials,
two MAC addresses, a keyboard serial and the mouse device ID. Gova decided to
**keep them all**. The repository is private, it holds his own machine's data,
and redacting the probe files would break the project rule that evidence is
copied whole and never altered. That decision has to be made again if the
repository is ever made public; `HANDOFF.md` says where they are.

**`HANDOFF.md` is off the remote, history and all.** It was purged with
`git-filter-repo` and it is in `.gitignore`. It is the working picture of one
person's desktop, so it stays on that desktop.

**I made a mistake and the sweep caught it.** The commit that added the
`.gitignore` rule said the file "is also purged from the whole history". I had
not done the purge yet. The statement was true an hour later, but it was not
true when I wrote it, and a commit message is not the place for an intention.

**Two defects came out of the rewrite itself.**

1. `git rebase --root --gpg-sign` replayed nothing, because the branch was
   already where it was going, so all 32 commits stayed unsigned and the
   summary said "Successfully rebased". `--force-rebase` is what actually
   recreates and signs them. A command that reports success and does nothing is
   worth remembering.
2. **A root-owned directory in the repository blocked the rewrite.**
   `scripts/patch-nct6687.sh` decided who should own its output from
   `SUDO_USER` alone. The `run-as-root` skill uses `pkexec`, which sets
   `PKEXEC_UID` and not `SUDO_USER`, so ten files in `data/probes/` stayed
   owned by root. Git could not delete what it did not own. Undoing it needed a
   separate root command from Gova.

   The same gap was in `install-nct6687d.sh` and `root-probe.sh`. All three now
   check both variables, with the reason written beside the code.

---

## 2026-09-22 — Session 6: per-core power, and a write nobody had noticed

**Goal:** Gova asked whether the Ryzen SMU target and the three unmapped
voltage rails complement each other, and to run them together if they do.

**They are one question, and it had a rule problem.** `exp-0010` proved the
rails are not in the board sensor chip at all, so the only place left to look
was the processor itself — the same place the SMU target pointed at. But
`ryzen_smu` and `zenpower3` do not read a register: they **write a command word
into the SMU mailbox** and read the reply. ADR 0007 forbids that, with no
exceptions, since the fan write of 2026-09-22 stopped the radiator fans and the
board shut the machine down at 98 °C. The plan had carried a forbidden route
for five sessions, because "install a DKMS module" does not sound like "write
to the processor".

**The answer was in a header file on this machine.**

```
/usr/src/linux-headers-7.0.0-31-generic/arch/x86/include/asm/msr-index.h:512
#define MSR_AMD_CORE_ENERGY_STATUS  0xc001029a
```

One energy counter for **each core**, and reading it is a read. `exp-0012`
captured it in three phases — idle, one thread busy, every thread busy — and
the middle phase settled it: with `cpu6` busy, **one** counter moved, to
17.4 W, while the other eleven stayed at idle.

**Measured**

| | |
|---|---|
| Cores under an all-core load | **103.98 W**, against `turbostat` **104.10 W** — 0.1 % apart |
| Package | 157.24 W, against 157.34 W |
| One sweep of 24 threads, `pread()` | **0.070 ms** |
| One sweep through the `rdmsr` process | 8.5-9.1 ms, a hundred times more |
| New channels | **13**: twelve cores and their sum |
| The screen | **166 channels, 5 hidden, 1.95 ms per pass** |
| Tests | **350**, up from 326. Still no mocks. |

**Two defects, and the screen found both.** The tests found neither.

1. Two rows both read `CPU Core 0 Power`, because the powercap `core` domain is
   also core 0. The older one is now `CPU Core 0 (RAPL)`. They read **1.624 W
   each**, which is a third confirmation of what `exp-0003` and `exp-0011` said
   about that domain.
2. The rows sorted as text: `Core 0, 1, 10, 11, 12, 13, 2, 3`. The sort now
   reads a number as a number, which also repairs `CPU0 use` to `CPU23 use`.

**A third thing the tests taught.** The fake MSR node is a sparse file, and in
a file the offset is a byte while on `/dev/cpu/N/msr` it is a register number.
So `0xc0010299` and `0xc001029a`, which are two registers on the machine,
overlap by seven bytes in the fake. The test double now says so, and a test
sets its counters only after the sampler has read the unit.

**Decisions**

- ADR 0010 — a register may be read; a mailbox may not be written. The three
  unmapped rails (`VDD MISC`, `CPU 1P8`, `CHIPSET Core`) are **dropped**, under
  the closing sentence of ADR 0007: if a question can only be answered by
  writing, drop the question.

**What changed on the machine**

- `sensors-guid` gained `CAP_SYS_RAWIO`, which `man 7 capabilities` requires to
  open an MSR node. Everything else about the unit is unchanged, so the
  filesystem stays read-only for it and the node is opened `O_RDONLY`.
- `/etc/modules-load.d/sensors-gui.conf` makes the `msr` module load at boot.
  **Not yet tested across a reboot.**

**Next**

Check the module after the next reboot. Then phase 4, or the driver patch
upstream. The Ryzen SMU leaves the `exp-0005` target list; the RTX 4090 board
over I2C is next on it, and it needs the same question asked first: does the
route read, or does it write?

---

## 2026-09-22 — Session 7: the card's I2C route closed, and each fan found

**Goal:** `exp-0005` target 3, the RTX 4090 board sensors. Gova chose it.

**What happened**

- **Checked the reboot item first, and it is only half true.** The machine did
  reboot, at 10:38:49, and `systemd-modules-load` did insert `msr` at boot. But
  `/etc/modules-load.d/sensors-gui.conf` was written at **11:32:16, after that
  boot**, so the file this project installed has still not been through one.
  The module loaded from `/etc/modules-load.d/libvirt-msr.conf`, which libvirt
  put there on 2026-06-24. So there is a safety net under our file, and the
  check stays open for the next reboot. The helper is enabled and active with
  `NRestarts=0`, and all twelve core channels read a value.
- **Found a stale decision record.** Everything in the repository — `CLAUDE.md`,
  `HANDOFF.md`, `state/STATUS.md`, ADR 0009 and ADR 0010 — cites ADR 0007 as
  "this project writes nothing to hardware". **The file did not say that.** It
  still held the six rules for writing safely, and the amendment of 2026-09-21
  that permits stopping a fan. The revert after the thermal shutdown was made
  everywhere except in the decision itself. Its old rule 1, read literally,
  permits an I2C write to any address outside `0x48`–`0x4F` — which is exactly
  the text that would have governed today's work. An amendment now records the
  revert; the old text stays, because it is what the machine shut down under.
- **`exp-0013`, part 1: the I2C route writes.** Answered on paper, with no bus
  touched. An I2C read must **write** the register number first. `i2cget(8)`
  says of itself that "an SMBus read transaction can be seen as a write
  transaction by certain chips", and `i2cdetect(8)` that it "can confuse your
  I2C bus, cause data loss and worse". It is the same shape as the SMN index
  register that ADR 0010 already closed, and on a card the second master is the
  card's own controller. **Dropped. ADR 0011.**
- **`exp-0013`, part 2: the `TLIMIT` lead failed.** `exp-0002` found those
  fields hold a headroom, so `threshold − headroom` might have given the
  hotspot. 95 samples from idle to 99 % use, edge 32 → 40 °C, power 43.7 →
  132.1 W: all three fields never moved. They are fixed offsets between the
  thresholds. Sensor indexes 1 to 7 are all "Invalid Argument".
- **`exp-0013`, part 3: the speed of each fan, with no write.** A sweep of all
  302 NVML fields found `nvmlDeviceGetFanSpeedRPM`, which reports **2 fans**
  separately. Under one load: **1205 and 1520 RPM** — the two fans do not turn
  at the same speed, and the single `fan_speed` channel reports fan 0 alone.
  Gova asked for an RPM channel and a percent channel for each fan, with the
  original kept. **4 new channels: 175 on screen, 1.84 ms per pass, 356 tests
  pass.**

**Findings**

1. **A rule that lives in five documents and not in the one that defines it is
   a defect.** Nothing was wrong on the screen, and every derived document was
   right. The source was wrong, and today's task was the first one it would
   have mattered for.
2. **Second time: the plan named the write, and the read was in the standard
   interface.** Session 6 found per-core power in an MSR the kernel's own
   header names, after five sessions of planning a DKMS module that writes.
   Today per-fan RPM was in NVML, after a plan that said "the card's own I2C
   bus". Sweep the ordinary interface before believing the exotic route.
3. **A negative result needs a measurement too.** "TLIMIT might hold the
   hotspot" was only closed by watching it stay still while the card warmed.

**Decisions**

- ADR 0011 — no I2C transaction, on any bus, at any address. It closes the
  card's hotspot, memory and VRM temperatures, the DDR5 PMIC rails
  (`exp-0005` target 4) and the unknown client at `0x4f` (target 5). Reading
  what a kernel driver publishes, as the DIMM temperatures are read, is
  untouched.
- ADR 0007 — the revert of 2026-09-22 is written into the decision itself.

**Next**

Phase 4, history and alarms. `exp-0005` has two targets left, the Wi-Fi chip
and MYSTIC LIGHT, and each gets the ADR 0010 question first.

**Added at the end of session 7**

Gova dropped phase 4: *"No need for history at all. This was all for fun
anyways."* So there is no store, no retention design and no graph over time,
and alarms go with it. The plan document was not written. The sampler's ring
buffer is the whole of the history from now on, by choice and not by omission.

That changes what "next" means. The application does what it was built to do:
it reads 170 channels of this machine and shows them. What is left on the list
is small and optional, and none of it is needed for the thing to work.


---

## 2026-09-22 — Session 8: the GUI stream begins, and the framework is chosen

**Goal:** `docs/gui-goal.md`, checkpoint 1. Choose the framework, record the
ADR, build a spike on the real sampler, and measure what it costs.

**What happened**

- **Read the brief and everything it points at**, then ran the terminal screen
  and looked at it: 175 channels, 2.31 ms on the last pass. That number turned
  out to be half the story; see below.
- **Built the same window twice**, both driven by the real `Registry`,
  `Sampler` and all five collectors, both drawing a large number, an arc gauge
  and a line over the last 120 samples:
  - a local web application — FastAPI on `127.0.0.1`, one frame for each
    sample over a WebSocket, shown by `google-chrome --app=` in its own
    profile, with no Node, no bundler and no build step;
  - the same thing in PySide6, sampler on a `QThread`.
- **Measured both, with everything else on the desktop left alone.** Both held
  **10.00 Hz with all 175 channels**, and the web window spent 0.29 ms of
  browser time on each frame.

| Running | CPU, cores | Memory |
|---|---|---|
| collection layer alone, 10 Hz | 0.0377 | 86 MiB |
| web window, 175 channels, 10 Hz | **0.1207** | 109 MiB + 1257 MiB |
| Qt window, 175 channels, 10 Hz | **0.0617** | 175 MiB |

- **Qt was cheaper and still lost.** Three reasons, in ADR 0012: the brief's
  central ask — an SVG of the hardware with each sensor placed on it, and a
  five-part tooltip on every one of 175 channels — is native in a browser and
  bespoke in Qt widgets; the cost gap is 0.059 cores, which is **0.25 % of
  this machine**; and **PySide6 does not start on this machine**. It needs
  `libxcb-cursor0`, which is not installed, so the Qt spike was measured only
  after the package was unpacked into a temporary directory as an ordinary
  user. Nothing on the machine was changed to get that number.
- **Asked whether the window changes what it measures**, because a browser
  composites through the card this application displays. Measured, 40 s in
  each state: nothing open 44.41 W, web window 40.28 W, Qt window 41.75 W.
  **The test separated nothing** — with nothing of ours open the card read the
  highest power of the three, because the desktop was busy. It is kept as it
  is, because it is the test that would have disproved the decision.

**Findings**

1. **The pass has a long tail, and six sessions of notes missed it.** 600
   passes at 10 Hz: p50 **2.157 ms**, p95 **26.448 ms**, max **56.839 ms**.
   Timing each collector says where it goes: the NVIDIA collector, p50
   0.102 ms and max **68.523 ms**, 31 passes of 600 over 20 ms. It is the two
   PCIe calls of `exp-0006`, about 20 ms each, which run only when their own
   interval expires. Two consequences: the GUI must sample on a worker thread,
   never on the event loop; and `docs/architecture.md` sets a 50 ms budget for
   one pass that **the machine does not keep**. Recorded as Q11.
2. **A status bar that prints the last value hides the distribution.** The
   "about 2 ms per pass" repeated since session 3 is the last pass, which is
   near the median. Nothing on the screen was wrong. The number was simply
   never the whole picture, and no test would ever have said so. Recorded as
   Q12; the GUI will show the median and the maximum.
3. **The spike's own gauge was drawn with a guessed number**, a path length of
   345 that was never measured, inside a box too short for the arc. The window
   showed two disconnected pieces. Read with `getTotalLength()` now. This is
   register 14 of `exp-0010` again: a guess that is not labelled a guess costs
   something. Both defects in the spike were found by looking at the window,
   neither by a test.

**Decisions**

- ADR 0012 — the GUI is a local web application in a dedicated Chrome
  application window, with the Python collection layer behind a WebSocket on
  `127.0.0.1`. It supersedes ADR 0004 for the new front end only; the terminal
  screen stays until checkpoint 7 is accepted. Electron and Tauri were
  rejected: Electron adds a runtime, a bundler and a packaging step that the
  brief puts out of scope, and Tauri needs a root install and a compile step.
- PySide6 was removed from the project after the measurement. `spike_qt.py`
  stays, with the two commands that bring it back.

**Next**

Checkpoint 1: wait for Gova. Nothing of the application itself is written yet,
and checkpoint 2 does not start before Gova answers.

---

## 2026-09-22 — Session 8, checkpoint 1: Gova's answer, and the widget review

**Gova's feedback, verbatim**

> 1. choose the option that gives the best experience
> 2. don't care at all
> 3. ok
>
> The thermal dial on top and the line chart look sub par.

**What that settled**

| # | The question | Gova's answer | What was done |
|---|---|---|---|
| 1 | Q11: raise the 50 ms pass budget, or give the two PCIe channels a longer interval? | "choose the option that gives the best experience" | Neither changes the collection layer. See below. |
| 2 | Chrome's 1.2 GiB of memory | "don't care at all" | The web stack is accepted. ADR 0012 stands. |
| 3 | The graphics-card test that separated nothing | "ok" | Kept as it is, with its caveat. |
| — | The dial and the line chart | "look sub par" | Both were rebuilt. Section below. |

**Q11, decided: the best experience, and no change to the collection layer.**
The tail is not moved, it is taken off the path that matters. The sampler runs
on a worker thread, so a 57 ms pass never holds up a frame; the two PCIe
channels keep their present interval, so PCIe throughput stays live; and
`docs/architecture.md` is corrected to say what the machine really does
instead of a budget it does not keep. Measured after the change: **10.00 Hz
with no dropped frame**, at a median pass of 2.4 ms and a maximum of 68.5 ms.
Raising the interval was rejected because it would make two real channels
slower to buy smoothness that the thread already buys for nothing.

**The widgets were rebuilt, and the dial was the wrong form**

The `dataviz` skill, which `docs/gui-goal.md` section 4.4 tells this project
to follow, puts "a single ratio against a limit" on a **meter**, not on a
dial. So the default is now a meter: the track is the fill's own hue, the
thresholds are hairlines on the track, and the ends of the scale are labelled.
A dial is kept for at most one hero value in a view, and it is built properly
— 270°, tick marks, the threshold zone on the track, the number inside.

**The old dial was also dishonest, which nobody had noticed.** It drew `Tctl`
against a scale of 0 to 100 °C. `k10temp` publishes **no** maximum and no
threshold for `Tctl`; the scale was invented by the spike's own fallback. Only
66 of the 175 channels carry a real scale and only 5 carry a threshold, so the
widget set now refuses to draw a bar or a dial without one, and shows a number
and a line instead.

The line chart was rebuilt as well: a stable axis that only moves when the
data leaves it, a span floor, clean tick values, hairline gridlines, a 10 %
wash, a 2 px line, an end marker with a surface ring, a labelled end point,
any published threshold drawn as a reference line with its word, and a
crosshair with a tooltip.

**Findings**

1. **A guessed scale is a guessed hardware fact.** `CLAUDE.md` forbids
   guessing a hardware fact, and the project has caught itself twice before
   on a register and on which card drove the monitors. A dial drawn to 100 °C
   when the driver publishes no maximum is the same mistake in a picture. The
   widget set now cannot make it: no scale, no bar.
2. **Two copies of a rule drift, and it took a test to see it.**
   `widgets.js` holds a second copy of `SensorSpec.format`, because the
   browser cannot call Python. A test that runs the real JavaScript in node
   against the real Python found that **41.25 °C read `41.2` in the terminal
   and `41.3` in the window**: Python rounds a tie to the even digit and
   `Number.toFixed` rounds it away from zero. The obvious repair,
   `Intl.NumberFormat` with `halfEven`, was **also wrong** — it turns -40.15
   into -40.2 where Python gives -40.1, because it rounds the shortest decimal
   form and not the number. The tie is now found in the exact expansion. The
   test sweeps about 2000 values across every unit and sixteen orders of
   magnitude.
3. **The colour validator earned its keep.** Run against the dark surface, it
   reports that critical and good are 4.1 apart under deuteranopia, far below
   the floor. So no state in this application is carried by colour: every one
   has an icon and a word.
4. **Four defects were found by opening the page, and none by a test**: the
   dial's scale labels were drawn under the arc and collided with it, the
   minimum was hidden completely on three of six dials, the threshold band was
   as heavy as the fill so a cool DIMM looked warm, and the endpoints read
   `480.00` instead of `480`.

**What the application costs now**

| Rate | Python | Chrome | Total |
|---|---|---|---|
| 1 Hz | 0.0120 cores | 0.0233 cores | **0.0353 cores** |
| 10 Hz | 0.0393 cores | 0.1400 cores | **0.1793 cores** |

0.1793 cores is **0.75 % of this machine**. It is higher than the spike's
0.1207 because the review page redraws six dials, six meters, six sparklines
and four charts on every frame; a real view draws less. Recorded in
`lab/exp-0015-gui-checkpoints/results/`.

**Next**

Gova picks the meter or the dial for a headline value, and says whether the
line chart is now right. Then checkpoint 2, the shell and the summary view.

---

## 2026-09-22 — Session 8, checkpoint 2: the shell and the summary view

**Gova's feedback on the widget review, verbatim**

> Go with the meter. And yes, much better now.

**What that settled, and what was done**

- The meter is the form for a value against a limit. **The dial was removed**
  from the widget set, from the gallery and from the code. The screenshot in
  `lab/exp-0015-gui-checkpoints/results/` keeps the record of what it was.
- The line chart is accepted as it stands.

**What was built**

The shell and the summary view, which is checkpoint 2.

- **The shell**: a header with the rate and pause controls, a navigation list
  of all eleven views, a stage that holds one view, and a status bar. The
  address after `#` says which view is on screen, so a view opens directly and
  the back button works. Only the view on screen is painted.
- **Every view that is not built yet is listed and says which checkpoint
  builds it.** An empty page would have been the other choice, and it would
  have hidden the plan.
- **The summary view**: the hottest part of the machine with every temperature
  beside it, the power that can be measured with a note that total system
  power cannot be, the four loads that publish a real scale, two charts,
  memory, storage health, every fan with the reason five headers read zero,
  the channels that come through the root helper, and what each colour means.
- **The status bar** carries all of section 4.5: channels shown and hidden,
  the rate, the median and the maximum pass, the paint time, the time of the
  last sample, whether the helper answers, and that the application is read
  only.

**Findings**

1. **Three defects, all found by opening the page, none by a test.** The line
   chart had a fixed width and ran underneath the card beside it; the card
   titles wrapped because the note beside them would not give way; and the
   view left a third of the screen empty. The chart now measures the box it is
   in and redraws when the box changes.
2. **A fifth of the cost was one wasted call.** The view cost 0.2147 cores at
   10 Hz. Writing text into an element only when the text is different brought
   it to **0.1720**. At 10 Hz with 175 channels that call happens about 1750
   times a second, and most values do not change between two passes.
3. **The hottest part of this machine at idle is the drive, not the
   processor.** `Sensor 1` on the SN770 read 62-65 °C while `Tctl` was near 50.
   The summary says so, and it also says that neither sensor publishes a
   threshold, so the application does not judge it.

**What the summary costs**

| Rate | Python | Chrome | Total | Of the machine |
|---|---|---|---|---|
| 1 Hz | 0.0107 | 0.0200 | **0.0307 cores** | 0.13 % |
| 10 Hz | 0.0403 | 0.1317 | **0.1720 cores** | 0.72 % |

**Tests.** 400 pass, no mocks. Eleven of them run the real `widgets.js` in
node and hold the rules that matter: a meter only where the hardware publishes
a scale, a state only from a published threshold, an axis with a floor that
does not move while the data fits it.

**Next**

Checkpoint 3: the graphics card, in full. It is the reference every other
group is built against.

---

## 2026-09-22 — Session 8: Gova's core display, and the processor leads

**Gova's words, verbatim**

> What do you think about using a component similar to a bar chart sound
> visualizer to display cpu load for all the cores?
> Something like this [image]. Use the image to reference the idea only. Not
> the colors or the design language.
> ---
> 1. Yes, the cpu is better.
> 2. We'll add more information as we derive them from other components as we
> develop the other screen as well.

**The answer: yes, with three conditions.** The form underneath the idea is a
bar chart comparing one measure across a category, which is the right form for
the question "is the load spread, or pinned to one core?" — a question that 24
rows of numbers cannot answer at a glance. The conditions are what keeps it a
measurement rather than a decoration:

1. **No rainbow.** The reference picture runs a spectrum across the columns,
   which paints *position* as if it were meaning. The `dataviz` skill is
   explicit: colour follows the entity, never its rank. Every column carries
   the same hue, and colour is left free to carry state.
2. **The order is the hardware's and never the values'.** A display that
   re-sorted itself by magnitude would flicker and would destroy the identity
   of each column.
3. **One scale for every column, from the spec.** A column half full means
   half of 100 %, always — never half of the largest value on screen.

**The grouping had to be read from the machine, and a guess would have been
wrong.** `/sys/devices/system/cpu/cpuN/topology/` says a thread's sibling is
**12 away**, not next to it: `cpu0` and `cpu12` are one core. Pairing `cpu0`
with `cpu1` would have put two different cores side by side and made a busy
core look half idle. The probe is
`data/probes/2026-09-22-cpu-topology.txt` and the table is in
`docs/hardware-inventory.md`.

It settled two more things the application needed. The gap in the core numbers
is real — the kernel numbers the cores 0-5 and 8-13, exactly as the per-core
energy channels of `exp-0012` are labelled, so `CPU Core 8 Power` is the
seventh core and the first on CCD 2. And `Tccd1` covers cores 0-5 while
`Tccd2` covers 8-13, so a core's temperature is now known.

**What was built.** `CoreBars`: one column for each thread, the two threads of
a core together, the two dies apart, with the die named under its own block so
the display needs no legend. Two versions are on the review page, solid and in
blocks of 5 %, and the same component draws the twelve per-core powers, which
shows it generalises. Hovering names the core and the thread.

**Findings**

1. **Twice the display had to be made smaller to be read.** A column that
   fills its slot is a block, not a level meter: on a 2500 px screen an
   uncapped slot is 100 px wide. A column is now at most 16 px and two columns
   at most 26 px apart, and what is left over is margin. The `dataviz` skill
   says this as a rule — cap the mark, let the leftover be air — and the
   screen said it again.
2. **A caption in the page cannot stay aligned with a mark on a canvas.** The
   die names were laid out with the page's own box model and drifted away from
   the blocks they named. They are drawn on the canvas now, where the geometry
   is known.
3. **A path inside a block comment ended it.** `/sys/.../cpu*/topology/`
   contains `*/`, which closed the comment and broke the module. Caught by
   loading every front-end module in node, which is now a habit worth keeping.
4. **I ran the machine to 95.1 °C to get a screenshot, and that was
   careless.** Six busy threads for a demonstration. Nothing was written to
   hardware, the fans answered at 3108 RPM and the processor throttles itself
   at that temperature, so it was never the shutdown of 2026-09-22 — that one
   happened because a write had **stopped** the fans. But heating this machine
   for a picture is not a good reason. The loops were stopped, Tctl fell to
   59 °C, and a demonstration needs two threads, not six.

**Gova's other two answers**

- **"the cpu is better"**: the summary now leads with `Tctl`, the processor's
  control sensor, instead of whichever sensor happens to be hottest. At idle
  the hottest sensor on this machine is the **drive** at 62-65 °C, which is
  true and is not what a person opens the screen to see. The hottest sensor is
  still named, on the line under the figure.
- **"We'll add more information as we derive them"**: the empty space at the
  bottom of the summary is left as it is, for the later views to fill.

**Tests.** 402 pass. Two of the new ones read
`data/probes/2026-09-22-cpu-topology.txt` and check the front end's copy of
the topology against what the machine actually reported, so the two cannot
drift apart.

**Next**

Gova chooses solid columns or blocks of 5 %. Then checkpoint 3, the graphics
card.

---

## 2026-09-22 — Session 8, end: the core display is chosen

**Gova's words, verbatim**

> Good work.
> Solid column for each core. I'm thinking that we could experiment showing
> such a bar graph each for core load, wattage, temperature etc. as this is a
> great way to visualize spread across the cores. But yes, I'm eager to see
> the other representations you come up with, as well.
>
> We could now move the work to another conversation, as this one's context
> window is filling up. Could you please end this convo and and write a
> handoff doc in ./tmp ?

**What was done**

- **Solid columns kept, blocks of 5 % removed** from `CoreBars`, from the
  review page and from the code. The screenshot in
  `lab/exp-0015-gui-checkpoints/results/2026-09-22-core-display-review.png`
  keeps the record of both.
- `tmp/HANDOFF-gui-stream.md` written, for the conversation that continues
  this work.

**One thing the next session must not get wrong.** Gova's idea is one of these
displays for each measure: load, power, temperature. Load and power are there
— 24 threads and 12 cores. **Temperature is not, and cannot be.** `k10temp` on
Zen 5 gives `Tctl` and one `Tccd` for each of the two dies, and nothing per
core (`docs/sensor-sources.md` section A). A bar for each core's temperature
would be twelve copies of two numbers, which is a picture of a measurement
this machine never made. The honest version is two columns, or the two blocks
of the load display shaded by their die temperature, and the tooltip saying
which sensor it is. Do not draw twelve.

**One question Gova's words leave open.** "Solid column for each core" may
mean the solid version, which is how it is built (24 columns, one for each
thread, paired by core), or it may mean one column for each core rather than
for each thread. The display is unchanged until Gova says which.

---

## 2026-09-23 — Session 9, checkpoint 3: the graphics card

**What was built**

The graphics card view, which `docs/gui-goal.md` calls the reference for
every other group.

- **All 21 card channels on screen**, in eight cards — temperature, power,
  fans, load, memory, clocks, PCIe link, processes — and on a schematic of
  the card. A meter only where the spec carries a scale; a number and a line
  elsewhere.
- **A description for every channel**, in `src/sensors_gui/descriptions.py`,
  next to the spec, so the terminal screen and the GUI share it. **Every
  sentence names its source**, and `tests/test_descriptions.py` fails if a
  source is not a file in this repository. A channel of another group has no
  description yet and says so; none is guessed.
- **The tooltip panel**, on every value and on every row of the diagram, by
  hover and by keyboard focus. It gives the five parts of section 4.2: what
  it measures, where it is read from, how it differs from its neighbours, the
  safe range with where the value sits, and the read interval with the age of
  the value. It stays live while it is open.
- **What the card cannot give is on screen.** The hotspot, memory and VRM
  temperatures read "not readable", and the tooltip gives the reason and
  ADR 0011. The clock event reasons and the PCIe link, which NVML gives and
  the collector does not read, read "not collected" (Q13).
- **The diagram is a schematic by function**, and says so in its own second
  line: no picture of the bare board is in this repository. Each reading is
  on the part NVIDIA names for it. Both fans and the hotspot are in a dashed
  "position not established" area. Every claim is in
  `docs/diagram-positions.md`.
- **The two fans on one axis**, in two validated colours (worst CVD ΔE 26.8),
  with a legend and a label at the end of each line, so the gap between them
  that `exp-0013` found is seen, not read.

**Findings**

1. **NVIDIA's own words were on the machine the whole time.**
   `nvidia-smi --help-query-gpu` prints a sentence for every field. It is
   copied whole into `data/evidence/nvidia-field-descriptions-2026-09-23/`,
   and most tooltip sentences rest on it. One of them changes how a channel
   must be read: the fan percent is "the intended fan speed", which "may
   exceed 100 %", and "if the fan is physically blocked … will not match the
   actual fan speed". So the percent is what the card asks, and the RPM is
   what the fan does, and the view puts them side by side.
2. **The inventory was out of date.** The driver is **595.91.07**, not
   595.84; it was updated after `exp-0002`. Corrected, with both versions
   kept.
3. **Six defects were found by opening the view, none by a test.** An axis
   ran from −1 to 1 RPM for two fans at rest — a speed below zero. Two ticks
   on the VRAM chart both read `1.3 GiB`. The SM clock's end label was cut
   off. A line of text ran out of a box on the diagram. The meter printed the
   ends of its scale raw, which would have read `25757220864` for VRAM. And
   after a change Chrome served the old `widgets.js` from its cache, so a
   reload showed the old page; the server now tells the browser to revalidate.
   Two of the six now have tests.
4. **"Normal" is a judgement.** The first tooltip said "normal" for the card's
   power, which publishes no threshold. It now says "not judged" there, which
   is the rule the summary already kept for `Tctl`.

**What it costs**

| Rate | Python | Chrome | Total | Of the machine |
|---|---|---|---|---|
| 1 Hz | 0.0127 | 0.0323 | **0.0450 cores** | 0.19 % |
| 10 Hz | 0.0423 | 0.1017 | **0.1440 cores** | 0.60 % |

**Tests.** 472 pass, no mocks. New: the descriptions against the real card
and against the files they cite; the tooltip's five parts, running the real
`tooltip.js` in node on the real Python descriptions; the axis floor; the
cache header.

**For Gova to look at**

`uv run python -m sensors_gui.web`, then "Graphics card". Hover anything.

1. The diagram is a schematic by function, not a picture of the board. Is
   that the right call, or do you want to send a photograph of the card (or
   point at MSI's drawing) so the regions can move to where the parts sit?
   That photograph would also answer how many physical fans the card has
   (Q14).
2. Q13: add the clock event reasons and the PCIe link to the collector? Same
   source, read only.
3. Q16: give the VRAM clock its maximum, so it gets a meter like the SM clock?

**Next**

Wait for Gova. Then apply the feedback to this view, to the summary, and to
every later group before checkpoint 4 starts.
