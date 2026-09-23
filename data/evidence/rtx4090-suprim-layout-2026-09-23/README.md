# RTX 4090 Suprim / Suprim X layout — published sources

Web research only, done 2026-09-23, for drawing a wireframe of this machine's MSI GeForce
RTX 4090 SUPRIM / SUPRIM X (VBIOS 95.02.3C.40.D1, PCI 10de:2684, 480 W default power limit,
150-530 W range — `data/probes/2026-09-23-nvidia-smi-q.txt`; exact SUPRIM vs. SUPRIM X
variant NOT established). No hardware on this machine was touched; this is desk research
against published third-party pages, fetched with the `firecrawl` CLI (some pages required
reading an Internet Archive Wayback Machine snapshot instead of the live page, because
TechPowerUp's and MSI's own bot-protection returned HTTP 403 on direct fetch — noted in each
file).

## Files

| File | Source | What it establishes |
|---|---|---|
| `techpowerup-introduction-specifications.txt` | TechPowerUp review, page 1 (via Wayback) | fan count ("trio"), 4-slot claim, reference GPU/memory table |
| `techpowerup-pictures-teardown.txt` | TechPowerUp review, page 3 (live) | dimensions, weight, slots, outputs, power connector, heatpipe count |
| `techpowerup-circuit-board-analysis.txt` | TechPowerUp review, page 4, "Circuit Board (PCB) Analysis" (via Wayback) | VRM phase counts/controller, memory chip part number, GPU die size |
| `msi-suprimx-specification.txt` | MSI SUPRIM X official spec page (via Wayback) | official dimensions/weight/power/outputs for SUPRIM X |
| `msi-suprim-air-specification.txt` | MSI SUPRIM (non-X) official spec page (via Wayback) | same fields for the plain air SUPRIM, for comparison |
| `msi-suprimx-overview.txt` | MSI SUPRIM X official overview page (via Wayback) | cooler marketing text: TRI FROZR 3S / TORX FAN 5.0 |
| `msi-suprim-air-overview.txt` | MSI SUPRIM (non-X) official overview page (via Wayback) | same cooler text, for comparison |
| `wccftech-suprimx-air-teardown.txt` | WCCFTech review, page 8 (live) | independent teardown of the air SUPRIM X: dimensions, 3 fans, PCB shorter than cooler, VRM phases |
| `wccftech-suprim-liquidx-teardown.txt` | WCCFTech review, page 10 (live) | Liquid X teardown, kept to show it is a different product, plus an internal inconsistency flag |
| `thefpsreview-suprimx.txt` | TheFPSReview review (live) | explicit 100 mm fan diameter claim, dual-BIOS switch position "near the rear of the PCB" |
| `gpufanreplacement-suprimx-fan-spec.txt` | GPUFanReplacement.com listing (live) | a conflicting 95 mm fan-diameter claim, third-party parts retailer, lower confidence |

Igor's Lab was searched for but no accessible circuit-board-analysis article for this exact
card was found in the time available; TechPowerUp's own "Circuit Board (PCB) Analysis" page
and two independent teardowns (WCCFTech, TheFPSReview) were used instead, per the task's "or
similar" allowance.

## Facts and where they come from

### 1. Physical dimensions and fan count/size

