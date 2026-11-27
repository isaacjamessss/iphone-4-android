#!/usr/bin/env bash
# Full RAM-only chain: phone must be in DFU mode (power+home 10 s, release power, hold home).
set -e
cd "$(dirname "$0")"
sudo ./a4boot artifacts/limera1n.payload artifacts/iBSS.n92ap-pwn.img3 reset
sleep 3
sudo python3 tools/dfu-upload.py artifacts/openiboot-archeyr.img3
sleep 6
sudo bash bootkit/boot-android.sh
