"""Build the Sprint Trail Colour v0.3 for GPNJ08 (P.N.03 Japan).

v0.3 = v0.2 with the element pool address fixed. v0.2 walked from esp_sys + 0x8548, which
is the *dummy* element the allocator returns when the pool is full; the pool itself is
the pointer stored at esp_sys + 0x8538 (allocator 0x800814D4: `lwz r0, -0x7ac8(r9)`,
trans loop 0x80082188: `lwz r29, -0x7ac8(r9)`). A Dolphin savestate taken during a sprint
showed v0.2 installed and running (t = 1.0) but tinting nothing, while the real pool at
0x80D60200 held the four id 9 elements (parts 7 / 12 / 22 / 18, start colour 5064FF55,
parent = player, alive for 245 frames) still blue. Everything below is v0.2 otherwise.

v0.1 recoloured a trail element once, when 0x8008E2D0 copied the definition's colour into
it. In Dolphin the trails stayed blue: the limb trails are effect id 9 (the definition's
id byte is +0x01, not +0x00) - a position-history line that is spawned when the limb
starts moving and then lives for the whole run - so a spawn-time hook never sees them
again once the sprint starts. v0.2 therefore recolours the *live* elements every frame:

  * hook 0x800AFE7C (`lfs f13, 0xd0(r31)`), the instruction after the Sprint Run hook in
    the player update (r31 = player). Both patches chain: Sprint Run's body returns to
    0x800AFE7C, which branches here; this body ends with `lis r9, 0x8017` (what the game
    expects in r9 at 0x800AFE80), the original `lfs` and a branch to 0x800AFE80.
  * t = clamp((sprint factor - 1) / (max factor - 1), 0, 1) from the Sprint Run v0.3
    parameter block (0x8018DD80, marker 'SPR3'; t = 0 without it); flags bit1 = step
    (t = 1 at max factor, else 0).
  * when t > 0, or when the previous frame tinted something (so a return to t = 0 restores
    the original colour once), walk the element pool (esp_sys = [r13 - 0x74F4], count at
    +0x8540, element pool pointer at +0x8538, 0x150 each). For every element that is in use (+0x18
    bit0 set, bit1 clear), has the wanted id (+0x19, default 9, 0xFFFFFFFF = any), whose
    start colour bytes (+0x88..+0x8B, written once by the init and never changed by the
    engine) equal the match colour (default the trail blue 5064FF55, 0 = any) and, with
    flags bit2, whose parent (+0x24) is the player, write the live colour floats
    +0x8C/+0x90/+0x94 (R, G, B) = start + (target - start) * t. The alpha float +0x98 is
    left alone (the engine fades it); the start bytes are left alone (they are the match
    key and the restore value). Effect id 9's trans function 0x800876B8 reads exactly
    these floats, and nothing in the engine rewrites the RGB floats after the init.
  * no calls, no LR/CTR use; registers r0, r3-r8, r10-r12, f1-f5, f8-f10, cr0.

Delivery: Dolphin [OnFrame] conditional dword patches, region 0x8018D400..0x8018D800
(unused part of the retail debug-text buffer, below Sprint Run at 0x8018D800; the same
region as v0.2, which is removed from the INI; v0.1 sat at 0x8018D000).
"""
from pathlib import Path
import struct, sys, json, hashlib
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
from keystone import Ks, KS_ARCH_PPC, KS_MODE_PPC32, KS_MODE_BIG_ENDIAN
from dol import read, md

HOOK = 0x800AFE7C
ORIGINAL = 0xC1BF00D0            # lfs f13, 0xd0(r31)
RESUME = HOOK + 4
REGION = 0x8018D400
CODE_MAX = 0x280
DATA_OFF = 0x280
SCRATCH_OFF = 0x2C0
PARAMS_OFF = 0x300
REGION_END = 0x8018D800          # exclusive; Sprint Run v0.3 starts here
MARKER = 0x54524C33              # 'TRL3'
SPRINT_MARKER = 0x53505233       # 'SPR3' at 0x8018DD80
SPRINT_PARAMS = 0x8018DD80
DEFAULTS = {'flags': 5, 'target': 0xFF880000, 'match': 0x5064FF55, 'id': 9}
ESP_SYS_R13 = -0x74F4            # [r13 - 0x74F4] = effect system work
POOL_COUNT = 0x8540              # esp_sys + 0x8540: number of element slots
POOL_PTR = 0x8538                # [esp_sys + 0x8538] = first element (esp_sys + 0x8548 is the dummy element)
ELEM_SIZE = 0x150
E_FLAGS, E_ID, E_PARENT, E_COL_BYTES, E_COL_FLOATS = 0x18, 0x19, 0x24, 0x88, 0x8C

