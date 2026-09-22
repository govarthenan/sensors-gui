#!/usr/bin/env bash
# restore-fans.sh — put every fan header back under the board's own control.
#
#     sudo ./scripts/restore-fans.sh
#
# Run this whenever a fan control test has left a header in manual mode, or
# whenever a fan reads 0 RPM and should not. It is safe to run at any time.

set -uo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run: sudo $0" >&2; exit 1; }

BOARD="$(dirname "$(grep -lx nct6687 /sys/class/hwmon/hwmon*/name 2>/dev/null | head -1)")"
[ -d "${BOARD}" ] || { echo "the nct6687 driver is not loaded" >&2; exit 1; }

echo "[restore] setting every fan header to automatic control"
for index in 1 2 3 4 5 6 7 8; do
    echo 2 > "${BOARD}/pwm${index}_enable" 2>/dev/null
done

sleep 3
echo "[restore] state now:"
for index in 1 2 3 4 5 6 7 8; do
    printf "  %-16s %6s RPM   pwm=%-4s enable=%s\n" \
        "$(cat "${BOARD}/fan${index}_label" 2>/dev/null || echo "fan${index}")" \
        "$(cat "${BOARD}/fan${index}_input" 2>/dev/null)" \
        "$(cat "${BOARD}/pwm${index}" 2>/dev/null)" \
        "$(cat "${BOARD}/pwm${index}_enable" 2>/dev/null)"
done

CPU_HWMON="$(dirname "$(grep -lx k10temp /sys/class/hwmon/hwmon*/name 2>/dev/null | head -1)")"
echo "[restore] Tctl $(( $(cat "${CPU_HWMON}/temp1_input") / 1000 )) C"

if [ "$(cat "${BOARD}/fan1_input" 2>/dev/null)" = "0" ]; then
    cat <<'WARN'

!!! The CPU fan header still reads 0 RPM.
!!! Try reloading the driver:
!!!     sudo modprobe -r nct6687 && sudo modprobe nct6687
!!! If that does not work, REBOOT. The BIOS will take the fans back.
WARN
    exit 1
fi
echo "[restore] the fans are turning again."
