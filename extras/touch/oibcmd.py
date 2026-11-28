#!/usr/bin/env python3
# run openiboot console commands and print their output (READ-ONLY use)
import sys, time
sys.path.insert(0, "/home/isaacjames/Desktop/1125262206/iphone33-android/tools")
from oibsend import OIB
o = OIB(drain=False)
import threading, usb.core
from oibsend import EP_IN
buf = bytearray(); stop = False
def rd():
    while not stop:
        try: buf.extend(o.dev.read(EP_IN, 16384, timeout=200).tobytes())
        except usb.core.USBError: pass
t = threading.Thread(target=rd, daemon=True); t.start()
for c in sys.argv[1:]:
    assert not c.startswith(("mtd_write", "nvram", "go", "reboot")), c
    o.write((c + "\n").encode()); time.sleep(4)
time.sleep(2); stop = True; t.join()
sys.stdout.write(buf.decode(errors="replace"))
