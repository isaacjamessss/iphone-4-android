#!/usr/bin/env python3
"""Print USB identity of attached Apple devices: VID:PID + serial (SRTG/CPID/...).

The DFU serial string contains SRTG:iBoot-XXX, which tells which stage is
running:
  SRTG:iBoot-574.4        -> bootrom DFU (clean or pwned)
  any other SRTG          -> iBSS loaded (openiboot upload possible)
Usage: python3 usbstate.py
"""
import usb.core

for dev in usb.core.find(find_all=True, idVendor=0x05AC):
    try:
        serial = usb.util.get_string(dev, dev.iSerialNumber) or "?"
    except Exception:
        serial = "<unreadable>"
    print("%03d:%03d  %04x:%04x  %s" % (dev.bus or 0, dev.address or 0,
                                        dev.idVendor, dev.idProduct, serial))
