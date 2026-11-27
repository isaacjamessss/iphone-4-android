#!/usr/bin/env python3
"""IMG3 repack tools for the n92ap Stage 1 flow.

Two subcommands:

  untrust-ibss <in.img3> <out.img3>
      Patch iBSS.n92ap.img3 so DFU manifest-boot accepts UNSIGNED images.
      Background (see docs/PORT-n92ap.md): iBSS's image3_load checks the
      image signature; on failure it consults an "untrusted images are
      permitted" policy at 0x84008178 and otherwise hard-fails via
      `beq.w` at decrypted offset 0x5d52. NOPing that branch makes every
      validation failure non-fatal, so a raw/unsigned follow-up image
      (our openiboot wrapper) is still copied and executed after manifest.
      The DATA body is AES-256-CBC with the published 5.1.1 iBSS key/iv
      (the same one tools/img3_payload.py decrypts with); the KBAG/SHSH/CERT
      tags are kept verbatim.

  wrap <payload> <ident> <out.img3>
      Build a minimal unsigned IMG3 (TYPE + DATA tags, no KBAG) around a raw
      binary. Use ident "ibec" for the iBSS manifest-boot path: the loader
      requires header ident 0x69626563 ('ibec').

Usage: img3_repack.py untrust-ibss <in.img3> <out.img3>
       img3_repack.py wrap <payload> <ident> <out.img3>
"""
import struct
import sys

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# Published iOS 5.1.1 iBSS.n92ap GID-decrypted KBAG key/iv (see HANDOFF 7.3).
IBSS_IV = bytes.fromhex("30121b6c9866b26fe5082ea3001de870")
IBSS_KEY = bytes.fromhex("4ce2b4a380a6df017ca101020e4af9aca892ce96a80bd664b12a75ac9d8f8ce4")

# decrypted-DATA offsets of patches applied to iBSS (see docs/PORT-n92ap.md)
UNTRUST_PATCHES = [
    # policy("untrusted images permitted") call in the constraint soft-fail path
    (0x5D52, bytes.fromhex("00f0af80"), bytes.fromhex("bf00bf00"), "beq.w fail -> nop"),
    # the policy function itself (called from 0x5b40 and 0x5d48): return 1 always
    (0x8178, bytes.fromhex("01280dd1"), bytes.fromhex("01207047"), "policy -> movs r0,#1; bx lr"),
]


def aes_cbc(data, key, iv, decrypt):
    op = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor() if decrypt \
        else Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return op.update(data) + op.finalize()


def parse_img3(blob):
    if blob[:4] != b"3gmI":
        raise SystemExit("not an IMG3 (magic %r)" % blob[:4])
    full_size, data_size, sig_area, ident = struct.unpack_from("<IIII", blob, 4)
    tags = []
    off = 20
    while off + 12 <= len(blob):
        tag = blob[off:off + 4][::-1]
        total, dlen = struct.unpack_from("<II", blob, off + 4)
        tags.append((tag, off, total, dlen))
        if total == 0:
            break
        off += total
    return dict(full=full_size, dsize=data_size, sig=sig_area, ident=ident, tags=tags)


def untrust_ibss(src, dst):
    blob = bytearray(open(src, "rb").read())
    info = parse_img3(blob)
    data_off = data_len = None
    for tag, off, total, dlen in info["tags"]:
        if tag == b"DATA":
            data_off, data_len = off + 12, dlen
    if data_off is None:
        raise SystemExit("no DATA tag")

    body = bytes(blob[data_off:data_off + data_len])
    plain = bytearray(aes_cbc(body, IBSS_KEY, IBSS_IV, decrypt=True))
    for off, old, new, what in UNTRUST_PATCHES:
        cur = bytes(plain[off:off + 4])
        if cur == new:
            print("0x%x already patched (%s)" % (off, what))
            continue
        if cur != old:
            raise SystemExit("unexpected bytes at 0x%x: %s" % (off, cur.hex()))
        plain[off:off + 4] = new
        print("patched 0x%x: %s -> %s (%s)" % (off, old.hex(), new.hex(), what))
    blob[data_off:data_off + data_len] = aes_cbc(bytes(plain), IBSS_KEY, IBSS_IV, decrypt=False)
    open(dst, "wb").write(blob)
    print("wrote %s (%d bytes)" % (dst, len(blob)))


