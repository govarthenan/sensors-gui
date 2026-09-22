#!/usr/bin/env bash
# probe-core-energy.sh — capture the AMD per-core energy counters.
#
# Run it like this, from the project root:
#
#     sudo ./scripts/probe-core-energy.sh
#
# THIS SCRIPT ONLY READS. `rdmsr` reads a CPU register; it writes nothing, it
# loads no module and it changes no file outside data/probes/. See ADR 0007.
# The SMU mailbox route to the same data (ryzen_smu, zenpower3) WRITES a
# command to the processor. This script deliberately does not use it.
#
# The question it answers:
#
#   The powercap `core` domain on this machine is core 0 only. exp-0003 and
#   exp-0011 both proved that. But the processor holds one energy counter for
#   EACH core, at MSR 0xc001029a. Does this Zen 5 part give all twelve, and do
#   they agree with turbostat and with the package counter?
#
# The three MSRs, from this kernel's own header
# (/usr/src/linux-headers-$(uname -r)/arch/x86/include/asm/msr-index.h):
#
#   0xc0010299  MSR_AMD_RAPL_POWER_UNIT    bits 12:8 = energy unit, 1/2^ESU J
#   0xc001029a  MSR_AMD_CORE_ENERGY_STATUS one counter for each core, 32 bit
#   0xc001029b  MSR_AMD_PKG_ENERGY_STATUS  one counter for the package, 32 bit
#
# Three phases, because a per-core counter must be proved core by core:
#
#   A. idle      — every counter climbs slowly.
#   B. one core  — ONE core is made busy. Only that core's counter must jump.
#   C. all cores — every counter climbs, and the sum must approach the package.
#
# Results go to data/probes/core-energy-<timestamp>/.

set -uo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This script needs root. Run: sudo $0" >&2
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${PROJECT_ROOT}/data/probes/core-energy-${STAMP}"
mkdir -p "${OUT}"

# `sudo` sets SUDO_USER; `pkexec`, which the run-as-root skill uses, sets
# PKEXEC_UID instead. Without the second one the results are left owned by
# root inside the user's repository, where the user cannot change them.
if [ -n "${SUDO_USER:-}" ]; then
    CALLER="${SUDO_USER}"
elif [ -n "${PKEXEC_UID:-}" ]; then
    CALLER="$(id -nu "${PKEXEC_UID}" 2>/dev/null || echo root)"
else
    CALLER="root"
fi

log() { echo "[probe-core-energy] $*"; }

header() {
    # header <file> <command text>
    {
        echo "# captured $(date -u +%Y-%m-%dT%H:%M:%SZ) on $(hostname)"
        echo "# command: $2"
        echo "# source:  this machine, dst-gova-pc"
        echo
    } > "$1"
}

MSR_UNIT=0xc0010299
MSR_CORE=0xc001029a
MSR_PKG=0xc001029b

# --- 0. Can this run at all? ------------------------------------------------
log "check the preconditions"
header "${OUT}/preconditions.txt" "checks for rdmsr, the msr module, lockdown and the CPU family"
{
    echo "rdmsr:    $(command -v rdmsr || echo 'NOT INSTALLED — apt install msr-tools')"
    echo "msr.ko:   $(lsmod | awk '$1=="msr"{print "loaded"}' || true)"
    modprobe msr 2>&1 && echo "modprobe msr: ok"
    echo "lockdown: $(cat /sys/kernel/security/lockdown 2>&1)"
    echo "kernel:   $(uname -r)"
    echo
    grep -m1 'model name' /proc/cpuinfo
    grep -m1 'cpu family' /proc/cpuinfo
    grep -m1 -w 'model' /proc/cpuinfo
    echo
    echo "/dev/cpu/*/msr node count: $(ls -d /dev/cpu/[0-9]*/msr 2>/dev/null | wc -l)"
    echo
    echo "--- the MSR numbers, from this kernel's header, not from memory ---"
    grep -nE 'MSR_AMD_(RAPL_POWER_UNIT|CORE_ENERGY_STATUS|PKG_ENERGY_STATUS)' \
        "/usr/src/linux-headers-$(uname -r)/arch/x86/include/asm/msr-index.h" 2>&1
} >> "${OUT}/preconditions.txt" 2>&1

if ! command -v rdmsr > /dev/null 2>&1; then
    log "rdmsr is not installed. Install msr-tools and run this again."
    [ "${CALLER}" != "root" ] && chown -R "${CALLER}:${CALLER}" "${OUT}"
    exit 2
fi

# A first read, to fail early and clearly if this part does not carry them.
if ! rdmsr -p 0 "${MSR_CORE}" > /dev/null 2>&1; then
    log "MSR ${MSR_CORE} cannot be read on cpu0. See ${OUT}/preconditions.txt"
    {
        echo
        echo "FIRST READ FAILED:"
        rdmsr -p 0 "${MSR_CORE}" 2>&1
    } >> "${OUT}/preconditions.txt"
    [ "${CALLER}" != "root" ] && chown -R "${CALLER}:${CALLER}" "${OUT}"
    exit 3
fi

