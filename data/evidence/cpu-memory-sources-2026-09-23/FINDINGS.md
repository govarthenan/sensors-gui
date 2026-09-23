# Findings: CPU and memory tooltip sources

Command: (analysis of the files in this folder plus
`src/sensors_gui/collectors/system.py`, no new command run)
Date: 2026-09-23T16:32:00+05:30
Host: dst-gova-pc

This folder backs the tooltip sentences for the PROCESSOR and MEMORY
channels. It does not write any tooltip text; it collects and cites the
primary sources. The application code is cited by file and line, never
copied.

## a. Does the kernel apply a Tctl offset to this CPU (Ryzen 9 9900X, family
0x1a)?

**No.**

`drivers/hwmon/k10temp.c` (tag v7.0) applies an offset only through
`tctl_offset_table`, and that table has six entries, all for family `0x17`
(the original Zen / Zen+ Ryzen 1000/2000 series and two Threadripper
families):

```
static const struct tctl_offset tctl_offset_table[] = {
	{ 0x17, "AMD Ryzen 5 1600X", 20000 },
	{ 0x17, "AMD Ryzen 7 1700X", 20000 },
	{ 0x17, "AMD Ryzen 7 1800X", 20000 },
	{ 0x17, "AMD Ryzen 7 2700X", 10000 },
	{ 0x17, "AMD Ryzen Threadripper 19", 27000 }, /* 19{00,20,50}X */
	{ 0x17, "AMD Ryzen Threadripper 29", 27000 }, /* 29{20,50,70,90}[W]X */
};
```
(`k10temp-c-extracts.txt`, extract 1, lines 121-128)

`k10temp_probe()` walks this table and only sets an offset, and only shows
Tdie, when the family matches:

```
for (i = 0; i < ARRAY_SIZE(tctl_offset_table); i++) {
	const struct tctl_offset *entry = &tctl_offset_table[i];

	if (boot_cpu_data.x86 == entry->model &&
	    strstr(boot_cpu_data.x86_model_id, entry->id)) {
		data->show_temp |= BIT(TDIE_BIT);	/* show Tdie */
		data->temp_offset = entry->offset;
		break;
	}
}
```
(`k10temp-c-extracts.txt`, extract 3, lines 523-532)

This machine's CPU is family `0x1a` (`cpu family : 26` decimal), model
`0x44` (`model : 68` decimal) -- see `probe-cpu-memory-sysfs.txt`. The
family/model switch just above the offset loop handles `0x1a` only for CCD
temperature support, not for an offset:

```
} else if (boot_cpu_data.x86 == 0x1a) {
	switch (boot_cpu_data.x86_model) {
	case 0x40 ... 0x4f:	/* Zen5 Ryzen Desktop */
		data->ccd_offset = 0x308;
		k10temp_get_ccd_support(data, 8);
		break;
	}
}
```
(`k10temp-c-extracts.txt`, extract 3, lines 514-521; `0x44` falls inside
`0x40 ... 0x4f`)

Because the loop over `tctl_offset_table` never matches family `0x1a`,
`data->temp_offset` stays at its `devm_kzalloc` default of `0`, and
`TDIE_BIT` is never set, so this CPU exports Tctl only (plus its Tccd
channels), no Tdie. `probe-cpu-memory-sysfs.txt` confirms this directly:
`hwmon2` (k10temp) only has `temp1_label: Tctl`, `temp3_label: Tccd1`,
`temp4_label: Tccd2` -- there is no `temp2_input`/`temp2_label` (Tdie) on
this machine.

## b. What Tctl is vs Tccd, per the kernel docs

From `k10temp.rst`, quoting the AMD manual:

> Tctl is the processor temperature control value, used by the platform to
> control cooling systems. Tctl is a non-physical temperature on an
> arbitrary scale measured in degrees. It does _not_ represent an actual
> physical temperature like die or case temperature. Instead, it specifies
> the processor temperature relative to the point at which the system must
> supply the maximum cooling for the processor's specified maximum case
> temperature and maximum thermal power dissipation.

And on the CCD sensors:

> On Family 17h and Family 18h CPUs, additional temperature sensors may
> report Core Complex Die (CCD) temperatures. Up to 8 such temperatures are
> reported as temp{3..10}_input, labeled Tccd{1..8}. Actual support depends
> on the CPU variant.

(The doc text names 17h/18h explicitly; the driver source in
`k10temp-c-extracts.txt` extract 3 is what actually extends CCD reporting
to family `0x1a`/model `0x40-0x4f`, i.e. this CPU, with 8 CCD channels --
this machine's board only populates `Tccd1` and `Tccd2` of those 8, per the
probe.)

And on Tdie versus Tctl in general:

> On some AMD CPUs, there is a difference between the die temperature
> (Tdie) and the reported temperature (Tctl). Tdie is the real measured
> temperature, and Tctl is used for fan control. While Tctl is always
> available as temp1_input, the driver exports Tdie temperature as
> temp2_input for those CPUs which support it.

