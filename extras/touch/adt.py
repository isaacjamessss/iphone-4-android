import struct,sys
d=open(sys.argv[1],'rb').read()
def node(o,path):
    np_,nc=struct.unpack_from('<II',d,o); o+=8; props={}
    for _ in range(np_):
        name=d[o:o+32].split(b'\0')[0].decode(); ln=struct.unpack_from('<I',d,o+32)[0]&0x7fffffff
        props[name]=d[o+36:o+36+ln]; o+=36+((ln+3)&~3)
    p=path+'/'+props.get('name',b'?').rstrip(b'\0').decode(errors='replace')
    yield p,props
    for _ in range(nc):
        g=node(o,p)
        for x in g:
            if x[0]=='__end__': o=x[1]
            else: yield x
    yield '__end__',o
def fmt(v):
    s=v.rstrip(b'\0')
    if s and all(32<=c<127 for c in s): return repr(s.decode())
    if len(v)%4==0 and len(v)<=64: return ' '.join('%08x'%w for w in struct.unpack('<%dI'%(len(v)//4),v))
    return v[:48].hex()+('...(%d)'%len(v) if len(v)>48 else '')
pat=sys.argv[2:]
for p,props in node(0,''):
    if p=='__end__': continue
    if any(x in p.lower() for x in pat) or any(x in props.get('compatible',b'').decode(errors='ignore').lower() for x in pat):
        print('==',p)
        for k,v in props.items(): print('   %-28s %s'%(k,fmt(v)))