# --- 1. Topology: which thread sits on which core ---------------------------
# The energy counter is per CORE, not per thread. Two threads of one core must
# return the same value. That is one of the checks this capture makes possible.
log "capture the CPU topology"
header "${OUT}/topology.tsv" "read /sys/devices/system/cpu/cpu*/topology/ for every thread"
{
    printf 'cpu\tcore_id\tdie_id\tpackage_id\tthread_siblings\n'
    for d in /sys/devices/system/cpu/cpu[0-9]*; do
        cpu="$(basename "${d}" | tr -d 'cpu')"
        t="${d}/topology"
        [ -d "${t}" ] || continue
        printf '%s\t%s\t%s\t%s\t%s\n' \
            "${cpu}" \
            "$(cat "${t}/core_id" 2>/dev/null)" \
            "$(cat "${t}/die_id" 2>/dev/null)" \
            "$(cat "${t}/physical_package_id" 2>/dev/null)" \
            "$(cat "${t}/thread_siblings_list" 2>/dev/null)"
    done | sort -n -k1
} >> "${OUT}/topology.tsv" 2>&1

CPUS="$(ls -d /sys/devices/system/cpu/cpu[0-9]* | sed 's/.*cpu//' | sort -n)"
NCPU="$(echo "${CPUS}" | wc -l)"
log "${NCPU} threads"

