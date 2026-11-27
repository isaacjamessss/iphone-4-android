#!/usr/bin/env python3
"""Decode the ATAG diagnostic record (PA 0x0F600000, layout in build-bootkit.py).
usage: sudo python3 tools/oiblog.py 0x0F600000 0x100 rec.txt
       python3 tools/decode-rec.py rec.txt.raw"""
import re, struct, sys

raw = open(sys.argv[1], "rb").read()
data = bytearray()
if raw[:4] in (b"STB1", b"\0\0\0\0") or len(raw) == 0x100:   # binary from tools/oibread.py
    data = bytearray(raw)
txt = "" if data else raw.decode(errors="replace")
for m in re.finditer(r"^[0-9a-fA-F]{8}:?\s+((?:[0-9a-fA-F]{2}\s+){1,16})", txt, re.M):
    data += bytes.fromhex(m.group(1).replace(" ", ""))
data = bytes(data[:0x100]).ljust(0x100, b"\0")
W = lambda o: struct.unpack_from("<I", data, o)[0]
words = lambda o: " ".join("%08x" % W(o + 4 * i) for i in range(8))
TAG_CORE = 0x54410001

def tags_ok(o):
    return W(o) in (2, 5) and W(o + 4) == TAG_CORE

def magic(o, want):
    got = data[o:o + 4]
    return "OK " if got == want else "-- (%r)" % bytes(got)

print("stub  %s r2=%08x SCTLR=%08x (M=%d C=%d) TTBR0=%08x" % (
    magic(0, b"STB1"), W(4), W(8), W(8) & 1, (W(8) >> 2) & 1, W(0xC)))
print("      @0x100 seen by stub: %s  %s" % (words(0x20), "ATAGs OK" if tags_ok(0x20) else "NOT ATAGs"))
print("k1    %s r1=%08x (%d) r2=%08x" % (magic(0x40, b"K1__"), W(0x44), W(0x44), W(0x48)))
print("      @[r2] at kernel entry: %s  %s" % (words(0x60), "ATAGs OK" if tags_ok(0x60) else "NOT ATAGs"))
v = bytes(data[0x80:0x84])
print("vet   %s" % {b"VOK!": "PASSED", b"VBAD": "FAILED (r2 := 0)"}.get(v, "not reached (%r)" % v))
print("m4    %s __atags_pointer=%08x" % (magic(0xA0, b"M4__"), W(0xA4)))
print("      @VA c0000100 before setup_arch: %s  %s" % (words(0xC0), "ATAGs OK" if tags_ok(0xC0) else "NOT ATAGs"))
