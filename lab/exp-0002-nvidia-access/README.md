# exp-0002 — NVIDIA access: NVML compared with `nvidia-smi`

Date: 2026-09-16

## Question

Which method should the application use to read the RTX 4090: the NVML C
library through the `nvidia-ml-py` binding, or the text output of
`nvidia-smi --query-gpu`? Which fields does each method give, and how long does
one full sample take?

## Method

`compare.py` reads the same 13 fields with each method, 30 times, and records
the minimum, median and maximum time. It then tries 25 more NVML calls that
`--query-gpu` does not give, and records which of them the driver supports.

```bash
uv run python lab/exp-0002-nvidia-access/compare.py
```

## Result

Driver 595.84. One GPU.

| Method | min | median | max |
|---|---|---|---|
| NVML | 0.41 ms | **0.67 ms** | 2.61 ms |
| `nvidia-smi` | 15.10 ms | **19.91 ms** | 27.61 ms |

NVML is about **30 times faster**. `nvidia-smi` starts a process for each
sample, which is the cost.

### Fields that only NVML gives

| Field | Value at idle | Note |
|---|---|---|
| `fan_count` | 2 | The card has two fans. `--query-gpu` gives one number only. |
| `total_energy_j` | 3 326 325 J | An energy counter since the driver loaded. Good for "energy used today". |
| `pcie_tx_kbps` / `pcie_rx_kbps` | 1 562 / 16 552 | PCIe throughput. |
| `encoder_util` / `decoder_util` | 0 / 0 | NVENC and NVDEC use. |
| `performance_state` | P5 | |
| `throttle_reasons` | bit field | Why the clock is low. |
| `bar1_memory` | 1 976 MiB | |
| `compute_processes` / `graphics_processes` | 0 / 7 | |
| `vbios_version` | 95.02.3C.40.D1 | |
| `max_clock_sm_mhz` | 3 165 MHz | Gives the top of the clock scale. |
| `memory_reserved_v2_mib` | 503 MiB | Only in the v2 memory structure. |

### Fields the hardware or driver does not give

| Field | Result |
|---|---|
| Hotspot temperature | **not supported** (`Invalid Argument`) |
| Memory (GDDR6X) temperature | **not supported** (`nvmlReturn=3`) |
| `serial` | not supported on a consumer card |
| `NVML_FI_DEV_TEMPERATURE_MEM_MAX_TLIMIT` | not supported |

The RTX 4090 gives the edge temperature only. Tools that show a hotspot on
this card read it from the board over I2C, not from NVML.

### A trap: two different "memory used" values

| Call | Value |
|---|---|
| `nvmlDeviceGetMemoryInfo(handle)` (v1) | 2426 MiB |
| `nvmlDeviceGetMemoryInfo(handle, version=nvmlMemory_v2)` | 1922 MiB |
| `nvidia-smi --query-gpu=memory.used` | 1923 MiB |

The v1 structure counts the 503 MiB that the driver reserves. The v2 structure
does not, and matches `nvidia-smi`. **The application must use v2**, or the
number it shows will not agree with every other tool.

### A trap: "T.Limit" values are not temperatures

`NVML_FI_DEV_TEMPERATURE_SHUTDOWN_TLIMIT` gave −7 and
`..._SLOWDOWN_TLIMIT` gave −2. These are **headroom in degrees**, not absolute
temperatures. The absolute limits come from
`nvmlDeviceGetTemperatureThreshold`: slowdown 104 °C, shutdown 99 °C.

Note that the slowdown value (104 °C) is higher than the shutdown value
(99 °C). The enumeration order in NVML is `SHUTDOWN = 0`, `SLOWDOWN = 1`, so
the script's two labels are reversed: 104 °C is the shutdown limit and 99 °C is
the slowdown limit. **Correct this in the collector.**

## Decision

Use NVML. See ADR 0003.
