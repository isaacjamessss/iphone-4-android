#!/usr/bin/env bash
# Sync the Windows-side working tree into the WSL build copy.
# Run via: wsl.exe --cd "<parent of iphone33-android>" -e bash -lc 'bash iphone33-android/tools/sync.sh'
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(dirname "$HERE")"
DEST="$HOME/iphone33-android"

mkdir -p "$DEST"
rsync -a --exclude='*.o' --exclude='*.obj' --exclude='.sconsign.dblite' \
      --exclude='*_openiboot' --exclude='*_openiboot.bin' \
      "$SRC/" "$DEST/"
echo "synced $SRC -> $DEST"
