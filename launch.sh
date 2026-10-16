#!/usr/bin/env bash
# launch.sh — the one command that starts sensors-gui and its tools.
#
# Run it from anywhere:
#
#     ./launch.sh                  the GUI, in its own Chrome window
#     ./launch.sh help             every command
#
# KEEP THIS FILE CURRENT. When an entry point, a flag or a developer tool is
# added, removed or renamed, change this file in the same commit (CLAUDE.md,
# section 4). It is a thin layer: each command calls the real entry point
# through uv and passes every extra argument through, so a new flag on an
# entry point works here with no change.
#
# It writes nothing to hardware. It does not install the helper and it does
# not use sudo; `scripts/install-helper.sh` does that, and Gova runs it.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

HELPER_SOCKET=/run/sensors-gui.sock
HELPER_UNIT=sensors-guid

usage() {
    cat <<'EOF'
Usage: ./launch.sh [COMMAND] [ARGS...]

Commands (ARGS go to the program unchanged):
  gui      The GUI in a Chrome application window. This is the default.
           ./launch.sh gui --page "/#cpu"      open one view
           ./launch.sh gui --hz 2              start at 2 Hz
  serve    The GUI server only, with no window, on port 8713 or the next free.
           ./launch.sh serve --port 8714
  tui      The terminal screen (ADR 0004).
  preview  Render the terminal screen once to stdout.
           With no ARGS: --rows 0 --all
  status   Show the helper service and the socket. Reads only.
  check    ruff check, ruff format --check and pytest. Run before a commit.
  test     pytest only. ARGS go to pytest, for example: ./launch.sh test -k web
  help     This text.

Needs root, run by hand, not from here:
  sudo ./scripts/install-helper.sh    install or update the helper service
EOF
}

# Show one line about the helper. Three sources need it; without it, 32
# channels show "needs the helper" and everything else still works.
helper_note() {
    if [ -S "$HELPER_SOCKET" ]; then
        return 0
    fi
    echo "launch: the helper socket $HELPER_SOCKET is missing." >&2
    echo "launch: 32 channels will show \"needs the helper\". To install: sudo ./scripts/install-helper.sh" >&2
}

helper_status() {
    local state
    state="$(systemctl is-active "$HELPER_UNIT" 2>/dev/null || true)"
    echo "service  $HELPER_UNIT: ${state:-unknown}"
    if [ -S "$HELPER_SOCKET" ]; then
        echo "socket   $(stat -c '%A %U:%G' "$HELPER_SOCKET") $HELPER_SOCKET"
    else
        echo "socket   missing: $HELPER_SOCKET"
    fi
    [ "$state" = "active" ] && [ -S "$HELPER_SOCKET" ]
}

command="${1:-gui}"
[ $# -gt 0 ] && shift

case "$command" in
    gui)
        helper_note
        exec uv run python -m sensors_gui.web "$@"
        ;;
    serve)
        helper_note
        exec uv run python -m sensors_gui.web --no-window "$@"
        ;;
    tui)
        helper_note
        exec uv run python -m sensors_gui "$@"
        ;;
    preview)
        [ $# -eq 0 ] && set -- --rows 0 --all
        exec uv run python scripts/preview-screen.py "$@"
        ;;
    status)
        helper_status
        ;;
    check)
        uv run ruff check src tests scripts
        uv run ruff format --check src tests scripts
        exec uv run pytest "$@"
        ;;
    test)
        exec uv run pytest "$@"
        ;;
    help | -h | --help)
        usage
        ;;
    *)
        echo "launch: unknown command: $command" >&2
        usage >&2
        exit 2
        ;;
esac
