# RTX 4090 SUPRIM Liquid X fan channels — published sources

Web research only, done 2026-09-23, to answer Gova's question: which NVML fan channel
(fan 0 or fan 1) is the fan mounted ON the card, and what does the other channel drive? No
hardware on this machine was touched; this is desk research against published third-party
pages and MSI's own site, fetched with the `firecrawl` CLI. Two pages needed an Internet
Archive Wayback Machine snapshot because TechPowerUp's own bot-protection returned a
challenge page on direct fetch; this is noted in that file. Raw scrapes are kept under
`.firecrawl/` at the project root (git-ignored), the files below are the trimmed, quoted
evidence.

Related: `lab/exp-0013-rtx4090-board-sensors/README.md` (found the two NVML fan channels and
their under-load RPMs, 1205 and 1520), `docs/physical-build.md` (corrected 2026-09-23: the
card is the SUPRIM LIQUID X, one fan on the card + a 240 mm radiator with 2 fans that is the
card's own, not the CPU cooler's), `data/evidence/rtx4090-suprim-layout-2026-09-23/` (earlier
research, some of it about the wrong card variant, kept as it stands), the MS-V510 board
schematic already saved there (`scribd-ms-v510-schematic-extract.txt`: two fan headers, "FAN
A (LEFT)" and "FAN B (RIGHT)", each on its own GPU GPIO PWM/TACH pair).

## Files

| File | Source | What it establishes |
|---|---|---|
| `msi-forum-radiator-fan-problem.txt` | MSI Forum, owner thread (live) | Where the radiator fans plug in, and that the card supplies their power/PWM through its own cable, not the motherboard, in stock form |
| `kitguru-suprim-liquidx-review.txt` | KitGuru review/teardown (live) | Card fan = 100 mm, cools VRM + PCB only; radiator fans use standard swappable 4-pin PWM headers; AIO made by Cooler Master; both fan groups run independent curves |
| `tomshardware-suprim-liquidx-review-page6.txt` | Tom's Hardware review (live) | Explicit statement that a reviewer could NOT tell which GPU-Z fan reading is which physical fan; card fan given as 95 mm (disagrees with KitGuru's 100 mm) |
| `techpowerup-suprim-liquidx-temps-fan-noise.txt` | TechPowerUp review, page 37 (via Wayback) | One RPM figure per test condition (1197 RPM gaming), no per-fan breakdown; numerically closer to this machine's fan0 than fan1 |
| `msi-meg-silent-gale-p12-specification.txt` | MSI's own product spec page (live) | Rated speed of the fan model WCCFTech says is on the radiator: 0-2000 RPM, 4-pin PWM |
| `guru3d-suprim-liquidx-review-page2.txt` | Guru3D review (live) | Independently confirms 1 card fan + 2 radiator fans; names the radiator fans "Gentle Typhoon", disagreeing with WCCFTech's and KitGuru's naming |
| `msi-official-installation-guide.txt` | MSI's own PDF installation leaflet (live) | The closest thing to an official manual found; its 9 steps never mention a fan cable at all, consistent with the radiator-to-card fan cable being factory-made |

## Facts and where they come from

### 1. Where the radiator fans are plugged in

**Established, from a first-hand account:** the two radiator fans connect to 4-pin PWM
connectors ON THE RADIATOR itself (a small hub/pigtail assembly), and that radiator hub is
wired back to the CARD, not the motherboard, by its own cable in stock form.

- MSI forum owner, after removing the fans: "I plugged the fans back in to the 4 pin
  connectors on the radiator" (`msi-forum-radiator-fan-problem.txt`).
- Same owner, over a year later, confirming the card-side connector exists and is separate
  from the motherboard: "I decided to plug the fans into the connector that came with the
  radiator on the 4090 just to see if it would supply power" — after having used the
  motherboard's own case-fan headers only as a workaround once that connector had failed
  (`msi-forum-radiator-fan-problem.txt`).
- KitGuru, independently: "As for the two fans, these connect via standard 4-pin PWM headers
  to the small exposed wires. This is good news as the fans can be easily swapped out for
  third-party models with no proprietary headers to contend with." (`kitguru-suprim-liquidx-review.txt`)
- MSI's own installation guide never instructs the installer to connect a fan cable at all —
  only the 16-pin GPU power connector is a cable step — consistent with the radiator-to-card
  fan cable being made at the factory (`msi-official-installation-guide.txt`).

**Not found:** no source gives the physical connector type or pin-out of the cable between
the radiator hub and the card (e.g. whether it is one of the "DUAL FAN 6-PIN FFC HEADERS"
named in the MS-V510 schematic, or something else). The schematic names two 6-pin FFC
headers on the GPU board itself, "FAN A (LEFT)" and "FAN B (RIGHT)"; no source connects those
header names to "the card's own fan" versus "the radiator's cable" by name.

