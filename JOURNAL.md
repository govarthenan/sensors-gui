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

**Decisions**

- ADR 0001 — all project memory lives in the repository.
- ADR 0002 — identify hwmon sources by name and device path, never by index.

**Next**

Gova must choose the GUI toolkit (Q5) and answer Q1, Q2 and Q6. Then
`exp-0002` (Super-I/O chip identification) and `exp-0003` (NVML compared with
`nvidia-smi`).
