#!/usr/bin/env bash
# The self-test and the suites of tests/manual on a real X display, not offscreen.
#
#   tools/manual_on_x.sh                         # 1366x768, self-test and every suite
#   tools/manual_on_x.sh 1024x700 tests/manual/test_every_dialog.py
#   LMS_SCREEN_SCALE=2 tools/manual_on_x.sh      # Qt scaled twice, as on a HiDPI screen
#
# Offscreen hides what a display shows: focus, window activation, the size a window manager
# gives, real fonts. The display is Xvfb, so nothing appears on the screen of the PC. A window
# manager is started when one is installed (openbox, fluxbox, icewm, xfwm4, metacity); then the
# suites also check that the window gets the focus back after each action. Without one they run
# all the same, and say so.
set -euo pipefail
cd "$(dirname "$0")/.."
size="${1:-1366x768}"
shift || true
targets=("$@")
command -v Xvfb >/dev/null || { echo "Xvfb is needed: apt install xvfb" >&2; exit 2; }

display=99
while [ -e "/tmp/.X${display}-lock" ]; do display=$((display + 1)); done
Xvfb ":${display}" -screen 0 "${size}x24" -nolisten tcp &
xvfb=$!
manager=""
cleanup() {
    [ -n "${manager_pid:-}" ] && kill "$manager_pid" 2>/dev/null || true
    kill "$xvfb" 2>/dev/null || true
}
trap cleanup EXIT
for _ in $(seq 50); do [ -e "/tmp/.X11-unix/X${display}" ] && break; sleep 0.1; done

export DISPLAY=":${display}" QT_QPA_PLATFORM=xcb
unset WAYLAND_DISPLAY
if [ -n "${LMS_SCREEN_SCALE:-}" ]; then
    export QT_SCALE_FACTOR="$LMS_SCREEN_SCALE"
fi
for candidate in openbox fluxbox icewm xfwm4 metacity; do
    if command -v "$candidate" >/dev/null; then
        manager="$candidate"
        "$candidate" >/dev/null 2>&1 &
        manager_pid=$!
        sleep 1
        break
    fi
done
if [ -n "$manager" ]; then
    export LMS_WINDOW_MANAGER="$manager"
    echo "Display :${display} ${size}, window manager ${manager}"
else
    echo "Display :${display} ${size}, no window manager installed (apt install openbox): focus is not checked"
fi

status=0
if [ ${#targets[@]} -eq 0 ]; then
    .venv/bin/lvgl-mpy-studio selftest || status=1
    targets=(tests/manual)
fi
.venv/bin/pytest -q tests/test_fit_screen.py "${targets[@]}" --manual || status=1
exit $status
