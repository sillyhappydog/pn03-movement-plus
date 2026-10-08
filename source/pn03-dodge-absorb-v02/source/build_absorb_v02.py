"""Build the Dodge Absorb v0.2 for GPNJ08 (P.N.03 Japan): v0.1 + the orb pickup effect and sound on absorb.

v0.1 (sidestep invincibility kept every frame + energy on every negated hit) is unchanged; see
build_absorb_v01.py for the design and the hooks. v0.2 adds, on each absorb, what the energy orb
pickup does (item actor update 0x800A7EE0, after the energy add 0x800A8458):
  * sound 0x800C9414(0, 0x37, 0, 0) and 0x800C9414(0, 0x39, 0, 0)
  * effect group 0 id 0x14 attached to the player: record = 0x80081AEC(0, 0x14),
    owner = 0x80081BF4(0), 0x8008EE44(player, 0, 0, record, owner, 0, 0, player, stack arg 0).
Because the absorb routine now calls functions that use the stack (the item pickup passes the 9th
argument at 8(r1)), it opens its own 32-byte frame (back chain, LR save slot for callees, the
stack argument) and restores r1 before returning. By default the effect and the sounds fire at
most once per frame (flags bit5), so a dense burst still reads as one flash per frame.

Parameters (marker 'DGA2' at 0x8018CD80): flags (bit0 enable, bit1 count area hits, bit2 keep
invincible, bit3 effect, bit4 sound, bit5 once per frame), energy_per_hit, cap_per_step,
keep_frames, fx_group, fx_id, se1, se2, and runtime counters (frame, last_fx_frame, ...).
Region 0x8018C800..0x8018D000.

2026-10-06 revision, both regions: one absorb per hit, default X 100. A regular shot reaches both
hooks: BltHitCk asks BltHitEm, which calls BltDmageSet with its commit argument 0 (r6 at hook B),
and then commits the same hit at hook A. Hook B now ignores those query calls and only counts
committed ones (area, piercing and effect attacks, which never reach hook A). Until then the JP
build counted every regular shot twice, so X = 50 really gave +100 per shot; with X = 100 a regular
shot is still worth 100 in JP, and attacks that arrive committed at hook B went from 50 to 100.
The USA build additionally hooks the hurtbox test in BltHitEm (it skips hurtboxes whose flags lack
bit 0, which is every player hurtbox while the invincibility counter runs).
"""
from pathlib import Path
import struct, sys, json, hashlib
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
from keystone import Ks, KS_ARCH_PPC, KS_MODE_PPC32, KS_MODE_BIG_ENDIAN
from dol import read, md
from regions import R, hi, lo, hiu, lou

HOOK0, ORIG0 = R.a(0x800AFE80), R.w(0x800AFE80, 0xC00991F8)          # lfs f0, -0x6e08(r9)   (player update, after the trail hook)
HOOK_A, ORIG_A = R.a(0x8000B950), R.w(0x8000B950, 0x40820038)        # bne 0x8000b988        (shot hit: invincible -> skip damage)
HOOK_B, ORIG_B = R.a(0x8000C218), R.w(0x8000C218, 0x4C820020)        # bnelr                 (area hit: invincible -> return)
RESUME0 = HOOK0 + 4
A_DAMAGE, A_SKIP = R.a(0x8000B954), R.a(0x8000B988)
B_CONT = R.a(0x8000C21C)
HUD_UP = R.a(0x80095CCC)                            # gauge target increased (leaf)
HUD_STRUCT = R.a(0x80191BA0)
EST_GET = R.a(0x80081AEC)                           # EspGetEstAddr(group, id)
EST_OWNER = R.a(0x80081BF4)                         # owner[group]
ESP_CREATE = R.a(0x8008EE44)                        # generator create (9 args, the last at 8(r1))
SE_PLAY = R.a(0x800C9414)                           # sound (type, id, pos*, flag)
HURTBOX_HOOK = R.a(0x8000BAC0) if R.name == 'US' else None
HURTBOX_ORIG = R.w(0x8000BAC0, 0x2C000000) if HURTBOX_HOOK else None
REGION = R.a(0x8018C800)
CODE_MAX = 0x500
SCRATCH_OFF = 0x540
PARAMS_OFF = 0x580
REGION_END = R.a(0x8018D000)
MARKER = 0x44474132                            # 'DGA2'
DEFAULTS = {'flags': 0x3F, 'energy_per_hit': int(sys.argv[1]) if len(sys.argv) > 1 else 100, 'cap_per_step': 0, 'keep_frames': 2,
            'fx_group': 0, 'fx_id': 0x14, 'se1': 0x37, 'se2': 0x39}
