#!/usr/bin/env bash
# Build openiboot for the iPhone 4 CDMA (iPhone3,3 / n92ap, A4 S5L8930).
# Run inside WSL2 Debian/Ubuntu from anywhere:
#   bash tools/build-openiboot.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/../src/openiBoot-master"

if ! command -v scons >/dev/null 2>&1 || ! command -v arm-none-eabi-gcc >/dev/null 2>&1; then
  echo "== installing build deps (needs sudo) =="
  sudo apt-get update
  sudo apt-get install -y \
    build-essential scons git python3 \
    gcc-arm-none-eabi binutils-arm-none-eabi \
    libpng-dev libssl-dev zlib1g-dev
fi

cd "$SRC"

# The tree is a 2012 codebase; modern GCC is much stricter. Drop -Werror
# (see ARMEnvironment.SConscript) if the build stops on warnings.
CROSS=arm-none-eabi- scons -j"$(nproc)" iPhone4CDMA

echo
ls -l "$SRC"/iphone_4_cdma_openiboot.bin
echo "Artifact: $SRC/iphone_4_cdma_openiboot.bin"
