"""Build the Sprint Run v0.3 for GPNJ08 (P.N.03 Japan).

v0.2 plus the fix for the forward warp the user saw in Dolphin (2026-10-01: "after reaching
top speed she keeps teleporting forward"):
  * v0.2's hook 2 derived the tick's time step from the layer's own fields, dt = +0x2A8 -
    +0x2AC (+ one cycle when +0x23E == 1). The frame advance 0x800A1770 rebuilds the time
    as frame << 6 and copies the previous time word into +0x2AC on every call, so on a tick
    where the game's advance had looped and body 1 then ran its extra advance, +0x2AC held
    the post-wrap time while body 1 restored the loop flag: dt came out as 17 frames and the
    linearised z moved the player one full cycle (~3500 units) in a single tick. About 40 %
    of the loops at 1.4x did this (Unicorn: 5 warps in 260 ticks). Plain extra-advance ticks
    were also short by up to 0.4 frames (a hitch every 2-3 ticks).
  * hook 2 now uses the factor directly: body 1 constructs the sampled time so that every
    tick advances by exactly `factor` frames (up to the 63/64 clamp), so
    z = (+0x25C.z / +0x2B2) * factor * dist_scale. No layer time field is read.
  * extra guards in hook 2: the player's own state must still be category 1 / sub-state 1
    (the tag is one frame stale at this hook), the layer must be a looping motion
    (+0x23C bit2) and +0x2B2 must be non-zero.
  * marker 'SPR3'; the parameter layout is the same as v0.2.
Everything else (threshold 45, ramp 15, max 1.4, turn cancel, jump inherit, footstep call,
loop-flag restore) is unchanged from v0.2.

Hook 1: 0x800AFE78 (`lis r9, -0x7fe9`), first instruction after the player update's state
dispatch; once per frame for the player, after the state handler ticked the motion. r31 =
player. Hook 2: 0x800A08E8 (`bl 0x800a15ac`) inside the generic motion update 0x800A0810;
r3 = actor, r4 = layer, r5 = local translation delta (Vec3), r6 = rotation delta. Both bodies
use only volatile registers (r0, r3-r12, f0-f13, cr0, lr, ctr).

Delivery: Dolphin [OnFrame] conditional dword patches, region 0x8018D800..0x8018DF00.
"""
from pathlib import Path
import struct, sys, json, hashlib
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
from keystone import Ks, KS_ARCH_PPC, KS_MODE_PPC32, KS_MODE_BIG_ENDIAN
from dol import read, md

HOOK1 = 0x800AFE78
ORIGINAL1 = 0x3D208017           # lis r9, -0x7fe9
RESUME1 = HOOK1 + 4
HOOK2 = 0x800A08E8
ORIGINAL2 = 0x48000CC5           # bl 0x800a15ac
RESUME2 = HOOK2 + 4
APPLY_ROOT = 0x800A15AC
ADVANCE = 0x800A1770             # motion layer frame advance (leaf)
FOOTSTEP = 0x800B5564            # run handler's footstep SE / dust (reads layer +0x2B0 via player+0x42C)
REGION = 0x8018D800
CODE_MAX = 0x500
DATA_OFF = 0x500
SCRATCH_OFF = 0x540
PARAMS_OFF = 0x580
REGION_END = 0x8018DF00          # exclusive; energy drive terrain pass v0.1 body starts here
MARKER = 0x53505233              # 'SPR3'
DEFAULTS = {'flags': 7, 'threshold': 45, 'ramp': 15, 'max_factor': 1.4, 'turn_cancel_rad': 1.0471976, 'dist_scale': 1.0}
FOOTSTEP_FRAMES = (6, 15)

