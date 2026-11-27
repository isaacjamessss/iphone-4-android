#!/usr/bin/env python3
"""Fast raw memory readback through openiboot's ACM 'recvfile' command
(acm/acm.c: device streams raw bytes over bulk IN, no hexdump, no fb drawing).
Replaces tools/oiblog.py (hexdump drawn on the fb console, ~2 min / 4 KB).
usage: sudo python3 tools/oibread.py ADDR LEN OUT
Writes raw bytes to OUT. For the printk buffer (PA 0x0028FCE0, 0x20000) it
also writes OUT.txt with NULs stripped."""
import os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import usb.core
from oibsend import OIB, EP_IN

addr = int(sys.argv[1], 0)
ln = int(sys.argv[2], 0)
out = sys.argv[3]
oib = OIB(drain=False)
# flush pending console text
t = time.time()
while time.time() - t < 0.5:
    try:
        oib.dev.read(EP_IN, 16384, timeout=100)
    except usb.core.USBError:
        pass
oib.write(("recvfile 0x%x %d\n" % (addr, ln)).encode())
buf = bytearray()
hdr = None
idle = time.time()
while time.time() - idle < 3.0:
    try:
        buf += oib.dev.read(EP_IN, 65536, timeout=500).tobytes()
        idle = time.time()
    except usb.core.USBError:
        continue
    if hdr is None:
        m = re.search(rb"ACM: Starting File: (\d+) (\d+)\n", buf)
        if m:
            hdr = m
    if hdr and len(buf) - hdr.end() >= ln:
        break
oib.close()
if hdr is None:
    sys.exit("no 'Starting File' header; got %d bytes: %r" % (len(buf), bytes(buf[:200])))
data = bytes(buf[hdr.end():hdr.end() + ln])
open(out, "wb").write(data)
print("read %d / %d bytes at 0x%x -> %s" % (len(data), ln, addr, out))
s = data.replace(b"\0", b"").decode(errors="replace")
if "Linux version" in s:
    open(out + ".txt", "w").write(s)
    print("LOG FOUND -> %s.txt" % out)