ROOT_R13 = R.root_sda
ENERGY, ENERGY_MAX = R.root_energy, R.root_energy_max

assert int.from_bytes(read(HOOK0, 4), 'big') == ORIG0 and int.from_bytes(read(HOOK_A, 4), 'big') == ORIG_A and int.from_bytes(read(HOOK_B, 4), 'big') == ORIG_B
assert read(R.a(0x800AFE7C), 4).hex() == R.w(0x800AFE7C, 'c1bf00d0') and read(R.a(0x800AFE84), 4).hex() == R.w(0x800AFE84, 'fc0d0000')
assert read(R.a(0x8000B948), 4).hex() == R.w(0x8000B948, '880b04e1') and read(A_DAMAGE, 4).hex() == R.w(A_DAMAGE, '800b04f0') and read(A_SKIP, 4).hex() == R.w(A_SKIP, '3ba00001')
assert read(R.a(0x8000C210), 4).hex() == R.w(0x8000C210, '880c04e1') and read(B_CONT, 4).hex() == R.w(B_CONT, '2c060000')
assert read(R.a(0x800AFBF8), 4).hex() == R.w(0x800AFBF8, '893f04e1') and read(R.a(0x800B5C90), 4).hex() == R.w(0x800B5C90, '881e04e1')
assert read(HUD_UP, 4).hex() == R.w(HUD_UP, '80030004') and read(R.a(0x800A84FC), 4).hex() == R.w(0x800A84FC, '38631ba0')
# The expected-word check above compares the US word with itself, so it cannot catch a wrong HUD_STRUCT. Derive the
# struct and the routine from the game's own small-orb pickup (lis r3 / addi r3 / bl) and require the same pair.
_orb = R.a(0x800A84FC)
_lis, _addi, _bl = (int.from_bytes(read(_orb + d, 4), 'big') for d in (-4, 0, 4))
assert _lis >> 16 == 0x3C60 and _addi >> 16 == 0x3863 and ((_lis & 0xFFFF) << 16) + lo(_addi) == HUD_STRUCT, hex(HUD_STRUCT)
assert _bl >> 26 == 18 and _bl & 3 == 1 and _orb + 4 + (_bl & 0x03FFFFFC) - (0x04000000 if _bl & 0x02000000 else 0) == HUD_UP
assert read(EST_GET, 4).hex() == R.w(EST_GET, '9421fff8') and read(EST_OWNER, 4).hex() == R.w(EST_OWNER, '812d8b0c') and read(ESP_CREATE, 4).hex() == R.w(ESP_CREATE, '9421ffd0')
# the orb pickup: SE 0x37 / 0x39, effect (0, 0x14) created with parent = player and the 9th argument 0 at 8(r1)
assert read(R.a(0x800A8204), 4).hex() == R.w(0x800A8204, '38800037') and read(R.a(0x800A8214), 4).hex() == R.w(0x800A8214, '38800039') and read(R.a(0x800A8288), 4).hex() == R.w(0x800A8288, '38800014')
assert read(R.a(0x800A8320), 4).hex() == R.w(0x800A8320, '93410008') and read(R.a(0x800A8330), 4).hex() == R.w(0x800A8330, '4bfe6b15')
assert read(R.a(0x800805b8), 4).hex() == R.w(0x800805b8, '39298130')
if HURTBOX_HOOK:
    # cPlayer::Main marks invincible hurtboxes as 2. JP accepts any nonzero
    # flags here; US requires bit 0, excluding the target before either hook.
    assert HURTBOX_ORIG == 0x700A0001
    assert int.from_bytes(read(HURTBOX_HOOK, 4), 'big') == HURTBOX_ORIG
    assert read(HURTBOX_HOOK + 4, 4).hex() == '4182027c'

BASE_HI = hi(REGION)                 # lis base for the region's own data (0x8019 for the OnFrame layout)
def rel(addr):
    v = addr - (BASE_HI << 16)
    assert -0x8000 <= v < 0x8000, hex(addr)
    return v