- **Dimensions 336 x 142 x 78 mm.** Stated identically by MSI's own SUPRIM X spec page
  ("Card Dimension (mm) — 336 x 142 x 78 mm", `msi-suprimx-specification.txt`), MSI's own
  SUPRIM (air) spec page (`msi-suprim-air-specification.txt`), and independently confirmed by
  WCCFTech's own teardown measurement: "The card measures the same at 336 x 142 x 78 mm and
  weighs in at 2413 grams" (`wccftech-suprimx-air-teardown.txt`).
  TechPowerUp gives a rounder figure from its own measurement: "Dimensions of the card are
  34.0 x 14.0 cm, and it weighs 2441 g." (`techpowerup-pictures-teardown.txt`) — note the
  small weight discrepancy (2413 g per MSI/WCCFTech vs. 2441 g per TechPowerUp's own scale).
  TheFPSReview gives the same size in imperial: "measuring 13 ¼ x 5 x 3 inches [...] weighing
  in at 5 pounds 5 ounces" (`thefpsreview-suprimx.txt`).
- **Slot width: disagreement between sources.** TechPowerUp: "Installation requires four
  slots in your system." (`techpowerup-pictures-teardown.txt`). WCCFTech: "The card features
  a standard 3.5 slot height" (`wccftech-suprimx-air-teardown.txt`). TheFPSReview: "This
  nearly 4-slot card" (`thefpsreview-suprimx.txt`). Kept as stated in each source; not
  resolved to a single number.
- **Fan count: three fans ("trio").** TechPowerUp: "...and uses a trio of fans."
  (`techpowerup-introduction-specifications.txt`). WCCFTech: "All three fans feature a
  ring-based design..." (`wccftech-suprimx-air-teardown.txt`). MicroCenter's own product title
  (search result, not separately saved) also calls it "Triple-Fan".
- **Fan diameter: two conflicting numbers found.**
  - TheFPSReview states 100 mm in running review text: "The 100mm fans are 9-bladed in three
    groups, connected by an interrupted outer rim." (`thefpsreview-suprimx.txt`).
  - A third-party aftermarket fan-replacement listing states 95 mm for the same fan/card
    family: "Fan Diameter: 95mm" (`gpufanreplacement-suprimx-fan-spec.txt`).
  - Neither MSI nor TechPowerUp's own pages give a numeric fan diameter.
  - **Not resolved** — both numbers are kept, TheFPSReview flagged as the higher-confidence
    one (an actual review of this card) and the parts listing flagged as lower-confidence (a
    commercial listing, not a teardown measurement).
- **Fan blade design (not a control-grouping fact):** "Each fan has three blades that form
  three sets and each fan has three sets of them that make up a total of 9 fan blades."
  (`wccftech-suprimx-air-teardown.txt`); TheFPSReview's "9-bladed in three groups" is the same
  fact in different words. This describes the blades **inside one fan**, not how the card's
  three fans are wired together — see fact 2 below.

### 2. Fans controlled as 2 groups (to explain NVML's 2 fan-control channels)

**Not found.** No source read for this task — MSI's own pages, TechPowerUp's review (all
pages read), WCCFTech's teardown, or TheFPSReview's review — states how the three TORX fans
are wired to the PCB (one header per fan, two fans sharing one header, etc.) or how many
independent PWM/tach channels the board exposes. The "9-bladed in three groups" /
"three sets of [blades]" language found in two sources (`wccftech-suprimx-air-teardown.txt`,
`thefpsreview-suprimx.txt`) is explicitly about blade geometry within a single fan, not fan
wiring, and must not be read as an answer to this question.

### 3. PCB layout

- **GPU die:** identified as NVIDIA AD102, "the world's first 4 nanometer GPU, built at TSMC
  Taiwan with a transistor count of 76.3 billion and a die size of 608 mm²"
  (`techpowerup-circuit-board-analysis.txt`). **No source states where on the PCB it sits**
  (no left/right/centre coordinate, only a photo captioned "Graphics Chip GPU" with no
  positional description).
- **GDDR6X memory chips:** "made by Micron and carry the model number D8BZC, which decodes to
  MT61K512M32KPA-21:U. They are specified to run at 1313 MHz (21 Gbps effective)."
  (`techpowerup-circuit-board-analysis.txt`). Chip count: "the 12 memory modules that are
  featured on the RTX 4090" (`wccftech-suprim-liquidx-teardown.txt`, describing the reference
  memory layout that the pump's four arms contact — this is a reference-board fact, not
  SUPRIM-X-specific, but the memory subsystem is unchanged per
  `techpowerup-introduction-specifications.txt`: "The memory configuration is unchanged").
  **No source states where the chips sit relative to the die** beyond a photo captioned
  "Graphics Card Memory Chips" with no coordinates.