assert int.from_bytes(read(HOOK, 4), 'big') == ORIGINAL
assert read(0x800AFE78, 4).hex() == '3d208017' and read(0x800AFE80, 4).hex() == 'c00991f8'   # lis r9,-0x7fe9 / lfs f0,-0x6e08(r9)
assert read(0x800821E0, 4).hex() == '3bfd0034' and read(0x800821E4, 4).hex() == '881fffe5'   # trans loop: id at elem+0x19
assert read(0x80082390, 4).hex() == '3bff0150'                                               # element stride 0x150
assert read(0x800814F8, 4).hex() == '80098538' and read(0x80081500, 4).hex() == '39298548'   # pool count / base
assert read(0x8008151C, 4).hex() == '813d8540'
assert read(0x800821B4, 4).hex() == '80098540' and read(0x800821BC, 4).hex() == '83a98538'   # trans loop: count / pool pointer
assert read(0x800876B8, 4).hex() == '9421ffd8'                                               # id 9 trans function
assert read(0x8008E31C, 4).hex() == 'd01f008c'                     # init writes the colour floats
assert read(0x80080588, 4).hex() == '3d208019' and read(0x8008058c, 4).hex() == '39291730'   # debug text buffer end 0x80191730
assert read(0x800805b8, 4).hex() == '39298130'                                               # debug text buffer start 0x80188130
assert int.from_bytes(read(0x80171810 + 9 * 4, 4), 'big') == 0x800876B8                      # trans table entry for id 9

BASE_HI = 0x8019
def rel(addr):
    v = addr - 0x80190000
    assert -0x8000 <= v < 0x8000, hex(addr)
    return v
DATA = rel(REGION + DATA_OFF)
SCR = rel(REGION + SCRATCH_OFF)
PRM = rel(REGION + PARAMS_OFF)
SPR = rel(SPRINT_PARAMS)
ks = Ks(KS_ARCH_PPC, KS_MODE_PPC32 | KS_MODE_BIG_ENDIAN)


def fword(f):
    return struct.unpack('>I', struct.pack('>f', f))[0]


DATA_WORDS = [
    ('one', fword(1.0)),               # +0x00
    ('zero', fword(0.0)),              # +0x04
    ('step_threshold', fword(0.999)),  # +0x08
    ('pad', 0),                        # +0x0C (keep the double 8-aligned)
    ('magic_hi', 0x43300000),          # +0x10 (double 2^52: unsigned int -> float)
    ('magic_lo', 0x00000000),          # +0x14
]
D = {name: DATA + i * 4 for i, (name, _) in enumerate(DATA_WORDS)}
assert (REGION + DATA_OFF + D['magic_hi'] - DATA) % 8 == 0
PARAM_LAYOUT = [('marker', 0x00), ('flags', 0x04), ('target', 0x08), ('match', 0x0C), ('id', 0x10),
                ('t', 0x14), ('tinted', 0x18), ('dirty', 0x1C), ('total', 0x20), ('reserved', 0x24)]
P = {name: PRM + off for name, off in PARAM_LAYOUT}