assert int.from_bytes(read(HOOK1, 4), 'big') == ORIGINAL1
assert int.from_bytes(read(HOOK2, 4), 'big') == ORIGINAL2
assert read(0x800AFE74, 4).hex() == '4e800021' and read(0x800AFE64, 4).hex() == '48000014' and read(0x800AFE7C, 4).hex() == 'c1bf00d0'
assert read(0x800A08E4, 4).hex() == '38a10008' and read(0x800A08EC, 4).hex() == '3bdf017c'   # addi r5,r1,8 / addi r30,r31,0x17c
assert read(APPLY_ROOT, 4).hex() == '9421ffd8'
assert read(ADVANCE, 4).hex() == 'a163023c' and read(ADVANCE + 0xD0, 4).hex() == '4e800020'
assert read(FOOTSTEP, 4).hex() == '9421ffe0' and read(FOOTSTEP + 0x14, 4).hex() == 'a01f042c'
assert read(0x800B1D10, 4).hex() == 'd01f0108'      # jump phase 6 stores the forward speed to +0x108
assert read(0x80080588, 4).hex() == '3d208019' and read(0x8008058c, 4).hex() == '39291730'
assert read(0x800805b8, 4).hex() == '39298130'

BASE_HI = 0x8019
DATA = REGION + DATA_OFF - 0x80190000
SCR = REGION + SCRATCH_OFF - 0x80190000
PRM = REGION + PARAMS_OFF - 0x80190000
for v in (DATA, SCR, PRM):
    assert -0x8000 <= v < 0x8000
ks = Ks(KS_ARCH_PPC, KS_MODE_PPC32 | KS_MODE_BIG_ENDIAN)


def fword(f):
    return struct.unpack('>I', struct.pack('>f', f))[0]


DATA_WORDS = [
    ('one', fword(1.0)),                       # +0x00
    ('two_pi', fword(6.283185307179586)),      # +0x04
    ('pi', fword(3.141592653589793)),          # +0x08
    ('minus_pi', fword(-3.141592653589793)),   # +0x0C
    ('max_frac', fword(63 / 64)),              # +0x10
    ('sixty_four', fword(64.0)),               # +0x14
    ('zero', fword(0.0)),                      # +0x18
    ('default_max_factor', fword(DEFAULTS['max_factor'])),        # +0x1C
    ('default_turn_cancel', fword(DEFAULTS['turn_cancel_rad'])),  # +0x20
    ('default_dist_scale', fword(DEFAULTS['dist_scale'])),        # +0x24
    ('magic_hi', 0x43300000),                  # +0x28 (double 2^52, unsigned int -> float)
    ('magic_lo', 0x00000000),                  # +0x2C
    ('inv_sixty_four', fword(1 / 64)),         # +0x30
]
D = {name: DATA + i * 4 for i, (name, _) in enumerate(DATA_WORDS)}
PARAM_LAYOUT = [('marker', 0x00), ('flags', 0x04), ('threshold', 0x08), ('ramp', 0x0C), ('max', 0x10), ('turn', 0x14),
                ('dist', 0x18), ('reserved', 0x1C), ('counter', 0x20), ('tag', 0x24), ('prev_yaw', 0x28), ('acc', 0x2C),
                ('factor', 0x30), ('player', 0x34), ('footsteps', 0x38), ('looped', 0x3C)]
P = {name: PRM + off for name, off in PARAM_LAYOUT}