- **VRM / power phases:** GPU voltage "a massive 26-phase design managed by a Monolithic
  Power Systems MP2891 controller, which also handles memory voltage"; GPU DrMOS "Monolithic
  MP86957... rated for 70 A of current each"; memory voltage "a four-phase design... For
  memory, Monolithic MP86957 DrMOS with a 70 A rating are used too."
  (`techpowerup-circuit-board-analysis.txt`, TechPowerUp's own phase count: 26 GPU + 4
  memory). WCCFTech separately describes it as "a 26+2 phase PWM design"
  (`wccftech-suprimx-air-teardown.txt`) — **the two independent sources disagree on the
  memory-phase count (4 vs. 2)**; both are kept, not reconciled.
  **No source states whether the VRM sits left or right of the GPU** — only that these parts
  exist and their electrical ratings.
- **12VHPWR / 16-pin power connector:** "The card uses the new 12+4 pin ATX 12VHPWR
  connector, which is rated for up to 600 W of power draw." (`techpowerup-pictures-teardown.txt`);
  MSI's own spec table: "Power connectors — 16-pin x 1" (`msi-suprimx-specification.txt`);
  TheFPSReview: "the 16-pin 12VHPWR card connector" (`thefpsreview-suprimx.txt`). All sources
  agree it is a single 16-pin (12+4) connector. **No source states exactly where on the PCB
  edge it sits** beyond the generic fact (common to essentially all such cards, but not
  stated as a coordinate here) that it is on the top edge near the rear of the card, visible
  in the "Graphics Card Power Plugs" photo (`techpowerup-pictures-teardown.txt`) — this is a
  photo caption/description, not a stated coordinate, so it is **not** used as a "stated in
  text" fact.
- **PCIe edge:** not separately described by any source beyond the interface spec, "Interface
  — PCI Express® Gen 4" (`msi-suprimx-specification.txt`). No source describes its position
  beyond it being the card's bottom edge connector (standard for any add-in card, but not
  stated explicitly by any source read here).
- **Display outputs:** "DisplayPort x 3 (v1.4a)" and "HDMI™ x 1... HDMI™ 2.1a"
  (`msi-suprimx-specification.txt`, and independently confirmed word-for-word by
  `techpowerup-pictures-teardown.txt`, `wccftech-suprimx-air-teardown.txt`, and
  `thefpsreview-suprimx.txt`). All four independent sources agree: 3x DisplayPort 1.4a + 1x
  HDMI 2.1a, on the standard rear bracket (shown in TechPowerUp's "Monitor Outputs, Display
  Connectors" photo, `techpowerup-pictures-teardown.txt` — again a photo caption, no stated
  coordinate).
- **PCB shorter than the cooler ("common: fans blow through past the PCB end") — CONFIRMED
  in text**, specifically for the air-cooled SUPRIM X: "The graphics card also comes with a
  compact PCB design which means that the shroud, heatsink, and backplate are all extended
  beyond the PCB. The third fan blows air through the heatsink and blows it out from the
  cutouts that are situated at the very end of the backplate." (`wccftech-suprimx-air-teardown.txt`,
  from the page confirmed by the article's own table of contents to be the air SUPRIM X
  section). The same sentence also appears under the Liquid X section of the same article
  (`wccftech-suprim-liquidx-teardown.txt`), where it does not fit (the Liquid X does not have
  "a third fan" on its shroud) — flagged there as a likely copy/paste artifact and NOT used
  as evidence about the Liquid X.
- **One PCB-position fact found:** "A dual BIOS switch is positioned near the rear of the
  PCB." (`thefpsreview-suprimx.txt`). This is the only component position (relative to the
  card, "near the rear") stated in text by any source read for this task.

### 4. What would distinguish SUPRIM from SUPRIM X (VBIOS / 480 W)

**Not found — and the two official MSI spec pages actively show the opposite.** MSI's own
specification tables for the SUPRIM X (`msi-suprimx-specification.txt`) and the non-X air
SUPRIM (`msi-suprim-air-specification.txt`) are identical in every field relevant to this
machine's probe:
- Card Dimension (mm): `336 x 142 x 78 mm` — same on both.
- Weight: `2413g / 3636g` — same on both.
- Power connectors: `16-pin x 1` — same on both.
- Power consumption: `Silent mode: 450W` / `Gaming mode: 480W` — **identical on both pages**,
  matching this machine's probed 480 W default.
- Output: `DisplayPort x 3 (v1.4a)` / `HDMI™ x 1` — same on both.

