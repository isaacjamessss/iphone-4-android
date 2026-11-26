#!/usr/bin/env python3
"""Send the zero-length DFU_DNLOAD that tells the A4 bootrom to execute the
image it just downloaded. Equivalent to old libirecovery's dfuNotifyFinished=1."""
import sys

import usb.core

VID, PID = 0x05AC, 0x1227

dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    sys.exit("no 05ac:1227 DFU device found")

try:
    dev.set_configuration()
except Exception as exc:  # already configured / busy
    print("set_configuration:", exc)

try:
    dev.ctrl_transfer(0x21, 1, 0, 0, None, 0)
    print("ZLP (DFU_DNLOAD, 0 bytes) sent")
except Exception as exc:
    sys.exit("ZLP failed: %s" % exc)
