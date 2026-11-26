#!/usr/bin/env python3
"""Fetch a single member out of a remote ZIP/IPSW using HTTP range requests.

Only the central directory and the requested member's bytes are downloaded,
so an 830 MB IPSW costs a few hundred KB.

Usage: ipsw_fetch.py <url> <name-substring> <output>
"""
import struct
import sys
import urllib.request

UA = {"User-Agent": "iphone33-port/1.0"}


def head_size(url):
    req = urllib.request.Request(url, method="HEAD", headers=UA)
    with urllib.request.urlopen(req) as resp:
        return int(resp.headers["Content-Length"]), resp.headers.get("Accept-Ranges")


def get_range(url, start, end):
    req = urllib.request.Request(url, headers={**UA, "Range": "bytes=%d-%d" % (start, end)})
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def find_eocd(url, size):
    tail_len = min(size, 0x10000)
    tail = get_range(url, size - tail_len, size - 1)
    pos = tail.rfind(b"PK\x05\x06")
    if pos < 0:
        raise SystemExit("no end-of-central-directory record")
    (_, disk, cd_disk, n_disk, n_total, cd_size, cd_off, clen) = struct.unpack_from(
        "<IHHHHIIH", tail, pos)
    return cd_off, cd_size, n_total


def parse_central(directory, want):
    i = 0
    entries = []
    while i + 46 <= len(directory) and directory[i:i + 4] == b"PK\x01\x02":
        (_, _, _, _, method, _, _, _, _, _, _, _, _, _, _, _, local_off) = struct.unpack_from(
            "<IHHHHHHIIIHHHHHII", directory, i)
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", directory, i + 28)
        name = directory[i + 46:i + 46 + name_len].decode("utf-8", "replace")
        entries.append((name, method, local_off))
        i += 46 + name_len + extra_len + comment_len
    matches = [e for e in entries if want.lower() in e[0].lower()]
    return matches


def extract(url, entry, out_path):
    name, method, local_off = entry
    header = get_range(url, local_off, local_off + 29)
    name_len, extra_len = struct.unpack_from("<HH", header, 26)
    data_start = local_off + 30 + name_len + extra_len

    # compressed size / uncompressed size live in the central directory; re-read it
    # cheaply by fetching the 64-byte central entry via the same local offset search
    # is not possible, so caller passes them in the entry tuple.
    raise RuntimeError("unused")


def main(url, want, out_path):
    size, ranges = head_size(url)
    print("remote size %d bytes (Accept-Ranges: %s)" % (size, ranges))
    cd_off, cd_size, n_total = find_eocd(url, size)
    print("central directory: %d entries at %d" % (n_total, cd_off))
    directory = get_range(url, cd_off, cd_off + cd_size - 1)

    matches = parse_central(directory, want)
    if not matches:
        raise SystemExit("no entry matching %r" % want)
    name, method, local_off = matches[0]
    print("match: %s (method %d)" % (name, method))

    # central entry gives sizes; parse it again for the chosen one
    i = directory.find(b"PK\x01\x02")
    chosen = None
    while i + 46 <= len(directory) and directory[i:i + 4] == b"PK\x01\x02":
        (_sig, _vm, _vn, _flags, _method, _t, _d, _crc, csize, usize, _nl, _el, _cl,
         _ds, _ia, _ea, _loff) = struct.unpack_from("<IHHHHHHIIIHHHHHII", directory, i)
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", directory, i + 28)
        cname = directory[i + 46:i + 46 + name_len].decode("utf-8", "replace")
        if cname == name:
            chosen = (csize, usize)
            break
        i += 46 + name_len + extra_len + comment_len
    if chosen is None:
        raise SystemExit("central entry vanished")

    csize, usize = chosen
    header = get_range(url, local_off, local_off + 29)
    lname_len, lextra_len = struct.unpack_from("<HH", header, 26)
    data_start = local_off + 30 + lname_len + lextra_len
    blob = get_range(url, data_start, data_start + csize - 1)

    if method == 0:
        data = blob
    elif method == 8:
        import zlib
        data = zlib.decompress(blob, -15)
    else:
        raise SystemExit("unsupported compression method %d" % method)

    if len(data) != usize:
        print("warning: got %d bytes, expected %d" % (len(data), usize))
    with open(out_path, "wb") as f:
        f.write(data)
    print("wrote %s (%d bytes)" % (out_path, len(data)))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: ipsw_fetch.py <url> <name-substring> <output>")
    main(sys.argv[1], sys.argv[2], sys.argv[3])
