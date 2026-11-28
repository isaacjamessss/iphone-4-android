import gzip, sys
src, out = sys.argv[1], sys.argv[2]
repl = {}   # name -> (data, mode or None)
adds = []
for a in sys.argv[3:]:
    name, path, mode = a.split('=')
    repl[name] = (open(path, 'rb').read(), int(mode, 8) if mode else None)
d = gzip.decompress(open(src, 'rb').read())
o = bytearray(); i = 0; seen = set(); ino_max = 0
def pad4(n): return (4 - n % 4) % 4
entries = []
while True:
    assert d[i:i+6] == b'070701', d[i:i+6]
    h = d[i:i+110]; f = [int(h[6+8*k:14+8*k], 16) for k in range(13)]
    nsz, fsz = f[11], f[6]
    name = d[i+110:i+110+nsz-1].decode()
    p = i + 110 + nsz; p += pad4(p)
    data = d[p:p+fsz]; p += fsz; p += pad4(p)
    entries.append((f, name, data)); i = p
    if name == 'TRAILER!!!': break
def emit(f, name, data):
    nb = name.encode() + b'\0'
    f = list(f); f[6] = len(data); f[11] = len(nb)
    hdr = b'070701' + b''.join(b'%08x' % v for v in f)
    o.extend(hdr + nb); o.extend(b'\0' * pad4(len(o)))
    o.extend(data); o.extend(b'\0' * pad4(len(o)))
for f, name, data in entries:
    ino_max = max(ino_max, f[0])
    if name in repl:
        nd, mode = repl[name]
        if mode is not None: f = list(f); f[1] = (f[1] & ~0o7777) | mode
        print('replace', name, len(data), '->', len(nd)); seen.add(name); data = nd
    if name == 'TRAILER!!!':
        for n, (nd, mode) in repl.items():
            if n not in seen:
                ino_max += 1
                # ino mode uid gid nlink mtime size devmaj devmin rdevmaj rdevmin namesize check
                emit([ino_max, 0o100000 | (mode or 0o755), 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0], n, nd)
                print('add', n, len(nd))
    emit(f, name, data)
o.extend(b'\0' * ((512 - len(o) % 512) % 512))
open(out, 'wb').write(gzip.compress(bytes(o), 9))
print('entries', len(entries), 'out', len(o))