body = f'''
lis 10,{BASE_HI}
lwz 0,{P['marker']}(10)
lis 11,{MARKER >> 16}
ori 11,11,{MARKER & 0xFFFF}
cmpw 0,11
beq init_ok
stw 11,{P['marker']}(10)
li 0,{DEFAULTS['flags']}
stw 0,{P['flags']}(10)
lis 0,{DEFAULTS['target'] >> 16}
ori 0,0,{DEFAULTS['target'] & 0xFFFF}
stw 0,{P['target']}(10)
lis 0,{DEFAULTS['match'] >> 16}
ori 0,0,{DEFAULTS['match'] & 0xFFFF}
stw 0,{P['match']}(10)
li 0,{DEFAULTS['id']}
stw 0,{P['id']}(10)
li 0,0
stw 0,{P['t']}(10)
stw 0,{P['tinted']}(10)
stw 0,{P['dirty']}(10)
stw 0,{P['total']}(10)
stw 0,{P['reserved']}(10)
init_ok:
lwz 0,{P['flags']}(10)
andi. 0,0,1
beq done
lwz 0,{SPR}(10)
lis 11,{SPRINT_MARKER >> 16}
ori 11,11,{SPRINT_MARKER & 0xFFFF}
cmpw 0,11
bne zero_t
lfs 2,{D['one']}(10)
lfs 4,{D['zero']}(10)
lfs 1,{SPR + 0x30}(10)
fsubs 1,1,2
lfs 3,{SPR + 0x10}(10)
fsubs 3,3,2
fcmpu 0,3,4
ble zero_t
fdivs 1,1,3
fcmpu 0,1,4
bge t_lo_ok
fmr 1,4
t_lo_ok:
fcmpu 0,1,2
ble t_hi_ok
fmr 1,2
t_hi_ok:
lwz 0,{P['flags']}(10)
andi. 0,0,2
beq t_done
lfs 5,{D['step_threshold']}(10)
fcmpu 0,1,5
blt step_zero
fmr 1,2
b t_done
step_zero:
fmr 1,4
b t_done
zero_t:
lfs 1,{D['zero']}(10)
t_done:
stfs 1,{P['t']}(10)
li 0,0
stw 0,{P['tinted']}(10)
lfs 4,{D['zero']}(10)
fcmpu 0,1,4
bne do_scan
lwz 0,{P['dirty']}(10)
cmpwi 0,0
beq done
do_scan:
lwz 3,{ESP_SYS_R13}(13)
cmpwi 3,0
beq done
addis 4,3,1
lwz 5,{POOL_COUNT - 0x10000}(4)
lwz 6,{POOL_PTR - 0x10000}(4)
cmpwi 6,0
beq done
li 7,0
lfd 8,{D['magic_hi']}(10)
lis 12,0x4330
stw 12,{SCR}(10)
loop:
cmplw 7,5
bge scan_done
lbz 0,{E_FLAGS}(6)
andi. 11,0,1
beq next
andi. 11,0,2
bne next
lwz 11,{P['id']}(10)
cmpwi 11,-1
beq id_ok
lbz 0,{E_ID}(6)
cmpw 0,11
bne next
id_ok:
lwz 11,{P['match']}(10)
cmpwi 11,0
beq match_ok
lwz 0,{E_COL_BYTES}(6)
cmpw 0,11
bne next
match_ok:
lwz 0,{P['flags']}(10)
andi. 0,0,4
beq parent_ok
lwz 0,{E_PARENT}(6)
cmpw 0,31
bne next
parent_ok:
li 11,0
channel:
add 8,6,11
lbz 0,{E_COL_BYTES}(8)
stw 0,{SCR + 4}(10)
lfd 9,{SCR}(10)
fsub 9,9,8
frsp 9,9
addi 8,10,{P['target']}
lbzx 0,8,11
stw 0,{SCR + 4}(10)
lfd 10,{SCR}(10)
fsub 10,10,8
frsp 10,10
fsubs 10,10,9
fmuls 10,10,1
fadds 10,10,9
slwi 0,11,2
add 8,6,0
stfs 10,{E_COL_FLOATS}(8)
addi 11,11,1
cmpwi 11,3
blt channel
lwz 8,{P['tinted']}(10)
addi 8,8,1
stw 8,{P['tinted']}(10)
lwz 8,{P['total']}(10)
addi 8,8,1
stw 8,{P['total']}(10)
next:
addi 6,6,{ELEM_SIZE}
addi 7,7,1
b loop
scan_done:
li 0,0
lfs 4,{D['zero']}(10)
fcmpu 0,1,4
beq set_dirty
li 0,1
set_dirty:
stw 0,{P['dirty']}(10)
done:
lis 9,0x8017
lfs 13,0xd0(31)
'''
code = bytes(ks.asm(body, addr=REGION)[0])
assert code[-4:] == ORIGINAL.to_bytes(4, 'big'), code[-4:].hex()
disp = RESUME - (REGION + len(code))
assert disp % 4 == 0 and -0x2000000 <= disp < 0x2000000
code += (0x48000000 | (disp & 0x03FFFFFC)).to_bytes(4, 'big')
assert len(code) <= CODE_MAX, len(code)
assert (0x4E800020).to_bytes(4, 'big') not in code          # no blr inside the body
for ins in md.disasm(code, REGION):
    assert not (ins.mnemonic == 'addi' and ins.op_str.startswith('r0, r0')), ins   # addi r0,r0,x is li
    assert ins.mnemonic not in ('bl', 'blrl', 'bctrl', 'mtlr', 'mtctr'), ins       # no calls: LR/CTR untouched
