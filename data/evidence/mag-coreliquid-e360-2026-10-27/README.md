# MSI MAG CORELIQUID E360 — manual and specification

Fetched 2026-10-27 for `lab/exp-0020-case-cooler-identity/`. Desk research only;
nothing on the machine was touched.

**Status: the cooler model is inferred, not established.** The pump block in
`docs/photos/03-pump-and-top-fans.jpg` (round, a black cap with the "msi"
plate, a lit ring) matches the black E360 in MSI's product image and in the
manual's drawing. No label on the machine has been read. Gova can confirm it
from the box, the invoice or the pump cable label.

| File | Source | How it was made |
|---|---|---|
| `manual-p12-connection.png` | `https://download.msi.com/archive/mnu_exe/lc/7ZW5_7ZW6.pdf`, PDF page 13 (printed page 12), "Connection" | `curl -sL -o 7ZW5_7ZW6.pdf <url>`; `pdftoppm -f 13 -l 13 -r 150 -png`. PDF SHA-256 `70178435eddc9de46fdfdaba266270aae5c6cda75fc6495daa99860cff874617`, 6.8 MB, 20 pages, created 2024-09-03. The PDF is not kept (size). |
| `manual-contents-06.png`, `manual-contents-07.png` | the same PDF, pages 6 and 7, "Packing Contents" | `pdftoppm -f 6 -l 7 -r 110 -png` |
| `manual-cover-01.png` | the same PDF, page 1: one manual for E240, E360 and their WHITE versions | `pdftoppm -f 1 -l 1 -r 80 -png` |
| `specification.txt` | `https://www.msi.com/Liquid-Cooling/MAG-CORELIQUID-E360/Specification` | `firecrawl scrape <url>`; the specification block only, repeated lines removed. Plain WebFetch got HTTP 403. |
| `msi-e360-overview-screenshot.jpg` | `https://www.msi.com/Liquid-Cooling/MAG-CORELIQUID-E360` | `firecrawl scrape <url> --screenshot`, 1920 x 1080, reduced to 1400 px JPEG |

## What the manual and the specification say

- **Connection (manual p.12):** the pump's 4-pin cable goes to `PUMP_FAN`.
  The three radiator fans go through the 1-to-3 PWM cable (part Q, 360 only)
  to `CPU_FAN`. The block's ARGB cable and the fans' ARGB go to `JRAINBOW`.
  Part P (Molex to 4-pin) can feed the fans from the power supply.
- **Part R (360 only)**, "Optional Fan Down Slow Speed Controller Cable": a
  low-noise adapter for the fans. The specification lists it as "1 x low
  noise adapter cable".
- **Pump:** 4-pin, **3000 RPM ± 10 %** (2700 to 3300 RPM).
- **Fans:** 3 x 120 mm, 4-pin PWM, ARGB. The MSI page gives no fan speed.
  Retailers give 600-1800 RPM (Alza, Ebuyer: "600±250RPM-1800±200RPM") or
  500-2000 RPM (Memory Express, Dateks). Not an MSI figure; not established.
- **No EZ Conn.** Nothing in this manual uses the `JAF_1` header.

## Why it matters, and the conflict it shows

The manual wiring says `CPU_FAN1` = the 3 radiator fans and `PUMP_SYS1` = the
pump. The readings of this machine do not fit that well:

- `CPU_FAN1` reads **2131-2234 RPM at duty 140-148 of 255** (55-58 %), and up
  to 2758 RPM under load (`exp-0008`) and 3125 RPM in the BIOS
  (`docs/photos/bios/02`). That is above any published maximum of the fans
  (1800 ± 200 or 2000) at about half duty, and inside the pump's
  2700-3300 RPM at the top.
- `PUMP_SYS1` reads a steady **1461-1479 RPM at duty 255 of 255**. That is
  half the pump's rated speed, or the fans at full duty through the
  low-noise cable R.

So either the pump and the fans were connected to the other headers than the
manual shows, or the cooler is not an E360, or a tachometer counts in a way
not established. `lab/exp-0020-case-cooler-identity/README.md` lists the
hypotheses. The BIOS test of Q20 settles it.
