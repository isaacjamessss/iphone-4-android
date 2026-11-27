#!/usr/bin/env bash
# Boot Android 2.3.7 on an iPhone 4 CDMA (n92ap). Everything is RAM-only:
# nothing is ever written to the phone's NAND; a hard reset returns to iOS.
#
#   DFU mode -> limera1n + patched iBSS -> openiboot -> T4 kernel + initrd
#
# Put the phone in DFU (hold power+home 10 s, release power, keep holding
# home until the screen stays black), then run:  ./boot.sh
# If openiboot is already running (USB 0525:1280) the DFU steps are skipped.
set -e
cd "$(dirname "$0")"
[ "$EUID" -eq 0 ] || exec sudo "$0" "$@"

if ! lsusb | grep -q 0525:1280; then
    echo "waiting for DFU mode (05ac:1227)..."
    until lsusb | grep -q 05ac:1227; do sleep 1; done
    tools/a4boot boot/limera1n.payload boot/iBSS.n92ap-pwn.img3 reset
    sleep 3
    python3 tools/dfu-upload.py boot/openiboot-archeyr.img3
    sleep 6
fi

# Upload kernel, initrd, checkpoint blob and boot stub, then jump to the stub.
# oibsend waits for openiboot's ack after every file (~2 min, mostly initrd).
exec python3 tools/oibsend.py boot \
    boot/zImage        0x44000000 \
    boot/t4-initrd.bin 0x09000000 \
    boot/kcaves.bin    0x00e00000 \
    boot/stub.bin      0x04200000 \
    --go "go 0x04200000"
