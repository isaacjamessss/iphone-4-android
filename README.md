# Android 2.3.7 on the iPhone 4 CDMA (iPhone3,3 / n92ap)

Boots **Android 2.3.7 (Gingerbread) to the launcher** on an iPhone 4 CDMA,
with a **root ADB shell over USB**. Everything runs from RAM: nothing is
written to the phone's storage, and a hard reset (power + home) returns to
iOS.

Kernel and Android userland come from the iDroid-based **T4** build for the
iPod touch 4 (same A4 SoC, same 640x960 screen); this repo makes it boot on
the n92ap with a small binary boot kit and openiboot.

## Status

| Works | Doesn't work (yet) |
|---|---|
| Kernel console on screen | **Touchscreen** (T4 driver is iPod-touch-4 only, see below) |
| Android init, system_server, launcher | Wi-Fi, Bluetooth, audio, storage (NAND) |
| Root ADB over USB (`T4RAMADB01`) | Cellular (CDMA modem has no driver) |
| Home / volume buttons | 512 MB RAM (kernel is told 256 MB) |
| Caches on, normal speed | |

## Requirements

- iPhone 4 **CDMA** (n92ap). Other models are untested.
- Linux PC (native, not a VM) with `python3`, `python3-pyusb` (`pip install pyusb`),
  `lsusb` (usbutils), `adb`, and `sudo`.
- A USB cable. Keep the phone plugged in the whole time.

## Boot it

1. Put the phone in **DFU mode**: hold **power + home** for 10 s, release
   power, keep holding home until the screen stays black (no logo).
2. Run:

   ```sh
   ./boot.sh
   ```

   It exploits the boot ROM (limera1n), loads a patched iBSS and openiboot,
   uploads kernel + 46 MB initrd (about 2 minutes) and jumps to the kernel.
3. The screen shows a few solid colour checkpoints (ending olive), then
   kernel text, then the Android home screen.
4. Get a shell:

   ```sh
   adb devices          # -> T4RAMADB01  device
   adb -s T4RAMADB01 shell
   ```

If openiboot is already running on the phone (`lsusb` shows `0525:1280`),
`./boot.sh` skips the DFU steps and uploads straight away.

## If it crashes: read the kernel log

The kernel log survives a DFU reset, so you can read a crashed boot back:

1. **Don't power the phone off.** Put it straight into DFU mode.
2. Run:

   ```sh
   ./readlog.sh            # -> logs/<date>/log.bin.txt
   ```

It reloads openiboot and pulls the 128 KB printk buffer (and the boot-stage
records) over USB in a few seconds.

## Layout

```
boot.sh             DFU -> Android
readlog.sh          DFU -> read the last boot's kernel log
boot/               everything that gets uploaded to the phone
  limera1n.payload    boot ROM exploit payload
  iBSS.n92ap-pwn.img3 patched iBSS (signature checks off)
  openiboot-archeyr.img3  openiboot for n92ap (archeYR fork)
  zImage              T4 3.0.8 kernel, patched (see below)
  kcaves.bin          checkpoint/patch blob, loaded at PA 0x00E00000
  stub.bin            boot stub: builds ATAGs (cmdline, 256 MB, initrd), jumps
  t4-initrd.bin       T4 Android 2.3.7 root filesystem (gzip cpio)
tools/              host tools boot.sh/readlog.sh use
  a4boot(.c)          limera1n + iBSS loader
  dfu-upload.py       DFU upload of openiboot
  oibsend.py          upload files to openiboot (with ack check)
  oibread.py          raw memory readback via openiboot `recvfile`
  decode-rec.py       decode boot-stage records
extras/             development history and debugging material
  build/              kit builder + pristine T4 kernel inputs
  docs/               port notes, session logs, crash logs
  debug-tools/        bring-up and diagnostic tools
  old-kits/ qemu/ artifacts/ openiboot/ android-images/
```

## What the boot kit changes

The T4 kernel was built for the iPod touch 4 and its own handoff code. To
boot it on the n92ap from openiboot, `extras/build/build-bootkit.py`
patches the unmodified T4 kernel (`extras/build/t4-kernel.bin`) and audits
every change (300+ checks):

- Kernel entry and early boot points are redirected to small "caves" in
  `kcaves.bin` that paint a colour checkpoint and then run the original
  instruction (useful when nothing else is visible).
- `stub.bin` builds the ATAGs at 0x100 (memory, initrd, command line
  `console=t4fb0 loglevel=4 rdinit=/init panic=0 t4fb=0x0F700000 noalign`)
  and enters the kernel with r1 = 3564, r2 = 0x100.
- `composite_suspend` returns immediately: the T4 USB gadget code crashes
  when the PC suspends the USB bus.

Rebuild after changing anything:

```sh
python3 extras/build/build-bootkit.py phone     # writes boot/zImage, kcaves.bin, stub.bin
```

Notable bugs found on the way (details in `extras/docs/SESSION-2026-11-26.md`):

- A checkpoint replayed `teq r2,#3` instead of `tst r2,#3` in `__vet_atags`,
  so the kernel always ignored the ATAGs and booted with 16 MB.
- An earlier workaround left the CPU caches off, which made Android very slow.
- openiboot sometimes drops USB packets under load; `oibsend.py` now waits
  for openiboot's "Received file" ack and recovers if it's missing.

## Next: touchscreen

The T4 touch driver (`/sbin/t4-touch-input`) talks to the **iPod touch 4**
touch controller (N81 firmware, SPI1, CS GPIO 0x601, reset 0x204,
IRQ 0x205). On the iPhone 4 the firmware upload is never acknowledged and
SPI reads return `ffffffff`. Fixing touch needs the n92ap pin assignments
(from the iOS device tree) and the iPhone 4 Zephyr2 touch firmware (from
the iOS kernelcache).

## Safety

Everything is RAM-only: the kit never writes to NAND, and a hard reset
returns the phone to iOS.
