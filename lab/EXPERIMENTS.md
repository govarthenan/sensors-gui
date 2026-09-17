# Experiment index

| ID | Title | Date | Question | Result |
|---|---|---|---|---|
| [exp-0001](exp-0001-hwmon-sweep/) | hwmon sweep | 2026-09-16 | What does hwmon expose on this machine? | 7 devices, 15 channels, all readable as user. No Super-I/O. |
| [exp-0002](exp-0002-nvidia-access/) | NVIDIA access: NVML or `nvidia-smi`? | 2026-09-16 | Which method, how fast, which fields? | NVML, 0.67 ms against 19.91 ms, and more fields. ADR 0003. |
| exp-0003 | Super-I/O chip identification | **reserved** | Which sensor chip is on the MSI board? | waits for Gova to run `scripts/root-probe.sh` |
| [exp-0004](exp-0004-hwmon-read-cost/) | The cost of a hwmon read | 2026-09-16 | Does every channel cost the same? | No. NVMe and SPD5118 cost 1.5–2 ms; the rest cost 5 µs. ADR 0006. |
