#!/usr/bin/env python3
"""Robust openiboot ACM sender (0525:1280) — replaces OiBC's fragile file upload.

Speaks openiboot's ACM stream protocol (acm/acm.c):
  - a command line ("sendfile <addr> <len>", "go <addr>", ...) is one chunk
  - following bulk data is memcpy'd to <addr> until <len> bytes arrive

Every write is retried on transient USB errors (EINTR etc.), and an optional
console drain thread prints openiboot's ACM output to stderr.

Usage:
  oibsend.py up FILE ADDR     upload FILE to openiboot memory at ADDR
  oibsend.py cmd TEXT         send one console command
  oibsend.py console          attach and print ACM console output
"""
import sys
import threading
import time

import usb.core
import usb.util

VID, PID = 0x0525, 0x1280
EP_OUT, EP_IN = 0x02, 0x81
CHUNK = 0x4000


class OIB:
    def __init__(self, drain=True):
        self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        if self.dev is None:
            sys.exit("no 0525:1280 openiboot device (is openiboot up?)")
        try:
            cfg = self.dev.get_active_configuration()
        except usb.core.USBError:
            cfg = None
        if cfg is None:
            self.dev.set_configuration()
        try:
            usb.util.claim_interface(self.dev, 0)
        except Exception:
            pass
        self._stop = threading.Event()
        if drain:
            threading.Thread(target=self._drain, daemon=True).start()

    def _drain(self):
        while not self._stop.is_set():
            try:
                data = self.dev.read(EP_IN, 4096, timeout=500)
                sys.stderr.write(data.tobytes().decode(errors="replace"))
                sys.stderr.flush()
            except usb.core.USBError:
                pass
            except Exception:
                return

    def write(self, data, timeout=5000):
        for attempt in range(5):
            try:
                self.dev.write(EP_OUT, data, timeout=timeout)
                return
            except usb.core.USBError as exc:
                print("write retry %d: %s" % (attempt + 1, exc), file=sys.stderr)
                time.sleep(0.5)
        sys.exit("write failed after retries")

    def cmd(self, text):
        self.write(text.encode() + b"\n")
        time.sleep(0.1)

    def up(self, path, addr):
        data = open(path, "rb").read()
        print("uploading %s (%d bytes) -> 0x%x" % (path, len(data), addr))
        self.write(b"sendfile 0x%x %d\n" % (addr, len(data)))
        time.sleep(0.1)
        sent = 0
        while sent < len(data):
            n = min(CHUNK, len(data) - sent)
            self.write(data[sent:sent + n], timeout=10000)
            sent += n
            if sent % (4 << 20) < CHUNK:
                print("  %d / %d" % (sent, len(data)), flush=True)
        print("done: %d bytes at 0x%x" % (len(data), addr))

    def close(self):
        self._stop.set()
        time.sleep(0.2)


def main():
    args = sys.argv[1:]
    if len(args) >= 1 and args[0] == "console":
        OIB(drain=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        return
    if len(args) >= 1 and args[0] == "boot":
        # one session for everything: openiboot's ACM wedges across reopen
        # (set_configuration resets its gadget endpoints mid-conversation).
        # boot [--pre CMD]... FILE ADDR [FILE ADDR ...] [--go CMD]
        rest = args[1:]
        go, pres = None, []
        while "--pre" in rest:
            i = rest.index("--pre")
            pres.append(rest[i + 1])
            del rest[i:i + 2]
        if "--go" in rest:
            i = rest.index("--go")
            go = " ".join(rest[i + 1:])
            rest = rest[:i]
        if len(rest) < 2 or len(rest) % 2:
            sys.exit("usage: oibsend.py boot [--pre CMD]... FILE ADDR [...] [--go CMD]")
        oib = OIB()
        try:
            # A bus reset unwedges a wedged ACM (writes time out after a prior
            # abort) and is harmless when healthy. Uploads restart from scratch
            # on failure: openiboot's ACM occasionally stalls under load.
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    oib.dev.reset()
                except Exception:
                    pass
                time.sleep(2)
                oib = OIB()  # re-find after re-enumeration
                try:
                    for c in pres:
                        print("pre: %s" % c)
                        oib.cmd(c)
                        time.sleep(1)
                    for f, a in zip(rest[::2], rest[1::2]):
                        oib.up(f, int(a, 0))
                    if go:
                        print("sending: %s" % go)
                        oib.cmd(go)
                    time.sleep(1)
                    break
                except SystemExit:
                    if attempt == max_attempts:
                        raise
                    print("attempt %d failed; bus-resetting and retrying" % attempt)
                    time.sleep(2)
        finally:
            time.sleep(0.5)  # let the console drain print the tail
            oib.close()
        return
    oib = OIB()
    try:
        if args[0] == "up" and len(args) == 3:
            oib.up(args[1], int(args[2], 0))
        elif args[0] == "cmd" and len(args) >= 2:
            oib.cmd(" ".join(args[1:]))
        else:
            sys.exit(__doc__)
    finally:
        time.sleep(0.3)  # let the console drain print the tail
        oib.close()


if __name__ == "__main__":
    main()
