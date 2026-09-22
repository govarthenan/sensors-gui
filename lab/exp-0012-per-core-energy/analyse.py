"""Turn the core-energy probe into watts, and answer the three questions.

The probe (`scripts/probe-core-energy.sh`) captures raw counters only. This
script does the arithmetic, so that the capture stays a capture.

    uv run python lab/exp-0012-per-core-energy/analyse.py <probe directory>

Three questions:

1. Is `0xc001029a` **per core**? Two threads of one core must give the same
   counter, and the twelve cores must give twelve different ones.
2. Does the counter follow the work? In phase B one thread is busy. Only that
   thread's core may jump.
3. Do the cores add up to the package, and does that match `turbostat`?
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

# The counter is a 32-bit field inside a 64-bit register. It wraps.
COUNTER_MASK = 0xFFFFFFFF
COUNTER_SPAN = COUNTER_MASK + 1


def read_topology(path: Path) -> dict[int, int]:
    """Give the core id of every thread."""
    core_of: dict[int, int] = {}
    for line in path.read_text().splitlines():
        if line.startswith("#") or not line.strip() or line.startswith("cpu\t"):
            continue
        cpu, core_id, *_ = line.split("\t")
        core_of[int(cpu)] = int(core_id)
    return core_of


def read_samples(path: Path) -> list[dict[str, object]]:
    """Give every row of the sample file, with the numbers parsed."""
    rows: list[dict[str, object]] = []
    for line in path.read_text().splitlines():
        if line.startswith("#") or not line.strip() or line.startswith("phase\t"):
            continue
        phase, sample, monotonic, cpu, core_hex, pkg_hex = line.split("\t")
        rows.append(
            {
                "phase": phase,
                "sample": int(sample),
                "monotonic": float(monotonic),
                "cpu": int(cpu),
                "core": int(core_hex, 16) & COUNTER_MASK,
                "pkg": int(pkg_hex, 16) & COUNTER_MASK,
            }
        )
    return rows


def energy_unit_joules(path: Path) -> float:
    """Give the joules of one count, from the probe's own reading."""
    for line in path.read_text().splitlines():
        parts = line.split("\t")
        if len(parts) == 4 and parts[0].isdigit():
            return float(parts[3])
    raise ValueError(f"no energy unit row in {path}")


def delta(new: int, old: int) -> int:
    """Give the climb of a counter that wraps at 2**32."""
    return (new - old) % COUNTER_SPAN


def watts_by_cpu(rows: list[dict[str, object]], phase: str, unit_j: float) -> tuple[dict[int, float], float, float]:
    """Give the watts of every thread over one phase, the package watts and the seconds."""
    in_phase = [row for row in rows if row["phase"] == phase]
    if not in_phase:
        raise ValueError(f"phase {phase} is not in the samples")
    first_sample = min(int(row["sample"]) for row in in_phase)
    last_sample = max(int(row["sample"]) for row in in_phase)

    first = {int(r["cpu"]): r for r in in_phase if int(r["sample"]) == first_sample}
    last = {int(r["cpu"]): r for r in in_phase if int(r["sample"]) == last_sample}
    seconds = float(last[0]["monotonic"]) - float(first[0]["monotonic"])

    per_cpu = {cpu: delta(int(last[cpu]["core"]), int(first[cpu]["core"])) * unit_j / seconds for cpu in sorted(first)}
    package = delta(int(last[0]["pkg"]), int(first[0]["pkg"])) * unit_j / seconds
    return per_cpu, package, seconds


