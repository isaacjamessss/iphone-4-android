#!/usr/bin/env python3
"""Read the dead kernel's printk buffer back through openiboot (needs DRAM
retention across the DFU reset). __log_buf = VA 0xC028FCE0 -> PA 0x0028FCE0,
0x20000 bytes (found via the log_buf/log_buf_len pair at VA 0xC0275AA4).
usage: sudo python3 tools/oiblog.py [ADDR] [LEN] [OUT]
Writes the raw openiboot hexdump to OUT.raw and decoded text to OUT."""
import os, re, sys, time, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import usb.core
from oibsend import OIB, EP_IN

addr = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x0028FCE0
ln = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x20000
out = sys.argv[3] if len(sys.argv) > 3 else "kernel-log.txt"
oib = OIB(drain=False)
buf = bytearray()
STEP = 0x1000   # small pieces: openiboot's bufferPrintf buffer is finite
for a in range(addr, addr + ln, STEP):
    oib.cmd("hexdump 0x%x %d" % (a, min(STEP, addr + ln - a)))
    idle = time.time()
    while time.time() - idle < 1.0:
        try:
            buf += oib.dev.read(EP_IN, 16384, timeout=300).tobytes(); idle = time.time()
        except usb.core.USBError:
            pass
    print("\r0x%x" % a, end="", file=sys.stderr, flush=True)
oib.close()
txt = buf.decode(errors="replace")
open(out + ".raw", "w").write(txt)
data = bytearray()
for m in re.finditer(r"^[0-9a-fA-F]{8}:?\s+((?:[0-9a-fA-F]{2}\s+){1,16})", txt, re.M):
    data += bytes.fromhex(m.group(1).replace(" ", ""))
s = data.replace(b"\0", b"").decode(errors="replace")
open(out, "w").write(s)
print("hexdump %d chars, %d bytes decoded -> %s" % (len(txt), len(data), out))
print("Linux version" in s and "LOG FOUND (DRAM retained)" or "no 'Linux version' in buffer")
