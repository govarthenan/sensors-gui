# Ryzen 9900X package layout — sources, 2026-09-23

Collected for the diagram work described in the task that produced this
folder: a diagram of the AMD Ryzen 9 9900X (Zen 5, "Granite Ridge", AM5, 12
cores in 2 CCDs of 6 enabled cores each, plus an I/O die) that places each
sensor where it physically sits. This folder holds the sources; it does not
draw anything.

Web research only. Every file here starts with the command, the date and the
source, per `data/evidence/README.md`'s rules. No hardware on dst-gova-pc was
read to produce any of this — it is all published third-party material.

## Q1 — Physical layout of the AM5 package (IOD vs. CCDs, package outline)

**Answer:** The cIOD (client I/O die) sits centrally on the package, and up to
two Zen 5 CCDs sit near each other, close to the cIOD — described by three
independent outlets citing the same annotated die shots (Nemez, Fritzchens
Fritz, HighYieldYT). The package outline is 40 x 40 mm, per Wikipedia's Socket
AM5 infobox (sourced to AMD/press material). No text source states which side
of the package the "golden triangle" pin-1 mark faces relative to the IOD or
CCDs; my own observation of the package photo (labelled as an observation, not
a documented claim) is in the TechPowerUp file.

Quotes:
- "The 'Granite Ridge' package looks similar to 'Raphael,' with up to two
  8-core CPU complex dies (CCDs) depending on the processor model, and a
  centrally located client I/O die (cIOD)." — `techpowerup-granite-ridge-annotated.txt`
- "The 'Granite Ridge' package sees the up to two 'Zen 5' CCDs snuck up closer
  to each other than the 'Zen 4' CCDs on 'Raphael.' In the picture above, you
  can see the pad of the absent CCD behind the solder mask of the fiberglass
  substrate, close to the present CCD." — `techpowerup-granite-ridge-annotated.txt`
  (same statement, independently written up in `guru3d-annotated-die-shots.txt`:
  "up to two Zen 5 CCDs are positioned closer together compared to the Zen 4
  CCDs in Raphael. The die images show the pad area for a potential second CCD
  located beneath the solder mask of the fiberglass substrate, near the
  existing CCD.")
- "Processor dimensions | 40 x 40 mm | 1,600 mm2" — `wikipedia-socket-am5.txt`

My own observation of the package image (labelled, in
`techpowerup-granite-ridge-annotated.txt`, "OBSERVATION" section): the cIOD
sits in the upper-middle of the substrate; a single populated CCD sits below
it; an empty, unpopulated CCD-shaped pad sits beside that CCD at the same
height, matching the "absent CCD" text above. This photograph is of a
single-CCD chip (a Ryzen 5 9600X, per `wccftech-zen5-ccd-die-shots.txt`), not
the 9900X itself — the two-CCD claim rests on the empty second pad visible on
that same substrate design, not on a photo of a populated two-CCD chip.
Not established: which side of the package faces the pin-1 "golden triangle"
relative to IOD/CCD placement — no source in this folder states this in words.

Files: `techpowerup-granite-ridge-annotated.txt`, `guru3d-annotated-die-shots.txt`,
`wccftech-zen5-ccd-die-shots.txt`, `wikipedia-socket-am5.txt`

## Q2 — Die sizes: Zen 5 CCD and 6 nm I/O die

**Answer:** Confirmed by AMD via HardwareLuxx.de's Q&A, reported by
TechPowerUp: the Zen 5 CCD ("Eldora") is 70.6 mm², and the reused 6 nm cIOD is
122 mm².

Quotes:
- "the 'Zen 5' CCD measures 70.6 mm², whereas the 'Zen 4' CCD is 71 mm²." — `techpowerup-die-sizes.txt`
- "This chip [the cIOD] measures 122 mm², and packs 3.4 billion transistors." — `techpowerup-die-sizes.txt`

Both figures match what CLAUDE.md asked to confirm. No disagreement found
between sources; die sizes were only found stated in this one write-up
(TechPowerUp, sourced to HardwareLuxx.de/AMD), so only one primary source is
filed for this question. `techpowerup-granite-ridge-annotated.txt` independently
confirms the process nodes (CCD on TSMC N4P/4 nm, cIOD on TSMC N6/6 nm) without
repeating the mm² figures.

File: `techpowerup-die-sizes.txt`

## Q3 — Core layout inside a Zen 5 CCD

**Answer:** The CCD's text descriptions (three outlets, same source material)
say the 8 cores share "a centrally located 32 MB L3 cache", with each core's
L2 cache facing the L3 and its Vector Engine (FPU) pushed to the die edge.
None of the three articles' *text* states the geometric arrangement (how many
cores per side) in words. My own observation of the annotated CCD image (see
below, labelled, not a text-source claim) shows the 8 cores as two vertical
columns of four, one column on each side of the central L3 cache strip — not
the "two rows of four" phrasing floated as a guess in the task. This is an
observation of the image, not a quote from any article's text.

Quotes:
- "The CCD contains 8 full-sized 'Zen 5' CPU cores, each with 1 MB of L2
  cache, and a centrally located 32 MB L3 cache that's shared among all eight
  cores." — `techpowerup-granite-ridge-annotated.txt`
- "The core's Vector Engine is pushed to the very edge of the core. On the
  CCD, these should be the edges of the die. [...] The innermost component
  (facing the shared L3 cache) is the 1 MB L2 cache." — `techpowerup-granite-ridge-annotated.txt`

