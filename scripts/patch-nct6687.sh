#!/usr/bin/env bash
# patch-nct6687.sh — apply the MS-7E47 read-only driver patch, rebuild it
# through DKMS, reload the module, and print a before/after comparison.
#
#     sudo ./scripts/patch-nct6687.sh
#
# What this changes
#   driver/nct6687-ms7e47.patch, applied to /usr/src/nct6687d-1/nct6687.c. It
#   adds a ninth fan channel ("EZ Conn Fan") and corrects/relabels several of
#   the fourteen voltage channels for the MSI PRO X870-P WIFI (MS-7E47). See
#   driver/README.md for the evidence behind every mapping, including which
#   voltage overrides are unverified guesses that need checking against the
#   BIOS after this script finishes.
#
# What this never does
#   It never opens a pwm* file, for reading or writing, and never touches
#   pwm_enable. It only reads fan*/in* sensor files, applies a source patch,
#   rebuilds, and reloads. See docs/decisions/0007-rules-for-writing-to-hardware.md.
#
# Reversal
#   sudo ./scripts/uninstall-nct6687d.sh
#   sudo ./scripts/install-nct6687d.sh
#   A timestamped backup of the pre-patch nct6687.c is also kept next to the
#   pinned source; this script prints its path at the end.

set -uo pipefail

PACKAGE_NAME="nct6687d"
PACKAGE_VERSION="1"
SRC_DIR="/usr/src/${PACKAGE_NAME}-${PACKAGE_VERSION}"
MODULE="nct6687"
PINNED_COMMIT="5f12dd1"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATCH_FILE="${PROJECT_ROOT}/driver/nct6687-ms7e47.patch"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${PROJECT_ROOT}/data/probes/nct6687-patch-${STAMP}"
CALLER="${SUDO_USER:-root}"

log()  { echo "[patch-nct6687] $*"; }
fail() { echo "[patch-nct6687] ERROR: $*" >&2; exit 1; }

# --- 0. Preconditions ---------------------------------------------------------
[ "$(id -u)" -eq 0 ] || fail "run this with sudo"
[ -f "${PATCH_FILE}" ] || fail "patch file not found: ${PATCH_FILE}"
[ -d "${SRC_DIR}" ] || fail "${SRC_DIR} does not exist. Run scripts/install-nct6687d.sh first."
[ -f "${SRC_DIR}/nct6687.c" ] || fail "${SRC_DIR}/nct6687.c does not exist."

for tool in patch dkms modprobe; do
    command -v "${tool}" >/dev/null 2>&1 || fail "${tool} is missing."
done

mkdir -p "${OUT}"

if [ -d "${SRC_DIR}/.git" ]; then
    SRC_COMMIT="$(git -C "${SRC_DIR}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
    log "source at ${SRC_DIR} is at commit ${SRC_COMMIT} (patch was built against ${PINNED_COMMIT})"
    if [ "${SRC_COMMIT}" != "${PINNED_COMMIT}" ]; then
        log "  WARNING: commit differs from the pinned one. The dry-run check below is what actually decides"
        log "  whether the patch is safe to apply -- this is only a heads-up, not a hard stop."
    fi
fi

# --- helpers to read sensors without ever opening pwm* -----------------------
find_hwmon() {
    local d
    for d in /sys/class/hwmon/hwmon*; do
        [ -r "${d}/name" ] || continue
        if [ "$(cat "${d}/name" 2>/dev/null)" = "${MODULE}" ]; then
            echo "${d}"
            return 0
        fi
    done
    return 1
}

# Prints one line per fanN_input / inN_input under a hwmon dir, in numeric
# channel order (plain glob order is lexical: in10 would sort before in2).
# Only ever globs fan*_input / fan*_label / in*_input / in*_label -- never
# pwm*.
snapshot() {
    local hwmon="$1" f chan label value
    if [ -z "${hwmon}" ]; then
        echo "  (module not loaded -- no snapshot)"
        return
    fi
    for f in $(printf '%s\n' "${hwmon}"/fan*_input | sort -V); do
        [ -e "${f}" ] || continue
        chan="${f#"${hwmon}"/fan}"
        chan="${chan%_input}"
        label="$(cat "${hwmon}/fan${chan}_label" 2>/dev/null)"
        value="$(cat "${f}" 2>/dev/null)"
        printf '  fan%-3s %-18s %s RPM\n' "${chan}" "${label:-(no label)}" "${value:-?}"
    done
    for f in $(printf '%s\n' "${hwmon}"/in*_input | sort -V); do
        [ -e "${f}" ] || continue
        chan="${f#"${hwmon}"/in}"
        chan="${chan%_input}"
        label="$(cat "${hwmon}/in${chan}_label" 2>/dev/null)"
        value="$(cat "${f}" 2>/dev/null)"
        printf '  in%-4s %-18s %s\n' "${chan}" "${label:-(no label)}" \
            "$(awk -v v="${value:-0}" 'BEGIN { printf "%.3f V", v / 1000 }')"
    done
}

# --- 1. Snapshot BEFORE -------------------------------------------------------
log "--- before ---"
HWMON_BEFORE="$(find_hwmon || true)"
if [ -n "${HWMON_BEFORE}" ]; then
    log "module currently loaded at ${HWMON_BEFORE}"
