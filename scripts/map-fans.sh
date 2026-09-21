#!/usr/bin/env bash
# map-fans.sh — find out which fan is on which motherboard header.
#
#     sudo ./scripts/map-fans.sh
#
# The problem
#   The MSI PRO X870-P WIFI has 8 fan headers and one EZ Conn header (JAF_1).
#   Nine fans are in the case. Only 3 headers return a speed signal, so
#   software alone cannot say which fan is where.
#
# The method
#   Stop every fan except the pump. Then run ONE header at a time at full
#   speed. Only one fan turns, so the operator can SEE which one it is. This
#   is Gova's method; listening to a louder fan did not work.
#
#   Step 0 answers the biggest question by itself: with every board header at
#   zero, any fan that KEEPS TURNING is not wired to the motherboard.
#
# SAFETY — every rule is enforced in code, not left to the operator.
#   See docs/decisions/0007-rules-for-writing-to-hardware.md.
#   - The pump header is never written to. It is found by its label.
#   - A temperature watchdog samples every second. If any watched sensor goes
#     over its limit, everything is restored at once and the script stops.
#   - The script refuses to start if the machine is already warm.
#   - Each step is bounded in seconds, and the whole run is bounded too.
#   - The original values are saved first and restored on every exit path,
#     including Ctrl-C, a kill signal, and an error.

set -uo pipefail

STEP_SECONDS=15         # how long the operator has to look at each step
TOTAL_LIMIT_SECONDS=420 # the whole run may never last longer than this
START_MAX_TCTL=65       # refuse to start if the CPU is warmer than this
ABORT_TCTL=80           # stop and restore at once above this
ABORT_VRM=70
ABORT_NVME=70
PUMP_PATTERN='[Pp]ump'

[ "$(id -u)" -eq 0 ] || { echo "This script needs root. Run: sudo $0" >&2; exit 1; }

# --- find the chips ----------------------------------------------------------
find_hwmon() {
    for dir in /sys/class/hwmon/hwmon*; do
        [ "$(cat "${dir}/name" 2>/dev/null)" = "$1" ] && { echo "${dir}"; return 0; }
    done
    return 1
}
BOARD="$(find_hwmon nct6687)" || { echo "The nct6687 driver is not loaded. Run scripts/install-nct6687d.sh." >&2; exit 1; }
CPU="$(find_hwmon k10temp)"   || { echo "k10temp is missing; the watchdog cannot work." >&2; exit 1; }
NVME="$(find_hwmon nvme)" || NVME=""

millideg() { local v; v="$(cat "$1" 2>/dev/null)" || { echo 0; return; }; echo $(( v / 1000 )); }
tctl()    { millideg "${CPU}/temp1_input"; }
vrm()     { millideg "${BOARD}/temp3_input"; }
nvme_t()  { [ -n "${NVME}" ] && millideg "${NVME}/temp1_input" || echo 0; }

# --- classify the headers ----------------------------------------------------
CHANNELS=()
declare -A LABEL
for path in "${BOARD}"/pwm[0-9]; do
    [ -w "${path}" ] || continue
    index="${path##*pwm}"
    name="$(cat "${BOARD}/fan${index}_label" 2>/dev/null || echo "fan${index}")"
    LABEL["${index}"]="${name}"
    if [[ "${name}" =~ ${PUMP_PATTERN} ]]; then
        echo "  pwm${index}  ${name}  -- PROTECTED, never written to"
    else
        CHANNELS+=("${index}")
    fi
done
[ "${#CHANNELS[@]}" -gt 0 ] || { echo "no writable fan headers found" >&2; exit 1; }

# --- refuse to start on a warm machine ---------------------------------------
start_tctl="$(tctl)"
if [ "${start_tctl}" -gt "${START_MAX_TCTL}" ]; then
    echo "REFUSING TO START: Tctl is ${start_tctl} C, over the ${START_MAX_TCTL} C limit." >&2
    echo "Let the machine settle, then run this again." >&2
    exit 1
fi
echo "start state: Tctl ${start_tctl} C, VRM $(vrm) C, NVMe $(nvme_t) C"

# --- save, and promise to restore --------------------------------------------
declare -A ORIGINAL_PWM ORIGINAL_ENABLE
for index in "${CHANNELS[@]}"; do
    ORIGINAL_PWM["${index}"]="$(cat "${BOARD}/pwm${index}")"
    ORIGINAL_ENABLE["${index}"]="$(cat "${BOARD}/pwm${index}_enable")"