body1 = f'''
lis 9,{BASE_HI}
lwz 0,{P['marker']}(9)
lis 10,0x5350
ori 10,10,0x5233
cmpw 0,10
beq init_ok
stw 10,{P['marker']}(9)
li 0,{DEFAULTS['flags']}
stw 0,{P['flags']}(9)
li 0,{DEFAULTS['threshold']}
stw 0,{P['threshold']}(9)
li 0,{DEFAULTS['ramp']}
stw 0,{P['ramp']}(9)
lfs 0,{D['default_max_factor']}(9)
stfs 0,{P['max']}(9)
lfs 0,{D['default_turn_cancel']}(9)
stfs 0,{P['turn']}(9)
lfs 0,{D['default_dist_scale']}(9)
stfs 0,{P['dist']}(9)
li 0,0
stw 0,{P['reserved']}(9)
stw 0,{P['counter']}(9)
stw 0,{P['tag']}(9)
stw 0,{P['prev_yaw']}(9)
stw 0,{P['acc']}(9)
stw 0,{P['footsteps']}(9)
stw 0,{P['looped']}(9)
lfs 0,{D['one']}(9)
stfs 0,{P['factor']}(9)
init_ok:
stw 31,{P['player']}(9)
lwz 12,{P['flags']}(9)
andi. 0,12,1
beq done
lbz 0,248(31)
lbz 3,249(31)
lbz 4,250(31)
lwz 5,1528(31)
lwz 6,{P['counter']}(9)
lwz 7,{P['tag']}(9)
cmpwi 0,1
bne reset
cmpwi 3,1
beq run_state
cmpwi 3,3
beq jump_state
cmpwi 3,0
bne reset
cmpwi 7,3
bne reset
li 7,48
b store_state
run_state:
andi. 0,5,1
beq reset
lfs 1,208(31)
cmpwi 7,1
bne run_first
lfs 2,{P['prev_yaw']}(9)
fsubs 3,1,2
lfs 4,{D['pi']}(9)
fcmpu 0,3,4
ble wrap_lo
lfs 4,{D['two_pi']}(9)
fsubs 3,3,4
b wrapped
wrap_lo:
lfs 4,{D['minus_pi']}(9)
fcmpu 0,3,4
bge wrapped
lfs 4,{D['two_pi']}(9)
fadds 3,3,4
wrapped:
fabs 3,3
lfs 4,{P['turn']}(9)
fcmpu 0,3,4
bgt reset_turn
run_first:
stfs 1,{P['prev_yaw']}(9)
addi 6,6,1
cmplwi 6,30000
ble run_ok
li 6,30000
run_ok:
li 7,1
b store_state
reset_turn:
stfs 1,{P['prev_yaw']}(9)
li 6,0
li 7,1
b store_state
jump_state:
lfs 1,208(31)
stfs 1,{P['prev_yaw']}(9)
li 7,3
b store_state
reset:
li 6,0
li 7,0
store_state:
stw 6,{P['counter']}(9)
stw 7,{P['tag']}(9)
lfs 5,{D['one']}(9)
lwz 8,{P['threshold']}(9)
cmplw 6,8
blt factor_done
lfs 5,{P['max']}(9)
lwz 11,{P['ramp']}(9)
cmpwi 11,0
ble factor_done
subf 0,8,6
cmplw 0,11
bge factor_done
lis 10,0x4330
stw 10,{SCR}(9)
stw 0,{SCR + 4}(9)
lfd 6,{SCR}(9)
lfd 7,{D['magic_hi']}(9)
fsub 6,6,7
frsp 6,6
stw 11,{SCR + 4}(9)
lfd 7,{SCR}(9)
lfd 8,{D['magic_hi']}(9)
fsub 7,7,8
frsp 7,7
fdivs 6,6,7
lfs 7,{D['one']}(9)
fsubs 5,5,7
fmuls 5,5,6
fadds 5,5,7
factor_done:
stfs 5,{P['factor']}(9)
cmpwi 7,1
bne not_running
lfs 7,{D['one']}(9)
fcmpu 0,5,7
ble not_running
lfs 6,{P['acc']}(9)
fsubs 8,5,7
fadds 6,6,8
addi 8,31,380
fcmpu 0,6,7
blt no_extra
lbz 0,574(8)
stw 0,{P['looped']}(9)
mr 3,8
lis 0,0x800a
ori 0,0,0x1770
mtctr 0
bctrl
lis 9,{BASE_HI}
addi 8,31,380
lwz 0,{P['looped']}(9)
cmpwi 0,1
bne loop_ok
li 0,1
stb 0,574(8)
loop_ok:
lhz 10,688(8)
cmpwi 10,{FOOTSTEP_FRAMES[0]}
beq footstep
cmpwi 10,{FOOTSTEP_FRAMES[1]}
bne foot_ok
footstep:
mr 3,31
lis 0,0x800b
ori 0,0,0x5564
mtctr 0
bctrl
lis 9,{BASE_HI}
addi 8,31,380
lwz 10,{P['footsteps']}(9)
addi 10,10,1
stw 10,{P['footsteps']}(9)
foot_ok:
lfs 6,{P['acc']}(9)
lfs 5,{P['factor']}(9)
lfs 7,{D['one']}(9)
fsubs 8,5,7
fadds 6,6,8
fsubs 6,6,7
no_extra:
fmr 12,6
lfs 7,{D['max_frac']}(9)
fcmpu 0,12,7
ble frac_ok
fmr 12,7
frac_ok:
lfs 7,{D['sixty_four']}(9)
fmuls 12,12,7
fctiwz 12,12
stfd 12,{SCR}(9)
lwz 0,{SCR + 4}(9)
lhz 10,688(8)
slwi 10,10,6
or 10,10,0
sth 10,680(8)
stfs 6,{P['acc']}(9)
b apply_jump
not_running:
lfs 6,{D['zero']}(9)
stfs 6,{P['acc']}(9)
apply_jump:
cmpwi 7,3
bne done
lwz 12,{P['flags']}(9)
andi. 0,12,2
beq done
lbz 4,250(31)
cmpwi 4,6
bne done
lfs 7,{D['one']}(9)
fcmpu 0,5,7
ble done
lfs 8,264(31)
fmuls 8,8,5
stfs 8,264(31)
done:
lis 9,0x8017
'''
# note: after the extra advance the accumulated debt is recomputed from the stored values
# (acc + factor - 1 - 1) because the calls clobbered f6/f8; the stored acc is still the old one.

