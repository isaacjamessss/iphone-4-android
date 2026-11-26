# openiboot port: iPhone 4 CDMA (iPhone3,3 / n92ap)

Status: **scaffolded; build graph validated by an SCons dry run. Not yet compiled with a real ARM toolchain, not yet booted.**

## Why this port exists

Upstream `iDroid-Project/openiBoot` ships one iPhone 4 target:

| Target | Board | MACH_ID | Radio module |
|---|---|---|---|
| `iPhone4` | n90ap (iPhone3,1, GSM) | 3563 | `radio-xgold618` |

`iPhone3,3` is **n92ap**: same A4 / S5L8930 application processor and 512 MB
RAM, but a Qualcomm MDM6600 baseband instead of the Infineon X-Gold 618, plus
a different antenna/board layout. No bootloader, kernel, or Android tree
supports n92ap.

## What was added

- `plat-a4/iPhone4CDMA.SConscript` — target `iPhone4CDMA`, output
  `iphone_4_cdma_openiboot.bin`, define `CONFIG_IPHONE_4_CDMA`, **no**
  `radio-xgold618` module.
- `plat-a4/SConscript` — registers the new target.
- `Makefile` — `PLATFORM=IPHONE4CDMA`.
- `CONFIG_IPHONE_4_CDMA` added alongside `CONFIG_IPHONE_4` in:
  - `plat-a4/includes/hardware/a4.h` (RAM end `0x60000000`)
  - `plat-a4/includes/hardware/clcd.h` (framebuffer `0x5F700000`, DISPLAYID 0)
  - `plat-a4/clcd.c` (GPIO 0x207 pulldown)
  - `plat-a4/h2fmi.c` (NAND chip/board/timing tables)
- Build system made Python 3 / SCons 4 compatible (`has_key` → `in`).

## Open questions to resolve before trusting it

1. **MACH_ID 3565 is provisional.** It is only used as the Linux ATAG machine
   number (`actions.c`), so it does not affect openiboot booting or the
   console. Verify against the n92ap device tree before booting a kernel.
2. **Display.** n92ap reuses DISPLAYID 0 (iPhone 4 panel). Gamma tables in
   `plat-a4/clcd.c` are selected for `CONFIG_A4`; panel ID handshake differs
   between GSM and CDMA boards in some iOS builds. Verify with `pinot_panel_id`.
3. **NAND.** The h2fmi chip/board tables are copied from n90ap. **Do not use
   them** — the A4 warning in upstream's README applies: NAND writes can cause
   permanent block damage. RAM-load only.
4. **PMU / clock init.** Assumed identical (Dialog D1815 class). This is the
   most likely place bring-up fails; expect to need a UART or USB early log.
5. **Baseband.** MDM6600 is not driven at all. That is fine for a console, and
   fatal for calls/SMS/data later.

## Boot path (non-destructive)

A4 has no persistent openiboot install: **every boot is a RAM load.**

```
power off
  -> DFU (Power 3s, +Home 10s, release Power, hold Home 10s; screen black)
  -> limera1n pwn (bootrom exploit; n92ap is vulnerable, CPID 0x8930 / BDID 6)
  -> upload iphone_4_cdma_openiboot.bin into RAM
  -> openiboot console (USB)
```

Nothing is written to NAND, so the iOS 5 untethered install is untouched and
a normal power cycle returns to iOS.

Tooling candidates for the pwn+upload step (decide and verify at Stage 1):
`syringe`/`loadibec` (iDroid, Linux), `redsn0w` "Just boot" (Windows) followed
by `irecovery -f`, or `oibc` once openiboot is running.

## Next milestones

1. Compile `iPhone4CDMA` cleanly (expect old-code vs modern-GCC warnings).
2. Get the openiboot console over USB on real hardware.
3. Only then: n92ap device tree for mainline Linux, minimal initramfs.
4. Android userspace is out of scope until display + touch + block storage
   exist in the kernel — they do not, for any A4 phone.

## Bring-up log (2026-11-22)

Build is done and hardware bring-up reached the manifest stage.