# --- 2. The energy unit -----------------------------------------------------
# Every counter below is in units of 1/2^ESU joules. Without this number the
# samples are only a ratio.
log "read the energy unit"
header "${OUT}/energy-unit.txt" "rdmsr -p 0 ${MSR_UNIT}, on every thread"
{
    echo "bits 12:8 of ${MSR_UNIT} hold ESU. One count = 1/2^ESU joules."
    echo
    printf 'cpu\traw_hex\tesu\tjoules_per_count\n'
    for cpu in ${CPUS}; do
        raw="$(rdmsr -p "${cpu}" "${MSR_UNIT}" 2>&1)"
        if [[ "${raw}" =~ ^[0-9a-fA-F]+$ ]]; then
            esu=$(( (16#${raw} >> 8) & 0x1f ))
            per_count="$(awk -v e="${esu}" 'BEGIN{printf "%.10f", 1/(2^e)}')"
        else
            esu="read failed"
            per_count="-"
        fi
        printf '%s\t%s\t%s\t%s\n' "${cpu}" "${raw}" "${esu}" "${per_count}"
    done
} >> "${OUT}/energy-unit.txt" 2>&1

# --- the sampler ------------------------------------------------------------
# One row for each thread for each sample: phase, sample number, the monotonic
# clock, the thread, the core counter and the package counter.
SAMPLES="${OUT}/samples.tsv"
header "${SAMPLES}" "rdmsr ${MSR_CORE} on every thread and ${MSR_PKG} on cpu0, in three phases"
printf 'phase\tsample\tmonotonic_s\tcpu\tcore_energy_hex\tpkg_energy_hex\n' >> "${SAMPLES}"

sample_round() {
    # sample_round <phase> <count> <gap_seconds>
    local phase="$1" count="$2" gap="$3" i cpu now pkg
    for i in $(seq 1 "${count}"); do
        now="$(awk '{print $1}' /proc/uptime)"
        pkg="$(rdmsr -p 0 "${MSR_PKG}" 2>/dev/null)"
        for cpu in ${CPUS}; do
            printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
                "${phase}" "${i}" "${now}" "${cpu}" \
                "$(rdmsr -p "${cpu}" "${MSR_CORE}" 2>/dev/null)" "${pkg}" >> "${SAMPLES}"
        done
        sleep "${gap}"
    done
}

# A busy loop with no dependency. `taskset` pins it to one thread.
BURN_PIDS=()
burn_start() {
    # burn_start <cpu list, comma separated or "all">
    local target="$1" cpu
    if [ "${target}" = "all" ]; then
        for cpu in ${CPUS}; do
            taskset -c "${cpu}" sh -c 'while :; do :; done' &
            BURN_PIDS+=("$!")
        done
    else
        taskset -c "${target}" sh -c 'while :; do :; done' &
        BURN_PIDS+=("$!")
    fi
}
burn_stop() {
    local pid
    for pid in "${BURN_PIDS[@]:-}"; do
        [ -n "${pid}" ] && kill "${pid}" 2> /dev/null
    done
    BURN_PIDS=()
    wait 2> /dev/null
}
trap burn_stop EXIT

# --- 3. Phase A: idle -------------------------------------------------------
log "phase A — idle, 6 samples, 1 s apart"
sample_round idle 6 1

# --- 4. Phase B: one core busy ----------------------------------------------
# The discriminator. If only one counter jumps, the MSR is truly per core.
# Thread 6 is chosen because it is not thread 0, and on a 2-CCD part it is
# clear of the thread the sampler itself runs on.
BUSY_CPU=6
log "phase B — thread ${BUSY_CPU} busy, 6 samples, 1 s apart"
burn_start "${BUSY_CPU}"
sleep 2
sample_round "load_cpu${BUSY_CPU}" 6 1
burn_stop
sleep 3

# --- 5. Phase C: every core busy --------------------------------------------
log "phase C — every thread busy, 6 samples, 1 s apart"
burn_start all
sleep 2
sample_round load_all 6 1
burn_stop
sleep 3

# --- 6. turbostat, the second opinion ---------------------------------------
# turbostat reads the same MSRs through its own code. If this capture and
# turbostat disagree, this capture is wrong.
if command -v turbostat > /dev/null 2>&1; then
    log "capture turbostat, idle"
    header "${OUT}/turbostat-idle.txt" "turbostat --quiet --show Core,CPU,Busy%,Avg_MHz,CorWatt,PkgWatt --num_iterations 3 --interval 1"
    turbostat --quiet --show Core,CPU,Busy%,Avg_MHz,CorWatt,PkgWatt \
        --num_iterations 3 --interval 1 >> "${OUT}/turbostat-idle.txt" 2>&1

    log "capture turbostat, every thread busy"
    header "${OUT}/turbostat-load.txt" "the same, with every thread busy"
    burn_start all
    sleep 2
    turbostat --quiet --show Core,CPU,Busy%,Avg_MHz,CorWatt,PkgWatt \
        --num_iterations 3 --interval 1 >> "${OUT}/turbostat-load.txt" 2>&1
    burn_stop
else
    log "turbostat is not installed, skipping the second opinion"
fi

# --- 7. The cost of one read ------------------------------------------------
# ADR 0006 gives every channel its own read interval. That needs a number.
log "time the reads"
header "${OUT}/read-cost.txt" "time one rdmsr, and one sweep of every thread"
{
    echo "--- one rdmsr on cpu0, five times ---"
    for i in 1 2 3 4 5; do
        start="$(date +%s.%N)"
        rdmsr -p 0 "${MSR_CORE}" > /dev/null 2>&1
        end="$(date +%s.%N)"
        echo "read ${i}: $(echo "${end} ${start}" | awk '{printf "%.3f ms", ($1-$2)*1000}')"
    done
    echo
    echo "--- one sweep of all ${NCPU} threads, five times (a new process each read) ---"
    for i in 1 2 3 4 5; do
        start="$(date +%s.%N)"
        for cpu in ${CPUS}; do rdmsr -p "${cpu}" "${MSR_CORE}" > /dev/null 2>&1; done
        end="$(date +%s.%N)"
        echo "sweep ${i}: $(echo "${end} ${start}" | awk '{printf "%.3f ms", ($1-$2)*1000}')"
    done
    echo
    echo "NOTE: rdmsr is a process. The helper will use pread() on /dev/cpu/N/msr,"
    echo "which costs much less. This number is the upper limit, not the target."
} >> "${OUT}/read-cost.txt" 2>&1

# --- 8. The same read without the rdmsr process -----------------------------
# This is how the helper will do it: seek to the MSR number in /dev/cpu/N/msr
# and read 8 bytes. It is the same read, with no process.
log "time the pread() route, which is what the helper will use"
header "${OUT}/pread-cost.txt" "python3: pread 8 bytes at offset ${MSR_CORE} of /dev/cpu/N/msr"
python3 - "${NCPU}" >> "${OUT}/pread-cost.txt" 2>&1 <<'PY'
import os, sys, time

MSR_CORE = 0xC001029A
ncpu = int(sys.argv[1])
fds = {}
for cpu in range(ncpu):
    try:
        fds[cpu] = os.open(f"/dev/cpu/{cpu}/msr", os.O_RDONLY)
    except OSError as error:
        print(f"cpu {cpu}: open failed: {error}")

if not fds:
    print("no /dev/cpu/N/msr could be opened; nothing to time")
    raise SystemExit(0)

def sweep():
    out = {}
    for cpu, fd in fds.items():
        out[cpu] = int.from_bytes(os.pread(fd, 8, MSR_CORE), "little")
    return out

first = sweep()
print(f"threads read: {len(first)}")
print("first values:", {c: hex(v) for c, v in list(first.items())[:4]}, "...")

costs = []
for _ in range(10):
    start = time.perf_counter()
    sweep()
    costs.append((time.perf_counter() - start) * 1000)
print(f"one sweep of {len(fds)} threads: "
      f"min {min(costs):.4f} ms, median {sorted(costs)[len(costs)//2]:.4f} ms, "
      f"max {max(costs):.4f} ms")

time.sleep(1.0)
second = sweep()
climbed = sum(1 for c in first if second[c] != first[c])
print(f"counters that changed in 1 s: {climbed} of {len(first)}")
for fd in fds.values():
    os.close(fd)
PY

# --- 9. Versions ------------------------------------------------------------
log "capture the versions"
header "${OUT}/versions.txt" "uname -r, rdmsr --version, turbostat version"
{
    uname -r
    echo
    rdmsr --version 2>&1 | head -2
    echo
    turbostat --version 2>&1 | head -2
    echo
    python3 --version
} >> "${OUT}/versions.txt" 2>&1

# --- 10. Hand the results back to the caller --------------------------------
if [ "${CALLER}" != "root" ]; then
    chown -R "${CALLER}:${CALLER}" "${OUT}"
fi

log "done. Results in ${OUT}"
ls -l "${OUT}"
