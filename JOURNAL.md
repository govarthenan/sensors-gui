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

**Next**

Gova runs `sudo ./scripts/install-nct6687d.sh`. The expected fan count is now
known, which is what makes a `0 RPM` reading readable: 0 will mean a stopped
fan, not a missing one.

