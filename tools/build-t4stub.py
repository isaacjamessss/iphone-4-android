#!/usr/bin/env python3
"""Build the fixed-address Linux boot stub for the touch4-idroid Android payload.

Replicates the touch4-idroid handoff's verified layout, self-contained:
  kernel  copied 0x42000000 -> 0x02000000 (their stub does the same copy)
  initrd  at 0x09000000 (0x0 window: proven writable for 46 MB)
  ATAGs   at 0x100 (MEM 256M, INITRD2 at 0x09000000, machine 3564)
  jump    r0=0, r1=3564, r2=0x100, pc=0x02000000

Status colors at the framebuffer (physical 0x0F700000 per UI0 register):
  magenta = stub running, red = kernel missing at 0x02000000,
  green = kernel copied+verified (then delay, ATAGs, jump).

Usage: build-t4stub.py [out.bin]
"""
import struct
import sys

RUN = 0x04000000
KERNEL_SRC = 0x44000000          # zImage entry word hardcodes 0x44000000!
KERNEL = 0x44000000              # jump target = the zImage entry
KERNEL_LEN = 0x1493BC
KERNEL_MAGIC = 0xE51FF004
INITRD = 0x09000000
INITRD_SIZE = 0x02C5AD75
RD_KB = 0x14481
MACHINE = 3564
FB = 0x0F700000
FB_FILL_END = 0x0FA00000
DELAY = 0x00800000
MAGENTA = 0x00FF00FF
RED = 0x00FF0000
GREEN = 0x0000FF00
CMDLINE = (b"console=t4fb0 loglevel=8 ignore_loglevel rdinit=/init panic=0 "
           b"t4fb=0x0F700000 t4_test=T4_ANDROID_TOUCH_03 slub_debug=FZPU noalign")


def w(*vals):
    return b"".join(struct.pack("<I", v) for v in vals)


def build():
    cl = CMDLINE + b"\x00"
    cl_pad = cl + b"\x00" * ((-len(cl)) % 4)
    atags = b"".join([
        w(5, 0x54410001, 1, 0x1000, 0),
        w(4, 0x54410002, 0x10000000, 0),
        w(5, 0x54410004, 0, RD_KB, 0),
        w(4, 0x54420005, INITRD, INITRD_SIZE),
        w(len(cl_pad) // 4 + 2, 0x54410009), cl_pad,
        w(0, 0),
    ])
    pool_off = 0xB4
    atag_addr = RUN + pool_off + 14 * 4
    values = [FB, FB_FILL_END, MAGENTA, KERNEL_SRC, KERNEL, KERNEL_LEN,
              KERNEL_MAGIC, RED, GREEN, DELAY, atag_addr,
              atag_addr + len(atags), MACHINE,
              KERNEL + 0x20]  # entry = after the ARM vector table
                               # (vectors at +0..+0x1F are hang-stubs;
                               #  the real code starts with `b` at +0x20)

    def L(rt, slot, addr):
        return 0xE59F0000 | (rt << 12) | (pool_off + 4 * slot - (addr + 8))

    ins = [
        L(0, 0, 0x00), L(1, 1, 0x04), L(2, 2, 0x08),   # paint magenta
        0xE4802004, 0xE1500001, 0x1AFFFFFC,
        L(0, 3, 0x18), L(1, 4, 0x1C), L(2, 5, 0x20),   # copy kernel
        0xE4903004, 0xE4813004, 0xE2522004, 0x1AFFFFFB,
        L(0, 4, 0x34), 0xE5900000, L(1, 6, 0x3C),      # verify magic
        0xE1500001, 0x0A000006,                        # beq green (0x64)
        L(0, 0, 0x48), L(1, 1, 0x4C), L(2, 7, 0x50),   # paint red
        0xE4802004, 0xE1500001, 0x1AFFFFFC,
        0xEAFFFFFE,                                    # hang (fail)
        L(0, 0, 0x64), L(1, 1, 0x68), L(2, 8, 0x6C),   # paint green
        0xE4802004, 0xE1500001, 0x1AFFFFFC,
        L(3, 9, 0x7C), 0xE2533001, 0x1AFFFFFD,         # delay
        L(3, 10, 0x88), 0xE3A04C01, L(5, 11, 0x90),    # copy atags
        0xE4930004, 0xE4840004, 0xE1530005, 0x1AFFFFFB,
        0xE3A00000, L(1, 12, 0xA8), 0xE3A02C01,        # r0=0, r1=mach, r2=0x100
        L(15, 13, 0xB0),                               # ldr pc, =kernel
    ]
    assert len(ins) == 45
    stub = w(*ins) + w(*values) + atags
    assert len(w(*ins)) == 0xB4
    return stub


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "stub.bin"
    stub = build()
    open(out, "wb").write(stub)
    print("wrote %s (%d bytes)" % (out, len(stub)))