| Step | Result |
|---|---|
| `scons iPhone4CDMA` | 245,784 B `iphone_4_cdma_openiboot.bin`, ARMv7 EXEC, entry 0x0 |
| n90ap control build | 309,912 B (same structure, minus X-Gold radio) |
| Device identity | `MODEL: n92ap`, `PRODUCT: iPhone3,3`, CPID 0x8930, BDID 0x06 |
| limera1n (native Windows tool) | `PWND: limera1n` confirmed by irecovery |
| `iBSS.n92ap` | extracted from 5.1.1 (9B206) IPSW via HTTP ranges, AES-decrypted, 65,536 B |
| iBSS upload | 32/32 chunks, DFU status 5 each |
| Manifest | `dfuMANIFESTWAITRESET` (state 8) — image accepted |

### Blocker: the bus reset

The A4 bootrom only jumps to a downloaded image after a **USB bus reset**.
Over USB/IP that cannot be delivered:

- `libusb_reset_device` resets the *virtual* vhci port, never the phone.
- `usbipd detach`/`attach` and a physical replug produce a disconnect, which
  returns DFU to `dfuIDLE` and discards the manifest.
- `DFU_DETACH` and a DFU `go` command are both ignored.
- On Windows, libusb only performs a real reset through the **libusbK /
  libusb0** back-ends (`ResetDevice`); WinUSB has no device reset.

Resolutions, in order of preference:

1. Run the uploader on native Linux (live USB) — `libusb_reset_device` is a
   real port reset there.
2. Bind the DFU device to libusbK on Windows and run the uploader natively.
3. Rework the flow so the image is executed by the pwned bootrom without a
   manifest reset (custom limera1n-style payload) — research project.

Nothing here writes NAND. A power cycle always returns to iOS.

### 2026-11-24: moved to native Linux

The project now lives on a native Linux host (`~/Documents/Default
Project/iphone33-android`). This is resolution #1 from the blocker list above:
on native Linux `libusb_reset_device()` issues a real `USBDEVFS_RESET` port
reset, so the manifest-reset blocker does not exist. All four artifact
SHA-256s re-verified against HANDOFF §4.

- `tools/linux-stage1.sh` — end-to-end Stage 1 driver for Linux (deps via
  apt/dnf/pacman/zypper/apk, compiles `a4boot`, DFU check via `lsusb`,
  pwn + iBSS with `reset`, openiboot upload, waits for VID 0x0525, opens
  picocom on `/dev/ttyACM*`).
- Caveat: the OpenCode agent session runs inside a Flatpak sandbox
  (`ai.opencode.opencode`) with no `/dev/bus/usb` and no
  `org.freedesktop.Flatpak` host access, so USB steps must run on the host
  (either grant the flatpak `--talk-name=org.freedesktop.Flatpak` and restart,
  or run the script in a host terminal).

### 2026-11-24: first real pwn — three fixes to the Stage 1 flow

First run on native Linux failed: `a4boot`'s iBSS upload died with
`bad DFU status 10 (dfuERROR)` at chunk 2. Comparing against syringe's
reference (`Chronic-Dev/syringe: syringe/exploits/limera1n/limera1n.c`,
`syringe/libirecovery.c`, `exploits/limera1n/limera1n.S`) found three
discrepancies, all now fixed in `tools/a4boot.c`:

1. **Wrong image.** The 584-byte payload is pod2g's `limera1n.S` build
   (verified byte-identical to syringe `external/Win32/limera1n.h`). It
   calls the bootrom's `usb_wait_for_image(0x84000000, 0x2c000)` and then
   **searches the received image for IMG3 DATA + KBAG tags and GID-decrypts
   it itself**. So the upload must be the encrypted `iBSS.n92ap.img3`
   (68,100 B), NOT the decrypted `iBSS.n92ap.bin` as previously assumed —
   a raw .bin fails the tag search and the payload just waits again.
   The payload then patches RSA/perm/tag checks AND the `go` handler to
   `BX 0x41000000`, which is why `--go "go jump 0x41000000"` boots openiboot.
2. **Stalling write.** syringe's non-Apple path is a plain synchronous
   control transfer with a 10 ms timeout (`libusb_control_transfer(..., 10)`).
   The async-submit/cancel in `a4boot` was a USB/IP workaround and a
   fidelity risk; replaced with the reference behaviour.
3. **Missing `irecv_finish_transfer`.** After the trigger, syringe does
   `irecv_reset` + `irecv_finish_transfer` (DNLOAD(0) + 3x GETSTATUS + reset)
   + reconnect before uploading the image. Without it the DFU state machine
   is left corrupted (that is the dfuERROR at chunk 2).