The **only** difference between the two MSI spec pages is the Core Clocks field: SUPRIM X
"Boost: 2625 MHz (GAMING & SILENT Mode)" / "Extreme Performance: 2640 MHz (MSI Center)" vs.
plain SUPRIM "Boost: 2595MHz" / "Extreme Performance: 2610 MHz". Neither page lists a VBIOS
version at all. So: **the 480 W default power limit reported by this machine's probe does
not distinguish SUPRIM from SUPRIM X — both are specified at 480 W gaming-mode by MSI
itself** — and no source read gives a VBIOS string for either variant. Telling this
machine's card apart as SUPRIM vs. SUPRIM X would require either a boost-clock reading
(2595 vs. 2625 MHz) or a source that maps the VBIOS string `95.02.3C.40.D1` to one variant,
neither of which was found.

Separately, MSI's own cooler-description text ("TRI FROZR 3S" / "TORX FAN 5.0" / blade
design / "Two sets of durable ball bearings") is worded identically on the SUPRIM X overview
page (`msi-suprimx-overview.txt`) and the plain SUPRIM overview page
(`msi-suprim-air-overview.txt`), down to the same image-asset folder name
(`.../RTX-4090-SUPRIM/RTX-4090-SUPRIM-24G/images2/...`) being used on both pages. This is
evidence (from MSI's own site) that **the air SUPRIM and SUPRIM X share the same cooler
design**; no source states this in so many words ("they share the same cooler"), so it is
reported here as an inference from identical published text/assets, not a directly quoted
claim.

The SUPRIM **Liquid X** is clearly a different product from both air variants: 2-slot,
280x140x43mm card + separate 240mm radiator, single block-fan (`wccftech-suprim-liquidx-teardown.txt`),
vs. the air variants' 4(or 3.5)-slot, 336x142x78mm, triple-fan shroud. No source states
whether the Liquid X's card PCB (as opposed to its cooler) is the same PCB as the air
variants; the "26+2 phase PWM design" sentence is worded identically for both the air SUPRIM
X section and the Liquid X section of the WCCFTech article, which is suggestive of a shared
PCB but is not a direct statement to that effect.

## Approximate relative layout — final answer for the caller

Per the task's instruction to give fractions "ONLY where a source... supports it": **no
source read gives numeric coordinates or fractions of card length/height for any component.**
The following is everything that can honestly be derived from what was found, each flagged
by its evidence type; nothing below should be treated as more precise than it is:

- **GPU die centre:** not found (no source gives a position, only identity/size).
- **Memory chips region:** not found as a position; count established as 12 chips
  ("stated in text", `wccftech-suprim-liquidx-teardown.txt`) but not their placement.
- **VRM regions (left/right of GPU):** not found. Phase counts are stated in text (26 GPU +
  4 memory per TechPowerUp, or "26+2" per WCCFTech) but no source says which side of the GPU
  they sit on.
- **12VHPWR connector:** not found as a fraction/position; only that there is exactly one
  16-pin connector ("stated in text", both MSI spec pages and TechPowerUp/TheFPSReview).
  A TechPowerUp photo shows it ("read from a photo description": captioned "Graphics Card
  Power Plugs"), but the caption gives no coordinate.
- **PCIe edge:** not found as a position (interface type only is stated in text).
- **Display outputs bracket:** not found as a fraction/position; only the output count/types
  are stated in text (3x DP 1.4a + 1x HDMI 2.1a, four independent sources), and a TechPowerUp
  photo shows the bracket ("read from a photo description": captioned "Monitor Outputs,
  Display Connectors") without a coordinate.
- **Fan centres:** not found as fractions of card length. What is "stated in text": there are
  three fans (`techpowerup-introduction-specifications.txt`, `wccftech-suprimx-air-teardown.txt`),
  the outermost ("third") fan's airflow exits past the end of the PCB/backplate
  (`wccftech-suprimx-air-teardown.txt`), and the fans are 100 mm ("stated in text",
  TheFPSReview) or 95 mm ("stated in text", third-party parts listing) in diameter — but no
  source gives their centre-to-centre spacing or position along the card.

No fraction/coordinate numbers are given in this report for any of the above, in line with
the instruction not to invent facts that are not established by a source.
