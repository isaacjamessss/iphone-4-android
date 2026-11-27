#!/usr/bin/env bash
# Boot chain (self-healing: bus reset + retry on ACM stalls).
set -e
cd "/home/sakura/Documents/Default Project/iphone33-android/bootkit"
python3 "/home/sakura/Documents/Default Project/iphone33-android/tools/oibsend.py" boot \
  zImage 0x44000000 /home/sakura/Downloads/t4-initrd.bin 0x09000000 kcaves.bin 0x01000000 stub.bin 0x04200000 \
  --go "go 0x04200000"
