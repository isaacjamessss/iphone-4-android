#!/usr/bin/env python3
"""Extract and decrypt the DATA payload of an IMG3 (iBSS/iBEC/LLB).

The A4 bootrom DFU takes the *decrypted payload*, not the IMG3 container, so
this strips the container and applies AES-128-CBC with the published IV/key.

Usage: img3_payload.py <in.img3> <iv-hex> <key-hex> <out.bin>
"""
import struct
import sys

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

TAGS = {b"DATA", b"KBAG", b"SHSH", b"CERT", b"SEPO", b"TYPE", b"BORD", b"ECID"}


def main(src, iv_hex, key_hex, dst):
    blob = open(src, "rb").read()
    if blob[:4] != b"3gmI":
        raise SystemExit("not an IMG3 (magic %r)" % blob[:4])

    full_size, data_size, sig_area, ident = struct.unpack_from("<IIII", blob, 4)
    print("IMG3 ident=%08x dataSize=%d fullSize=%d" % (ident, data_size, full_size))

    off = 20
    payload = None
    while off + 12 <= len(blob):
        tag = blob[off:off + 4][::-1]   # 4CC stored as a little-endian uint32
        if tag not in TAGS:
            break
        total_len, data_len = struct.unpack_from("<II", blob, off + 4)
        print("  tag %s total=%d data=%d at %d" % (tag.decode(), total_len, data_len, off))
        body = blob[off + 12:off + 12 + data_len]
        if tag == b"DATA":
            payload = body
        if total_len == 0:
            break
        off += total_len
    if payload is None:
        raise SystemExit("no DATA tag found")

    iv = bytes.fromhex(iv_hex)
    key = bytes.fromhex(key_hex)
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    out = dec.update(payload) + dec.finalize()

    with open(dst, "wb") as f:
        f.write(out)
    print("wrote %s (%d bytes), first bytes: %s" % (dst, len(out), out[:4].hex()))


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit("usage: img3_payload.py <in.img3> <iv-hex> <key-hex> <out.bin>")
    main(*sys.argv[1:])