Combined with finding (a): on this machine Tctl (`temp1_input`) is the
only "control" reading exported, it carries no offset, and there is no
Tdie channel to compare it against.

## c. Where psutil's `cpu_freq()` min/max come from on Linux

**`scaling_min_freq` and `scaling_max_freq`, never `cpuinfo_min_freq` or
`cpuinfo_max_freq`.**

`psutil/_pslinux.py` lines 674-677 (`psutil-7.2.2-extracts.txt`, extract 3):

```
curr = int(curr) / 1000
max_ = int(bcat(pjoin(path, "scaling_max_freq"))) / 1000
min_ = int(bcat(pjoin(path, "scaling_min_freq"))) / 1000
ret.append(ntp.scpufreq(curr, min_, max_))
```

`cpuinfo_min_freq`/`cpuinfo_max_freq` do not appear anywhere in
`_pslinux.py`'s `cpu_freq()`. This is exactly why
`src/sensors_gui/collectors/system.py:110-133` (`_hardware_minimum`) reads
`cpuinfo_min_freq` itself, bypassing `psutil.cpu_freq().min`: the
docstring there says psutil's `scaling_min_freq` is "the lowest the
kernel's frequency policy asks for: 3.0 GHz on this machine," while
`cpuinfo_min_freq` is "the lowest the part itself can run at: 614 MHz."
`probe-cpu-memory-sysfs.txt` confirms both numbers on cpu0:
`scaling_min_freq:3001551`, `cpuinfo_min_freq:613954` (values in kHz).

## d. How psutil 7.2.2 computes memory `used` and `available` on Linux

**`available`** comes straight from `/proc/meminfo`'s own `MemAvailable:`
field when present and non-zero (this kernel provides it -- see
`probe-cpu-memory-sysfs.txt`); only if that field is missing or reads 0
does psutil fall back to `calculate_avail_vmem()`, which reimplements the
kernel's own MemAvailable algorithm from `Active(file)`, `Inactive(file)`,
`SReclaimable` and the per-zone low watermarks in `/proc/zoneinfo`
(`psutil-7.2.2-extracts.txt`, extracts 5 and 6).

**`used` is computed as `total - available`, not `total - free`:**

```
used = total - avail
```
(`psutil-7.2.2-extracts.txt`, extract 5, `_pslinux.py` line 408)

This is a genuine discrepancy worth flagging (see "surprising" below): the
`virtual_memory()` docstring in `psutil/__init__.py` states

> used: memory used, calculated differently depending on the platform and
> designed for informational purposes only:
> ...
> Linux: total - free

but the installed Linux implementation actually computes `total - avail`,
not `total - free`. `src/sensors_gui/collectors/system.py` does not
recompute `used`; it takes it straight from
`psutil.virtual_memory().used` (`_discover_memory`/`_memory_field_reader`,
`system.py:352-398`), so the app's "Memory used" channel reflects
whatever the installed psutil actually does (`total - avail`), not what
its own docstring says.

`buffers`, `cached` and `shared` come directly from named `/proc/meminfo`
fields, with `cached` folding in `SReclaimable`:

```
buffers = mems[b'Buffers:']
...
cached = mems[b"Cached:"]
...
cached += mems.get(b"SReclaimable:", 0)  # since kernel 2.6.19
...
shared = mems[b'Shmem:']  # since kernel 2.6.32
```
(`psutil-7.2.2-extracts.txt`, extract 5, `_pslinux.py` lines 327-352)

`free` is `mems[b'MemFree:']` verbatim (`_pslinux.py` line 325).

## e. What swap `sin`/`sout` are

Cumulative bytes swapped in/out since boot, read from `/proc/vmstat`'s
`pswpin`/`pswpout` counters (which are pages), multiplied by 4 KiB to
convert to bytes:

```
if line.startswith(b'pswpin'):
	sin = int(line.split(b' ')[1]) * 4 * 1024
elif line.startswith(b'pswpout'):
	sout = int(line.split(b' ')[1]) * 4 * 1024
```
(`psutil-7.2.2-extracts.txt`, extract 7, `_pslinux.py` lines 473-476)

The `swap_memory()` docstring confirms this is cumulative, not a rate:
"sin: no. of bytes the system has swapped in from disk (cumulative)."
`src/sensors_gui/collectors/system.py` turns this cumulative counter into
a rate itself: `_discover_swap`/`_swap_rate_reader`/`_refresh_swap_rates`
(`system.py:400-457`, `618-627`) call the shared `_rate_between()` helper
(`system.py:75-99`) against `psutil.swap_memory().sin`/`.sout` on
successive passes, the same wrap-safe delta logic used for the disk and
network byte counters. On this machine `SwapTotal`/`SwapFree` both read 0
(`probe-cpu-memory-sysfs.txt`), so `sin`/`sout` are expected to stay 0 --
there is no swap space configured to move pages through.

## f. What the spd5118 doc says about limits, and who sets them

`spd5118.rst` describes `temp1_max` and `temp1_crit` (and `temp1_min`,
`temp1_lcrit`) as read-write attributes:

