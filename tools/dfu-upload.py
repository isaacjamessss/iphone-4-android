#!/usr/bin/env python3
"""A4 DFU image uploader that replicates old libirecovery's semantics.

Two modes:
  default        upload chunks, then manifest (zero-length DNLOAD + status +
                 USB reset). Use this for the iBSS stage.
  --go "CMD"     upload chunks, then send a DFU command (0x40/0). Use this to
                 start openiboot from iBSS: --go "go jump 0x41000000".

Usage: dfu-upload.py [--no-reset] [--go CMD] <image>
"""
import sys

import usb.core

VID, PID = 0x05AC, 0x1227
CHUNK = 0x800
DFU_DNLOAD_IDLE = 5


def main(path, do_reset=True, go_cmd=None):
    data = open(path, "rb").read()
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        sys.exit("no 05ac:1227 DFU device")

    try:
        dev.set_configuration()
    except Exception as exc:
        print("set_configuration:", exc)

    sent = 0
    for off in range(0, len(data), CHUNK):
        chunk = data[off:off + CHUNK]
        got = dev.ctrl_transfer(0x21, 1, 0, 0, chunk, 2000)
        if got != len(chunk):
            sys.exit("short write at %d: %d/%d" % (off, got, len(chunk)))
        status = dev.ctrl_transfer(0xA1, 3, 0, 0, 6, 2000)
        if status[4] != DFU_DNLOAD_IDLE:
            sys.exit("bad DFU status %d at offset %d" % (status[4], off))
        sent += len(chunk)

    print("uploaded %d bytes in %d chunks" % (sent, (len(data) + CHUNK - 1) // CHUNK))

    if go_cmd:
        print("sending %r" % go_cmd)
        dev.ctrl_transfer(0x40, 0, 0, 0, go_cmd.encode() + b"\x00", 2000)
        print("sent")
        return

    # Zero-length DNLOAD: bootrom manifests the image and jumps to it
    # (after the host resets the bus).
    dev.ctrl_transfer(0x21, 1, 0, 0, None, 0)
    for _ in range(3):
        try:
            dev.ctrl_transfer(0xA1, 3, 0, 0, 6, 2000)
        except Exception as exc:
            print("status read:", exc)
    if do_reset:
        try:
            dev.reset()
            print("bus reset issued")
        except Exception as exc:
            print("reset:", exc)

    print("manifested")


if __name__ == "__main__":
    argv = sys.argv[1:]
    do_reset = "--no-reset" not in argv
    go_cmd = None
    if "--go" in argv:
        i = argv.index("--go")
        go_cmd = argv[i + 1]
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        sys.exit("usage: dfu-upload.py [--no-reset] [--go CMD] <image>")
    main(args[0], do_reset, go_cmd)
