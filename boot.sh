#!/usr/bin/env bash
# Boot Android 2.3.7 on an iPhone 4 CDMA (n92ap). Everything is RAM-only:
# nothing is ever written to the phone's NAND; a hard reset returns to iOS.
#
#   DFU mode -> limera1n + patched iBSS -> openiboot -> T4 kernel + initrd
#
# Put the phone in DFU (hold power+home 10 s, release power, keep holding
# home until the screen stays black), then run:  ./boot.sh [mode]
# If openiboot is already running (USB 0525:1280) the DFU steps are skipped.
#
#   ./boot.sh          320x480 (2x scaled), touch working   (boot/lowres + initrd-touch5-lowres)
#   ./boot.sh quiet    640x960, stock T4 initrd, no touch  (boot/quiet)
#   ./boot.sh colour   640x960 with colour checkpoints, for debugging early boot
#
# Each stub.bin has the size of ITS initrd baked into the ATAGs - keep pairs together.
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

case "${1:-lowres}" in
    lowres) K=boot/lowres; I=boot/initrd-touch5-lowres.bin ;;
    quiet)  K=boot/quiet;  I=boot/t4-initrd.bin ;;
    colour|color) K=boot;  I=boot/t4-initrd.bin ;;
    *) echo "usage: $0 [lowres|quiet|colour]"; exit 1 ;;
esac

# Upload kernel, initrd, checkpoint blob and boot stub, then jump to the stub.
# oibsend waits for openiboot's ack after every file (~2 min, mostly initrd).
exec python3 tools/oibsend.py boot \
    $K/zImage    0x44000000 \
    $I           0x09000000 \
    $K/kcaves.bin 0x00e00000 \
    $K/stub.bin  0x04200000 \
    --go "go 0x04200000"