```
temp1_lcrit		Low critical high temperature (RW)
temp1_min		Minimum temperature (RW)
temp1_max		Maximum temperature (RW)
temp1_crit		Critical high temperature (RW)
```

and

> A SPD5118 compliant chip supports a single temperature sensor. Critical
> minimum, minimum, maximum, and critical temperature can be configured.

The doc does not say who sets the values this project reads. It only
says they "can be configured" (RW). On this machine (`probe-cpu-memory-
sysfs.txt`) both DIMMs read `temp1_max: 55000` (55 degC) and
`temp1_crit: 85000` (85 degC), with `temp1_min`/`temp1_lcrit` both 0 (no
low-side limit set). This project never wrote those values -- every read
in this folder and in the app is a plain `read()` of the sysfs file, per
CLAUDE.md's "writes nothing to hardware" rule. The values are therefore
either the SPD5118 chip's own power-on defaults (from the DIMM's own SPD
NVRAM/firmware) or were set by the BIOS before boot; this folder does not
establish which, and no experiment in `lab/` was found that does either.

## g. Anything surprising

1. **The `virtual_memory()` docstring does not match the Linux code.** The
   docstring says Linux `used` is `total - free`; the installed 7.2.2 code
   computes `total - avail` (finding d above). Any tooltip sentence that
   quotes the docstring's "Linux: total - free" line would misdescribe
   what this app's "Memory used" channel actually shows.
2. **This machine's `scaling_min_freq` (3.0 GHz) is quintuple its
   `cpuinfo_min_freq` (614 MHz).** This is the concrete number behind the
   `_hardware_minimum()` comment in `system.py` and the 2026-09-23
   choice recorded there; the probe in this folder is a second,
   independent confirmation of both figures on cpu0 today (values differ
   slightly probe-to-probe because the machine was under some load, but
   the same order-of-magnitude gap holds throughout).
3. **The kernel doc for RAPL (`powercap.rst`) never mentions AMD.** It
   describes Intel RAPL by name throughout, yet this machine's
   `/sys/class/powercap/intel-rapl:0/energy_uj` node (used by the
   `sensors-guid` helper per CLAUDE.md section 5) is on an AMD Ryzen 9
   9900X. The interface is the same MSR-based powercap control type under
   the same `intel-rapl` control-type name; the doc copied here describes
   the generic interface shape (package/core zones, `energy_uj`), not an
   Intel-only claim, so it still supports the tooltip, but a tooltip
   sentence should not imply this doc is AMD-specific.
4. **k10temp's own doc text lags its own driver source.** `k10temp.rst`
   says CCD temperatures are a Family 17h/18h feature ("Up to 8 such
   temperatures are reported as temp{3..10}_input... Actual support
   depends on the CPU variant"), but the driver source
   (`k10temp-c-extracts.txt`, extract 3) extends CCD support to family
   `0x19` and `0x1a` as well -- this machine's CCD channels (`Tccd1`,
   `Tccd2`) exist because of code the prose document does not describe.
   The prose (`k10temp.rst`) is still the right source for what Tctl/Tdie
   *mean*; the source (`k10temp.c`) was needed for what this specific
   family/model combination actually gets.

## Citations into `src/sensors_gui/collectors/system.py` (not copied here)

| Channel | psutil call / sysfs file | Where in `system.py` |
|---|---|---|
| CPU use | `psutil.cpu_percent()` | `_discover_cpu` (line 231), reader `_cpu_percent_total` refreshed at line 581 |
| CPUn use | `psutil.cpu_percent(percpu=True)` | `_discover_cpu` (lines 213-229), refreshed at line 575 |
| CPUn frequency, current | `psutil.cpu_freq(percpu=True)[n].current` | `_discover_cpu_frequency` (lines 270-295), reader `_cpu_freq_reader` (lines 331-340), refreshed at line 587 |
| CPUn frequency, low | `cpuinfo_min_freq` sysfs file directly (falls back to psutil's `.min` in MHz) | `_hardware_minimum` (lines 110-133), called at line 287 |
| CPUn frequency, high | `psutil.cpu_freq(percpu=True)[n].max` | line 288 |
| Load average (1/5/15 min) | `os.getloadavg()` | `_discover_cpu` (lines 249-267), refreshed at line 597 |
| Memory total/available/used/free/use%/buffers/cached/shared | `psutil.virtual_memory()` fields | `_discover_memory` (lines 352-389), reader `_memory_field_reader` (lines 391-398), refreshed at line 603 |
| Swap total/used/free/use% | `psutil.swap_memory()` fields | `_discover_swap` (lines 400-424), reader `_swap_field_reader` (lines 442-449), refreshed at line 609 |
| Swap in/out (rate) | `psutil.swap_memory().sin`/`.sout`, turned into a rate | `_discover_swap` (lines 425-439), `_swap_rate_reader` (lines 451-457), `_refresh_swap_rates` (lines 618-627), using `_rate_between` (lines 75-99) |