done

RESTORED=0
restore() {
    [ "${RESTORED}" -eq 1 ] && return
    RESTORED=1
    echo
    echo "[restore] returning every fan header to the board's own control"
    for index in "${CHANNELS[@]}"; do
        echo "${ORIGINAL_PWM[${index}]}" > "${BOARD}/pwm${index}" 2>/dev/null
        echo "${ORIGINAL_ENABLE[${index}]}" > "${BOARD}/pwm${index}_enable" 2>/dev/null
    done
    echo "[restore] done.  Tctl $(tctl) C, VRM $(vrm) C, NVMe $(nvme_t) C"
}
trap restore EXIT INT TERM

RUN_START="$(date +%s)"
check_safe() {
    local t v n now
    t="$(tctl)"; v="$(vrm)"; n="$(nvme_t)"; now="$(date +%s)"
    if [ "${t}" -ge "${ABORT_TCTL}" ] || [ "${v}" -ge "${ABORT_VRM}" ] || [ "${n}" -ge "${ABORT_NVME}" ]; then
        echo
        echo "!!! WATCHDOG: Tctl ${t} C, VRM ${v} C, NVMe ${n} C -- stopping now"
        return 1
    fi
    if [ $(( now - RUN_START )) -ge "${TOTAL_LIMIT_SECONDS}" ]; then
        echo
        echo "!!! time limit reached -- stopping now"
        return 1
    fi
    return 0
}

# Hold a state for N seconds, checking the watchdog every second.
hold() {
    local seconds="$1" i
    for (( i = 0; i < seconds; i++ )); do
        check_safe || return 1
        sleep 1
    done
    return 0
}

set_all() {
    local value="$1" index
    for index in "${CHANNELS[@]}"; do
        echo 1 > "${BOARD}/pwm${index}_enable" 2>/dev/null   # 1 = manual
        echo "${value}" > "${BOARD}/pwm${index}" 2>/dev/null
    done
}

reporting_speeds() {
    local out="" index rpm
    for index in 1 2 3 4 5 6 7 8; do
        rpm="$(cat "${BOARD}/fan${index}_input" 2>/dev/null)" || continue
        [ "${rpm}" = "0" ] && continue
        out+="${LABEL[${index}]:-fan${index}}=${rpm} "
    done
    echo "${out:-none}"
}

cat <<'INTRO'

-------------------------------------------------------------------
  FAN MAPPING TEST
-------------------------------------------------------------------
  STEP 0  Every board fan stops, except the pump.
          COUNT THE FANS THAT KEEP TURNING. Those are not wired to
          the motherboard, and that is the answer we most need.

  THEN    One header at a time runs at full speed, alone.
          Say which fan turns. Write it down as you go.

  The pump is never touched. A watchdog checks the CPU, the VRM and
  the drive every second and puts everything back if anything warms.
  Ctrl-C also puts everything back.
-------------------------------------------------------------------
INTRO
read -r -p "Press Enter when you can see inside the case. " _

# --- step 0: everything off --------------------------------------------------
echo
echo "=============================================================="
echo "  STEP 0 — ALL BOARD FANS STOPPED (the pump keeps running)"
echo "  Look now. HOW MANY FANS ARE STILL TURNING?"
echo "=============================================================="
set_all 0
hold "${STEP_SECONDS}" || exit 1
echo "  speeds the board still reports: $(reporting_speeds)"
echo "  temperatures: Tctl $(tctl) C, VRM $(vrm) C, NVMe $(nvme_t) C"

# --- one header at a time ----------------------------------------------------
for index in "${CHANNELS[@]}"; do
    set_all 0
    echo 255 > "${BOARD}/pwm${index}" 2>/dev/null
    echo
    echo "=============================================================="
    echo "  ONLY THIS HEADER IS RUNNING:  pwm${index}  (\"${LABEL[${index}]}\")"
    echo "  Which fan is turning? (front / top / rear / radiator / none)"
    echo "=============================================================="
    hold "${STEP_SECONDS}" || exit 1
    echo "  speeds: $(reporting_speeds)"
done

echo
echo "All headers tested. Tell Claude what you saw at each step."
# The trap restores everything.
