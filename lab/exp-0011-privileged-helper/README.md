# exp-0011 — the privileged helper

Date: 2026-09-22, session 5. Gova approved each root command at the desktop
password dialog, through the `run-as-root` skill.

## Question

Two sensor sources on this machine need root, and the screen must not. Can a
small root service publish them on a Unix socket, and do the numbers it gives
agree with an independent measurement?

The two sources, and why they need root:

| Source | Path | Mode |
|---|---|---|
| RAPL CPU energy | `/sys/class/powercap/intel-rapl:*/energy_uj` | `-r--------` root:root |
| NVMe SMART log | `/dev/nvme0` | `crw-------` root:root |

## Method

1. `sudo ./scripts/probe-privileged.sh` — a read-only capture of both sources,
   so that the reader could be built against real numbers and real field names
   instead of a guess. Raw output: `data/probes/privileged-20260922T051641Z/`.
2. Build `sensors-guid` (one file, standard library only) and
   `PrivilegedCollector` (the client). 47 tests, no mocks.
3. `sudo ./scripts/install-helper.sh` — install, enable, start **and check**.
4. Read the socket as the ordinary user `gova`, with no password.
5. Render the screen and look at it.

## Result: it works, and the numbers agree

**19 new channels**, all giving a value: 4 from RAPL and 15 from SMART.

### RAPL against turbostat — `results/rapl-vs-turbostat.txt`

| Measure | RAPL | turbostat | Verdict |
|---|---|---|---|
| CPU package power | 69.02 W | 75–81 W | The same size. The two did not measure the same seconds. |
| RAPL `core` domain | 1.69 W | CPU 0 alone: 2.07–3.68 W | **Agrees with one core.** |
| RAPL `core` domain | 1.69 W | all twelve cores: 22.8–28.0 W | **Does not agree with the package.** |

**This confirms `exp-0003` finding 2 with fresh numbers.** The powercap `core`
domain follows core 0, not the twelve cores. The channel is therefore labelled
`CPU Core 0 Power`. Calling it "CPU Cores" would be wrong by a factor of more
than ten.

Later, with the service running, the helper reported `CPU Core 0 Power`
**2.534 W** while `turbostat` had given CPU 0 **2.55 W**. Two different
mechanisms, the same number.

### The counter wraps, and often

`max_energy_range_uj` is **65 532 610 987**. At the 70 W this machine idles
near, the counter fills in about **15 minutes**. A reader that ignored the wrap
would report a large negative power four times an hour. The helper takes the
rise modulo the range, and a test drives a real wrap through it.

### SMART — `results/helper-live-readings.txt`

Read from the socket by the user `gova`, **with no root and no password**:

| Channel | Value |
|---|---|
| SSD Wear | 0 % |
| Spare Available | 100 % (the drive's own threshold is 10 %) |
| Data Written | 10 104 404 480 000 B = 9.2 TiB |
| Data Read | 2 637 935 616 000 B = 2.4 TiB |
| Power-On Hours | 331 h |
| Power Cycles | 150 |
| **Unsafe Shutdowns** | **31** |
| Media Errors, Critical Warning | 0, 0 |
| All six throttle counters | 0 — this drive has never throttled |

### The cost

| Measure | Value |
|---|---|
| One `read` request over the socket | **0.034–0.080 ms** |
| One SMART read from the drive | 3.0 ms, five times measured |
| The screen, with the 19 new channels | **153 channels, 2.02 ms per pass** |

The client asks for everything on every pass and the hardware pays nothing,
because the helper samples on its own clock: RAPL once a second, SMART once a
minute. That is ADR 0006's rule, moved across the socket.

### The service — `results/service-state.txt`

```
$ systemctl is-enabled sensors-guid.service   ->  enabled
$ systemctl is-active  sensors-guid.service   ->  active
$ stat -c '%A %U:%G' /run/sensors-gui.sock    ->  srw-rw---- root:gova
CapabilityBoundingSet = cap_chown cap_dac_override cap_dac_read_search cap_fowner cap_sys_admin
ProtectSystem         = strict
PrivateNetwork        = yes
RestrictAddressFamilies = AF_UNIX
```

`ProtectSystem=strict` makes the whole filesystem read-only for this process
except `/run`. The rule that this project writes nothing therefore holds even
if the code is wrong. `PrivateNetwork=yes` means a root process reading the
machine's sensors cannot reach a network at all.

The installed copy and the repository copy have the same SHA-256, and the
install script records it, so drift can be seen rather than guessed at.

## Four defects, all found by running the thing

The tests did not find the first two. Running the helper did.

1. **The label said `CPU Package 0 Power`.** There is one package. The index
   belongs on the second one, not the first.
2. **A failed `nvme` call reported its usage banner, not its reason.** nvme-cli
   prints a bold usage block on every failure, and the real line — `Permission
   denied` — was on the other stream. Taking the first line of stderr hid the
   one word that tells a person what to do.
3. **A failed bind made the root process delete the file in its way.**
   `socketserver` calls `server_close()` when `server_bind()` raises, and the
   override unlinked the socket path unconditionally. Pointed at an ordinary
   file, as root, it deleted it. A test now proves it does not.
4. **`nvme_command=None` searched the PATH**, so "nvme-cli is not installed"
   could not be tested on a machine that has it, and the branch was never run.

Defect 3 is the one worth remembering. It is the same shape as the fault that
caused the thermal shutdown: a clean-up path that acted without checking what
it was acting on.

## What is still missing

| Missing | Why |
|---|---|
| Per-core power for all 12 cores | Needs the Ryzen SMU mailbox (`ryzen_smu` or `zenpower3`). RAPL on Zen 5 gives the package and core 0 only. |
| Total system power | The NZXT C1200 has no telemetry link. Nothing can measure it. |
| A power meter scale | The board declares no RAPL power constraint, so there is no honest top of scale and the channel gets no bar. |

## Files

| File | Contents |
|---|---|
| `results/service-state.txt` | The service, the socket and the checksum, read as the ordinary user. |
| `results/helper-live-readings.txt` | All 19 channels from the socket, with no root, and the cost of a request. |
| `results/rapl-vs-turbostat.txt` | Every sample-to-sample power, against turbostat. |
| `results/screen-with-the-helper.txt` | The CPU and Storage panels as the application drew them. |
| `data/probes/privileged-20260922T051641Z/` | The raw root capture the whole build was made from. |
