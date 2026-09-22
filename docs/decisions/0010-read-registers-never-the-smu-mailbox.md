# ADR 0010 — Read a register, never write to a mailbox

- Date: 2026-09-22
- Status: accepted
- Extends: ADR 0007 (this project writes nothing to hardware)
- Evidence: `lab/exp-0012-per-core-energy/`, `data/probes/core-energy-20260922T055615Z/`

## Context

`state/STATUS.md` has carried one target since the first session: **per-core
power**. The powercap tree gives the CPU package and one core, because the
kernel's `core` domain on this Zen 5 part follows core 0 alone. `exp-0003` and
`exp-0011` each proved that against `turbostat`.

The route the plan named for the remaining eleven cores was `ryzen_smu` or
`zenpower3`. Both read the AMD SMU. They do not read a register and stop there:
they **write a command word into the SMU mailbox**, then read the answer out of
a reply register. The same is true of the SMN route those drivers use for the
voltage rails, which writes an address into PCI configuration register `0x60`
of the host bridge before reading `0x64`.

ADR 0007 says this project writes nothing to hardware, with no exceptions and
no conditions. It was written the day a fan-control write stopped the radiator
fans and the board shut the machine down at 98 °C. So the plan named a route
the rules forbid, and nobody had noticed, because "install a DKMS module" does
not sound like "write to the processor".

Two questions follow:

1. Is there a route to per-core power that only reads?
2. What happens to the three voltage rails the BIOS reads and Linux does not,
   which `exp-0010` proved are not in the board sensor chip at all?

## Decision

### 1. A read of a register is allowed. A write to a mailbox is not.

The rule of ADR 0007 is kept as it stands, and this is how it is applied to a
processor register:

| Operation | Allowed | Why |
|---|---|---|
| `RDMSR`, or `pread()` on `/dev/cpu/N/msr` | **yes** | the processor is asked for the content of one register; nothing changes |
| `WRMSR`, or `pwrite()` on the same node | **no** | it changes the processor's state |
| Writing a command word to the SMU mailbox | **no** | it is a write, and the same mailbox carries commands that set limits and voltages |
| Writing an address to a PCI configuration index register to read SMN | **no** | it is a write to a shared register, and a second reader can be part-way through its own transaction |

The distinction is not "does this particular command look harmless". It is
whether the machine is **asked** or **told**. A read cannot leave the hardware
in a state that a later failure makes permanent. Fault 3 of the thermal
shutdown was exactly that: mode and speed were separate writes, so a partial
success left the worst state.

### 2. Per-core power comes from `0xc001029a`

`MSR_AMD_CORE_ENERGY_STATUS` holds one energy counter for each core. The number
is in this kernel's own header, `arch/x86/include/asm/msr-index.h`, together
with `MSR_AMD_RAPL_POWER_UNIT` (`0xc0010299`) which gives the size of one
count.

`exp-0012` proved on this machine, under load, that:

- all twelve cores read separately, and with one thread busy exactly one
  counter moved;
- the sum matched `turbostat` to **0.1 %** (103.98 W against 104.10 W);
- one sweep of twenty-four threads costs **0.070 ms** through `pread()`.

The helper reads it. Two things are needed and both are recorded in
`scripts/install-helper.sh` and `scripts/sensors-guid.service`:

- the `msr` module, made to load at boot through `/etc/modules-load.d/`;
- `CAP_SYS_RAWIO`, which `man 7 capabilities` requires to "open devices for
  accessing x86 model-specific registers".

The service's other restrictions are unchanged, so the whole filesystem stays
read-only for it and the node is opened `O_RDONLY`.

### 3. The three unmapped voltage rails stay dropped

`VDD MISC`, `CPU 1P8` and `CHIPSET Core` are read by the BIOS. `exp-0010`
proved they are not in the Nuvoton chip's voltage block: both untried registers
are accounted for, one empty and one holding the CMOS battery. What remains is
the SMU or SMN route, and by decision 1 that is a write.

So the question is **dropped**, under the closing sentence of ADR 0007: *if a
question can only be answered by writing, drop the question.* The rails are
listed as unreachable in `docs/sensor-sources.md` with this reason, not with
"not tried yet".

This can be reopened only by Gova, and only with a new ADR that says what
changed. The cost of being wrong is the machine, and the value is three
reference voltages.

## Consequences

- Thirteen channels were added with no new risk: twelve cores and their sum.
- `ryzen_smu` and `zenpower3` leave the target list of `exp-0005`. Target 2 is
  answered for power, and closed for voltage.
- `CPU Core 0` is now read twice, once through powercap and once from the
  register. The two agreed to **0.001 W** the first time they were shown side
  by side, so the older row keeps the name `CPU Core 0 (RAPL)` and both stay.
  Two readings of one thing that agree are worth more than one.
- A route that needs a write is now something to **look for** before it is
  planned. The word "driver" hid one for five sessions.
