#!/usr/bin/env bash
# install-helper.sh — install `sensors-guid`, the privileged read-only helper.
#
# Run it like this, from the project root:
#
#     sudo ./scripts/install-helper.sh
#
# It is re-runnable. Running it again copies the current helper over the
# installed one and restarts the service, which is what to do after the
# repository changes.
#
# What it does:
#   1. copies src/sensors_gui/helper/sensors_guid.py to
#      /usr/local/lib/sensors-gui/, so that root never runs code from a
#      directory the user can write (ADR 0009);
#   2. installs /etc/systemd/system/sensors-guid.service;
#   3. enables and starts the service;
#   4. CHECKS IT. The socket must exist with the right mode and group, the
#      helper must answer, and it must give real numbers. A restore that is
#      not verified is the first of the four faults that caused the thermal
#      shutdown of 2026-09-22.
#
# It writes nothing to hardware.

set -uo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This script needs root. Run: sudo $0" >&2
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_HELPER="${PROJECT_ROOT}/src/sensors_gui/helper/sensors_guid.py"
SOURCE_UNIT="${PROJECT_ROOT}/scripts/sensors-guid.service"

INSTALL_DIR="/usr/local/lib/sensors-gui"
INSTALLED_HELPER="${INSTALL_DIR}/sensors_guid.py"
UNIT_PATH="/etc/systemd/system/sensors-guid.service"
SOCKET_PATH="/run/sensors-gui.sock"
SERVICE="sensors-guid.service"

# The group that may read the socket. It must match the unit file.
SOCKET_GROUP="gova"

log()  { echo "[install-helper] $*"; }
fail() { echo "[install-helper] FAILED: $*" >&2; exit 1; }

[ -f "${SOURCE_HELPER}" ] || fail "cannot find ${SOURCE_HELPER}"
[ -f "${SOURCE_UNIT}" ]   || fail "cannot find ${SOURCE_UNIT}"
getent group "${SOCKET_GROUP}" > /dev/null || fail "there is no group ${SOCKET_GROUP}"

# --- 1. the helper ----------------------------------------------------------
log "copy the helper to ${INSTALLED_HELPER}"
install -d -o root -g root -m 0755 "${INSTALL_DIR}"
install -o root -g root -m 0644 "${SOURCE_HELPER}" "${INSTALLED_HELPER}"

# A record of which copy this is, so a drift between the repository and the
# installed file can be seen without guessing.
sha256sum "${SOURCE_HELPER}" | awk '{print $1}' > "${INSTALL_DIR}/sensors_guid.py.sha256"
chmod 0644 "${INSTALL_DIR}/sensors_guid.py.sha256"

# A syntax check that writes nothing. `python3 -m py_compile` would leave a
# root-owned __pycache__ beside the helper, and the service cannot use it
# anyway: ProtectSystem=strict makes that directory read-only for it.
log "check that the helper compiles under the system Python"
/usr/bin/python3 -c "import pathlib, sys; compile(pathlib.Path(sys.argv[1]).read_text(), sys.argv[1], 'exec')" \
    "${INSTALLED_HELPER}" || fail "the helper does not compile"
rm -rf "${INSTALL_DIR}/__pycache__"

# --- 2. the unit ------------------------------------------------------------
log "install ${UNIT_PATH}"
install -o root -g root -m 0644 "${SOURCE_UNIT}" "${UNIT_PATH}"

# --- 3. start it ------------------------------------------------------------
log "reload systemd and start ${SERVICE}"
systemctl daemon-reload || fail "systemctl daemon-reload failed"
systemctl enable "${SERVICE}" > /dev/null 2>&1 || fail "systemctl enable failed"
systemctl restart "${SERVICE}" || fail "systemctl restart failed"

# Give it a moment to bind the socket and take its first two energy samples.
sleep 3

# --- 4. check it ------------------------------------------------------------
log "check the service"
systemctl is-active --quiet "${SERVICE}" || {
    systemctl status "${SERVICE}" --no-pager --lines 30
    fail "the service is not active"
}

[ -S "${SOCKET_PATH}" ] || fail "there is no socket at ${SOCKET_PATH}"

MODE_AND_OWNER="$(stat -c '%a %U:%G' "${SOCKET_PATH}")"
log "socket: ${SOCKET_PATH} ${MODE_AND_OWNER}"
[ "${MODE_AND_OWNER}" = "660 root:${SOCKET_GROUP}" ] \
    || fail "the socket should be 660 root:${SOCKET_GROUP}, it is ${MODE_AND_OWNER}"

log "ask the helper for its readings"
/usr/bin/python3 - "${SOCKET_PATH}" <<'PYTHON' || fail "the helper did not answer correctly"
import json
import socket
import sys

path = sys.argv[1]
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
    client.settimeout(5.0)
    client.connect(path)
    stream = client.makefile("rwb")
    stream.write(b'{"protocol": 1, "command": "describe"}\n')
    stream.flush()
    described = json.loads(stream.readline())
    stream.write(b'{"protocol": 1, "command": "read"}\n')
    stream.flush()
    answer = json.loads(stream.readline())

if not described.get("ok") or not answer.get("ok"):
    print("the helper refused the request", file=sys.stderr)
    raise SystemExit(1)

labels = {(c["device"], c["channel"]): (c["label"], c["unit"]) for c in described["channels"]}
good = 0
for reading in answer["readings"]:
    label, unit = labels.get((reading["device"], reading["channel"]), (reading["channel"], ""))
    if reading["value"] is None:
        print(f"  {label:24} --        {reading['error']}")
    else:
        good += 1
        print(f"  {label:24} {reading['value']:>16.3f} {unit}")

print(f"\n{good} of {len(answer['readings'])} channels gave a value.")
if good == 0:
    print("no channel gave a value; the helper is running but blind", file=sys.stderr)
    raise SystemExit(1)
PYTHON

log "done. The service is enabled and will start at every boot."
log "stop it with:      sudo systemctl stop ${SERVICE}"
log "remove it with:    sudo ./scripts/uninstall-helper.sh"
