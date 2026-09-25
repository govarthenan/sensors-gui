# NZXT C1200: no telemetry link, and its efficiency curve

- Date accessed: 2026-09-25
- Tool: WebFetch (a summarising tool). Text in quotes is what the tool returned as a quote; check it against the URL before it is used as a hard number.

## 1. NZXT product page — no USB, no CAM, no power reading

- URL: https://nzxt.com/products/c1200-gold-atx
- Tool result (summary): "No mention of USB connection, digital monitoring, or NZXT CAM support for this power supply model." "This PSU lacks smart monitoring capabilities—no USB header, no CAM integration, and no power reading features mentioned."
- Quotes returned: "135 mm fluid dynamic bearing fan with Zero Fan Mode is completely silent when under 50% load." — "80 PLUS Gold Efficiency, Cybenetics Gold Efficiency, and Cybenetics A- Noise Level Ratings." — "Durable, heat-resistant 12V-2x6 connector pumps up to 600 watts to NVIDIA® GeForce RTX™ 50 Series."
- Specification table returned: model number PA-2G2BB/BW series; 1200 W; AC input 100–240 Vac, 50–60 Hz; +12V 100 A.
- Machine side: nothing on the USB bus belongs to a power supply (`results/usb-devices.txt`), and no NZXT vendor ID (`1e71`) is present.

## 2. Cybenetics report 24PS2447A, "NZXT C1200 Gold" (CWT platform), 2024-05

- URL: https://www.cybenetics.com/evaluations/psus/2447/ and https://www.cybenetics.com/evaluations/psus/2447/cert/en/
- Returned values:

| Load | 115 V | 230 V |
|---|---|---|
| 10 % (120 W) | 84.263 % | 85.43 % |
| 20 % (240 W) | 89.275 % | 90.402 % |
| 30 % (360 W) | 90.853 % | 92.314 % |
| 40 % (480 W) | 90.949 % | 92.75 % |
| 50 % (600 W) | 90.601 % | 92.7 % |
| 60 % (720 W) | 90.018 % | 92.368 % |
| 70 % (840 W) | 89.271 % | 91.915 % |
| 80 % (960 W) | 88.389 % | 91.434 % |
| 90 % (1080 W) | 87.445 % | 90.854 % |
| 100 % (1200 W) | 86.433 % | 90.191 % |
| 2 % or 10 W | 74.614 % | 73.986 % |
| Standby | 0.0173 W | 0.0828 W |
| Average power factor | 0.983 | 0.961 |

- Returned: "ATX Version: Outside Validation Scope"; test date May 17, 2024; issue date May 20, 2024; OEM Channel Well Technology (CWT).
- Also: "Tool result: No digital monitoring interface mentioned in specifications."

## 3. Hardware Busters review (older C1200 Gold, 2023-02-26)

- URL: https://hwbusters.com/psus/nzxt-c1200-gold-psu-review-top-performance/
- Returned: OEM CWT; ATX v3.0; "Selectable semi-passive operation"; no mention of digital monitoring. A second review exists for an ATX 3.1 version: https://hwbusters.com/psus/nzxt-c1200-atx-v3-1-psu-review/ (not fetched).

## Open point

There is more than one "C1200" (2023 ATX 3.0 Gold, 2024 ATX 3.1 Gold, and a white variant). `docs/physical-build.md` records "NZXT C1200" from a photograph through the shroud window. **Which revision is in this machine is not established.** The label on the side of the supply gives the model number (PA-...). The efficiency table above is for report 24PS2447A; a different revision can have a different curve.

## Mains in Sri Lanka (for the 230 V column)

- Source: WebSearch "Sri Lanka plug socket type voltage 230V Type G Type D", 2026-09-25. Summary: Sri Lanka uses 230 V, 50 Hz, with plug types D, G and M; Type G (BS 1363) is the official standard. Links: https://www.worldstandards.eu/electricity/plug-voltage-by-country/sri-lanka/ , https://www.power-plugs-sockets.com/sri-lanka/
- So the **230 V** column applies, if the supply here is the tested revision.
