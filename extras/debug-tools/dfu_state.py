#!/usr/bin/env python3
"""Probe/advance the A4 DFU state machine after an image upload.

Reads DFU status, sends the zero-length end-of-download, prints the state
transitions, and optionally sends a DFU "go" command.

Usage: dfu_state.py [--go]
"""
import sys
import time

import usb.core
from usb.core import USBError

VID, PID = 0x05AC, 0x1227

STATE = {
    0: "appIDLE", 1: "appDETACH", 2: "dfuIDLE", 3: "dfuDNLOADSYNC",
    4: "dfuDNLOAD", 5: "dfuDNLOADIDLE", 6: "dfuMANIFESTSYNC",
    7: "dfuMANIFEST", 8: "dfuMANIFESTWAITRESET", 9: "dfuUPLOADIDLE",
    10: "dfuERROR",
}


def status(dev):
    try:
        st = dev.ctrl_transfer(0xA1, 3, 0, 0, 6, 2000)
        return st[4]
    except USBError as exc:
        return "err(%s)" % exc


def show(dev, label):
    s = status(dev)
    print("%-22s %s %s" % (label, s, STATE.get(s, "")))


def main(do_go):
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        sys.exit("no 05ac:1227 DFU device")
    try:
        dev.set_configuration()
    except Exception:
        pass

    show(dev, "before")
    print("sending zero-length DNLOAD")
    try:
        dev.ctrl_transfer(0x21, 1, 0, 0, None, 1000)
    except USBError as exc:
        print("  zlp:", exc)
    time.sleep(0.2)
    show(dev, "after zlp")
    for i in range(3):
        time.sleep(0.2)
        show(dev, "poll %d" % i)

    if do_go:
        print("sending 'go' (0x40/0)")
        try:
            dev.ctrl_transfer(0x40, 0, 0, 0, b"go\x00", 1000)
        except USBError as exc:
            print("  go:", exc)
        time.sleep(1)
        show(dev, "after go")


if __name__ == "__main__":
    main("--go" in sys.argv)