### 2. Which fan is "Fan 1" and which is "Fan 2" in monitoring tools

**Not found, and explicitly stated to be unknown even by a professional reviewer with the
card in hand.**

- Tom's Hardware, in its own review of this exact card: "There are three fans, two 120mm
  fans on the radiator and the 95mm fan on the card. **It's not clear which fan speeds are
  reported by GPU-Z**..." (`tomshardware-suprim-liquidx-review-page6.txt`) — this is the
  single most direct statement found on the question, and the answer it gives is that the
  mapping is not published or knowable from the tool's output alone.
- TechPowerUp's review reports one RPM number per test condition, not one per fan, and does
  not caption which channel it is (`techpowerup-suprim-liquidx-temps-fan-noise.txt`).
- No MSI Afterburner, GPU-Z, HWiNFO or MSI Center screenshot naming "Fan1"/"Fan2" (or
  equivalent) against a labelled photograph of this card's two fan groups was found in the
  time available. Search results turned up screenshots and forum threads about fan reporting
  on OTHER MSI SUPRIM cards (e.g. the air-cooled RTX 3080/3090 SUPRIM X, which has 3 physical
  fans and known issues with tools showing only 2 of them), which are a different product and
  were not saved as evidence for this card.

**A numeric, not-fully-conclusive observation kept here rather than in the README's main
claims:** TechPowerUp's single reported RPM figure for this card under gaming load, 1197 RPM,
sits close to this machine's own measured fan0 (1205 RPM, `lab/exp-0013-rtx4090-board-sensors/`)
and further from fan1 (1520 RPM). This is suggestive, not proof — different physical card,
different ambient, different load, and TechPowerUp does not say which NVML/GPU-Z index it
read.

### 3. Rated maximum RPM

- **Radiator fans, if they are the MEG Silent Gale P12 (WCCFTech's identification, not
  independently confirmed — see the disagreement below):** MSI's own spec page states
  "Fan Speed: 0~2000 RPM" (`msi-meg-silent-gale-p12-specification.txt`).
- **The card's own Torx 5.0 shroud fan:** **not found.** MSI markets "TORX FAN 5.0" only by
  its blade/ring design across every MSI page found that mentions it, with no RPM figure
  anywhere. No review read gave a stated maximum RPM for the card's own fan either; the
  highest RPM figure found for it is Tom's Hardware's own overclocked/custom-fan-curve
  result, "2000-2200" (`tomshardware-suprim-liquidx-review-page6.txt`), which is a measured
  result under a non-stock fan curve, not a rated maximum.
- **Disagreement on which fan brand is on the radiator, kept unresolved:** WCCFTech says
  "MSI's latest MEG Silent GALE P12 fans" (existing evidence,
  `data/evidence/rtx4090-suprim-layout-2026-09-23/wccftech-suprim-liquidx-teardown.txt`);
  KitGuru calls them "MSI's included Silent Gale fans", matching WCCFTech
  (`kitguru-suprim-liquidx-review.txt`); Guru3D calls the same fans "Gentle Typhoon 120 mm
  fans", twice, independently (`guru3d-suprim-liquidx-review-page2.txt`). Two of three named
  sources agree on "Silent Gale"; Guru3D's "Gentle Typhoon" is kept as stated, flagged lower
  confidence (Gentle Typhoon is normally a Scythe-branded line, not previously seen bundled
  with an MSI OEM AIO in any other source read).

## What is established versus inferred — summary for the caller

**Established, from a stated source:**
- One fan is on the card itself (95-100 mm, sources disagree on the exact figure), and cools
  the VRM/PCB only, not the GPU or memory (liquid-cooled). Two fans are on the 240 mm
  radiator. (KitGuru, Guru3D, Tom's Hardware, WCCFTech — four independent sources agree on
  this basic 1 + 2 layout.)
- The radiator's two fans plug into the radiator's own 4-pin PWM hub, which is wired to the
  card (not the motherboard) by its own cable in stock form; the motherboard is only usable
  as a manual workaround, and doing so loses the card's own idle-fan-stop behaviour.
- A professional reviewer (Tom's Hardware) explicitly could not determine which GPU-Z fan
  reading corresponds to which physical fan, on this exact card.
- If the radiator fans are the MEG Silent Gale P12 (as WCCFTech and KitGuru's naming imply),
  their rated maximum is 2000 RPM.

**Not found by any source read:**
- Which NVML/GPU-Z/HWiNFO/Afterburner fan index (Fan 1 vs Fan 2, or index 0 vs 1) is the card
  fan versus the radiator pair.
- A rated maximum RPM for the card's own Torx 5.0 fan.
- The physical connector type/pin-out of the cable between the radiator hub and the card.
- Confirmation of which fan brand is really on the radiator (three sources, two names).
