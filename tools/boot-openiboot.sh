#!/usr/bin/env bash
# Stage 1: limera1n-pwn an A4 device in DFU and RAM-load openiboot for n92ap.
# Nothing is written to NAND. A power cycle returns to iOS.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/src/openiBoot-master/iphone_4_cdma_openiboot.bin"
OUT="/tmp/oib-boot"
mkdir -p "$OUT"

say() { echo "$*"; }

[ -f "$BIN" ] || { echo "missing $BIN"; exit 1; }

# 1. Wait for DFU (up to 90s)
echo "== waiting for DFU device =="
found=0
for _ in $(seq 1 90); do
  if irecovery -q > "$OUT/dfu.txt" 2>&1 && grep -q "CPID" "$OUT/dfu.txt"; then
    found=1; break
  fi
  sleep 1
done
cat "$OUT/dfu.txt"
[ "$found" = 1 ] || { echo "RESULT: no device in DFU"; exit 1; }
grep -E "CPID|BDID|ECID|MODE" "$OUT/dfu.txt"

# 2. limera1n (exploit is built into libirecovery; no payload file needed)
echo "== injecting limera1n =="
printf '/limera1n\n/exit\n' | irecovery -s > "$OUT/limera1n.txt" 2>&1
sleep 5
tail -15 "$OUT/limera1n.txt"

echo "== device state after exploit =="
irecovery -q > "$OUT/pwned.txt" 2>&1
cat "$OUT/pwned.txt"

# 3. Upload openiboot flat image and jump to it.
#    A4 load address is 0x41000000; entry.sx relocates itself to 0x0.
echo "== uploading openiboot =="
irecovery -f "$BIN" 2>&1 | tail -3
sleep 1
irecovery -c "go jump 0x41000000" 2>&1 | tail -3
sleep 6

# 4. openiboot should re-enumerate as 0525:xxxx "Apple Mobile Device (OpenIBoot Mode)"
echo "== USB devices now =="
lsusb
if lsusb | grep -qi "0525:"; then
  echo "RESULT: openiboot enumerated on USB"
  ls /dev/ttyACM* 2>/dev/null && echo "RESULT: ACM console present"
else
  echo "RESULT: no openiboot USB device (likely hung in early init)"
fi
