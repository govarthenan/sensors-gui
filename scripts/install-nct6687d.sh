#!/usr/bin/env bash
# install-nct6687d.sh — install the Nuvoton NCT6687D driver through DKMS.
#
#     sudo ./scripts/install-nct6687d.sh
#
# Why this is needed
#   The MSI PRO X870-P WIFI has a Nuvoton Super-I/O chip that holds the fan
#   speeds, the fan control outputs, the VRM and chipset temperatures and the
#   motherboard voltage rails. The mainline kernel has no driver that reads it
#   correctly on this board.
#
# Why it works although Secure Boot is on
#   The kernel is in integrity lockdown and `sig_enforce=Y`, so an unsigned
#   module cannot load. This machine already has a Machine Owner Key enrolled
#   and DKMS signs every module it builds with it. That is how the NVIDIA
#   module loads. The same applies here. No BIOS change is needed.
#
# Reversal
#   sudo ./scripts/uninstall-nct6687d.sh

set -uo pipefail

REPO_URL="https://github.com/Fred78290/nct6687d"
PACKAGE_NAME="nct6687d"
PACKAGE_VERSION="1"
SRC_DIR="/usr/src/${PACKAGE_NAME}-${PACKAGE_VERSION}"
MODULE="nct6687"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${PROJECT_ROOT}/data/probes/nct6687d-install-${STAMP}"
CALLER="${SUDO_USER:-root}"

log()  { echo "[nct6687d] $*"; }
fail() { echo "[nct6687d] ERROR: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "run this with sudo"
mkdir -p "${OUT}"

# --- 1. Checks before any change ---------------------------------------------
log "--- checks ---"

BOARD="$(cat /sys/devices/virtual/dmi/id/board_name 2>/dev/null)"
log "board: ${BOARD}"
case "${BOARD}" in
    MS-7E47) log "  the driver lists this board (PRO X870-P WIFI / MS-7E47)" ;;
    *)       log "  WARNING: this board is not the one the project recorded" ;;
esac

for tool in dkms git make gcc; do
    command -v "${tool}" >/dev/null 2>&1 || fail "${tool} is missing. Run: apt install dkms git build-essential"
done

[ -d "/lib/modules/$(uname -r)/build" ] || fail "kernel headers are missing. Run: apt install linux-headers-$(uname -r)"

if [ "$(cat /sys/module/module/parameters/sig_enforce 2>/dev/null)" = "Y" ]; then
    [ -f /var/lib/shim-signed/mok/MOK.priv ] || fail \
        "module signatures are enforced but /var/lib/shim-signed/mok/MOK.priv is missing. DKMS cannot sign."
    log "  signature enforcement is on, and the DKMS signing key is present"
fi

# --- 2. Get the source -------------------------------------------------------
log "--- source ---"
if [ -d "${SRC_DIR}/.git" ]; then
    log "updating ${SRC_DIR}"
    git -C "${SRC_DIR}" fetch --depth 1 origin main -q && git -C "${SRC_DIR}" reset --hard origin/main -q
else
    rm -rf "${SRC_DIR}"
    log "cloning into ${SRC_DIR}"
    git clone -q --depth 1 "${REPO_URL}" "${SRC_DIR}" || fail "clone failed"
fi
git -C "${SRC_DIR}" log -1 --format='%h %ad %s' --date=short | tee "${OUT}/source-commit.txt"

# --- 3. Build and install through DKMS ---------------------------------------
log "--- dkms ---"
dkms remove -m "${PACKAGE_NAME}" -v "${PACKAGE_VERSION}" --all >/dev/null 2>&1 || true
dkms add -m "${PACKAGE_NAME}" -v "${PACKAGE_VERSION}" 2>&1 | tee "${OUT}/dkms-add.txt"
dkms build -m "${PACKAGE_NAME}" -v "${PACKAGE_VERSION}" 2>&1 | tee "${OUT}/dkms-build.txt" \
    || fail "build failed. See ${OUT}/dkms-build.txt"
dkms install -m "${PACKAGE_NAME}" -v "${PACKAGE_VERSION}" 2>&1 | tee "${OUT}/dkms-install.txt" \
    || fail "install failed. See ${OUT}/dkms-install.txt"

log "signature of the built module:"
modinfo "${MODULE}" 2>/dev/null | grep -E "^(filename|sig_id|signer|sig_key)" | tee "${OUT}/modinfo.txt"

# --- 4. Keep the in-tree driver out of the way -------------------------------
# nct6683 is the mainline driver for the same chip family. It binds first and
# reports wrong values on MSI boards.
if [ ! -f /etc/modprobe.d/nct6683-blacklist.conf ]; then
    echo "blacklist nct6683" > /etc/modprobe.d/nct6683-blacklist.conf
    log "wrote /etc/modprobe.d/nct6683-blacklist.conf"
fi
modprobe -r nct6683 2>/dev/null || true

# --- 5. Load it --------------------------------------------------------------
log "--- load ---"
modprobe -r "${MODULE}" 2>/dev/null || true
if modprobe "${MODULE}" 2>"${OUT}/modprobe-error.txt"; then
    log "module loaded"
else
    log "plain load failed; trying force=1"
    if modprobe "${MODULE}" force=1 2>>"${OUT}/modprobe-error.txt"; then
        log "module loaded with force=1"
        echo "options ${MODULE} force=1" > /etc/modprobe.d/nct6687-force.conf
    else
        cat "${OUT}/modprobe-error.txt" >&2
        dmesg 2>/dev/null | tail -20 | tee "${OUT}/dmesg-tail.txt"
        if dmesg 2>/dev/null | tail -40 | grep -qi "Resource conflict"; then
            log ""
            log "ACPI holds the I/O region. Add this kernel parameter and reboot:"
            log "    acpi_enforce_resources=lax"
            log "Edit GRUB_CMDLINE_LINUX_DEFAULT in /etc/default/grub, then run update-grub."
        fi
        fail "the module did not load. See ${OUT}/"
    fi
fi

echo "${MODULE}" > /etc/modules-load.d/nct6687.conf
log "wrote /etc/modules-load.d/nct6687.conf so it loads at boot"

# --- 6. Show what appeared ---------------------------------------------------
log "--- result ---"
sensors -A 2>&1 | tee "${OUT}/sensors-after.txt" | sed -n "/${MODULE}/,/^$/p"
{
    echo "# hwmon devices after the install"
    for d in /sys/class/hwmon/hwmon*; do
        echo "$(basename "$d") = $(cat "$d/name" 2>/dev/null)"
    done
} | tee "${OUT}/hwmon-after.txt"

dmesg 2>/dev/null | grep -i "${MODULE}" | tail -10 > "${OUT}/dmesg-nct6687.txt" || true
chown -R "${CALLER}:${CALLER}" "${OUT}" 2>/dev/null || true

log "done. Results: ${OUT}"
