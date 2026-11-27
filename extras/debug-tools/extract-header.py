import re
import sys

src, dst = sys.argv[1], sys.argv[2]
text = open(src, "r", encoding="utf-8", errors="replace").read()
blob = bytes(int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{2})", text))
with open(dst, "wb") as f:
    f.write(blob)
print("wrote", len(blob), "bytes", hex(len(blob)), "->", dst)
