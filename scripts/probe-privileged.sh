#!/usr/bin/env bash
# probe-privileged.sh — capture the two root-only sensor sources of phase 2.
#
# Run it like this, from the project root:
#
#     sudo ./scripts/probe-privileged.sh
#
# THIS SCRIPT ONLY READS. It opens no device for writing, it loads no module
# and it changes no file outside data/probes/. See ADR 0007.
#
# It captures what the privileged helper of ADR 0005 must parse:
#   1. the RAPL energy counters, sampled several times, so the reader can be
#      built against real numbers and a real sample interval;
#   2. the NVMe SMART/health log in JSON, so the field names come from this
#      machine and not from a guess.
#
# Results go to data/probes/privileged-<timestamp>/.

set -uo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This script needs root. Run: sudo $0" >&2
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${PROJECT_ROOT}/data/probes/privileged-${STAMP}"
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

log() { echo "[probe-privileged] $*"; }

header() {
    # header <file> <command text>
    {
        echo "# captured $(date -u +%Y-%m-%dT%H:%M:%SZ) on $(hostname)"
        echo "# command: $2"
        echo "# source:  this machine, dst-gova-pc"
        echo
    } > "$1"
}

log "output directory: ${OUT}"

# --- 1. RAPL: the powercap tree --------------------------------------------
log "capture the powercap tree"
header "${OUT}/rapl-tree.txt" "ls -l and cat of every /sys/class/powercap domain"
{
    ls -l /sys/class/powercap/
    echo
    for d in /sys/class/powercap/*/; do
        [ -f "${d}name" ] || continue
        echo "--- ${d}"
        echo "  name                = $(cat "${d}name" 2>&1)"
        echo "  max_energy_range_uj = $(cat "${d}max_energy_range_uj" 2>&1)"
        echo "  enabled             = $(cat "${d}enabled" 2>&1)"
        echo "  mode of energy_uj   = $(stat -c '%A %U:%G' "${d}energy_uj" 2>&1)"
    done
} >> "${OUT}/rapl-tree.txt" 2>&1

# --- 2. RAPL: ten samples, one second apart ---------------------------------
# The helper turns a counter in microjoules into watts. It needs two things
# from this capture: that the counter really does climb, and how far it climbs
# in a known time. The output is machine-readable so a test can use it.
log "capture 10 RAPL samples, 1 second apart (takes 10 seconds)"
header "${OUT}/rapl-samples.tsv" "read energy_uj of every domain once a second, 10 times"
{
    printf 'sample\tmonotonic_s\tdomain\tname\tenergy_uj\n'
    for i in $(seq 1 10); do
        now="$(awk '{print $1}' /proc/uptime)"
        for d in /sys/class/powercap/intel-rapl:*/; do
            [ -f "${d}energy_uj" ] || continue
            printf '%s\t%s\t%s\t%s\t%s\n' \
                "${i}" "${now}" "$(basename "${d}")" \
                "$(cat "${d}name" 2>/dev/null)" "$(cat "${d}energy_uj" 2>/dev/null)"
        done
        sleep 1
    done
} >> "${OUT}/rapl-samples.tsv" 2>&1

# --- 3. turbostat, for a second opinion on package power --------------------
# exp-0003 found that the powercap `core` domain is core 0 only, not the sum of
# the cores. turbostat reads the per-core MSRs, so it is the check.
if command -v turbostat > /dev/null 2>&1; then
    log "capture turbostat"
    header "${OUT}/turbostat.txt" "turbostat --quiet --show PkgWatt,CorWatt,Busy%,Avg_MHz --num_iterations 3 --interval 1"
    turbostat --quiet --show PkgWatt,CorWatt,Busy%,Avg_MHz --num_iterations 3 --interval 1 \
        >> "${OUT}/turbostat.txt" 2>&1
else
    log "turbostat is not installed, skipping"
fi

# --- 4. NVMe: the SMART log, in JSON and as text ----------------------------
for dev in /dev/nvme[0-9]; do
    [ -c "${dev}" ] || continue
    name="$(basename "${dev}")"

    log "capture the SMART log of ${dev}"
    header "${OUT}/${name}-smart-log.json.txt" "nvme smart-log -o json ${dev}"
    nvme smart-log -o json "${dev}" >> "${OUT}/${name}-smart-log.json.txt" 2>&1
    # A second copy with no header, so a test can load it as plain JSON.
    nvme smart-log -o json "${dev}" > "${OUT}/${name}-smart-log.json" 2>/dev/null

    header "${OUT}/${name}-smart-log.txt" "nvme smart-log ${dev}"
    nvme smart-log "${dev}" >> "${OUT}/${name}-smart-log.txt" 2>&1

    header "${OUT}/${name}-id-ctrl.txt" "nvme id-ctrl ${dev}"
    nvme id-ctrl "${dev}" >> "${OUT}/${name}-id-ctrl.txt" 2>&1

    header "${OUT}/${name}-smartctl.txt" "smartctl -a ${dev}"
    smartctl -a "${dev}" >> "${OUT}/${name}-smartctl.txt" 2>&1
done

# --- 5. The cost of one SMART read ------------------------------------------
# ADR 0006 gives every channel its own read interval. That needs a number.
log "time five SMART reads"
header "${OUT}/smart-read-cost.txt" "time nvme smart-log -o json /dev/nvme0, five times"
{
    for i in 1 2 3 4 5; do
        start="$(date +%s.%N)"
        nvme smart-log -o json /dev/nvme0 > /dev/null 2>&1
        end="$(date +%s.%N)"
        echo "read ${i}: $(echo "${end} ${start}" | awk '{printf "%.1f ms", ($1-$2)*1000}')"
    done
} >> "${OUT}/smart-read-cost.txt" 2>&1

# --- 6. Version facts, so the parsing can be tied to a version --------------
log "capture tool versions"
header "${OUT}/versions.txt" "nvme version, smartctl version, uname -r"
{
    nvme version
    echo
    smartctl --version | head -2
    echo
    uname -r
    echo
    python3 --version
} >> "${OUT}/versions.txt" 2>&1

# --- 7. Hand the results back to the caller ---------------------------------
if [ "${CALLER}" != "root" ]; then
    chown -R "${CALLER}:${CALLER}" "${OUT}"
fi

log "done. Results in ${OUT}"
ls -l "${OUT}"
