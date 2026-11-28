import struct,sys
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
d=open(sys.argv[1],'rb').read(); iv=bytes.fromhex(sys.argv[2]); key=bytes.fromhex(sys.argv[3])
off=20
while off<len(d):
    mag,tot,dl=struct.unpack_from('<III',d,off)
    if mag==0x44415441: # 'DATA'
        p=d[off+12:off+12+dl]; n=len(p)//16*16
        out=(lambda c: c.update(p[:n])+c.finalize())(Cipher(algorithms.AES(key),modes.CBC(iv)).decryptor())+p[n:]
        open(sys.argv[4],'wb').write(out); print('DATA',dl); break
    off+=tot