data = b''.join(v.to_bytes(4, 'big') for _, v in DATA_WORDS)
assert DATA_OFF + len(data) <= SCRATCH_OFF and PARAMS_OFF + 0x28 <= REGION_END - REGION
disp = REGION - HOOK
assert disp % 4 == 0 and -0x2000000 <= disp < 0x2000000
hook_word = 0x48000000 | (disp & 0x03FFFFFC)

out = Path(__file__).parent / 'trail-v03-build'
out.mkdir(exist_ok=True)
(out / 'trail.s').write_text(body)
(out / 'trail.bin').write_bytes(code)
(out / 'trail.data.bin').write_bytes(data)
insns = list(md.disasm(code, REGION))
assert len(insns) == len(code) // 4
(out / 'trail.dis.txt').write_text('\n'.join(f'{i.address:08X}: {i.bytes.hex().upper()}  {i.mnemonic:9} {i.op_str}' for i in insns) + '\n')
patch = [f'0x{REGION + o:08X}:dword:0x{int.from_bytes(code[o:o + 4], "big"):08X}:0x00000000' for o in range(0, len(code), 4)]
patch += [f'0x{REGION + DATA_OFF + o:08X}:dword:0x{int.from_bytes(data[o:o + 4], "big"):08X}:0x00000000' for o in range(0, len(data), 4)]
patch.append(f'0x{HOOK:08X}:dword:0x{hook_word:08X}:0x{ORIGINAL:08X}')
(out / 'patch.txt').write_text('\n'.join(patch) + '\n')
params_abs = {name: REGION + PARAMS_OFF + off for name, off in PARAM_LAYOUT}
manifest = {
    'hook': HOOK, 'original': ORIGINAL, 'hook_word': hook_word, 'resume': RESUME,
    'region': REGION, 'region_end': REGION_END, 'data_offset': DATA_OFF, 'scratch_offset': SCRATCH_OFF, 'params_offset': PARAMS_OFF,
    'delivery': 'OnFrame conditional dword patches', 'bytes': len(code), 'data_bytes': len(data),
    'sha256': hashlib.sha256(code).hexdigest(), 'patch_entries': len(patch), 'marker': MARKER,
    'sprint_params': SPRINT_PARAMS, 'sprint_marker': SPRINT_MARKER, 'params': params_abs, 'defaults': DEFAULTS,
    'esp_sys_r13': ESP_SYS_R13, 'pool_count': POOL_COUNT, 'pool_ptr': POOL_PTR, 'dummy_elem': 0x8548, 'elem_size': ELEM_SIZE,
    'elem_fields': {'flags': E_FLAGS, 'id': E_ID, 'parent': E_PARENT, 'colour_bytes': E_COL_BYTES, 'colour_floats': E_COL_FLOATS},
    'effect_record': {'group': 0x28, 'id': 5, 'header': 0x30, 'def_size': 0x12C, 'defs': 4, 'parts': [7, 12, 22, 18], 'esp_id': 9},
}
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps({k: (hex(v) if isinstance(v, int) else v) for k, v in manifest.items() if k in ('hook_word', 'region', 'bytes', 'data_bytes', 'patch_entries', 'sha256')}, indent=2))
print('params', {k: hex(v) for k, v in params_abs.items()})
