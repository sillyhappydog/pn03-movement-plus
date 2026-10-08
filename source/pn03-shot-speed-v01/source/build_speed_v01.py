"""Build Shot Speed v0.1 for GPNJ08 (P.N.03 Japan): multiply the player's palm-shot speed by a factor.

How the palm shot moves (2026-10-02, savestate slot 7 with two shots in flight):
  * The shot actor (class 3, actor+0xFC == 3) stores its per-frame velocity vector at +0x100 (|v| = 1800
    units per frame in vanilla). The in-flight handler (class-3 sub-state 1, 0x8000F690) forms
    `to = pos(+0xC0) + v(+0x100)` and calls the move-and-collide routine 0x8000B770 with it, so the
    displacement per frame is exactly +0x100.
  * +0x100 is written once, in the class initialiser 0x80010004 (called from the effect element update
    on the shot's first frame): it copies the element's velocity (element+0x40 .. +0x48) into +0x100 ..
    +0x108, and the absolute aim angle later only rotates the vector (0x8000C8FC), keeping its length.

Hook: 0x800100C0 (`lfs f13, 0x50(r28)`), right after +0x100/+0x104/+0x108 are stored. The body scales
the three floats by `factor` when the actor is class 3, owned by the player (first object of root+0x50's
list) and has no target (+0x12C == 0: palm shots, with or without lock-on; energy drive shots carry a
target and are left alone), then executes the original instruction. Live registers at the site (r3..r10,
r28..r31, f12, f31) are preserved; r0/r11/r12 and f1/f2 are used.

Delivery: Dolphin [OnFrame] conditional dword patches, body at 0x8018C600, params at 0x8018C700 ('SPD1'),
hook word conditional on the original instruction.
"""
from pathlib import Path
import struct, sys, json, hashlib
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
from keystone import Ks, KS_ARCH_PPC, KS_MODE_PPC32, KS_MODE_BIG_ENDIAN
from dol import read, md

HOOK, ORIGINAL, RESUME = 0x800100C0, 0xC1BC0050, 0x800100C4     # lfs f13, 0x50(r28)
REGION, PARAMS, REGION_END = 0x8018C600, 0x8018C700, 0x8018C800
ROOT_SDA = -0x74AC
FACTOR = float(sys.argv[1]) if len(sys.argv) > 1 else 2.5

assert int.from_bytes(read(HOOK, 4), 'big') == ORIGINAL
assert read(0x800100AC, 4).hex() == 'd01f0100'      # stfs f0, 0x100(r31)
assert read(0x800100BC, 4).hex() == 'd00a0008'      # stfs f0, 8(r10)  (= actor+0x108)
assert read(0x800100C4, 4).hex() == 'd1bf010c'      # stfs f13, 0x10c(r31)
assert read(0x8000F6DC, 4).hex() == '389f0100'      # addi r4, r31, 0x100 (velocity added to the position)
assert read(0x8000F6F0, 4).hex() == '480ef829'      # bl 0x800fef18 (vector add)
assert read(0x8000FFD8, 4).hex() == '880300f8'      # class-3 update dispatch by +0xF8

P = dict(tag=0x00, flags=0x04, factor=0x08, count=0x0C, last_v=0x10, last_class_seen=0x1C)
P_HI = (PARAMS + 0x8000) >> 16
P_LO = PARAMS & 0xFFFF
if P_LO >= 0x8000:
    P_LO -= 0x10000
ks = Ks(KS_ARCH_PPC, KS_MODE_PPC32 | KS_MODE_BIG_ENDIAN)

asm = f'''
lbz 0,0xFC(31)
cmpwi 0,3
bne done
lwz 0,0x12C(31)
cmpwi 0,0
bne done
lwz 12,{ROOT_SDA}(13)
lwz 12,0x50(12)
lwz 12,0(12)
lwz 12,0(12)
lwz 0,0xE4(31)
cmpw 0,12
bne done
lis 12,{P_HI}
addi 12,12,{P_LO}
lwz 0,{P['flags']}(12)
andi. 0,0,1
beq done
lfs 1,{P['factor']}(12)
lfs 2,0x100(31)
fmuls 2,2,1
stfs 2,0x100(31)
stfs 2,{P['last_v']}(12)
lfs 2,0x104(31)
fmuls 2,2,1
stfs 2,0x104(31)
stfs 2,{P['last_v'] + 4}(12)
lfs 2,0x108(31)
fmuls 2,2,1
stfs 2,0x108(31)
stfs 2,{P['last_v'] + 8}(12)
lwz 11,{P['count']}(12)
addi 11,11,1
stw 11,{P['count']}(12)
done:
lfs 13,0x50(28)
'''
code = bytes(ks.asm(asm, addr=REGION)[0])
assert code[-4:] == ORIGINAL.to_bytes(4, 'big')
disp = RESUME - (REGION + len(code))
RETURN_WORD = 0x48000000 | (disp & 0x03FFFFFC)
code += RETURN_WORD.to_bytes(4, 'big')
assert REGION + len(code) <= PARAMS
insns = list(md.disasm(code, REGION))
for prev, cur in zip(insns, insns[1:]):
    assert not (cur.mnemonic == 'li' and cur.op_str.startswith('r0,') and prev.mnemonic == 'lwz' and prev.op_str.startswith('r0,')), 'r0 add trap'
HOOK_WORD = 0x48000000 | ((REGION - HOOK) & 0x03FFFFFC)

def fw(x): return struct.unpack('>I', struct.pack('>f', x))[0]
params = {P['tag']: 0x53504431, P['flags']: 1, P['factor']: fw(FACTOR)}     # 'SPD1'
out = Path(__file__).parent / 'speed-v01-build'
out.mkdir(exist_ok=True)
(out / 'speed.s').write_text(asm)
(out / 'speed.bin').write_bytes(code)
(out / 'speed.dis.txt').write_text('\n'.join(f'{i.address:08x}: {i.bytes.hex()} {i.mnemonic} {i.op_str}' for i in insns))
patch = [f'0x{REGION + o:08X}:dword:0x{int.from_bytes(code[o:o + 4], "big"):08X}:0x00000000' for o in range(0, len(code), 4)]
patch += [f'0x{PARAMS + off:08X}:dword:0x{val:08X}:0x00000000' for off, val in sorted(params.items())]
patch.append(f'0x{HOOK:08X}:dword:0x{HOOK_WORD:08X}:0x{ORIGINAL:08X}')
(out / 'patch.txt').write_text('\n'.join(patch) + '\n')
manifest = {'hook': HOOK, 'original': ORIGINAL, 'hook_word': HOOK_WORD, 'return_word': RETURN_WORD, 'resume': RESUME,
            'region': REGION, 'params': PARAMS, 'param_offsets': P, 'factor': FACTOR, 'vanilla_speed': 1800.0,
            'bytes': len(code), 'sha256': hashlib.sha256(code).hexdigest(), 'patch_entries': len(patch),
            'delivery': 'OnFrame conditional dword patches'}
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps({k: v for k, v in manifest.items() if k in ('hook_word', 'bytes', 'patch_entries', 'factor')}, indent=2))
