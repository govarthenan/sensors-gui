#!/usr/bin/env bash
# uninstall-helper.sh — remove `sensors-guid` completely.
#
# Run it like this, from the project root:
#
#     sudo ./scripts/uninstall-helper.sh
#
# It stops the service, disables it, and removes the unit, the installed helper
# and the socket. It touches nothing else, and it writes nothing to hardware.
#
# The screen keeps working without the helper. The root-only channels then show
# "needs the helper" instead of a number, which is ADR 0005 rule 3.

set -uo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This script needs root. Run: sudo $0" >&2
    exit 1
fi

INSTALL_DIR="/usr/local/lib/sensors-gui"
UNIT_PATH="/etc/systemd/system/sensors-guid.service"
SOCKET_PATH="/run/sensors-gui.sock"
SERVICE="sensors-guid.service"

log() { echo "[uninstall-helper] $*"; }

if systemctl list-unit-files "${SERVICE}" > /dev/null 2>&1; then
    log "stop and disable ${SERVICE}"
    systemctl stop "${SERVICE}" > /dev/null 2>&1
    systemctl disable "${SERVICE}" > /dev/null 2>&1
fi

if [ -f "${UNIT_PATH}" ]; then
    log "remove ${UNIT_PATH}"
    rm -f "${UNIT_PATH}"
fi

if [ -d "${INSTALL_DIR}" ]; then
    log "remove ${INSTALL_DIR}"
    rm -f "${INSTALL_DIR}/sensors_guid.py" "${INSTALL_DIR}/sensors_guid.py.sha256"
    rm -rf "${INSTALL_DIR}/__pycache__"
    rmdir --ignore-fail-on-non-empty "${INSTALL_DIR}"
fi

# Only a socket is removed, never an ordinary file.
if [ -S "${SOCKET_PATH}" ]; then
    log "remove ${SOCKET_PATH}"
    rm -f "${SOCKET_PATH}"
fi

systemctl daemon-reload
log "done. The screen will now show the root-only channels as 'needs the helper'."
