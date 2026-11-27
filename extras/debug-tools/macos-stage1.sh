#!/usr/bin/env bash
# Stage 1 on macOS: pwn the A4 bootrom, load iBSS, then load openiboot.
# Requires: Xcode CLT, brew libusb python3, pip3 install pyusb.
set -euo pipefail
cd "$(dirname "$0")/.."

cc -O2 -o a4boot tools/a4boot.c \
   -I"$(brew --prefix libusb)/include" \
   -L"$(brew --prefix libusb)/lib" -lusb-1.0

cat <<'MSG'

Phone must be in DFU: Power 3s -> +Home 10s -> release Power, hold Home 10s.
Screen must stay black. Verify with: system_profiler SPUSBDataType | grep 1227

MSG
read -r -p "Press Enter when the phone is in DFU..."

sudo ./a4boot artifacts/limera1n.payload artifacts/iBSS.n92ap.bin reset || {
    echo "pwn/iBSS failed - check PWND with: irecovery -q"
    exit 1
}

echo
echo "If iBSS took over, SRTG in 'irecovery -q' is no longer iBoot-574.4."
read -r -p "Press Enter to upload openiboot..."

sudo python3 tools/dfu-upload.py --go "go jump 0x41000000" \
     artifacts/iphone_4_cdma_openiboot.bin

cat <<'MSG'

openiboot should now enumerate as VID 0x0525, "OpenIBoot Mode".
  system_profiler SPUSBDataType | grep -i -A6 OpenIBoot
  ls /dev/cu.usbmodem*
  screen /dev/cu.usbmodemXXXX 115200

MSG
