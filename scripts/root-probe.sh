#!/usr/bin/env bash
# root-probe.sh — collect every sensor fact that needs root, in one run.
#
# Run it like this, from the project root:
#
#     sudo ./scripts/root-probe.sh
#
# The script only reads, with one exception: `sensors-detect --auto` can add
# lines to /etc/modules. The script makes a backup of that file first and shows
# the difference at the end, so the change is visible and reversible.
#
# Results go to data/probes/root-probe-<timestamp>/.

set -uo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This script needs root. Run: sudo $0" >&2
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${PROJECT_ROOT}/data/probes/root-probe-${STAMP}"
mkdir -p "${OUT}"

# Let the user who called sudo own the results.
# `sudo` sets SUDO_USER; `pkexec`, which the `run-as-root` skill uses, sets
# PKEXEC_UID instead. Without the second one the results are left owned by root
# inside the user's repository, where the user cannot change or delete them.
# That really happened: a root-owned probe directory from this script blocked a
# git history rewrite on 2026-09-22 and needed a separate root command to undo.
if [ -n "${SUDO_USER:-}" ]; then
    CALLER="${SUDO_USER}"
elif [ -n "${PKEXEC_UID:-}" ]; then
    CALLER="$(id -nu "${PKEXEC_UID}" 2>/dev/null || echo root)"
else
    CALLER="root"
fi

log() { echo "[root-probe] $*"; }

capture() {
    # capture <name> <command...>
    local name="$1"; shift
    log "capture ${name}"
    { echo "\$ $*"; echo; "$@"; } > "${OUT}/${name}.txt" 2>&1
}

log "output directory: ${OUT}"

# --- 1. DMI: memory modules, board, CPU -------------------------------------
capture dmidecode-memory     dmidecode -t memory
capture dmidecode-baseboard  dmidecode -t baseboard
capture dmidecode-processor  dmidecode -t processor
capture dmidecode-chassis    dmidecode -t chassis

# --- 2. RAPL: CPU energy counters -------------------------------------------
log "capture rapl"
{
    echo "# powercap domains"
    for d in /sys/class/powercap/*/; do
        [ -f "${d}name" ] || continue
        echo "--- ${d}"
        echo "  name                 = $(cat "${d}name" 2>&1)"
        echo "  energy_uj            = $(cat "${d}energy_uj" 2>&1)"
        echo "  max_energy_range_uj  = $(cat "${d}max_energy_range_uj" 2>&1)"
        echo "  enabled              = $(cat "${d}enabled" 2>&1)"
    done
    echo
    echo "# two reads one second apart, to show the power in watts"
    for d in /sys/class/powercap/intel-rapl:0 /sys/class/powercap/intel-rapl:0:0; do
        [ -f "${d}/energy_uj" ] || continue
        a=$(cat "${d}/energy_uj"); sleep 1; b=$(cat "${d}/energy_uj")
        echo "  $(cat "${d}/name"): $(( (b - a) / 1000 )) mW over 1 s  (raw ${a} -> ${b})"
    done
} > "${OUT}/rapl.txt" 2>&1

# --- 3. turbostat: per-core frequency, C-states, package power ---------------
capture turbostat  turbostat --quiet --show Core,CPU,Busy%,Bzy_MHz,TSC_MHz,PkgWatt,CorWatt,PkgTmp --num_iterations 2 --interval 1

# --- 4. NVMe: SMART and identify --------------------------------------------
if command -v nvme >/dev/null 2>&1; then
    capture nvme-list          nvme list
    capture nvme-smart-log     nvme smart-log /dev/nvme0
    capture nvme-id-ctrl       nvme id-ctrl /dev/nvme0
    capture nvme-error-log     nvme error-log /dev/nvme0
else
    echo "nvme-cli is not installed. Run: sudo apt install nvme-cli" > "${OUT}/nvme-list.txt"
fi

if command -v smartctl >/dev/null 2>&1; then
    capture smartctl-nvme  smartctl -a /dev/nvme0
else
    echo "smartmontools is not installed. Run: sudo apt install smartmontools" > "${OUT}/smartctl-nvme.txt"
fi

# --- 5. I/O ports and Super-I/O ---------------------------------------------
capture ioports   cat /proc/ioports
capture iomem     cat /proc/iomem
capture modules   cat /etc/modules

# --- 6. sensors-detect: find the Super-I/O chip ------------------------------
# This is the one step that can change a file. Back /etc/modules up first.
if [ -f /etc/modules ]; then
    cp -a /etc/modules "${OUT}/etc-modules.before"
fi
log "run sensors-detect --auto (this can add lines to /etc/modules)"
sensors-detect --auto > "${OUT}/sensors-detect.txt" 2>&1
if [ -f /etc/modules ]; then
    cp -a /etc/modules "${OUT}/etc-modules.after"
    if ! diff -u "${OUT}/etc-modules.before" "${OUT}/etc-modules.after" > "${OUT}/etc-modules.diff"; then
        log "NOTE: sensors-detect changed /etc/modules. See etc-modules.diff"
    else
        log "/etc/modules is unchanged"
    fi
fi

# --- 7. hwmon after the probe ------------------------------------------------
capture sensors-after  sensors -A -u

chown -R "${CALLER}:${CALLER}" "${OUT}" 2>/dev/null || true

log "done"
log "results: ${OUT}"
ls -1 "${OUT}"
