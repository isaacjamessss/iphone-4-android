> Repo note: this is the development folder from the porting PC. Booting is
> now done with `./boot.sh` (default = touch). Not included here: the
> per-phone files (`mtcal-n92.bin`, `ioreg-devicetree-live.plist`), raw
> captures, the IPSW device tree/kernelcache extracts, and the intermediate
> initrd/driver variants. The final driver is inside
> `boot/initrd-touch4-lowres.bin`; `touch4/` holds the scripts added to it.

# touch/ - iPhone 4 (n92ap) touchscreen bring-up

## Quick start (next session)
1. `./boot-touch.sh` (phone in DFU) - boots initrd-touch3 (best so far).
   `./boot-touch.sh bootanim` = same + stock Gingerbread boot animation.
   Add `quiet` (e.g. `./boot-touch.sh quiet`) = no rainbow checkpoints
   (bootkit/quiet/ + stub-*-quiet.bin; built with QUIET=1, untested on phone yet).
2. `./capture-touch.sh` (interactive) or `./capture-touch.sh --auto 6`:
   step 1 records the input events Android gets (KEY QUESTION: does the
   driver emit real touches now?), steps 2-5 capture frames with no finger /
   top-left / bottom-right / centre and decode them -> capture-*/summary.txt

## What's in here
| file | what |
|---|---|
| boot-touch.sh | DFU/openiboot -> Android with a touch initrd (+ matching stub) |
| capture-touch.sh | controlled capture: getevent + driver SPI buffer snapshots |
| n1frame.py | find + decode N1/Zephyr2 frames in memory dumps |
| initrd-touch3(-bootanim).bin + stub-*.bin | built initrds; stub size MUST match |
| cpio_patch.py | rewrite stock initrd replacing/adding files (byte-exact round trip) |
| t4-touch-input-n92len | driver in touch3: chip id 0x4e31 + own cal + frame-length fix |
| t4-touch-input-n92 | without the frame-length fix |
| t4-touch-input-n92d5 | frame SPI clkdiv 5 - WORSE, don't use |
| t4-touch-start.sh | service script: pmutool set 0x16 0x02 (LDO12) then driver |
| pmutool, src/pmutool.c | PMU I2C read/write via /dev/mem |
| memdump, src/memdump.c | ptrace /proc/pid/mem dumper (kernel 3.0 needs ptrace) |
| mtcal-n92.bin | THIS phone's touch calibration (has a serial - never publish) |
| ioreg-devicetree-live.plist | live iOS 6.1.3 device tree (idevicediagnostics) |
| devicetree-n92ap-5.1.1.bin, adt.py, img3dec.py, lzss.py | IPSW DT + tools |
| init.rc.bootanim | init.rc with boot animation enabled |
| capture/stk*.bin | first raw captures (random taps) |

## Frame format (verified, all checksums valid)
`EA|EB, seq, L(u16), ?` then payload; checksum = sum(bytes[5:L+3]) == u16 at [L+3].
Payload = Zephyr2: 24 B header (type 0x44, frame#, hlen 0x18, u32 ts, ...,
[16]=numFingers, [17]=fingerLen 0x1e) + 30 B fingers: id, event, ?, ?,
s16 x (0..5000), s16 y (0..7500), relx, rely, size maj/min, orient, force maj/min.
Events seen: 3 = moving, 4 = touching, 7 = lift, 0 = empty slot (force 0,0).
T4 parser offsets match this (x f+4, y f+6 flipped 7500-y, skip if force==0).
