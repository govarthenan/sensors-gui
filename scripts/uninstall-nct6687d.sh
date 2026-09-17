#!/usr/bin/env bash
# uninstall-nct6687d.sh — undo install-nct6687d.sh completely.
#
#     sudo ./scripts/uninstall-nct6687d.sh

set -uo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run this with sudo" >&2; exit 1; }

echo "[nct6687d] unloading the module"
modprobe -r nct6687 2>/dev/null || true

echo "[nct6687d] removing the DKMS package"
dkms remove -m nct6687d -v 1 --all 2>/dev/null || true
rm -rf /usr/src/nct6687d-1

echo "[nct6687d] removing the configuration files"
rm -f /etc/modprobe.d/nct6683-blacklist.conf \
      /etc/modprobe.d/nct6687-force.conf \
      /etc/modules-load.d/nct6687.conf

echo "[nct6687d] done. The machine is back to its state before the install."
