#!/usr/bin/env bash
# map-fans.sh — find out which fan is on which motherboard header.
#
#     sudo ./scripts/map-fans.sh
#
# The problem
#   The board has 8 fan headers. Nine fans are in the case. Only 3 headers
#   return a speed signal, so software alone cannot say which fan is where.
#
# The method
#   Set every header to a low speed. Then raise one header at a time to full
#   speed for 8 seconds, and tell the operator which header it is. The operator
#   watches and listens, and says which fan became loud. That maps a header to
#   a fan without opening the case.
#
# SAFETY
#   - The pump header is NEVER touched. The script finds it by its label and
#     refuses to write to it.
#   - No fan is ever set below 30 percent. A stopped fan is not needed for this
#     test, and a low speed is enough to hear the difference.
#   - The original values are saved first, and restored when the script ends,
#     including when it is interrupted with Ctrl-C or killed.
#   - There is a hard time limit. If the operator walks away, everything goes
#     back to automatic control by itself.
#
# This script WRITES to the fan control outputs. Reading is safe; writing is
# not, so every rule above is enforced in code, not left to the operator.

set -uo pipefail

MIN_PWM=77        # 30 percent of 255. Low, but every fan keeps turning.
MAX_PWM=255       # 100 percent.
SETTLE_SECONDS=4  # time for a fan to reach the low speed
BURST_SECONDS=8   # time the operator has to watch and listen
PUMP_PATTERN='[Pp]ump'

[ "$(id -u)" -eq 0 ] || { echo "This script needs root. Run: sudo $0" >&2; exit 1; }

# --- find the board sensor chip ---------------------------------------------
HWMON=""
for dir in /sys/class/hwmon/hwmon*; do
    [ "$(cat "${dir}/name" 2>/dev/null)" = "nct6687" ] && HWMON="${dir}" && break
done
[ -n "${HWMON}" ] || { echo "The nct6687 driver is not loaded. Run scripts/install-nct6687d.sh first." >&2; exit 1; }
echo "board sensor chip: ${HWMON}"

# --- work out which headers may be touched ----------------------------------
CHANNELS=()
PUMP_CHANNELS=()
for path in "${HWMON}"/pwm[0-9]; do
    [ -w "${path}" ] || continue
    index="${path##*pwm}"
    label="$(cat "${HWMON}/fan${index}_label" 2>/dev/null || echo "fan${index}")"
    if [[ "${label}" =~ ${PUMP_PATTERN} ]]; then
        PUMP_CHANNELS+=("${index}")
        echo "  pwm${index}  ${label}  -- PROTECTED, this script will not write to it"
    else
        CHANNELS+=("${index}")
        echo "  pwm${index}  ${label}"
    fi
done
[ "${#CHANNELS[@]}" -gt 0 ] || { echo "no writable fan headers found" >&2; exit 1; }

# --- save the original state, and promise to restore it ----------------------
declare -A ORIGINAL_PWM ORIGINAL_ENABLE
for index in "${CHANNELS[@]}"; do
    ORIGINAL_PWM["${index}"]="$(cat "${HWMON}/pwm${index}" 2>/dev/null)"
    ORIGINAL_ENABLE["${index}"]="$(cat "${HWMON}/pwm${index}_enable" 2>/dev/null)"
done

restore() {
    echo
    echo "[restore] putting every fan header back to how it was"
    for index in "${CHANNELS[@]}"; do
        [ -n "${ORIGINAL_PWM[${index}]:-}" ] && echo "${ORIGINAL_PWM[${index}]}" > "${HWMON}/pwm${index}" 2>/dev/null
        [ -n "${ORIGINAL_ENABLE[${index}]:-}" ] && echo "${ORIGINAL_ENABLE[${index}]}" > "${HWMON}/pwm${index}_enable" 2>/dev/null
    done
    echo "[restore] done. The fans are back under the board's own control."
}
trap restore EXIT INT TERM

speeds() {
    local out=""
    for index in 1 2 3 4 5 6 7 8; do
        local rpm; rpm="$(cat "${HWMON}/fan${index}_input" 2>/dev/null)" || continue
        [ "${rpm}" = "0" ] && continue
        out+="$(cat "${HWMON}/fan${index}_label" 2>/dev/null || echo "fan${index}")=${rpm} "
    done
    echo "${out}"
}

cat <<'INTRO'

-------------------------------------------------------------------
  FAN MAPPING TEST
-------------------------------------------------------------------
  What happens:
    1. Every fan except the pump goes to 30 percent. It gets quiet.
    2. One header at a time goes to 100 percent for 8 seconds.
    3. You watch the case and say which fan became loud.

  Write your answers down as they appear. At the end, tell Claude.

  The pump is not touched. Everything goes back to normal at the end,
  even if you press Ctrl-C.
-------------------------------------------------------------------
INTRO
read -r -p "Press Enter when you can see and hear the case. " _

# --- quiet everything --------------------------------------------------------
echo
echo "[phase 1] setting every header to 30 percent..."
for index in "${CHANNELS[@]}"; do
    echo 1 > "${HWMON}/pwm${index}_enable" 2>/dev/null   # 1 = manual control
    echo "${MIN_PWM}" > "${HWMON}/pwm${index}" 2>/dev/null
done
sleep "${SETTLE_SECONDS}"
echo "[phase 1] quiet.  speeds now: $(speeds)"

# --- one header at a time ----------------------------------------------------
for index in "${CHANNELS[@]}"; do
    label="$(cat "${HWMON}/fan${index}_label" 2>/dev/null || echo "fan${index}")"
    echo
    echo "=============================================================="
    echo "  NOW AT FULL SPEED:  header pwm${index}  (\"${label}\")"
    echo "  Watch the case for ${BURST_SECONDS} seconds. Which fan is loud?"
    echo "=============================================================="
    echo "${MAX_PWM}" > "${HWMON}/pwm${index}" 2>/dev/null
    sleep "${BURST_SECONDS}"
    echo "  speeds during the burst: $(speeds)"
    echo "${MIN_PWM}" > "${HWMON}/pwm${index}" 2>/dev/null
    sleep 2
done

echo
echo "All headers tested."
# The trap restores everything on exit.