body2 = f'''
lis 9,{BASE_HI}
lwz 0,{P['marker']}(9)
lis 10,0x5350
ori 10,10,0x5233
cmpw 0,10
bne call
lwz 0,{P['player']}(9)
cmpw 0,3
bne call
lwz 0,{P['flags']}(9)
andi. 0,0,4
beq call
lwz 0,{P['tag']}(9)
cmpwi 0,1
bne call
lbz 0,248(3)
cmpwi 0,1
bne call
lbz 0,249(3)
cmpwi 0,1
bne call
lhz 0,572(4)
andi. 0,0,4
beq call
lhz 11,690(4)
cmpwi 11,0
beq call
lfs 1,{P['factor']}(9)
lfs 2,{D['one']}(9)
fcmpu 0,1,2
ble call
lis 12,0x4330
stw 12,{SCR}(9)
stw 11,{SCR + 4}(9)
lfd 4,{SCR}(9)
lfd 5,{D['magic_hi']}(9)
fsub 4,4,5
frsp 4,4
lfs 6,612(4)
fdivs 6,6,4
fmuls 6,6,1
lfs 7,{P['dist']}(9)
fmuls 6,6,7
stfs 6,8(5)
call:
lis 0,0x800a
ori 0,0,0x15ac
mtctr 0
bctrl
'''
code1 = bytes(ks.asm(body1, addr=REGION)[0])
assert code1[-4:] == ORIGINAL1.to_bytes(4, 'big'), code1[-4:].hex()
disp = RESUME1 - (REGION + len(code1))
assert disp % 4 == 0 and -0x2000000 <= disp < 0x2000000
code1 += (0x48000000 | (disp & 0x03FFFFFC)).to_bytes(4, 'big')
BODY2 = REGION + len(code1)
code2 = bytes(ks.asm(body2, addr=BODY2)[0])
disp = RESUME2 - (BODY2 + len(code2))
assert disp % 4 == 0 and -0x2000000 <= disp < 0x2000000
code2 += (0x48000000 | (disp & 0x03FFFFFC)).to_bytes(4, 'big')
code = code1 + code2
assert len(code) <= CODE_MAX, len(code)
assert (0x4E800020).to_bytes(4, 'big') not in code          # no blr inside the bodies
data = b''.join(v.to_bytes(4, 'big') for _, v in DATA_WORDS)
assert DATA_OFF + len(data) <= SCRATCH_OFF and PARAMS_OFF + 0x40 <= REGION_END - REGION
hook_words = {}
for hook, target in ((HOOK1, REGION), (HOOK2, BODY2)):
    disp = target - hook
    assert disp % 4 == 0 and -0x2000000 <= disp < 0x2000000
    hook_words[hook] = 0x48000000 | (disp & 0x03FFFFFC)

