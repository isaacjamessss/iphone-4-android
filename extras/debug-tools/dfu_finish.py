#!/usr/bin/env python3
"""Try DFU-native ways to leave dfuMANIFESTWAITRESET without a bus reset.

Usage: dfu_finish.py [detach|go]
"""
import sys
import time

import usb.core
from usb.core import USBError

VID, PID = 0x05AC, 0x1227

STATE = {2: "dfuIDLE", 5: "dfuDNLOADIDLE", 6: "dfuMANIFESTSYNC",
         7: "dfuMANIFEST", 8: "dfuMANIFESTWAITRESET", 10: "dfuERROR"}


def state(dev):
    try:
        st = dev.ctrl_transfer(0xA1, 3, 0, 0, 6, 2000)
        return st[4]
    except USBError as exc:
        return "err(%s)" % exc


def main(mode):
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        sys.exit("no device")
    try:
        dev.set_configuration()
    except Exception:
        pass
    s = state(dev)
    print("before:", s, STATE.get(s, ""))

    if mode == "detach":
        print("sending DFU_DETACH (0x21/0, wValue=1000)")
        try:
            dev.ctrl_transfer(0x21, 0, 1000, 0, None, 1000)
        except USBError as exc:
            print("  detach:", exc)
    elif mode == "go":
        print("sending 'go' (0x40/0)")
        try:
            dev.ctrl_transfer(0x40, 0, 0, 0, b"go\x00", 1000)
        except USBError as exc:
            print("  go:", exc)

    time.sleep(1.5)
    s = state(dev)
    print("after: ", s, STATE.get(s, ""))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "detach")
