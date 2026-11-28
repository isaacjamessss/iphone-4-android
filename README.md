# Android 2.3.7 on the iPhone 4 CDMA (iPhone3,3 / n92ap)

Boots **Android 2.3.7 (Gingerbread) to the launcher** on an iPhone 4 CDMA,
with a **working touchscreen** and a **root ADB shell over USB**. Everything runs from RAM: nothing is
written to the phone's storage, and a hard reset (power + home) returns to
iOS.

Kernel and Android userland come from the iDroid-based **T4** build for the
iPod touch 4 (same A4 SoC, same 640x960 screen); this repo makes it boot on
the n92ap with a small binary boot kit and openiboot.

## Status

| Works | Doesn't work (yet) |
|---|---|
| Kernel console on screen | Wi-Fi, Bluetooth, audio, storage (NAND) |
| Android init, system_server, launcher | Cellular (CDMA modem has no driver) |
| **Touchscreen** (multitouch) | GPU (SGX535 has no driver: software rendering) |
| Root ADB over USB (`T4RAMADB01`) | 512 MB RAM (kernel is told 256 MB) |
| Home / volume buttons | |
| 320x480 display, 2x scaled, page flipping | |
| Quiet boot (no colour checkpoints, no debug bar) | |

Known issues: touch reports only ~11 times per second (being fixed: the
driver's 1 ms sleeps take ~20 ms on this 100 Hz kernel); no GPU, so the UI
is software-rendered (that's why the default renders at 320x480).

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
   ./boot.sh            # default: 320x480 + touch
   ./boot.sh quiet      # 640x960, stock T4 initrd (no touch)
   ./boot.sh colour     # 640x960 with colour checkpoints (debugging early boot)
   ```

   It exploits the boot ROM (limera1n), loads a patched iBSS and openiboot,
   uploads kernel + 47 MB initrd (a few minutes) and jumps to the kernel.
3. The screen shows kernel text, the Android logo, then the home screen
   (`colour` mode first shows solid colour checkpoints, ending olive).
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
  lowres/             DEFAULT kit: 320x480 kernel + stub for initrd-touch4-lowres.bin
  initrd-touch4-lowres.bin  T4 Android 2.3.7 rootfs + n92ap touch driver,
                      /sys/power fix, density 160 (contains the author's touch cal)
  quiet/              640x960 kit without checkpoints (stock t4-initrd.bin)
  zImage kcaves.bin stub.bin  640x960 colour-checkpoint kit (stock t4-initrd.bin)
  t4-initrd.bin       stock T4 Android 2.3.7 root filesystem (gzip cpio)
tools/              host tools boot.sh/readlog.sh use
  a4boot(.c)          limera1n + iBSS loader
  dfu-upload.py       DFU upload of openiboot
  oibsend.py          upload files to openiboot (with ack check)
  oibread.py          raw memory readback via openiboot `recvfile`
  decode-rec.py       decode boot-stage records
extras/             development history and debugging material
  build/              kit builder (QUIET=1 / LOWRES=1), lowres-fb.S, pristine T4 kernel
  touch/              touch bring-up: frame decoder, capture tools, pmutool, initrd patcher
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
python3 extras/build/build-bootkit.py phone            # boot/        colour kit
QUIET=1 python3 extras/build/build-bootkit.py phone    # boot/quiet/  no checkpoints
LOWRES=1 python3 extras/build/build-bootkit.py phone   # boot/lowres/ 320x480 (needs clang, ld.lld, llvm-objcopy)
```

The LOWRES kit makes the kernel framebuffer 320x480 RGB565 with two pages,
so Android page-flips straight into it; kernel code placed over the removed
debug overlay scales each flipped page 2x to the real 640x960 screen within
~10 ms (the stock driver copied the whole screen blindly every 100 ms).
Details: `extras/docs/NOTES-2026-11-27.md`.

Notable bugs found on the way (details in `extras/docs/SESSION-2026-11-26.md`):

- A checkpoint replayed `teq r2,#3` instead of `tst r2,#3` in `__vet_atags`,
  so the kernel always ignored the ATAGs and booted with 16 MB.
- An earlier workaround left the CPU caches off, which made Android very slow.
- openiboot sometimes drops USB packets under load; `oibsend.py` now waits
  for openiboot's "Received file" ack and recovers if it's missing.

## Touchscreen

The T4 touch driver (`/sbin/t4-touch-input` in `initrd-touch4-lowres.bin`)
is patched for the iPhone 4: the controller is powered from PMU LDO12
(`pmutool set 0x16 0x02` in `t4-touch-start.sh`), chip id 0x4e31 is
accepted, frame lengths are taken from the frame itself, and the per-unit
calibration is embedded. Android also needs a fake `/sys/power` (this kernel
has no wakelocks; without it PowerManager never turns the "screen on" and
drops all touches) - see `extras/docs/NOTES-2026-11-27.md`.

**Other phones need their own calibration.** The initrd contains the
calibration of the phone it was developed on; touch may be offset or
noisy on another unit. To use yours:

1. On the phone's stock iOS, with libimobiledevice on the PC:
   `idevicediagnostics ioreg IODeviceTree multi-touch` and save the
   256-byte `multi-touch-calibration` data.
2. Write those 256 bytes into the driver at file offset **0x19d90**
   (1024-byte slot, rest zeros) - extract `sbin/t4-touch-input` from the
   initrd and patch it.
3. Rebuild the initrd and a matching stub:

   ```sh
   python3 extras/touch/cpio_patch.py boot/initrd-touch4-lowres.bin my-initrd.bin \
       sbin/t4-touch-input=t4-touch-input.mycal=0755
   QUIET=1 T4_INITRD=my-initrd.bin python3 extras/build/build-t4stub.py my-stub.bin
   ```

   and boot those two instead of `boot/initrd-touch4-lowres.bin` /
   `boot/lowres/stub.bin` (the stub carries the initrd size).

## Safety

Everything is RAM-only: the kit never writes to NAND, and a hard reset
returns the phone to iOS.
