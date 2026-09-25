# The parts that no sensor measures: what the web gives

- Date accessed: 2026-09-25
- Tool: WebSearch / WebFetch (summarising).

## 1. The two monitors (MSI MD272QXP) — they are NOT on the PC's power supply

- Source: WebSearch "MSI MD272QXP specifications power consumption typical watts power input", 2026-09-25. The result summary gave "On Mode Power consumption of 16.1 watts, Sleep Mode Power of 0.3 watts, and Off Mode Power of 0.18 watts" and "51.07 kWh/yr", from the ENERGY STAR entry https://www.energystar.gov/productfinder/product/certified-displays/details/2635695 . The page itself did not render in WebFetch, so **the figure is not verified**.
- The monitors have their own mains supply. A wall meter on the PC's plug does not see them unless they share the same plug or strip.

## 2. X870 chipset power

- Source: WebSearch "AMD X870 chipset Promontory 21 power consumption watts each chip", 2026-09-25. Summary: X870 has **one** Promontory 21 chip (X870E has two). **No published power figure was found. Not established.** Links: https://www.techspot.com/review/2907-amd-x870-motherboards/ , https://www.techpowerup.com/323052/amd-shuffles-feature-sets-of-its-800-series-chipset-x870-is-b650e-successor

## 3. DDR5 module power

- Source: WebSearch "DDR5 DIMM power consumption watts per module measured PMIC 32GB 6000 EXPO", 2026-09-25. **No measured per-module figure was found. Not established.** The PMIC rails of these modules are closed to this project (ADR 0011).

## 4. The NVMe drive — from the machine, not the web

- The drive declares its own power states (`results/nvme-power.txt`, copied from the root probe of 2026-09-22): PS0 max 5.00 W, PS1 3.30 W, PS2 2.20 W, and three sleep states from 0.0150 W down. These are **declared maxima**, not measurements.
