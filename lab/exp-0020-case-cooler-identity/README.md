# exp-0020 — Which case and cooler, and what does their wiring say about Q20?

Started 2026-10-27, session 13. Stage 1 of the checkpoint 5 plan. Desk
research and one read of sysfs; nothing was written to hardware.

## Question

Gova (2026-10-27): "First, pull the schematics of the relevant components
(case, mobo etc. and try to find out yourself)." Then: "Use the photos."

1. What are the case, the CPU cooler and the case fans, from the photographs?
2. What do their manuals say about which fan goes to which header (Q20)?

## Method

1. Looked at `docs/photos/02` to `05`.
2. Compared the pump block with MSI's product images: the liquid cooling list,
   page 1 (`results/msi-liquid-cooling-list-page1.jpg`), then the product pages
   of the round-pump models (`results/msi-m360-c360-360rv2-no-match.jpg`,
   `results/msi-e360-360r-match-check.jpg`). Screenshots by
   `firecrawl scrape <url> --screenshot`; msi.com gives HTTP 403 to WebFetch.
3. Downloaded the matching cooler's manual and specification and copied the
   pages that matter into `data/evidence/mag-coreliquid-e360-2026-10-27/`.
4. Read the board fan speeds and duty from sysfs:
   `results/2026-10-27-fan-rpm-and-duty.txt`.

## Result

### The cooler: MSI MAG CORELIQUID E360 (black) — inferred

- The pump in photo 03 (round, black cap with the "msi" plate, lit ring)
  matches the black E360 on MSI's page and the pump in the manual's drawing.
  It does not match the square or angular blocks of the A13, A15, I360, M360,
  C360 or the P and E15 series.
- **Inferred, not established.** Gova can confirm it from the box, the invoice
  or a label.
- The E360 has a 360 mm radiator with 3 fans, which agrees with the 3 top fans
  on the CPU radiator (`docs/physical-build.md`, CORRECTION table).

### What the E360 manual says about the headers

The pump goes to `PUMP_FAN`; the 3 radiator fans go, through one 1-to-3 PWM
cable, to `CPU_FAN`. So on this board one tachometer reports for all 3 fans.
Pump: 3000 RPM ± 10 %. Fans: no MSI figure; retailers say 1800 or 2000 RPM
at most. Evidence: `data/evidence/mag-coreliquid-e360-2026-10-27/README.md`.

### The readings do not fit the manual well

| Header | Reads | Duty | Fits the manual (fans on CPU_FAN1, pump on PUMP_SYS1)? |
|---|---|---|---|
| `CPU_FAN1` | 2131-2234 RPM now; 2758 under load (`exp-0008`); 3125 in the BIOS | 140-148 of 255 | Poorly: above the fans' published maximum at about half duty |
| `PUMP_SYS1` | 1461-1479 RPM, steady | 255 of 255 | Poorly: half the pump's 3000 ± 10 % |

Hypotheses, none established:

- **H1** — The pump is on `CPU_FAN1` and the 3 radiator fans are on
  `PUMP_SYS1` (perhaps through the low-noise cable R). The numbers fit this
  best. If it is true, the thermal shutdown of 2026-09-22 stopped **the
  pump**, not the radiator fans.
- **H2** — The wiring is as the manual shows, and a tachometer counts in a way
  not established (for example a pump that reports two pulses for each turn,
  read as half its speed). This does not explain `CPU_FAN1` at 2234 RPM on
  half duty.
- **H3** — The cooler is not an E360, and its parts have other speeds.

**The BIOS test of Q20 settles H1 against H2.** For `CPU_FAN1`, Gova listens
and looks: either the pump or the 3 top fans change. Neither header is ever
set to 0.

### The case and the case fans: not identified

The case (a mesh tower with a honeycomb rear and bottom, 3 front fans inside
the front, a bottom shroud) and the 7 case-side fans were not matched to a
product. A search of MSI's MAG FORGE and MAG PANO cases found no match. Gova
asked "Which components do you need named?": **the case model and the model
of the front, top and rear fans.** The top fans may be the E360's own fans.

### What it means for Q20

- `JAF_1` EZ Conn reads one live fan (986 RPM). The E360 does not use EZ Conn,
  so it is a case fan or a group of case fans, which ones not established.
- `SYS_FAN1` reads one live fan (1266-1283 RPM), which one not established.
- 3 front + 1 rear = 4 case fans, and 2 headers (`SYS_FAN1`, `JAF_1`) report.
  At least one header has more than one fan.
