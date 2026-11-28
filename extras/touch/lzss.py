import struct,sys
d=open(sys.argv[1],'rb').read()
usz,csz=struct.unpack_from('>II',d,12); src=d[0x180:0x180+csz]
N,F,TH=4096,18,2; text=bytearray(b' '*(N-F))+bytearray(F); r=N-F; out=bytearray(); i=0; flags=0
while i<len(src):
    flags>>=1
    if not flags&0x100:
        flags=src[i]|0xff00; i+=1
        if i>=len(src): break
    if flags&1:
        c=src[i]; i+=1; out.append(c); text[r]=c; r=(r+1)&(N-1)
    else:
        if i+1>=len(src): break
        a=src[i]; b=src[i+1]; i+=2; a|=(b&0xf0)<<4; b=(b&0x0f)+TH
        for k in range(b+1):
            c=text[(a+k)&(N-1)]; out.append(c); text[r]=c; r=(r+1)&(N-1)
open(sys.argv[2],'wb').write(out); print(len(out),usz)
