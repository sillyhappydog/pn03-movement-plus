"""Build the Transition Null Projection v0.1 patch for GPNJ08 (P.N.03 Japan).

Problem (2026-10-01): during the Mission 9 boss-rush room transitions the game keeps drawing the
room with the camera frozen (root+0x5C bit31) while the camera's projection matrix (camera struct
+0xC0, copied to root+0x2C0) is still all zero. GXSetProjection(0x80121344) uploads the zero
matrix as a perspective projection. Real hardware then rasterises nothing (every vertex maps to
(0,0,0,w); triangles that cross w = 0 are clipped) and the screen stays black, which is what real
hardware recordings show. Dolphin's host GPU turns the w -> 0 vertices into NaN and paints the
screen with huge triangles.

Fix: hook the entry of GXSetProjection. When m00, m11, m22 and m23 of the given 4x4 matrix are all
(+/-)zero, upload an orthographic projection whose x/y offsets are 10.0 instead. Every vertex then
lands at NDC (10, 10) with w = 1, outside the clip volume, so nothing is drawn: the same black frame
as hardware, without NaN. Any other matrix runs the original function unchanged.

Delivery: Dolphin [OnFrame] conditional dword patches, body at 0x8018C000 (debug text bump buffer,
below Dodge Absorb v0.2 at 0x8018C800), hook word conditional on the original instruction.
"""
from pathlib import Path
import sys, json, hashlib
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
from keystone import Ks, KS_ARCH_PPC, KS_MODE_PPC32, KS_MODE_BIG_ENDIAN
from dol import read, md

HOOK = 0x80121344                 # GXSetProjection entry: lwz r5, -0x5a80(r13)
ORIGINAL = 0x80ADA580
RESUME = HOOK + 4                 # cmpwi r4, 1
REGION = 0x8018C000               # body load address
REGION_END = 0x8018C800           # exclusive; Dodge Absorb v0.2 body starts here
GX_SDA_OFFSET = -0x5A80           # lwz rX, -0x5a80(r13) = __GXData
WGPIPE_HI = 0xCC01                # lis r5, 0xCC01 ; -0x8000(r5) = 0xCC008000
OFFSET = 0x41200000               # 10.0f, x/y offset of the null orthographic projection

assert int.from_bytes(read(HOOK, 4), 'big') == ORIGINAL
assert read(0x80121348, 4).hex() == '2c040001'       # cmpwi r4, 1
assert read(0x8012134C, 4).hex() == '90850420'       # stw r4, 0x420(r5)
assert read(0x801213A0, 4).hex() == '3ca0cc01'       # lis r5, -0x33ff (WGPIPE)
assert read(0x801213AC, 4).hex() == '38031020'       # addi r0, r3, 0x1020 (XF projection regs)
assert read(0x801213F0, 4).hex() == 'b0040002'       # sth r0, 2(r4)
assert read(0x801213F4, 4).hex() == '4e800020'       # blr (leaf function: LR is the caller's at entry)
ks = Ks(KS_ARCH_PPC, KS_MODE_PPC32 | KS_MODE_BIG_ENDIAN)

asm = f'''
lwz 5,0(3)
lwz 0,0x14(3)
or 5,5,0
lwz 0,0x28(3)
or 5,5,0
lwz 0,0x2c(3)
or 5,5,0
rlwinm. 5,5,0,1,31
bne original
lis 5,{WGPIPE_HI}
li 0,0x10
stb 0,-0x8000(5)
lis 0,6
ori 0,0,0x1020
stw 0,-0x8000(5)
li 0,0
stw 0,-0x8000(5)
lis 0,{OFFSET >> 16}
stw 0,-0x8000(5)
li 0,0
stw 0,-0x8000(5)
lis 0,{OFFSET >> 16}
stw 0,-0x8000(5)
li 0,0
stw 0,-0x8000(5)
stw 0,-0x8000(5)
li 0,1
stw 0,-0x8000(5)
lwz 4,{GX_SDA_OFFSET}(13)
sth 0,2(4)
blr
original:
lwz 5,{GX_SDA_OFFSET}(13)
'''
code = bytes(ks.asm(asm, addr=REGION)[0])
assert code[-4:] == ORIGINAL.to_bytes(4, 'big')
disp = RESUME - (REGION + len(code))
RETURN_WORD = 0x48000000 | (disp & 0x03FFFFFC)
code += RETURN_WORD.to_bytes(4, 'big')
assert len(code) % 4 == 0 and REGION + len(code) <= REGION_END, (len(code), REGION_END - REGION)
disp = REGION - HOOK
assert -0x2000000 <= disp < 0x2000000
HOOK_WORD = 0x48000000 | (disp & 0x03FFFFFC)

out = Path(__file__).parent / 'nullproj-v01-build'
out.mkdir(exist_ok=True)
(out / 'nullproj.s').write_text(asm)
(out / 'nullproj.bin').write_bytes(code)
insns = list(md.disasm(code, REGION))
patch = [f'0x{REGION + o:08X}:dword:0x{int.from_bytes(code[o:o + 4], "big"):08X}:0x00000000' for o in range(0, len(code), 4)]
patch.append(f'0x{HOOK:08X}:dword:0x{HOOK_WORD:08X}:0x{ORIGINAL:08X}')
(out / 'patch.txt').write_text('\n'.join(patch) + '\n')
(out / 'nullproj.dis.txt').write_text('\n'.join(f'{i.address:08x}: {i.bytes.hex()} {i.mnemonic} {i.op_str}' for i in insns))
manifest = {'hook': HOOK, 'original': ORIGINAL, 'hook_word': HOOK_WORD, 'return_word': RETURN_WORD, 'resume': RESUME,
            'region': REGION, 'region_end': REGION_END, 'bytes': len(code), 'sha256': hashlib.sha256(code).hexdigest(),
            'patch_entries': len(patch), 'delivery': 'OnFrame conditional dword patches',
            'null_projection': {'type': 'orthographic (1)', 'coefficients': [0, 10.0, 0, 10.0, 0, 0],
                                'test': 'm00 | m11 | m22 | m23 of the 4x4 argument, sign bit ignored, == 0'}}
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps({k: v for k, v in manifest.items() if k in ('bytes', 'sha256', 'region', 'hook_word', 'return_word', 'patch_entries')}, indent=2))
