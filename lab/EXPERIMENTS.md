# Experiment index

| ID | Title | Date | Question | Result |
|---|---|---|---|---|
| [exp-0001](exp-0001-hwmon-sweep/) | hwmon sweep | 2026-09-16 | What does hwmon expose on this machine? | 7 devices, 15 channels, all readable as user. No Super-I/O. |
| [exp-0002](exp-0002-nvidia-access/) | NVIDIA access: NVML or `nvidia-smi`? | 2026-09-16 | Which method, how fast, which fields? | NVML, 0.67 ms against 19.91 ms, and more fields. ADR 0003. |
| [exp-0003](exp-0003-root-probe/) | The root probe | 2026-09-17 | What do the root-only sensors give, and which Super-I/O chip is fitted? | RAPL, SMART and DMI all work. The Super-I/O question stays open: Secure Boot lockdown blocks the user-space probe. |
| [exp-0004](exp-0004-hwmon-read-cost/) | The cost of a hwmon read | 2026-09-16 | Does every channel cost the same? | No. NVMe and SPD5118 cost 1.5–2 ms; the rest cost 5 µs. ADR 0006. |
| [exp-0005](exp-0005-component-census/) | Component census and coverage matrix | 2026-09-17, open | How many sensors does this PC hold, and how many can we reach? | Step 1 done: 111 components, 18 with a known source. 10 targets to chase. |
| [exp-0006](exp-0006-nvml-read-cost/) | The cost of an NVML read | 2026-09-21 | Does NVML have expensive calls too? | Yes. Two PCIe calls take 92 % of a pass, 20.6 ms each. A pass fell from 48.4 ms to 0.0227 ms. |
| [exp-0007](exp-0007-nct6687-verification/) | Verify the nct6687 channels | 2026-09-21 | Which of the 29 new channels can we trust? | The chip is an NCT6687D. Fans and temperatures are good. 4 voltages are wrong, because the driver has no voltage map for this board. `_min`/`_max` are not thresholds. |
| [exp-0008](exp-0008-load-response/) | Which channels react to load | 2026-09-21 | Which readings are real, not just plausible? | 45 of 60 channels move. The 15 that do not all have a reason. All 14 board voltages are live; 6 are mislabelled. |
| [exp-0009](exp-0009-bios-ground-truth/) | The BIOS as ground truth | 2026-09-22 | Which voltage label belongs to which reading, and where are the fans? | The fans are on the EZ Conn header, which Linux cannot read. Of 14 voltages, 4 are right, 2 are misnamed and 8 are wrong. |
| [exp-0010](exp-0010-driver-patch-results/) | What the driver patch found | 2026-09-22 | Were the two register guesses right? | Both wrong, and one found the CMOS battery. The EZ Conn fan reads 963-988 RPM at register 0x146, matching the BIOS. |
| [exp-0011](exp-0011-privileged-helper/) | The privileged helper | 2026-09-22 | Can a small root service publish the root-only sensors, and do its numbers agree? | Yes. 19 channels, 0.034 ms per request. RAPL agrees with turbostat, and the `core` domain is core 0 again. Four defects, all found by running it. |