With all three fixed: 34/34 chunks uploaded, manifest + reset OK, and the
USB serial changed `SCEP:01 IBFL:00 SRTG:[iBoot-574.4]` → `SCEP:02 IBFL:03`
(no SRTG) — firmware state advanced. An accidental empty manifest
(`tools/dfu_state.py` is a DESTRUCTIVE probe that advances the DFU state
machine — never use it mid-flow) crashed iBSS, which watchdog-rebooted into
iOS (`05ac:129c`), proving iBSS was executing. Nothing touches NAND.

Remaining to Stage 1: re-enter DFU, run the now-proven a4boot sequence, then
`dfu-upload.py --go "go jump 0x41000000" artifacts/iphone_4_cdma_openiboot.bin`
and grab the openiboot ACM console (VID 0x0525, `/dev/ttyACM*`).

Note: this payload does NOT patch the USB serial with `PWND:` — verify pwn
by the SRTG/serial change instead (`tools/usbstate.py`).

### 2026-11-24: iBSS manifest-boot reverse-engineered (Stage 1 endgame)

The 5.1.1 n92ap iBSS has **no command parser** (no `go`/`getenv` strings at
all), so syringe's `go jump 0x41000000` flow can never work on it — the
syringe `FP_CMD` patterns are 4.x-era and none of the six payload patch
patterns exist in this image. The only boot path is Apple's restore one:
**DFU upload + manifest + USB reset makes iBSS image3-load and execute the
uploaded image** (how iBEC normally gets loaded).

RE of `iBSS.n92ap.bin` (capstone, host wheel install) mapped the loader:

- DFU receive buffer is `0x4ff00000`, max `0x100000` (explains why the
  245 KB openiboot upload worked).
- `image3_load` (lib/image/image3/image3_wrapper.c) validates the image
  (`validate_signature` with ECID/NONC/SHSH/CERT, plus PROD/CHIP/TYPE/BORD
  constraints; expected ident for the manifest path is `'ibec'` =
  0x69626563), then `decrypt_payload` (KBAG/GID; skipped when no KBAG),
  then `copyobject` copies the DATA payload to the load address and the
  caller executes it (`"executing image..."` at decrypted 0x982).
- On validation failure with flags bit1 clear (manifest path passes flags=1)
  it checks an "untrusted images are permitted" policy
  (`bl 0x84008178(1)`, decrypted 0x5d48) and otherwise bails via `beq.w`
  at decrypted offset **0x5d52**.

The policy denies untrusted images in this build (verified empirically:
uploading an unsigned wrapper to running iBSS was rejected, iBSS returned
to dfuIDLE). `tools/img3_repack.py` therefore:

- `untrust-ibss` — NOPs the `beq.w` at decrypted 0x5d52 in
  `iBSS.n92ap.img3` (AES-256-CBC re-encrypt with the published KBAG
  key/iv, everything else kept verbatim) -> `artifacts/iBSS.n92ap-untrust.img3`.
  With it, every validation failure falls through to the
  "image validation failed but untrusted images are permitted" path.
- `wrap` — builds a minimal unsigned IMG3 (ident `ibec`, TYPE+DATA, no
  KBAG -> no decryption) around raw openiboot -> `artifacts/openiboot-n92ap.img3`.
  openiboot's `entry.sx` ArmReset computes its runtime address PC-relative
  and relocates itself to 0x0, so the exact execute address does not matter.

Final chain: DFU -> `a4boot` (pwn + untrust iBSS.img3 + manifest + reset)
-> iBSS runs -> `dfu-upload.py openiboot-n92ap.img3` (manifest + reset) ->
iBSS image3-loads and executes openiboot -> VID 0x0525 ACM console.

### Tooling in `tools/`

| File | Purpose |
|---|---|
| `build-openiboot.sh` | install deps + build `iPhone4CDMA` |
| `sync.sh` | rsync the Windows tree into WSL |
| `ipsw_fetch.py` | pull one member from a remote IPSW by HTTP range |
| `img3_payload.py` | extract + AES-CBC decrypt an IMG3 DATA payload |
| `dfu-upload.py` | chunked DFU upload + manifest (`--no-reset` for usbip) |
| `dfu_state.py` | read/advance DFU state machine |
| `dfu_finish.py` | probe DFU_DETACH / go |
| `limera1n.py`, `limera1n_async.c`, `a4boot.c` | limera1n implementations (USB/IP aborts are local-only, so these cannot pwn over usbip) |
