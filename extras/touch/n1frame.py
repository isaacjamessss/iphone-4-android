#!/usr/bin/env python3
"""Find and decode iPhone 4 (n90/n92, N1F55) multitouch frames.

Frames come off SPI1 as:  [0]=0xEA/0xEB  [1]=seq  [2:4]=L (u16 LE)  [4]=?
then the payload; checksum = sum(bytes[5 : L+3]) & 0xffff == u16 LE at [L+3].

Payload (from byte 5) is Apple's Zephyr2 layout (cf. openiboot
plat-s5l8900/multitouch-z2.c MTFrameHeader / FingerData):
  header (24 B): type(0x44) frameNum headerLen(0x18) unk3 | u32 timestamp |
                 u8 unk[4] | u16 unkC | u16 isImage | u8 numFingers |
                 u8 fingerDataLen(0x1e) | 6 B unk
  finger (fingerDataLen B): id event unk2 unk3 | s16 x | s16 y | s16 relX |
                 s16 relY | u16 sizeMajor | u16 sizeMinor | u16 orientation |
                 u16 forceMajor | u16 forceMinor | ...
Usage:
  n1frame.py FILE...          decode every checksum-valid frame found in the
                              files (raw memory dumps, e.g. touch/capture/*.bin)
"""
import re
import struct
import sys


def frames(blob):
    """yield checksum-valid frames found anywhere in a memory dump"""
    for m in re.finditer(rb"[\xea\xeb][\x00-\x03]..", blob, re.S):
        i = m.start()
        L = blob[i + 2] | blob[i + 3] << 8
        if not 2 <= L <= 0x294:
            continue
        x = blob[i:i + L + 5]
        if len(x) == L + 5 and sum(x[5:L + 3]) & 0xFFFF == (x[L + 3] | x[L + 4] << 8):
            yield x


def decode(x):
    p = x[5:]
    hdr = dict(type=p[0], frame=p[1], hlen=p[2], ts=struct.unpack_from("<I", p, 4)[0],
               nfing=p[16], flen=p[17])
    fingers = []
    o = hdr["hlen"]
    for _ in range(hdr["nfing"]):
        if o + 16 > len(p) or hdr["flen"] < 16:
            break
        fid, ev, u2, u3 = p[o:o + 4]
        fx, fy, rx, ry = struct.unpack_from("<hhhh", p, o + 4)
        smaj, smin, orient, fmaj, fmin = struct.unpack_from("<HHHHH", p, o + 12)
        fingers.append(dict(id=fid, ev=ev, x=fx, y=fy, rx=rx, ry=ry, size=(smaj, smin),
                            orient=orient, force=(fmaj, fmin)))
        o += hdr["flen"]
    return hdr, fingers


def main(paths):
    seen = set()
    for path in paths:
        for x in frames(open(path, "rb").read()):
            if x in seen:
                continue
            seen.add(x)
            hdr, fingers = decode(x)
            fs = "  ".join("id%d ev%d x=%d y=%d size=%s force=%s" % (
                f["id"], f["ev"], f["x"], f["y"], f["size"], f["force"]) for f in fingers)
            print("%-14s L=%-3d type=%02x frame=%02x n=%d  %s" % (
                path.split("/")[-1], len(x) - 5, hdr["type"], hdr["frame"], hdr["nfing"], fs))


if __name__ == "__main__":
    main(sys.argv[1:] or sys.exit(__doc__))
