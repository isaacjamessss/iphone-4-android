#!/usr/bin/env bash
# Controlled touch capture for the iPhone 4 (n92ap) Android port.
# Run on the PC with Android booted (adb device T4RAMADB01) and the touch
# driver running (touch initrd, e.g. initrd-touch3.bin + stub-touch3.bin).
#
#   ./capture-touch.sh            interactive: press Enter at each step
#   ./capture-touch.sh --auto 6   timed: 6 s per step (say the steps out loud)
#
# Step 1 records the raw input events Android receives while you tap/swipe
# (is the driver emitting anything at all?). Steps 2-5 snapshot the driver's
# SPI receive buffers while one finger is held at a known spot, and decode the
# frames with n1frame.py, so X/Y/event fields can be matched to positions.
# Output: capture-<date>/ (events.txt, <label>/*.bin, summary.txt)
set -e
cd "$(dirname "$0")"
A="adb -s T4RAMADB01"
AUTO=0; [ "$1" = "--auto" ] && AUTO=${2:-6}
OUT=capture-$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"

step() {   # step "instruction"
    echo; echo ">>> $1"
    if [ "$AUTO" -gt 0 ]; then
        for i in $(seq 3 -1 1); do printf "  starting in %d...\r" $i; sleep 1; done; echo
    else
        read -r -p "    press Enter when ready " _
    fi
}

$A get-state >/dev/null || { echo "phone not on adb (T4RAMADB01)"; exit 1; }
$A push memdump /data/local/tmp/memdump >/dev/null
$A shell chmod 755 /data/local/tmp/memdump
PID=$($A shell "ps | grep t4-touch-input | grep -v grep" | awk '{print $2}' | tr -d '\r')
[ -n "$PID" ] || { echo "t4-touch-input is not running"; exit 1; }
STK=$($A shell "grep stack /proc/$PID/maps" | awk '{print $1}' | tr -d '\r')
LO=0x${STK%-*}; HI=0x${STK#*-}; LEN=$((HI - LO))
echo "driver pid $PID, stack $LO-$HI ($LEN bytes)"

DUR=${AUTO:-0}; [ "$DUR" -gt 0 ] || DUR=8
step "STEP 1/5: tap and swipe all over the screen for $DUR s (recording input events)"
$A shell "getevent -t /dev/input/event1 > /data/local/tmp/events.txt & sleep $DUR; kill \$!" || true
$A pull /data/local/tmp/events.txt "$OUT/events.txt" >/dev/null
N=$(wc -l < "$OUT/events.txt")
echo "    $N input events recorded -> $OUT/events.txt"
[ "$N" -gt 0 ] && head -n 12 "$OUT/events.txt"

snap() {   # snap label count
    local d="$OUT/$1"; mkdir -p "$d"
    $A shell "i=0; while [ \$i -lt $2 ]; do /data/local/tmp/memdump $PID $LO $LEN /data/local/tmp/s\$i.bin >/dev/null; i=\$((i+1)); /sbin/busybox usleep 300000; done"
    for i in $(seq 0 $(($2 - 1))); do $A pull /data/local/tmp/s$i.bin "$d/" >/dev/null 2>&1; done
    echo "    --- $1 ---" | tee -a "$OUT/summary.txt"
    python3 -I n1frame.py "$d"/*.bin | tee -a "$OUT/summary.txt"
}

step "STEP 2/5: do NOT touch the screen";                  snap none 8
step "STEP 3/5: hold ONE finger on the TOP-LEFT corner";     snap topleft 10
step "STEP 4/5: hold ONE finger on the BOTTOM-RIGHT corner"; snap bottomright 10
step "STEP 5/5: hold ONE finger in the CENTRE";              snap centre 10
$A shell "dmesg | grep -E 'T4_INPUT (REAL|FRAME_ERR|EMIT)' | tail -n 20" > "$OUT/dmesg-tail.txt" || true
echo; echo "done -> $OUT (summary.txt, events.txt, dmesg-tail.txt)"
