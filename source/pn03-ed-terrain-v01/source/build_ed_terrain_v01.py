"""Build the Energy Drive terrain pass v0.1 for GPNJ08 (P.N.03 Japan).

Player-owned homing shots (energy drive shots that carry a lock-on target) ignore the
terrain sweep in the shot move-and-collide routine 0x8000B770 while their budget
lasts, so they are no longer absorbed by nearby walls, floors and pillars. Enemy hit
detection (0x8000B9AC) is untouched: it never looks at terrain, so a shot that passed
through a wall still hits its target.

Mechanism:
  * 0x8000B770(actor r3, from r4, to r5, out r6, do_terrain r7; f1 radius) runs the
    terrain raycast 0x80007960 only when r7 != 0, then the object hit test.
  * The hook replaces `cmpwi r7, 0` at 0x8000B7C8. The body forces r7 = 0 when
      - the actor's owner (+0xE4) is the player (first object of root+0x50's list),
      - the actor has a target (+0x12C != 0), and
      - the actor's +0x150 halfword is > 0 (decremented once per call).
    +0x150 is set at spawn (0x12C default, params +0x24 = 0x96 / 0x78 for the energy
    drive shot types) and is never read for shot classes 1/3/8, so it doubles as the
    terrain-immunity budget in frames. When it runs out the original terrain test
    resumes and the shot dies at the next wall as before.
  * Normal palm shots pass no target (+0x12C == 0) and enemy shots have another owner,
    so they keep the original behaviour.
  * Live registers at the hook site: r31 actor, r28 from, r27 to, r30 stack vector,
    r4 out pointer, r11 stack pointer copy (used by `stfs f0, 4(r11)` right after the
    hook). The body only touches r0, r9, r10, r12 and cr0, and ends with the original
    compare so cr0 is what the following `beq` expects.

Delivery: Dolphin [OnFrame] conditional dword patches, body at 0x8018DF00 (debug text
bump buffer, below movement v0.14 at 0x8018E000), hook word conditional on the
original instruction. Does not modify the DOL or ISO.
"""
from pathlib import Path
import sys, json, hashlib
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
from keystone import Ks, KS_ARCH_PPC, KS_MODE_PPC32, KS_MODE_BIG_ENDIAN
from dol import read, md

HOOK = 0x8000B7C8
ORIGINAL = 0x2C070000            # cmpwi r7, 0
RESUME = HOOK + 4                # li r29, 0
REGION = 0x8018DF00              # body load address
REGION_END = 0x8018E000          # exclusive; movement v0.14 body starts here
ROOT_SDA_OFFSET = -0x74AC        # lwz rX, -0x74ac(r13) = root pointer
OWNER = 0xE4
TARGET = 0x12C
BUDGET = 0x150

assert int.from_bytes(read(HOOK, 4), 'big') == ORIGINAL
assert read(0x8000B7C4, 4).hex() == 'c3e9ed84'      # lfs f31, -0x127c(r9)
assert read(0x8000B7CC, 4).hex() == '3ba00000'      # li r29, 0
assert read(0x8000B7D0, 4).hex() == 'd00b0004'      # stfs f0, 4(r11)
assert read(0x8000B7D4, 4).hex() == '41820068'      # beq 0x8000b83c
assert read(0x8000B7E8, 4).hex() == '4bffc179'      # bl 0x80007960 (terrain raycast)
assert read(0x8000B858, 4).hex() == '48000155'      # bl 0x8000b9ac (object hit test)
assert read(0x80080588, 4).hex() == '3d208019' and read(0x8008058c, 4).hex() == '39291730'   # bump limit 0x80191730
assert read(0x800805b8, 4).hex() == '39298130'                                                # bump base 0x80188130
ks = Ks(KS_ARCH_PPC, KS_MODE_PPC32 | KS_MODE_BIG_ENDIAN)

asm = f'''
cmpwi 7,0
beq done
lwz 0,{OWNER}(31)
lwz 9,{ROOT_SDA_OFFSET}(13)
cmpwi 9,0
beq done
lwz 9,80(9)
cmpwi 9,0
beq done
lwz 10,0(9)
lwz 12,4(9)
subf 12,10,12
cmpwi 12,0
beq done
lwz 9,0(10)
cmpw 0,9
bne done
lwz 0,{TARGET}(31)
cmpwi 0,0
beq done
lha 9,{BUDGET}(31)
cmpwi 9,0
ble done
addi 9,9,-1
sth 9,{BUDGET}(31)
li 7,0
done:
cmpwi 7,0
'''
code = bytes(ks.asm(asm, addr=REGION)[0])
assert code[-4:] == ORIGINAL.to_bytes(4, 'big')
disp = RESUME - (REGION + len(code))
assert disp % 4 == 0 and -0x2000000 <= disp < 0x2000000
RETURN_WORD = 0x48000000 | (disp & 0x03FFFFFC)
code += RETURN_WORD.to_bytes(4, 'big')
assert REGION + len(code) <= REGION_END, (len(code), REGION_END - REGION)
disp = REGION - HOOK
assert disp % 4 == 0 and -0x2000000 <= disp < 0x2000000
HOOK_WORD = 0x48000000 | (disp & 0x03FFFFFC)
for w in (0x4E800020, 0x4E800021):           # no blr / blrl inside the body
    assert w.to_bytes(4, 'big') not in code
out = Path(__file__).parent / 'ed-terrain-v01-build'
out.mkdir(exist_ok=True)
(out / 'ed.s').write_text(asm)
(out / 'ed.bin').write_bytes(code)
insns = list(md.disasm(code, REGION))
assert len(insns) == len(code) // 4
patch = [f'0x{REGION + o:08X}:dword:0x{int.from_bytes(code[o:o + 4], "big"):08X}:0x00000000' for o in range(0, len(code), 4)]
patch.append(f'0x{HOOK:08X}:dword:0x{HOOK_WORD:08X}:0x{ORIGINAL:08X}')
(out / 'patch.txt').write_text('\n'.join(patch) + '\n')
(out / 'ed.dis.txt').write_text('\n'.join(f'{i.address:08x}: {i.bytes.hex()} {i.mnemonic} {i.op_str}' for i in insns))
manifest = {'hook': HOOK, 'original': ORIGINAL, 'hook_word': HOOK_WORD, 'return_word': RETURN_WORD, 'resume': RESUME,
            'region': REGION, 'region_end': REGION_END, 'delivery': 'OnFrame conditional dword patches',
            'bytes': len(code), 'sha256': hashlib.sha256(code).hexdigest(), 'patch_entries': len(patch),
            'root_sda_offset': ROOT_SDA_OFFSET, 'owner_offset': OWNER, 'target_offset': TARGET, 'budget_offset': BUDGET,
            'terrain_raycast': 0x80007960, 'object_hit_test': 0x8000B9AC}
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps({k: v for k, v in manifest.items() if k in ('bytes', 'sha256', 'region', 'hook_word', 'return_word', 'patch_entries')}, indent=2))
