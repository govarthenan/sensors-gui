# ADR 0003 — Read the NVIDIA GPU through NVML, not `nvidia-smi`

- Date: 2026-09-16
- Status: accepted
- Evidence: `lab/exp-0002-nvidia-access/`

## Context

The RTX 4090 can be read two ways: the NVML C library (through the
`nvidia-ml-py` binding), or the text output of the `nvidia-smi` command.

Measurement on this machine (30 samples of 13 fields, driver 595.84):

| Method | median time |
|---|---|
| NVML | 0.67 ms |
| `nvidia-smi` | 19.91 ms |

NVML also gives fields that `--query-gpu` does not: the fan count, the total
energy counter, PCIe throughput, encoder and decoder use, throttle reasons,
BAR1 memory, process counts and the maximum clock.

## Decision

The application reads the NVIDIA GPU through NVML with the `nvidia-ml-py`
package. `nvidia-smi` is used only as a fallback if `nvmlInit` fails, and for
a diagnostic dump.

Two rules come with this decision:

1. Call `nvmlDeviceGetMemoryInfo(handle, version=nvmlMemory_v2)`. The version 1
   structure counts driver-reserved memory and disagrees with every other tool
   by about 500 MiB.
2. Do not trust the `*_TLIMIT` fields as temperatures. They are headroom
   values. Use `nvmlDeviceGetTemperatureThreshold` for absolute limits, and
   remember that in NVML `SHUTDOWN = 0` and `SLOWDOWN = 1`.

## Consequences

- A sample of the GPU costs less than 1 ms, so a 1 Hz or 4 Hz refresh is cheap.
- The application gets a dependency on `nvidia-ml-py`. That package is a thin
  binding and does not need CUDA.
- NVML must be started once and closed once, not for each sample.
- The hotspot and memory temperatures are not available on this card through
  NVML. The user interface must not show empty fields for them.