out = Path(__file__).parent / 'sprint-v03-build'
out.mkdir(exist_ok=True)
(out / 'sprint.s').write_text(body1 + '\n; ---- body2 (hook 0x800A08E8) ----\n' + body2)
(out / 'sprint.bin').write_bytes(code)
(out / 'sprint.data.bin').write_bytes(data)
insns = list(md.disasm(code, REGION))
assert len(insns) == len(code) // 4
patch = [f'0x{REGION + o:08X}:dword:0x{int.from_bytes(code[o:o + 4], "big"):08X}:0x00000000' for o in range(0, len(code), 4)]
patch += [f'0x{REGION + DATA_OFF + o:08X}:dword:0x{int.from_bytes(data[o:o + 4], "big"):08X}:0x00000000' for o in range(0, len(data), 4)]
patch.append(f'0x{HOOK1:08X}:dword:0x{hook_words[HOOK1]:08X}:0x{ORIGINAL1:08X}')
patch.append(f'0x{HOOK2:08X}:dword:0x{hook_words[HOOK2]:08X}:0x{ORIGINAL2:08X}')
(out / 'patch.txt').write_text('\n'.join(patch) + '\n')
(out / 'sprint.dis.txt').write_text('\n'.join(f'{i.address:08x}: {i.bytes.hex()} {i.mnemonic} {i.op_str}' for i in insns))


def li_line(value):
    word = 0x38000000 | (value & 0xFFFF)
    hits = [o for o in range(0, len(code1), 4) if int.from_bytes(code1[o:o + 4], 'big') == word]
    assert len(hits) == 1, (hex(word), hits)
    return patch[hits[0] // 4]


manifest = {'hook1': HOOK1, 'original1': ORIGINAL1, 'hook1_word': hook_words[HOOK1], 'resume1': RESUME1,
            'hook2': HOOK2, 'original2': ORIGINAL2, 'hook2_word': hook_words[HOOK2], 'resume2': RESUME2, 'body2': BODY2,
            'region': REGION, 'region_end': REGION_END, 'data_offset': DATA_OFF, 'scratch_offset': SCRATCH_OFF,
            'params_offset': PARAMS_OFF, 'params': {name: REGION + PARAMS_OFF + off for name, off in PARAM_LAYOUT},
            'delivery': 'OnFrame conditional dword patches', 'bytes': len(code), 'body1_bytes': len(code1), 'data_bytes': len(data),
            'sha256': hashlib.sha256(code).hexdigest(), 'patch_entries': len(patch), 'advance': ADVANCE, 'footstep': FOOTSTEP,
            'apply_root': APPLY_ROOT, 'marker': MARKER, 'defaults': DEFAULTS, 'footstep_frames': FOOTSTEP_FRAMES,
            'default_patch_lines': {**{name: patch[len(code) // 4 + i] for i, (name, _) in enumerate(DATA_WORDS) if name.startswith('default_')},
                                    'threshold': li_line(DEFAULTS['threshold']), 'ramp': li_line(DEFAULTS['ramp']), 'flags': li_line(DEFAULTS['flags'])}}
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps({k: v for k, v in manifest.items() if k in ('bytes', 'body1_bytes', 'data_bytes', 'sha256', 'region', 'body2', 'hook1_word', 'hook2_word', 'patch_entries', 'params', 'default_patch_lines')}, indent=2))
