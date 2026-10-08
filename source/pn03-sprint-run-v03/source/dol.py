import sys, struct, hashlib, re, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
PATH=Path(r'I:\PN03_extracted\sys\main.dol')
data=PATH.read_bytes()
assert hashlib.sha256(data).hexdigest()=='f3ba7ffb062c7ed0c1926b3775856b3026b44021a1d14abf28513cd15fa703ec'
def u32(o): return struct.unpack_from('>I',data,o)[0]
sections=[(u32(i*4),u32(0x48+i*4),u32(0x90+i*4)) for i in range(18) if u32(0x90+i*4)]
def off(va):
    for f,a,n in sections:
        if a<=va<a+n: return f+va-a
    raise ValueError(hex(va))
def read(va,n):
    o=off(va);return data[o:o+n]
md=Cs(CS_ARCH_PPC,CS_MODE_32|CS_MODE_BIG_ENDIAN)
md.skipdata=True
def dis(a,b):
    return '\n'.join(f'{i.address:08X}: {i.bytes.hex().upper()}  {i.mnemonic:9} {i.op_str}' for i in md.disasm(read(a,b-a),a))
def calls(target):
    out=[]
    for f,a,n in sections[:2]:
        for k in range(0,n,4):
            w=u32(f+k)
            if w>>26==18:
                rel=w&0x3fffffc
                if rel&0x2000000:rel-=0x4000000
                t=rel if w&2 else a+k+rel
                if t==target:out.append(a+k)
    return out
def imm(value):
    return [i.address for f,a,n in sections[:2] for i in md.disasm(data[f:f+n],a) if int.from_bytes(i.bytes,'big')&0xffff==value]
if __name__=='__main__':
    if sys.argv[1]=='dis': print(dis(int(sys.argv[2],16),int(sys.argv[3],16)))
    if sys.argv[1]=='calls':
        for a in calls(int(sys.argv[2],16)):print(dis(a-24,a+8))
    if sys.argv[1]=='imm':
        for a in imm(int(sys.argv[2],16)):print(dis(a-8,a+8))