SCR = rel(REGION + SCRATCH_OFF)
PRM = rel(REGION + PARAMS_OFF)
PARAM_LAYOUT = [('marker', 0x00), ('flags', 0x04), ('energy_per_hit', 0x08), ('cap_per_step', 0x0C), ('keep_frames', 0x10),
                ('player', 0x14), ('in_step_prev', 0x18), ('step_absorbed', 0x1C), ('total_absorbed', 0x20), ('total_energy', 0x24),
                ('steps', 0x28), ('last_target', 0x2C), ('hits_seen', 0x30), ('fx_group', 0x34), ('fx_id', 0x38), ('se1', 0x3C),
                ('se2', 0x40), ('frame', 0x44), ('last_fx_frame', 0x48), ('fx_spawned', 0x4C), ('reserved', 0x50)]
P = {name: PRM + off for name, off in PARAM_LAYOUT}
ks = Ks(KS_ARCH_PPC, KS_MODE_PPC32 | KS_MODE_BIG_ENDIAN)

# BltHitCk first queries BltHitEm, which calls BltDmageSet with damage disabled
# (r6 at hook B is zero), then commits the hit at hook A. Count only that commit.
# Both regions since 2026-10-06 (the JP build used to count the query as well).
AREA_COMMIT_CHECK = 'cmpwi 6,0\nbeqlr\n'

body0 = f'''
lis 10,{BASE_HI}
lwz 0,{P['marker']}(10)
lis 11,{MARKER >> 16}
ori 11,11,{MARKER & 0xFFFF}
cmpw 0,11
beq init_ok
stw 11,{P['marker']}(10)
li 0,{DEFAULTS['flags']}
stw 0,{P['flags']}(10)
li 0,{DEFAULTS['energy_per_hit']}
stw 0,{P['energy_per_hit']}(10)
li 0,{DEFAULTS['cap_per_step']}
stw 0,{P['cap_per_step']}(10)
li 0,{DEFAULTS['keep_frames']}
stw 0,{P['keep_frames']}(10)
li 0,{DEFAULTS['fx_group']}
stw 0,{P['fx_group']}(10)
li 0,{DEFAULTS['fx_id']}
stw 0,{P['fx_id']}(10)
li 0,{DEFAULTS['se1']}
stw 0,{P['se1']}(10)
li 0,{DEFAULTS['se2']}
stw 0,{P['se2']}(10)
li 0,0
stw 0,{P['player']}(10)
stw 0,{P['in_step_prev']}(10)
stw 0,{P['step_absorbed']}(10)
stw 0,{P['total_absorbed']}(10)
stw 0,{P['total_energy']}(10)
stw 0,{P['steps']}(10)
stw 0,{P['last_target']}(10)
stw 0,{P['hits_seen']}(10)
stw 0,{P['frame']}(10)
stw 0,{P['last_fx_frame']}(10)
stw 0,{P['fx_spawned']}(10)
stw 0,{P['reserved']}(10)
init_ok:
stw 31,{P['player']}(10)
lwz 11,{P['frame']}(10)
addi 11,11,1
stw 11,{P['frame']}(10)
lwz 0,{P['flags']}(10)
andi. 0,0,1
beq done0
lbz 3,248(31)
lbz 4,249(31)
li 5,0
cmpwi 3,1
bne state_known
cmpwi 4,2
bne state_known
li 5,1
state_known:
lwz 6,{P['in_step_prev']}(10)
cmpwi 5,0
beq store_prev
cmpwi 6,0
bne keep
li 0,0
stw 0,{P['step_absorbed']}(10)
lwz 7,{P['steps']}(10)
addi 7,7,1
stw 7,{P['steps']}(10)
keep:
lwz 0,{P['flags']}(10)
andi. 0,0,4
beq store_prev
lbz 7,1249(31)
andi. 0,7,128
bne store_prev
lwz 8,{P['keep_frames']}(10)
cmplw 7,8
bge store_prev
stb 8,1249(31)
store_prev:
stw 5,{P['in_step_prev']}(10)
done0:
lfs 0,{(ORIG0 & 0xFFFF) - 0x10000}(9)
'''

