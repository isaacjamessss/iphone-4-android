#!/usr/bin/env bash
# Stage 1 on native Linux: pwn the A4 bootrom, load iBSS, then load openiboot.
#
# Linux is the preferred host for this: libusb_reset_device() issues a real
# USBDEVFS_RESET port reset, which is exactly what the A4 bootrom needs to
# jump into a manifested image (the USB/IP blocker from the old machine does
# not exist here).
#
# Run from a host terminal (not inside a Flatpak/container):
#   bash tools/linux-stage1.sh
#
# Installs deps via apt/dnf/pacman/zypper/apk (needs sudo once), compiles
# a4boot, then walks through DFU -> limera1n -> iBSS -> openiboot console.
set -euo pipefail
cd "$(dirname "$0")/.."

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null || { echo "need root or sudo"; exit 1; }
    SUDO="sudo"
fi

# --- 1. dependencies -------------------------------------------------------
need_pkgs=0
command -v cc        >/dev/null || need_pkgs=1
command -v pkg-config >/dev/null || need_pkgs=1
command -v lsusb     >/dev/null || need_pkgs=1
python3 -c "import usb.core" 2>/dev/null || need_pkgs=1
pkg-config --exists libusb-1.0 2>/dev/null || need_pkgs=1

if [ "$need_pkgs" = 1 ]; then
    echo "==> installing build/USB dependencies"
    if command -v apt-get >/dev/null; then
        $SUDO apt-get update
        $SUDO apt-get install -y gcc pkg-config libusb-1.0-0-dev python3 python3-usb usbutils picocom
        $SUDO apt-get install -y irecovery || echo "note: irecovery unavailable (optional, for SRTG/PWND checks)"
    elif command -v dnf >/dev/null; then
        $SUDO dnf install -y gcc pkgconf-pkg-config libusb1-devel python3 python3-pyusb usbutils picocom
        $SUDO dnf install -y libirecovery || echo "note: irecovery unavailable (optional)"
    elif command -v pacman >/dev/null; then
        $SUDO pacman -S --needed --noconfirm gcc pkgconf libusb python-pyusb usbutils picocom
        $SUDO pacman -S --needed --noconfirm libirecovery || echo "note: irecovery unavailable (optional)"
    elif command -v zypper >/dev/null; then
        $SUDO zypper install -y gcc pkg-config libusb-1_0-devel python3 python3-pyusb usbutils picocom
        $SUDO zypper install -y libirecovery || echo "note: irecovery unavailable (optional)"
    elif command -v apk >/dev/null; then
        $SUDO apk add gcc pkgconf libusb-dev python3 py3-pyusb usbutils picocom
    else
        echo "unknown package manager; install manually: gcc, pkg-config, libusb-1.0 dev, python3+pyusb, usbutils, picocom"
        exit 1
    fi
fi

# --- 2. compile the exploit tool -------------------------------------------
echo "==> compiling a4boot"
cc -O2 -o a4boot tools/a4boot.c $(pkg-config --cflags --libs libusb-1.0)

# --- 3. phone into DFU ------------------------------------------------------
cat <<'MSG'

==> Put the phone in DFU (screen stays BLACK):
      1. Hold Power 3 s
      2. Keep Power, add Home, hold both 10 s
      3. Release Power, keep Home 10 s
    Cable must be connected to this machine the whole time.

MSG
while :; do
    read -r -p "Press Enter when the phone is in DFU..."
    if lsusb -d 05ac:1227 >/dev/null 2>&1; then
        lsusb -d 05ac:1227
        break
    fi
    echo "!! no 05ac:1227 DFU device visible. Check cable / retry the button sequence."
    echo "   (If it shows 05ac:1281 it is in recovery mode, not DFU.)"
done

# --- 4. limera1n pwn + iBSS upload (real bus resets) ------------------------
echo "==> pwn + iBSS upload (encrypted IMG3; the payload decrypts it)"
$SUDO ./a4boot artifacts/limera1n.payload artifacts/iBSS.n92ap.img3 reset || {
    echo "pwn/iBSS failed."
    echo "  - check 'sudo irecovery -q' for PWND: limera1n"
    echo "  - a power cycle clears the pwn; put the phone back in DFU and retry"
    exit 1
}

if command -v irecovery >/dev/null; then
    echo "==> post-iBSS identity (SRTG should no longer be iBoot-574.4):"
    $SUDO irecovery -q || true
fi

# --- 5. upload openiboot and jump -------------------------------------------
echo
read -r -p "Press Enter to upload openiboot..."
$SUDO python3 tools/dfu-upload.py --go "go jump 0x41000000" \
     artifacts/iphone_4_cdma_openiboot.bin

# --- 6. wait for openiboot USB + console ------------------------------------
echo "==> waiting for openiboot to enumerate (VID 0x0525)..."
found=""
for _ in $(seq 1 20); do
    if lsusb -d 0525: >/dev/null 2>&1; then found=1; break; fi
    sleep 1
done
if [ -z "$found" ]; then
    cat <<'MSG'
!! openiboot did not enumerate within 20 s. It likely hung in early init
   (PMU/clock first, then display - see HANDOFF.txt section 7.4).
   Nothing was written to NAND; power-cycle the phone to return to iOS.
MSG
    exit 1
fi
lsusb -d 0525:

# openiboot presents a CDC-ACM console -> /dev/ttyACM*
tty=""
for _ in $(seq 1 10); do
    for t in /dev/ttyACM*; do
        [ -e "$t" ] && tty="$t" && break 2
    done
    sleep 1
done
if [ -z "$tty" ]; then
    echo "!! 0525 device present but no /dev/ttyACM* appeared."
    echo "   Check: lsusb -v -d 0525: | grep -i interface"
    exit 1
fi

cat <<MSG

==> STAGE 1: openiboot console on $tty
    (ModemManager can grab ACM devices; if the console is silent:
       $SUDO systemctl stop ModemManager )
    Exit picocom: Ctrl-A then Ctrl-X

MSG
exec $SUDO picocom -b 115200 "$tty"