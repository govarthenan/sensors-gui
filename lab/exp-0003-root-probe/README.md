# exp-0003 — the root probe

Date: 2026-09-17. Gova ran the commands.

## Question

What do the sensors that need root give on this machine, and which Super-I/O
chip is on the MSI PRO X870-P WIFI?

## Method

```bash
sudo apt install -y smartmontools nvme-cli ddcutil
sudo ./scripts/root-probe.sh
```

Raw output: `data/probes/root-probe-20260917T060712Z/`.

## Result: the Super-I/O question is **not** answered

`sensors-detect` ended with "Sorry, no sensors were detected." **That result is
a false negative.** Three lines earlier the log holds:

```
/dev/port: Operation not permitted
```

The probe could not read one ISA port, even as root.

The cause:

| Check | Value |
|---|---|
| `mokutil --sb-state` | `SecureBoot enabled` |
| `/sys/kernel/security/lockdown` | `none [integrity] confidentiality` |
| `/sys/module/module/parameters/sig_enforce` | `Y` |
| kernel config | `CONFIG_LOCK_DOWN_IN_SECURE_BOOT=y` |

Secure Boot puts the kernel in **integrity lockdown**. Lockdown blocks
`/dev/port` and `iopl`, so **no user-space program can probe the ISA ports on
this machine**. `sensors-detect` cannot find a Super-I/O chip here, whatever
chip is fitted.

### The good news

A kernel module does not use `/dev/port`. It reads the ports from kernel space,
which lockdown does not block. The question is whether an out-of-tree module
can load at all, because `sig_enforce=Y`. It can:

| Check | Value |
|---|---|
| Enrolled MOK | `CN=aipc03-MS-7E47 Secure Boot Module Signature key` |
| Signing key on disk | `/var/lib/shim-signed/mok/MOK.priv` |
| `dkms status` | `nvidia/595.84 ... installed` for two kernels |
| `modinfo nvidia` | `signer: localhost.localdomain Secure Boot Module Signature key` |

DKMS on this machine already signs each module it builds with an enrolled key,
and the NVIDIA module loads. **A `nct6687d` DKMS module will be signed the same
way and will load.** No BIOS change and no MOK enrolment are needed.

## Result: CPU power through RAPL

| Domain | Path | Idle value |
|---|---|---|
| `package-0` | `/sys/class/powercap/intel-rapl:0/` | **40.33 W** |
| `core` | `/sys/class/powercap/intel-rapl:0:0/` | **0.269 W** |

`max_energy_range_uj = 65532610987`. The counter wraps there, so the reader
must handle the wrap.

**Trap.** The `core` domain is **not** the power of all 12 cores. `turbostat`
gave `CorWatt 3.71` for the package and `0.32` for CPU 0, and the RAPL `core`
delta was 0.269 W. On Zen 5 the core energy register is per core, and the
powercap `core` domain shows **core 0 only**. The user interface must label it
"Core 0", or must not show it. Total core power needs the per-core MSRs, which
is what `turbostat` reads.

`enabled` reads `0` for both domains, yet the counters do count. Do not use
`enabled` as a health check.

## Result: the drive, through SMART

`nvme smart-log /dev/nvme0` gives, among others:

| Field | Value |
|---|---|
| `percentage_used` | 0 % |
| `available_spare` | 100 % (threshold 10 %) |
| Data Units Written | 18 127 105 → **9.28 TB** |
| Data Units Read | 5 025 932 → 2.57 TB |
| `power_on_hours` | 320 |
| `power_cycles` | 144 |
| `unsafe_shutdowns` | **28** |
| `media_errors` | 0 |
| `critical_warning` | 0 |
| Thermal Management T1 / T2 counts and total time | all 0 — the drive has never throttled |
| Temperature, Sensor 1, Sensor 2 | 33, 45, 33 °C |

## Result: the memory modules

| Slot | Fitted | Size | Type | Rated | Configured | Voltage | Part | Rank |
|---|---|---|---|---|---|---|---|---|
| DIMMA1 | no | — | — | — | — | — | — | — |
| **DIMMA2** | yes | 32 GB | DDR5 | 5200 MT/s | **6400 MT/s** | 1.1 V | `UD5-6400` | 2 |
| DIMMB1 | no | — | — | — | — | — | — | — |
| **DIMMB2** | yes | 32 GB | DDR5 | 5200 MT/s | **6400 MT/s** | 1.1 V | `UD5-6400` | 2 |

The modules run above their JEDEC rating, so an EXPO or XMP profile is on.

This also names the two `spd5118` sensors. DDR5 puts the SPD hub of slot *n* at
`0x50 + n`:

| I2C address | Slot |
|---|---|
| `0-0051` | **DIMMA2** |
| `0-0053` | **DIMMB2** |

## Result: three unknown I2C clients

`sensors-detect` found clients at **0x49**, **0x4b** and **0x4f** on SMBus port
0 that no lm-sensors driver claims.

`0x49` and `0x4b` fit the DDR5 PMIC pattern: JEDEC puts the PMIC of slot *n* at
`0x48 + n`, which pairs `0x49` with the `0x51` SPD hub of DIMMA2, and `0x4b`
with the `0x53` hub of DIMMB2. A DDR5 PMIC holds the module's own voltage
regulators and can report VIN and the 1.1 V and 1.8 V rails.

`0x4f` is not explained. See `exp-0005`.

> **Safety rule.** A DDR5 PMIC **sets the voltage of the memory module**. Read
> it if you wish. **Never write to an address in 0x48–0x4F.** A wrong write can
> put a wrong voltage on a DIMM.

## Result: the monitors

`ddcutil detect` works, and `gova` needs no `i2c` group, because the `video`
group plus the DRM connector path is enough:

| Display | Bus | DRM connector | Monitor |
|---|---|---|---|
| 1 | `/dev/i2c-4` | `card1-HDMI-A-1` | MSI MD272QXP, serial PB1H824600444 |
| 2 | `/dev/i2c-5` | `card1-DP-1` | MSI MD272QXP, serial PB1H824600465 |

**Note for Gova.** `card1` is the **integrated** Radeon graphics, not the RTX
4090 (which is `card2`). Both monitors are plugged into the motherboard video
outputs, not into the graphics card.

## Findings, in order of importance

1. **Secure Boot lockdown makes `sensors-detect` blind.** Any tool that probes
   the ISA ports from user space fails on this machine. A kernel module does
   not, and DKMS here already signs with an enrolled key, so `nct6687d` can
   still be the answer.
2. The RAPL `core` domain is **core 0 only**, not the package cores.
3. The drive is healthy and has never thermally throttled, but it records **28
   unsafe shutdowns** in 144 power cycles.
4. The two DIMMs are in slots A2 and B2 and run at 6400 MT/s, above their 5200
   MT/s rating.
5. Three I2C clients are unclaimed. Two are almost certainly the DDR5 PMICs.
6. Both monitors run from the integrated graphics, not from the RTX 4090.