My own observation (`techpowerup-granite-ridge-annotated.txt`, "OBSERVATION"
section, image 2, https://tpucdn.com/img/o8fTKzZg4LzwrEPN.jpg): "the eight
cores are arranged as two vertical columns of four, one column on each side
of the shared L3 cache, not as two horizontal rows." Not established from any
article's own text — only from looking at the image myself, which I have
labelled as such rather than treating it as a quoted source claim.

Files: `techpowerup-granite-ridge-annotated.txt`, `guru3d-annotated-die-shots.txt`,
`wccftech-zen5-ccd-die-shots.txt`

## Q4 — Which physical cores are disabled on a 6-core-per-CCD part (9900X)?

**Answer: not established.** No source found names which two of the eight
physical cores on a CCD are fused off on the 9900X, or states any fixed
correspondence between the kernel's core IDs (0-5 and 8-13, per
`data/probes/2026-09-22-cpu-topology.txt`) and a physical position on the die.
The mechanism is described (eFuses blown per-chip during binning) but not the
specific map, and nothing found states whether the two disabled cores are in
fixed positions across samples of the same model or vary chip to chip
("silicon lottery").

Quote: "Modern chips [...] use eFuses, which are on-die fuses blown during the
binning process to sever a core or cache block for good." — `xda-developers-disabled-cores.txt`

File: `xda-developers-disabled-cores.txt` (describes the mechanism only, not a
per-chip map — filed as the closest source found, with the gap stated
explicitly)

## Q5 — Does k10temp's Tccd1/Tccd2 index tie to a physical CCD position?

**Answer: not established.** The kernel documentation only says up to 8 CCD
temperatures are exposed as `Tccd{1..8}`, without any statement of physical
position. Reading the driver source itself: the index used to select
`Tccd1`, `Tccd2`, etc. is just a loop counter (`i = 0 .. limit`) over SMN
register slots: nothing in the driver ties slot 0 to "the CCD nearer the pin-1
corner" or any other physical description, and the driver's own header
comment says the CCD register addressing "is not confirmed from chip
datasheets" (it was reverse-engineered by a third-party project, zenpower, and
carried into the mainline driver on that basis).

Quotes:
- "On Family 17h and Family 18h CPUs, additional temperature sensors may
  report Core Complex Die (CCD) temperatures. Up to 8 such temperatures are
  reported as temp{3..10}_input, labeled Tccd{1..8}. Actual support depends
  on the CPU variant." — `linux-k10temp-hwmon-doc.txt`
- "CCD register address information as well as the calculation to convert raw
  register values is from https://github.com/ocerman/zenpower. The
  information is not confirmed from chip datasheets, but experiments suggest
  that it provides reasonable temperature values." — `linux-k10temp-driver-source.txt`
  (file header comment in `k10temp.c`)

Files: `linux-k10temp-hwmon-doc.txt`, `linux-k10temp-driver-source.txt`

## Q6 — Where does Tctl come from physically?

**Answer:** Tctl is not a sensor reading at a physical place. Per AMD's own
documented definition (quoted in the kernel doc) it is "a non-physical
temperature on an arbitrary scale," used for fan-control purposes, distinct
from Tdie ("the real measured temperature"). Reading the driver source: Tctl
is produced by reading one register (`ZEN_REPORTED_TEMP_CTRL_BASE`) over the
SMN (System Management Network) register interface, addressed by node, not by
any single die location — consistent with it being a platform-level control
value rather than a die-position sensor.

Quotes:
- "Tctl is the processor temperature control value, used by the platform to
  control cooling systems. Tctl is a non-physical temperature on an arbitrary
  scale measured in degrees. It does _not_ represent an actual physical
  temperature like die or case temperature." — `linux-k10temp-hwmon-doc.txt`
  (itself quoting "the AMD manual")
- "On some AMD CPUs, there is a difference between the die temperature (Tdie)
  and the reported temperature (Tctl). Tdie is the real measured temperature,
  and Tctl is used for fan control." — `linux-k10temp-hwmon-doc.txt`

Files: `linux-k10temp-hwmon-doc.txt`, `linux-k10temp-driver-source.txt`

## Summary table

| Q | Answer | Established? |
|---|---|---|
| 1 | cIOD centrally located, two CCD seats close together beside it; package 40x40mm | Yes, for layout & size. Pin-1 orientation relative to layout: not established |
| 2 | CCD 70.6 mm², IOD 122 mm² | Yes |
| 3 | Text: cores around central L3, L2 facing L3, FPU at edge. Geometric row/column count: only from my own image observation, not article text | Partially — see caveat |
| 4 | Which physical cores are disabled on the 9900X | Not established |
| 5 | Whether Tccd1/Tccd2 ties to a physical CCD position | Not established |
| 6 | Tctl is a non-physical, platform control value, not a positioned sensor; read via one SMN register per AMD's k10temp driver | Yes |

## Files in this folder

| File | Answers |
|---|---|
| `techpowerup-granite-ridge-annotated.txt` | Q1, Q3 (text + my own labelled image observations) |
| `techpowerup-die-sizes.txt` | Q2 |
| `guru3d-annotated-die-shots.txt` | Q1, Q3 (second independent write-up) |
| `wccftech-zen5-ccd-die-shots.txt` | Q1, Q3 (third independent write-up; identifies the pictured chip as a 9600X) |
| `wikipedia-socket-am5.txt` | Q1 (package outline size) |
| `linux-k10temp-hwmon-doc.txt` | Q5, Q6 |
| `linux-k10temp-driver-source.txt` | Q5, Q6 (driver source, read-only) |
| `xda-developers-disabled-cores.txt` | Q4 |

## Note on the research method

Where a claim rests on my own look at a source's image rather than that
source's own text, it is marked "OBSERVATION" in the relevant file and in this
README, and kept separate from quoted text. No image was saved into this
repository; images were viewed only, per the task's copyright rule. Where a
claim is my own reasoning about published source material (e.g. reading what
the k10temp driver's loop structure implies) rather than a direct quote, it is
marked "my own reasoning" and kept apart from the quotes.
