#!/usr/bin/env bash
# Read the kernel log of the LAST boot back over USB (works even after a
# crash: DRAM survives a DFU reset). Do NOT power the phone off first.
#
# Put the phone in DFU (it reloads openiboot), then run:  ./readlog.sh [DIR]
# Writes DIR/log.bin(.txt) (printk buffer) and DIR/rec.bin (boot records).
set -e
cd "$(dirname "$0")"
[ "$EUID" -eq 0 ] || exec sudo "$0" "$@"
D=${1:-logs/$(date +%Y%m%d-%H%M%S)}
mkdir -p "$D"

if ! lsusb | grep -q 0525:1280; then
    echo "waiting for DFU mode (05ac:1227)..."
    until lsusb | grep -q 05ac:1227; do sleep 1; done
    tools/a4boot boot/limera1n.payload boot/iBSS.n92ap-pwn.img3 reset
    sleep 3
    python3 tools/dfu-upload.py boot/openiboot-archeyr.img3
    sleep 6
fi

# boot records written by the stub/kernel checkpoints (PA 0x0F600000)
python3 tools/oibread.py 0x0F600000 0x100 "$D/rec.bin"
python3 tools/decode-rec.py "$D/rec.bin"
# printk buffer __log_buf (VA 0xC028FCE0 -> PA 0x0028FCE0, 128 KB)
python3 tools/oibread.py 0x0028FCE0 0x20000 "$D/log.bin"
echo "log: $D/log.bin.txt"
