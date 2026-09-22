# exp-0012 — per-core power without a write

Started 2026-09-22, session 6.

## Question

`STATUS.md` next action 3 asks for per-core power, and `HANDOFF.md` records
that RAPL gives the package and **core 0 only** on this Zen 5 part. The route
written down for it is `ryzen_smu` or `zenpower3`.

Two questions, then, and the second one is the important one:

1. Does this processor expose one energy counter for **each** of the twelve
   cores, and do those counters agree with `turbostat` and with the package?
2. Can that be read **without writing anything to the hardware**?

Question 2 exists because the SMU route breaks ADR 0007. `ryzen_smu` and
`zenpower3` do not read a register: they **write a command word into the SMU
mailbox** and then read the answer. ADR 0007 says this project writes nothing
to hardware, with no exceptions and no conditions. So the SMU route needs
Gova's decision and a new ADR before a line of it is written.

## The other route, found in the kernel's own header

```
/usr/src/linux-headers-7.0.0-31-generic/arch/x86/include/asm/msr-index.h:511
#define MSR_AMD_RAPL_POWER_UNIT     0xc0010299
#define MSR_AMD_CORE_ENERGY_STATUS  0xc001029a
#define MSR_AMD_PKG_ENERGY_STATUS   0xc001029b
```

`0xc001029a` is documented as one counter for **each core**. Reading an MSR is
a read: `rdmsr` executes the `RDMSR` instruction, and `/dev/cpu/N/msr` answers a
`pread()`. Nothing is written, so ADR 0007 is kept.

Three facts checked on this machine before the probe was written:

| Fact | Value | Why it matters |
|---|---|---|
| CPU family | 26 (0x1A, Zen 5) | the part must carry these MSRs |
| `msr` module | loaded; `/dev/cpu/0/msr` is `crw------- root root` | the helper is root, so it can read it |
| Kernel lockdown | `integrity` | lockdown blocks MSR **writes**. Reads are the question. |

## Method

`scripts/probe-core-energy.sh`, read-only, three phases:

| Phase | What | What it proves |
|---|---|---|
| A | idle, 6 samples 1 s apart | every counter climbs |
| B | **one** thread busy, 6 samples | only that core's counter jumps — this is what makes the counter per-core and not a copy of the package |
| C | every thread busy, 6 samples | the counters sum to about the package power |

Plus: the energy unit from `0xc0010299`, the thread-to-core topology (two
threads of one core must return the same value), `turbostat` as a second
opinion, and the cost of a read both ways — through the `rdmsr` process and
through `pread()`, which is how the helper would do it.

```bash
sudo ./scripts/probe-core-energy.sh
```

## Result

Run on 2026-09-22. Raw capture: `data/probes/core-energy-20260922T055615Z/`.
Arithmetic: `analyse.py`, output kept at `results/analysis.txt`.

**Yes to both questions. All twelve cores read, and nothing was written.**

### The numbers

One count is **15.2588 microjoules** (`0xc0010299` gave `a1000`, so ESU = 16).

| Phase | Sum of the 12 cores | Package counter | Cores / package |
|---|---|---|---|
| idle | 10.00 W | 56.10 W | 17.8 % |
| one thread busy | 26.89 W | 75.70 W | 35.5 % |
| every thread busy | 103.98 W | 157.24 W | 66.1 % |

### Q1 — the counter is per core

The decisive test is phase B, not the sibling test. One thread (`cpu6`) was made
busy, and **one counter moved**:

```
core  8  17.439 W   <- cpu6 sits on core 8
core  9   0.409 W
core 10   0.466 W
core 11   0.317 W        every other core stayed at idle
core 12   0.359 W
core 13   0.392 W
```

That is what `powercap` cannot do. The `core` domain there is **core 0 only**
(`exp-0003`, `exp-0011`); here all twelve are separate and each one follows its
own work.

The supporting test: the two threads of one core differ by at most **31 mJ**,
against at least **2.1 J** between two cores, because the sampler reads the
threads a few milliseconds apart and the counter climbs in between. The ratio is
only 68, so this test alone would not prove it. Phase B does.

### Q2 — nothing was written

`rdmsr` executes the `RDMSR` instruction. `/dev/cpu/N/msr` answers a `pread()`.
No mailbox, no command word, no module built for the purpose. ADR 0007 is kept
whole.

### Q3 — turbostat agrees

`turbostat` reads the same registers through its own code. Under an all-core
load the two disagree by **0.1 %**:

| Phase | This capture | turbostat |
|---|---|---|
| idle, cores | 10.00 W | 9.49 W |
| idle, package | 56.10 W | 55.53 W |
| load, cores | **103.98 W** | **104.10 W** |
| load, package | **157.24 W** | **157.34 W** |

The idle rows differ more because the two captures ran at different moments and
an idle machine is not steady. The load rows are the check that matters.

### The cost of a read

| Route | One sweep of 24 threads |
|---|---|
| `rdmsr`, a process for each read | 8.5-9.1 ms |
| `pread()` on an open `/dev/cpu/N/msr` | **0.070 ms** |

A hundred times cheaper, and it is the route the helper will use: 24 file
descriptors opened once, then one `pread()` each. For comparison, the whole
screen pass today costs about 2 ms.

## Findings

1. **The question was answerable without the tool the plan named.** `STATUS.md`
   said per-core power needs `ryzen_smu` or `zenpower3`. It does not. The
   processor publishes it in a register that any root process may read, and the
   number the kernel's `powercap` shows is a smaller part of the same data.
2. **The route that was planned would have broken ADR 0007.** `ryzen_smu` and
   `zenpower3` write a command word into the SMU mailbox to get their answer.
   That is a write to hardware. The rule says there are no exceptions, so the
   plan needed a decision it never had. The MSR route removes the question.
3. **A register the kernel already names is worth reading before a module is
   built.** All three MSR numbers came from a header file on this machine,
   `/usr/src/linux-headers-$(uname -r)/arch/x86/include/asm/msr-index.h`. This
   is the same lesson as `exp-0010`, where the fan register was in a comment in
   the driver: **read what is already here first.**
4. The counter is 32 bit inside a 64 bit register and it wraps. At the 104 W
   this machine reached, a core counter wraps about every 10 minutes, and a
   reader that ignores that reports a large negative power. The same trap as
   the RAPL counter in `exp-0011`, and the same answer: subtract modulo 2**32.
