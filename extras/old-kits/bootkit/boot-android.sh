#!/usr/bin/env bash
# Boot chain (self-healing: bus reset + retry on ACM stalls).
set -e
cd "/home/isaacjames/Desktop/1125262206/iphone33-android/bootkit"
python3 "/home/isaacjames/Desktop/1125262206/iphone33-android/tools/oibsend.py" boot \
  zImage 0x44000000 /home/isaacjames/Desktop/iphone3,3/t4-initrd.bin 0x09000000 kcaves.bin 0x00e00000 stub.bin 0x04200000 \
  --go "go 0x04200000"