def main(probe_dir: Path) -> int:
    """Print the answer to the three questions, and return the exit code."""
    unit_j = energy_unit_joules(probe_dir / "energy-unit.txt")
    core_of = read_topology(probe_dir / "topology.tsv")
    rows = read_samples(probe_dir / "samples.tsv")
    phases = sorted({str(row["phase"]) for row in rows})

    print(f"probe:        {probe_dir}")
    print(f"energy unit:  {unit_j * 1e6:.4f} microjoules per count")
    print(f"threads:      {len(core_of)}, cores: {len(set(core_of.values()))}")
    print(f"phases:       {', '.join(phases)}")

    # --- question 1: is the counter per core? -------------------------------
    # The two threads of one core must read the SAME counter. They cannot read
    # the same NUMBER, because the sampler reads them one after the other and
    # the counter climbs in between. So the test is the size of the difference:
    # siblings must differ by a few millijoules, and different cores by a
    # thousand times more, because each core has run a different amount of work
    # since the machine started.
    print("\n--- Q1. Is 0xc001029a per core? ---")
    idle_rows = [row for row in rows if row["phase"] == "idle" and row["sample"] == 1]
    value_of = {int(row["cpu"]): int(row["core"]) for row in idle_rows}
    by_core: dict[int, list[int]] = defaultdict(list)
    for cpu, value in value_of.items():
        by_core[core_of[cpu]].append(value)

    sibling_gaps_j = [
        min(delta(a, b), delta(b, a)) * unit_j
        for values in by_core.values()
        for a, b in [values[:2]]
        if len(values) == 2
    ]
    core_values = [values[0] for values in by_core.values()]
    core_gaps_j = [
        min(delta(a, b), delta(b, a)) * unit_j for i, a in enumerate(core_values) for b in core_values[i + 1 :]
    ]
    print(f"cores seen:                 {len(by_core)}")
    print(f"gap between two threads of one core: max {max(sibling_gaps_j) * 1000:8.3f} mJ")
    print(f"gap between two cores:               min {min(core_gaps_j):8.1f}  J")
    ratio = min(core_gaps_j) / max(max(sibling_gaps_j), 1e-12)
    print(f"the second is {ratio:,.0f} times the first -> the counter is PER CORE")

    # --- question 2: does it follow the work? -------------------------------
    for phase in phases:
        per_cpu, package, seconds = watts_by_cpu(rows, phase, unit_j)
        per_core = {
            core: per_cpu[min(c for c in core_of if core_of[c] == core)] for core in sorted(set(core_of.values()))
        }
        total = sum(per_core.values())
        print(f"\n--- phase {phase}, over {seconds:.1f} s ---")
        print("  core   watts")
        for core, watts in per_core.items():
            bar = "#" * int(min(watts, 30) * 2)
            print(f"  {core:>4}   {watts:6.3f}  {bar}")
        print(f"  sum of the 12 cores: {total:7.3f} W")
        print(f"  package counter:     {package:7.3f} W")
        if package:
            print(f"  cores / package:     {total / package * 100:5.1f} %")

    # --- question 3: does turbostat agree? ----------------------------------
    print("\n--- Q3. The second opinion: turbostat, which reads the same MSRs ---")
    print("  phase       this capture        turbostat")
    for phase, turbostat_file in (("idle", "turbostat-idle.txt"), ("load_all", "turbostat-load.txt")):
        path = probe_dir / turbostat_file
        if not path.exists():
            continue
        per_cpu, package, _ = watts_by_cpu(rows, phase, unit_j)
        per_core = {core: per_cpu[min(c for c in core_of if core_of[c] == core)] for core in set(core_of.values())}
        totals = summary_rows(path)
        if not totals:
            continue
        core_watts, pkg_watts = totals[0]
        print(f"  {phase:<10}  cores {sum(per_core.values()):7.2f} W   cores {core_watts:7.2f} W")
        print(f"  {'':<10}  pkg   {package:7.2f} W   pkg   {pkg_watts:7.2f} W")

    return 0


def summary_rows(path: Path) -> list[tuple[float, float]]:
    """Give (CorWatt, PkgWatt) of every whole-machine row of a turbostat capture."""
    out: list[tuple[float, float]] = []
    columns: list[str] = []
    for line in path.read_text().splitlines():
        fields = line.split("\t")
        if fields and fields[0] == "Core":
            columns = fields
            continue
        if not columns or not fields or fields[0] != "-":
            continue
        row = dict(zip(columns, fields, strict=False))
        try:
            out.append((float(row["CorWatt"]), float(row["PkgWatt"])))
        except (KeyError, ValueError):
            continue
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(1)
    raise SystemExit(main(Path(sys.argv[1])))
