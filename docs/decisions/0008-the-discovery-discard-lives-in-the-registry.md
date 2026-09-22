# ADR 0008 — The discard after discovery belongs to the registry

- Date: 2026-09-22
- Status: accepted
- Evidence: `lab/exp-0007-nct6687-verification/`, finding 4

## Context

Some drivers report nonsense until they have updated once. Measured on this
machine: seconds after `modprobe nct6687`, the `sensors` output showed
`+3.3V 0.00 V`, `AVSB 0.00 V` and `VBat 0.00 V`. The same three channels read
3.332 V, 3.328 V and 2.046 V a few minutes later.

So the first read pass after a device appears must be taken and thrown away.
The question is **where**.

## Decision

The discard lives in `Registry.discover()`, not in `Sampler`.

`discover()` collects the specs, then calls `read_all()` once and drops the
result.

## Why not the sampler

Putting it in the sampler would mean a `_warmed_up` flag and a first call that
behaves differently from every other call. That is a special case in the hot
path, and a special case is where bugs live.

More importantly, the discard belongs to a **hardware event** — a device
settling after it appears — not to a particular reader. If two samplers ever
read one registry, or if the screen reads it directly as well, the warm-up
should still happen exactly once. Tying it to the registry makes that true by
construction.

## Consequences

- `Sampler.sample()` is uniform. Every call, including the first, does exactly
  one `registry.read_all()`.
- `discover()` is no longer free. It costs one full read pass, which on this
  machine is about 10 ms the first time, because the interval caches are cold
  and the NVMe and DIMM channels are read. That is acceptable for something
  that runs once at start and again only on a re-scan.
- `Registry` gains a public `read_all()`. It is the connector the sampler needs
  in order to read every collector without the registry exposing its list.
- A caller that builds a registry and reads it directly, without a sampler,
  gets the same protection for free.