else
    log "module not currently loaded; before-snapshot will say so"
fi
snapshot "${HWMON_BEFORE}" | tee "${OUT}/before.txt"

# --- 2. Back up the pinned source before touching it --------------------------
log "--- backup ---"
BACKUP="${SRC_DIR}/nct6687.c.orig-${STAMP}"
cp -a "${SRC_DIR}/nct6687.c" "${BACKUP}" || fail "could not back up ${SRC_DIR}/nct6687.c"
cp -a "${SRC_DIR}/nct6687.c" "${OUT}/nct6687.c.orig" 2>/dev/null || true
log "backup: ${BACKUP}"

# --- 3. Verify the patch applies cleanly, then apply it -----------------------
log "--- patch ---"
if ! patch -p1 -d "${SRC_DIR}" --dry-run <"${PATCH_FILE}" >"${OUT}/patch-dry-run.txt" 2>&1; then
    cat "${OUT}/patch-dry-run.txt" >&2
    fail "patch does not apply. See ${OUT}/patch-dry-run.txt. Aborting, nothing changed."
fi
log "dry run OK"

if ! patch -p1 -d "${SRC_DIR}" <"${PATCH_FILE}" >"${OUT}/patch-apply.txt" 2>&1; then
    cat "${OUT}/patch-apply.txt" >&2
    fail "patch failed to apply for real after a clean dry run. Restore from ${BACKUP}."
fi
cat "${OUT}/patch-apply.txt"
log "patch applied"

# --- 4. Rebuild through DKMS --------------------------------------------------
log "--- dkms rebuild ---"
dkms remove -m "${PACKAGE_NAME}" -v "${PACKAGE_VERSION}" --all >/dev/null 2>&1 || true
dkms add -m "${PACKAGE_NAME}" -v "${PACKAGE_VERSION}" 2>&1 | tee "${OUT}/dkms-add.txt"
dkms build -m "${PACKAGE_NAME}" -v "${PACKAGE_VERSION}" 2>&1 | tee "${OUT}/dkms-build.txt"
[ "${PIPESTATUS[0]}" -eq 0 ] || fail "build failed. See ${OUT}/dkms-build.txt. Pre-patch source: ${BACKUP}."
dkms install -m "${PACKAGE_NAME}" -v "${PACKAGE_VERSION}" 2>&1 | tee "${OUT}/dkms-install.txt"
[ "${PIPESTATUS[0]}" -eq 0 ] || fail "install failed. See ${OUT}/dkms-install.txt. Pre-patch source: ${BACKUP}."

# --- 5. Reload -----------------------------------------------------------------
log "--- reload ---"
modprobe -r "${MODULE}" 2>/dev/null || true
if modprobe "${MODULE}" 2>"${OUT}/modprobe-error.txt"; then
    log "module loaded"
elif [ -f /etc/modprobe.d/nct6687-force.conf ] && modprobe "${MODULE}" force=1 2>>"${OUT}/modprobe-error.txt"; then
    log "module loaded with force=1 (matches the existing /etc/modprobe.d/nct6687-force.conf)"
else
    cat "${OUT}/modprobe-error.txt" >&2
    fail "module did not reload. See ${OUT}/. Pre-patch: ${BACKUP}. Revert: uninstall-nct6687d.sh, install-nct6687d.sh."
fi

# --- 6. Snapshot AFTER, and compare --------------------------------------------
log "--- after ---"
# exp-0007 found the EC reports zero until it has updated once; give it a beat.
sleep 2
HWMON_AFTER="$(find_hwmon || true)"
[ -n "${HWMON_AFTER}" ] || fail "no hwmon device after reload. Check dmesg. Pre-patch source: ${BACKUP}."
snapshot "${HWMON_AFTER}" | tee "${OUT}/after.txt"

echo
log "--- before / after diff ---"
diff -u --label before --label after "${OUT}/before.txt" "${OUT}/after.txt" | tee "${OUT}/diff.txt"
log "(diff exit status is informational; a real diff is expected and not an error)"

echo
log "Check these by hand against the BIOS Hardware Monitor page (driver/README.md has the full table):"
log "  fan9 'EZ Conn Fan'   expect ~960-1600 RPM"
log "  in*  'CPU 1P8'       expect ~1.793 V  -- GUESS, may be wrong, see driver/README.md"
log "  in*  'CHIPSET Core'  expect ~1.047 V  -- GUESS, may be wrong, see driver/README.md"
log "  in*  'CPU VDDIO'     expect ~1.368 V  -- rename only, must match the old 'DRAM' value"
log "  in*  'System 3.3V'   expect ~3.288 V  -- rename only, must match the old 'AVCC3' value"
log "  in2, in6, in12 (old '+3.3V'/'CPU VDDP'/'AVSB') should no longer appear at all"
log ""
log "To revert: sudo ./scripts/uninstall-nct6687d.sh, then sudo ./scripts/install-nct6687d.sh"
log "Backup of the pre-patch source: ${BACKUP}"

chown -R "${CALLER}:${CALLER}" "${OUT}" 2>/dev/null || true
log "done. Results: ${OUT}"
