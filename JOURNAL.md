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

