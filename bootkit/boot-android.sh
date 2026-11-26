#!/usr/bin/env bash
# Boot chain (self-healing: bus reset + retry on ACM stalls).
# This PC: t4-initrd.bin is missing; the stub does not verify it and the
# m3..m10 start_kernel bisect ends at console_init, before the initrd is
# unpacked. Set INITRD=/path/t4-initrd.bin to send it anyway.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/bootkit"
extra=()
[ -n "$INITRD" ] && extra=("$INITRD" 0x09000000)
python3 "$ROOT/tools/oibsend.py" boot \
  zImage 0x44000000 "${extra[@]}" kcaves.bin 0x01000000 stub.bin 0x04200000 \
  --go "go 0x04200000"