stubs = f'''
stub_a:
cmpwi 0,0
beq cont_a
lis 10,{BASE_HI}
lwz 12,{P['marker']}(10)
lis 9,{MARKER >> 16}
ori 9,9,{MARKER & 0xFFFF}
cmpw 12,9
bne skip_a
lwz 12,{P['hits_seen']}(10)
addi 12,12,1
stw 12,{P['hits_seen']}(10)
lwz 12,{P['flags']}(10)
andi. 0,12,1
beq skip_a
lwz 12,{P['player']}(10)
cmpwi 12,0
beq skip_a
cmpw 11,12
bne skip_a
lbz 0,248(12)
cmpwi 0,1
bne skip_a
lbz 0,249(12)
cmpwi 0,2
bne skip_a
stw 11,{P['last_target']}(10)
bl absorb_common
skip_a:
b {A_SKIP}
cont_a:
b {A_DAMAGE}

stub_b:
cmpwi 0,0
beq cont_b
{AREA_COMMIT_CHECK}
mflr 0
lis 10,{BASE_HI}
stw 0,{SCR + 12}(10)
lwz 9,{P['marker']}(10)
lis 11,{MARKER >> 16}
ori 11,11,{MARKER & 0xFFFF}
cmpw 9,11
bne ret_b
lwz 9,{P['hits_seen']}(10)
addi 9,9,1
stw 9,{P['hits_seen']}(10)
lwz 9,{P['flags']}(10)
andi. 0,9,3
cmpwi 0,3
bne ret_b
lwz 11,{P['player']}(10)
cmpwi 11,0
beq ret_b
cmpw 12,11
bne ret_b
lbz 0,248(11)
cmpwi 0,1
bne ret_b
lbz 0,249(11)
cmpwi 0,2
bne ret_b
stw 11,{P['last_target']}(10)
bl absorb_common
ret_b:
lis 10,{BASE_HI}
lwz 0,{SCR + 12}(10)
mtlr 0
blr
cont_b:
b {B_CONT}

absorb_common:
mflr 0
stw 0,{SCR + 8}(10)
stwu 1,-32(1)
lwz 12,{P['cap_per_step']}(10)
cmpwi 12,0
beq cap_ok
lwz 0,{P['step_absorbed']}(10)
cmplw 0,12
bge absorb_exit
cap_ok:
lwz 12,{P['step_absorbed']}(10)
addi 12,12,1
stw 12,{P['step_absorbed']}(10)
lwz 12,{P['total_absorbed']}(10)
addi 12,12,1
stw 12,{P['total_absorbed']}(10)
lwz 9,{ROOT_R13}(13)
lha 12,{ENERGY}(9)
lha 0,{ENERGY_MAX}(9)
lwz 11,{P['energy_per_hit']}(10)
add 12,12,11
cmpw 12,0
ble no_clamp
mr 12,0
no_clamp:
sth 12,{ENERGY}(9)
lwz 12,{P['total_energy']}(10)
add 12,12,11
stw 12,{P['total_energy']}(10)
lis 3,{HUD_STRUCT >> 16}
addi 3,3,{HUD_STRUCT & 0xFFFF}
lis 0,{HUD_UP >> 16}
ori 0,0,{HUD_UP & 0xFFFF}
mtctr 0
bctrl
lis 10,{BASE_HI}
lwz 12,{P['flags']}(10)
andi. 0,12,24
beq absorb_exit
andi. 0,12,32
beq fx_go
lwz 11,{P['frame']}(10)
lwz 0,{P['last_fx_frame']}(10)
cmpw 11,0
beq absorb_exit
fx_go:
lwz 11,{P['frame']}(10)
stw 11,{P['last_fx_frame']}(10)
andi. 0,12,8
beq sound
lwz 3,{P['fx_group']}(10)
lwz 4,{P['fx_id']}(10)
lis 0,{EST_GET >> 16}
ori 0,0,{EST_GET & 0xFFFF}
mtctr 0
bctrl
lis 10,{BASE_HI}
cmpwi 3,0
beq sound
stw 3,{SCR + 16}(10)
lwz 3,{P['fx_group']}(10)
lis 0,{EST_OWNER >> 16}
ori 0,0,{EST_OWNER & 0xFFFF}
mtctr 0
bctrl
lis 10,{BASE_HI}
mr 7,3
lwz 6,{SCR + 16}(10)
lwz 3,{P['player']}(10)
mr 10,3
li 4,0
li 5,0
li 8,0
li 9,0
li 0,0
stw 0,8(1)
lis 0,{ESP_CREATE >> 16}
ori 0,0,{ESP_CREATE & 0xFFFF}
mtctr 0
bctrl
lis 10,{BASE_HI}
lwz 12,{P['fx_spawned']}(10)
addi 12,12,1
stw 12,{P['fx_spawned']}(10)
sound:
lis 10,{BASE_HI}
lwz 12,{P['flags']}(10)
andi. 0,12,16
beq absorb_exit
lwz 4,{P['se1']}(10)
cmpwi 4,0
beq se_second
li 3,0
li 5,0
li 6,0
lis 0,{SE_PLAY >> 16}
ori 0,0,{SE_PLAY & 0xFFFF}
mtctr 0
bctrl
lis 10,{BASE_HI}
se_second:
lwz 4,{P['se2']}(10)
cmpwi 4,0
beq absorb_exit
li 3,0
li 5,0
li 6,0
lis 0,{SE_PLAY >> 16}
ori 0,0,{SE_PLAY & 0xFFFF}
mtctr 0
bctrl
absorb_exit:
lis 10,{BASE_HI}
addi 1,1,32
lwz 0,{SCR + 8}(10)
mtlr 0
blr
'''
code0 = bytes(ks.asm(body0, addr=REGION)[0])
assert code0[-4:] == ORIG0.to_bytes(4, 'big'), code0[-4:].hex()
disp = RESUME0 - (REGION + len(code0))
assert disp % 4 == 0 and -0x2000000 <= disp < 0x2000000
code0 += (0x48000000 | (disp & 0x03FFFFFC)).to_bytes(4, 'big')
assert (0x4E800020).to_bytes(4, 'big') not in code0 and b'\x4e\x80\x04\x21' not in code0
STUBS = REGION + len(code0)
code1 = bytes(ks.asm(stubs, addr=STUBS)[0])
code = code0 + code1
hurtbox_stub = None
hurtbox_asm = ''
if HURTBOX_HOOK:
    hurtbox_stub = REGION + len(code)
    # Only the original output r10 and CR0 may change. r0 (hurtbox flags), r9,
    # the stack, and the hurtbox records themselves remain intact. Geometry,
    # other actors, non-step invincibility, and disabled absorption stay retail.
    hurtbox_asm = f'''
andi. 10,0,1
bne hurtbox_done
andi. 10,0,2
beq hurtbox_done
stwu 1,-16(1)
stw 9,8(1)
lis 9,{BASE_HI}
lwz 10,{P['marker']}(9)
xoris 10,10,{MARKER >> 16}
xori 10,10,{MARKER & 0xFFFF}
cmpwi 10,0
bne hurtbox_deny
lwz 10,{P['flags']}(9)
andi. 10,10,1
beq hurtbox_deny
lwz 10,{P['player']}(9)
cmpw 31,10
bne hurtbox_deny
lbz 10,248(31)
cmpwi 10,1
bne hurtbox_deny
lbz 10,249(31)
cmpwi 10,2
bne hurtbox_deny
lbz 10,1249(31)
cmpwi 10,0
beq hurtbox_deny
li 10,1
b hurtbox_restore
hurtbox_deny:
li 10,0
hurtbox_restore:
lwz 9,8(1)
addi 1,1,16
hurtbox_done:
cmpwi 10,0
b {HURTBOX_HOOK + 4}
'''
    code += bytes(ks.asm(hurtbox_asm, addr=hurtbox_stub)[0])