def tag4(name):
    return struct.pack("<I", int.from_bytes(name.encode().ljust(4, b" ")[::-1], "little"))


def wrap(payload_path, ident, dst, donor_path=None):
    payload = open(payload_path, "rb").read()
    if len(ident) != 4:
        raise SystemExit("ident must be 4 chars, e.g. ibec")
    ident_u32 = struct.unpack("<I", ident.encode()[::-1])[0]  # 'ibec' -> 0x69626563

    # Apple tag layout: {magic, totalLen, dataLen, content, zero pad};
    # totalLen MUST equal the tag's actual byte span or the loader's tag
    # walk desynchronises and find(DATA) fails (hard reject).
    type_tag = (b"EPYT" + struct.pack("<II", 32, 4) + ident.encode()[::-1]
                + b"\x00" * 16)
    data_tag = b"ATAD" + struct.pack("<II", 12 + len(payload), len(payload)) + payload
    body = type_tag + data_tag

    # Constraint tags (VERS/SEPO/BORD/CHIP...) copied verbatim from a real
    # image for this board so validate_constraints passes without soft-fail.
    if donor_path:
        donor = open(donor_path, "rb").read()
        for tag, off, total, dlen in parse_img3(donor)["tags"]:
            if tag in (b"TYPE", b"DATA", b"KBAG", b"SHSH", b"CERT"):
                continue
            body += donor[off:off + total]
            print("donor tag %s (%d bytes)" % (tag.decode(), total))

    # sigCheck = start of the signature area within the tags region; with no
    # SHSH/CERT tags it equals dataSize (Apple's: 0x101b8 + sig tags = dataSize).
    header = (b"3gmI" + struct.pack("<IIII", 20 + len(body), len(body), len(body),
                                    ident_u32))
    open(dst, "wb").write(header + body)
    print("wrote %s: ident=%s fullSize=%d payload=%d bytes"
          % (dst, ident, 20 + len(body), len(payload)))


def patch_plain(src, dst):
    plain = bytearray(open(src, "rb").read())
    for off, old, new, what in UNTRUST_PATCHES:
        cur = bytes(plain[off:off + 4])
        if cur == new:
            print("0x%x already patched (%s)" % (off, what))
            continue
        if cur != old:
            raise SystemExit("unexpected bytes at 0x%x: %s" % (off, cur.hex()))
        plain[off:off + 4] = new
        print("patched 0x%x: %s -> %s (%s)" % (off, old.hex(), new.hex(), what))
    open(dst, "wb").write(plain)
    print("wrote %s (%d bytes)" % (dst, len(plain)))


def reinject(orig_path, plain_path, dst):
    """Re-encrypt a patched plaintext iBSS and splice it into the original
    IMG3 container (KBAG/SHSH/CERT tags kept verbatim)."""
    blob = bytearray(open(orig_path, "rb").read())
    plain = open(plain_path, "rb").read()
    info = parse_img3(blob)
    for tag, off, total, dlen in info["tags"]:
        if tag == b"DATA":
            if dlen != len(plain):
                raise SystemExit("DATA length mismatch: img3 %d vs plain %d"
                                 % (dlen, len(plain)))
            blob[off + 12:off + 12 + dlen] = aes_cbc(plain, IBSS_KEY, IBSS_IV, decrypt=False)
            break
    else:
        raise SystemExit("no DATA tag")
    open(dst, "wb").write(blob)
    print("wrote %s (%d bytes)" % (dst, len(blob)))


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 3 and args[0] == "untrust-ibss":
        untrust_ibss(args[1], args[2])
    elif len(args) == 3 and args[0] == "patchplain":
        patch_plain(args[1], args[2])
    elif len(args) == 4 and args[0] == "reinject":
        reinject(args[1], args[2], args[3])
    elif len(args) in (4, 5) and args[0] == "wrap":
        wrap(args[1], args[2], args[3], args[4] if len(args) == 5 else None)
    else:
        sys.exit(__doc__)