assert len(code) <= CODE_MAX, len(code)
insns = list(md.disasm(code, REGION))
assert len(insns) == len(code) // 4
for ins in insns:
    assert not (ins.mnemonic == 'addi' and ins.op_str.startswith('r0, r0')), ins
for a, b in zip(insns, insns[1:]):            # `lwz r0,X / li r0,imm` is the addi-with-rA=r0 trap (capstone prints it as li)
    assert not (a.mnemonic == 'lwz' and a.op_str.startswith('r0,') and b.mnemonic == 'li' and b.op_str.startswith('r0,')), (a, b)
stub_a = STUBS
a_end = next(i for i in insns if i.address >= STUBS and i.mnemonic == 'b' and int(i.op_str, 16) == A_DAMAGE)
stub_b = a_end.address + 4
b_end = next(i for i in insns if i.address >= stub_b and i.mnemonic == 'b' and int(i.op_str, 16) == B_CONT)
absorb_common = b_end.address + 4
assert insns[(stub_b - REGION) // 4].mnemonic == 'cmpwi' and insns[(absorb_common - REGION) // 4].mnemonic == 'mflr'
hook_words = {}
hook_targets = [(HOOK0, REGION), (HOOK_A, stub_a), (HOOK_B, stub_b)]
if HURTBOX_HOOK:
    hook_targets.append((HURTBOX_HOOK, hurtbox_stub))
for hook, target in hook_targets:
    d = target - hook
    assert d % 4 == 0 and -0x2000000 <= d < 0x2000000
    hook_words[hook] = 0x48000000 | (d & 0x03FFFFFC)
assert len(code) <= SCRATCH_OFF and PARAMS_OFF + 0x60 <= REGION_END - REGION

out = Path(__file__).parent / ('absorb-v02-build' + R.suffix)
out.mkdir(exist_ok=True)
(out / 'absorb.s').write_text(body0 + '\n; ---- stubs ----\n' + stubs + hurtbox_asm)
(out / 'absorb.bin').write_bytes(code)
(out / 'absorb.dis.txt').write_text('\n'.join(f'{i.address:08X}: {i.bytes.hex().upper()}  {i.mnemonic:9} {i.op_str}' for i in insns) + '\n')
patch = [f'0x{REGION + o:08X}:dword:0x{int.from_bytes(code[o:o + 4], "big"):08X}:0x00000000' for o in range(0, len(code), 4)]
patch.append(f'0x{HOOK0:08X}:dword:0x{hook_words[HOOK0]:08X}:0x{ORIG0:08X}')
patch.append(f'0x{HOOK_A:08X}:dword:0x{hook_words[HOOK_A]:08X}:0x{ORIG_A:08X}')
patch.append(f'0x{HOOK_B:08X}:dword:0x{hook_words[HOOK_B]:08X}:0x{ORIG_B:08X}')
if HURTBOX_HOOK:
    patch.append(f'0x{HURTBOX_HOOK:08X}:dword:0x{hook_words[HURTBOX_HOOK]:08X}:0x{HURTBOX_ORIG:08X}')
(out / 'patch.txt').write_text('\n'.join(patch) + '\n')
params_abs = {name: REGION + PARAMS_OFF + off for name, off in PARAM_LAYOUT}


def imm_line(value):
    """Patch line of the first `li r0, value` in body 0's init block."""
    for i in insns:
        if i.address < STUBS and i.mnemonic == 'li':
            op = i.op_str.replace('r0, ', '')
            v = int(op, 16) if op.startswith('0x') else int(op)
            if v == value:
                return f'0x{i.address:08X}:dword:0x{int.from_bytes(i.bytes, "big"):08X}:0x00000000'
    return None


manifest = {
    'hook0': HOOK0, 'orig0': ORIG0, 'resume0': RESUME0, 'hook_a': HOOK_A, 'orig_a': ORIG_A, 'hook_b': HOOK_B, 'orig_b': ORIG_B,
    'hook_words': {hex(k): v for k, v in hook_words.items()}, 'stub_a': stub_a, 'stub_b': stub_b, 'absorb_common': absorb_common,
    'a_damage': A_DAMAGE, 'a_skip': A_SKIP, 'b_cont': B_CONT, 'hud_up': HUD_UP, 'hud_struct': HUD_STRUCT,
    'est_get': EST_GET, 'est_owner': EST_OWNER, 'esp_create': ESP_CREATE, 'se_play': SE_PLAY,
    'region': REGION, 'region_end': REGION_END, 'scratch_offset': SCRATCH_OFF, 'params_offset': PARAMS_OFF,
    'delivery': 'OnFrame conditional dword patches', 'bytes': len(code), 'body0_bytes': len(code0),
    'sha256': hashlib.sha256(code).hexdigest(), 'patch_entries': len(patch), 'marker': MARKER, 'params': params_abs, 'defaults': DEFAULTS,
    'root_r13': ROOT_R13, 'energy': ENERGY, 'energy_max': ENERGY_MAX,
    'default_patch_lines': {'energy_per_hit': imm_line(DEFAULTS['energy_per_hit']), 'flags': imm_line(DEFAULTS['flags']),
                            'fx_id': imm_line(DEFAULTS['fx_id']), 'se1': imm_line(DEFAULTS['se1']), 'se2': imm_line(DEFAULTS['se2'])},
}
manifest['area_requires_damage_commit'] = True
if HURTBOX_HOOK:
    manifest['hurtbox_hook'] = HURTBOX_HOOK
    manifest['hurtbox_orig'] = HURTBOX_ORIG
    manifest['hurtbox_stub'] = hurtbox_stub
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps({k: (hex(v) if isinstance(v, int) else v) for k, v in manifest.items() if k in ('hook_words', 'stub_a', 'stub_b', 'absorb_common', 'bytes', 'patch_entries', 'sha256', 'default_patch_lines')}, indent=2))
print('params', {k: hex(v) for k, v in params_abs.items()})
