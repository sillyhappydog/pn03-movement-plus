"""Build the C-stick independent camera v0.11 for GPNJ08 (P.N.03 Japan).

v0.10 plus the paced swing: a yaw request that also carries config flags bit5 (0x20, movement v0.19's Z
quick turn) is paced to Vanessa's own rotation. From the latch on, every frame the hook measures her yaw
change (player+0xD0 against the previous frame), and when it is at least `step_min` that change becomes
the goal step and its sign the goal direction; the camera therefore turns by exactly what she turned,
one frame behind her, in her spin direction (the direction rule of v0.9 still decides the long way round
for a goal more than 170 degrees away, which is how an exactly opposite goal follows her spin). While no
rotation has been seen yet the camera holds still; once she stops it keeps the last step until the goal
is within one step and snaps. A request for the camera's current yaw snaps at once. Reason (live sample,
2026-10-08): the 180-degree turn rotates her 18 degrees per frame on average (peak 26.6), so the constant
12-degree step of v0.9/v0.10 arrived 7 frames after her. Runtime words +0x4C her last yaw, +0x50 paced.

v0.10 notes follow.

v0.9 plus the camera lock: while config flags bit4 (0x10, raised by movement v0.18 during a Z quick turn
and for two frames after it) is set, the C-stick is ignored entirely (no rotation, no cancelling of a
pending swing). Reason (live sample, 2026-10-08): the C-stick is held to select the quarter turn, so
during the turn it rotated the camera about 10 degrees per frame and cancelled the turn's swing; the
camera overshot her final facing and the end-of-turn follow pulled it back. Without a valid config
block the stick works as before.

v0.9 notes follow.

v0.7 plus a per-request swing step and direction, for the movement patch's Z quick turn request
(movement v0.17, 2026-10-08). Background: during the Z quick turn the movement patch used to raise
the follow flag every frame, so the camera chased Vanessa's *current* facing by the shortest path;
started while she faces the camera, that chase swung the camera out and back ("double processing" in
the user's recording). Movement v0.17 instead sends one yaw request (config +0x30, flags bit3) aimed
at her final facing, together with a signed step in config +0x38: the magnitude is the yaw change per
frame (12 degrees, about her own turn rate), the sign is her spin direction.

v0.9 reads +0x38 when it latches a bit3 request: a value whose magnitude is between `step_min`
(1 degree) and pi becomes the goal step and its sign the goal direction; anything else (0, NaN, tiny,
huge) keeps the default
`swing_step` (30 degrees) and no direction. A follow request (bit1) always uses the default step and
no direction. The swing then moves the yaw by the goal step per frame toward the goal; when a
direction is set and the remaining angle exceeds `dir_threshold` (170 degrees) it turns in that
direction even if that is the long way round, otherwise it takes the shorter side (exactly 180
degrees goes +yaw). A goal that is already within one step snaps at once, so a request for the
camera's current yaw moves nothing. v0.8's direct eye placement is not used (rejected in play).

Same as v0.7 otherwise: config-driven sensitivity (default 0.0036 = 6x), C-stick axis exclusivity,
the matrix rebuild through the game's C_MTXRotRad, cancel by a C-stick push, the game's own view
reset (SDA -0x7FE0) and a re-initialisation of the yaw state. Data words: +0x30 default step,
+0x34 goal yaw, +0x38 goal active, +0x3C goal step, +0x40 goal direction (0 / 1 / -1), +0x44
direction threshold, +0x48 minimum request step; the runtime words' patch lines write 0 only while
the word is 0.
Delivery is unchanged: [OnFrame] conditional dword patches into the top of the retail debug-text
bump buffer (0x80188130..0x80191730), hook 0x80018200 replaced by a branch while it still holds
the original word, body ends with the original instruction and a branch back.
This does not modify the original DOL or ISO.

usage: build_camera_v11.py [default swing step in degrees per frame, default 30] [direction threshold degrees, default 170]
"""
from pathlib import Path
import struct, sys, json, hashlib, math
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
from keystone import Ks, KS_ARCH_PPC, KS_MODE_PPC32, KS_MODE_BIG_ENDIAN
from dol import read, md
from regions import R, hi, lo, hiu, lou

HOOK = R.a(0x80018200)
ORIGINAL = R.w(0x80018200, 0x3B9F056C)            # addi r28, r31, 0x56c
REGION = R.a(0x80191000)              # body load address (top part of the debug text bump buffer)
REGION_END = R.a(0x801916C0)          # exclusive; the config block starts here
CONFIG = R.config
HELPER = R.a(0x800FC494)              # math helper called through ctr
MAGIC = 0x504E3034
DEFAULT_SENSITIVITY = 0.0036   # 6x (user's 2026-10-01 choice; was 0.0024 = 4x)
SWING_STEP_DEG = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0   # default swing toward a goal, degrees per frame (X reset, follow)
DIR_THRESHOLD_DEG = float(sys.argv[2]) if len(sys.argv) > 2 else 170.0   # above this remaining angle a requested direction wins over the shorter side
STEP_MIN_DEG = 1.0             # a requested step below this (or 0 / NaN) means "use the default step"
REQUEST_STEP_OFFSET = 0x38     # config word: signed step of a bit3 request (movement v0.17)
LOCK_FLAG_BIT = 0x10           # config flags bit4: ignore the C-stick (movement v0.18, Z quick turn)
PACED_FLAG_BIT = 0x20          # config flags bit5 with bit3: pace the swing to her rotation (movement v0.19)
assert 0 < SWING_STEP_DEG < 180 and 0 < DIR_THRESHOLD_DEG <= 180
CFG_HI = ((CONFIG + 0x8000) >> 16) & 0xFFFF
CFG_LO = CONFIG - (CFG_HI << 16)
assert -0x8000 <= CFG_LO < 0x8000
assert int.from_bytes(read(HOOK, 4), 'big') == ORIGINAL
assert read(R.a(0x800181fc), 4).hex() == R.w(0x800181fc, 'c3c90544')
assert read(R.a(0x80018204), 4).hex() == R.w(0x80018204, 'd00100b8')
assert read(R.a(0x80080588), 4).hex() == R.w(0x80080588, '3d208019') and read(R.a(0x8008058c), 4).hex() == R.w(0x8008058c, '39291730')   # bump limit 0x80191730
assert read(R.a(0x800805b8), 4).hex() == R.w(0x800805b8, '39298130')                                                # bump base 0x80188130
ks = Ks(KS_ARCH_PPC, KS_MODE_PPC32 | KS_MODE_BIG_ENDIAN)


def fword(f):
    return struct.unpack('>I', struct.pack('>f', f))[0]


lines = []


def emit(s):
    lines.extend(s.strip().splitlines())


emit('''
stwu 1,-384(1)
stw 0,8(1)
''')
for r in range(3, 13):
    emit(f'stw {r},{12 + (r - 3) * 4}(1)')
emit('''
mflr 0
stw 0,52(1)
mfcr 0
stw 0,56(1)
mfctr 0
stw 0,60(1)
mfxer 0
stw 0,64(1)
mfspr 0,912
stw 0,68(1)
li 0,0
mtspr 912,0
''')
for f in range(14):
    o = 80 + f * 16
    emit(f'stfd {f},{o}(1)')
    emit(f'.long 0x{(60 << 26) | (f << 21) | (1 << 16) | (o + 8):08x}')  # psq_st f,off(r1),0,0
emit('''
mffs 0
stfd 0,72(1)
nop
bl data_end
data:
.long 0
.long 0
''')
# data+0x00 actor pointer (owner of the yaw state), +0x04 camera yaw, then the words below
DATA_TAIL = [
    ('default_sensitivity', fword(DEFAULT_SENSITIVITY)),   # +0x08
    ('zero', fword(0.0)),                                  # +0x0C
    ('pi', fword(3.141592653589793)),                      # +0x10
    ('two_pi', fword(6.283185307179586)),                  # +0x14
    ('minus_pi', fword(-3.141592653589793)),               # +0x18
    ('one', fword(1.0)),                                   # +0x1C
    ('magic_hi', 0x43300000),                              # +0x20
    ('magic_lo', 0x80000000),                              # +0x24
    ('sensitivity_min', fword(0.00001)),                   # +0x28
    ('sensitivity_max', fword(0.1)),                       # +0x2C
    ('swing_step', fword(math.radians(SWING_STEP_DEG))),   # +0x30  default radians per frame toward the goal yaw
    ('goal_yaw', 0),                                       # +0x34  runtime: goal yaw (f32)
    ('goal_active', 0),                                    # +0x38  runtime: 1 while a goal is pending
    ('goal_step', 0),                                      # +0x3C  runtime: radians per frame for the current goal (f32)
    ('goal_dir', 0),                                       # +0x40  runtime: 0 shorter side, 1 +yaw, -1 -yaw when the remainder is large
    ('dir_threshold', fword(math.radians(DIR_THRESHOLD_DEG))),   # +0x44  remainder above which goal_dir wins
    ('step_min', fword(math.radians(STEP_MIN_DEG))),       # +0x48  smallest requested step that is honoured
    ('her_last_yaw', 0),                                   # +0x4C  runtime: her yaw seen last frame (paced swing)
    ('paced', 0),                                          # +0x50  runtime: 1 while the swing follows her rotation
]
for name, value in DATA_TAIL:
    emit(f'.long 0x{value:08x}')
emit(f'''
data_end:
mflr 12
stw 12,320(1)
lwz 0,0(12)
cmpw 0,31
bne initialize
lbz 0,{R.snap_sda}(13)
cmpwi 0,0
beq input
initialize:
stw 31,0(12)
lfs 0,208(31)
stfs 0,4(12)
li 0,0
stw 0,56(12)
stw 0,80(12)
input:
lis 11,{CFG_HI}
lwz 0,{CFG_LO}(11)
lis 9,0x504e
ori 9,9,0x3034
cmpw 0,9
bne input_pad
lwz 0,{CFG_LO + 0x1C}(11)
andi. 0,0,{LOCK_FLAG_BIT}
bne matrix
input_pad:
lis 11,0x801a
lbz 0,{R.pad - 0x801A0000 + 8}(11)
cmpwi 0,0
bne matrix
lbz 10,{R.pad - 0x801A0000 + 2}(11)
extsb 10,10
lbz 9,{R.pad - 0x801A0000 + 3}(11)
extsb 9,9
srawi 8,9,31
xor 9,9,8
subf 9,8,9
srawi 8,10,31
xor 0,10,8
subf 0,8,0
cmpw 9,0
bgt matrix
cmpwi 10,10
bgt right
cmpwi 10,-10
blt left
b matrix
right:
addi 10,10,-10
b convert
left:
addi 10,10,10
convert:
li 9,0
stw 9,56(12)
stw 9,80(12)
xoris 0,10,0x8000
stw 0,332(1)
lis 0,0x4330
stw 0,328(1)
lfd 0,328(1)
lfd 1,32(12)
fsub 0,0,1
frsp 0,0
lis 11,{CFG_HI}
lwz 0,{CFG_LO}(11)
lis 9,0x504e
ori 9,9,0x3034
cmpw 0,9
bne sensitivity_default
lfs 1,{CFG_LO + 8}(11)
lfs 13,40(12)
fcmpu 0,1,13
blt sensitivity_default
bso sensitivity_default
lfs 13,44(12)
fcmpu 0,1,13
bgt sensitivity_default
b sensitivity_ready
sensitivity_default:
lfs 1,8(12)
sensitivity_ready:
fmuls 0,0,1
lfs 1,4(12)
fsubs 0,1,0
lfs 1,16(12)
fcmpu 0,0,1
ble low_wrap
lfs 1,20(12)
fsubs 0,0,1
low_wrap:
lfs 1,24(12)
fcmpu 0,0,1
bge store_yaw
lfs 1,20(12)
fadds 0,0,1
store_yaw:
stfs 0,4(12)
matrix:
lis 11,{CFG_HI}
lwz 0,{CFG_LO}(11)
lis 9,0x504e
ori 9,9,0x3034
cmpw 0,9
bne goal_step
lwz 9,{CFG_LO + 0x1C}(11)
andi. 0,9,8
beq check_follow
lfs 0,{CFG_LO + 0x30}(11)
stfs 0,52(12)
li 0,1
stw 0,56(12)
andi. 0,9,{PACED_FLAG_BIT}
rlwinm 9,9,0,29,27
rlwinm 9,9,0,27,25
stw 9,{CFG_LO + 0x1C}(11)
beq request_unpaced
li 0,1
stw 0,80(12)
li 0,0
stw 0,64(12)
lfs 0,72(12)
stfs 0,60(12)
lfs 0,208(31)
stfs 0,76(12)
b goal_step
request_unpaced:
li 0,0
stw 0,80(12)
lfs 0,{CFG_LO + REQUEST_STEP_OFFSET}(11)
fabs 2,0
lfs 1,72(12)
fcmpu 0,2,1
bso request_default
blt request_default
lfs 1,16(12)
fcmpu 0,2,1
bgt request_default
stfs 2,60(12)
lfs 1,12(12)
fcmpu 0,0,1
blt request_negative
li 0,1
stw 0,64(12)
b goal_step
request_negative:
li 0,-1
stw 0,64(12)
b goal_step
request_default:
lfs 0,48(12)
stfs 0,60(12)
li 0,0
stw 0,64(12)
b goal_step
check_follow:
andi. 0,9,2
beq goal_step
lfs 0,208(31)
stfs 0,52(12)
li 0,1
stw 0,56(12)
lfs 0,48(12)
stfs 0,60(12)
li 0,0
stw 0,64(12)
stw 0,80(12)
goal_step:
lwz 0,56(12)
cmpwi 0,0
beq no_follow
lfs 0,52(12)
lfs 1,4(12)
fsubs 0,0,1
lfs 1,16(12)
fcmpu 0,0,1
ble d_not_high
lfs 1,20(12)
fsubs 0,0,1
d_not_high:
lfs 1,24(12)
fcmpu 0,0,1
bgt d_ok
lfs 1,20(12)
fadds 0,0,1
d_ok:
fabs 2,0
lwz 9,80(12)
cmpwi 9,0
beq paced_done
lfs 4,208(31)
lfs 5,76(12)
stfs 4,76(12)
fsubs 4,4,5
lfs 6,16(12)
fcmpu 0,4,6
ble pd_not_high
lfs 6,20(12)
fsubs 4,4,6
pd_not_high:
lfs 6,24(12)
fcmpu 0,4,6
bgt pd_ok
lfs 6,20(12)
fadds 4,4,6
pd_ok:
fabs 5,4
lfs 6,72(12)
fcmpu 0,5,6
blt paced_no_rotation
stfs 5,60(12)
lfs 6,12(12)
fcmpu 0,4,6
blt paced_negative
li 9,1
stw 9,64(12)
b paced_done
paced_negative:
li 9,-1
stw 9,64(12)
b paced_done
paced_no_rotation:
lwz 9,64(12)
cmpwi 9,0
bne paced_done
lfs 3,60(12)
fcmpu 0,2,3
bgt no_follow
b snap_goal
paced_done:
lfs 3,60(12)
fcmpu 0,2,3
bgt partial
snap_goal:
lfs 0,52(12)
stfs 0,4(12)
li 0,0
stw 0,56(12)
stw 0,80(12)
b no_follow
partial:
lwz 9,64(12)
cmpwi 9,0
beq dir_shortest
lfs 1,68(12)
fcmpu 0,2,1
ble dir_shortest
cmpwi 9,0
lfs 1,4(12)
blt step_negative
fadds 0,1,3
b step_wrap
dir_shortest:
lfs 1,12(12)
fcmpu 0,0,1
lfs 1,4(12)
blt step_negative
fadds 0,1,3
b step_wrap
step_negative:
fsubs 0,1,3
step_wrap:
lfs 1,16(12)
fcmpu 0,0,1
ble step_low
lfs 1,20(12)
fsubs 0,0,1
step_low:
lfs 1,24(12)
fcmpu 0,0,1
bge step_store
lfs 1,20(12)
fadds 0,0,1
step_store:
stfs 0,4(12)
no_follow:
lwz 0,3080(31)
stw 0,340(1)
lwz 0,3096(31)
stw 0,344(1)
lwz 0,3112(31)
stw 0,348(1)
lfs 1,4(12)
addi 3,31,3068
li 4,121
lis 11,{hiu(HELPER)}
ori 11,11,{lou(HELPER)}
mtctr 11
bctrl
lwz 0,340(1)
stw 0,3080(31)
lwz 0,344(1)
stw 0,3096(31)
lwz 0,348(1)
stw 0,3112(31)
lfd 0,72(1)
mtfsf 255,0
''')
for f in range(14):
    o = 80 + f * 16
    emit(f'.long 0x{(56 << 26) | (f << 21) | (1 << 16) | (o + 8):08x}')  # psq_l
    emit(f'lfd {f},{o}(1)')
emit('''
lwz 0,68(1)
mtspr 912,0
lwz 0,64(1)
mtxer 0
lwz 0,60(1)
mtctr 0
lwz 0,56(1)
mtcrf 255,0
lwz 0,52(1)
mtlr 0
''')
for r in range(3, 13):
    emit(f'lwz {r},{12 + (r - 3) * 4}(1)')
emit('''
lwz 0,8(1)
addi 1,1,384
addi 28,31,1388
''')
asm = '\n'.join(lines) + '\n'
code = bytes(ks.asm(asm, addr=REGION)[0])
assert code[-4:] == ORIGINAL.to_bytes(4, 'big')
disp = (HOOK + 4) - (REGION + len(code))
assert disp % 4 == 0 and -0x2000000 <= disp < 0x2000000
RETURN_WORD = 0x48000000 | (disp & 0x03FFFFFC)
code += RETURN_WORD.to_bytes(4, 'big')
assert REGION + len(code) <= REGION_END, (len(code), REGION_END - REGION)
disp = REGION - HOOK
assert disp % 4 == 0 and -0x2000000 <= disp < 0x2000000
HOOK_WORD = 0x48000000 | (disp & 0x03FFFFFC)
out = Path(__file__).parent / ('camera-v11-build' + R.suffix)
out.mkdir(exist_ok=True)
(out / 'camera.s').write_text(asm)
(out / 'camera.bin').write_bytes(code)
insns = list(md.disasm(code, REGION))
data_off = next(i.address + 4 - REGION for i in insns if i.mnemonic == 'bl')
assert data_off % 4 == 0
patch = [f'0x{REGION + o:08X}:dword:0x{int.from_bytes(code[o:o + 4], "big"):08X}:0x00000000' for o in range(0, len(code), 4)]
patch.append(f'0x{HOOK:08X}:dword:0x{HOOK_WORD:08X}:0x{ORIGINAL:08X}')
(out / 'patch.txt').write_text('\n'.join(patch) + '\n')
(out / 'camera.dis.txt').write_text('\n'.join(f'{i.address:08x}: {i.bytes.hex()} {i.mnemonic} {i.op_str}' for i in insns))
default_off = data_off + 8
step_off, thresh_off, min_off = data_off + 0x30, data_off + 0x44, data_off + 0x48
manifest = {'hook': HOOK, 'original': ORIGINAL, 'hook_word': HOOK_WORD, 'return_word': RETURN_WORD,
            'region': REGION, 'region_end': REGION_END, 'delivery': 'OnFrame conditional dword patches',
            'data_offset': data_off, 'data_end': data_off + 8 + 4 * len(DATA_TAIL),
            'bytes': len(code), 'sha256': hashlib.sha256(code).hexdigest(), 'config_block': CONFIG, 'config_magic': MAGIC,
            'default_sensitivity': DEFAULT_SENSITIVITY, 'follow_flag_bit': 2, 'request_flag_bit': 8, 'request_offset': 0x30,
            'request_step_offset': REQUEST_STEP_OFFSET, 'lock_flag_bit': LOCK_FLAG_BIT, 'paced_flag_bit': PACED_FLAG_BIT,
            'her_last_yaw_offset': data_off + 0x4C, 'paced_offset': data_off + 0x50,
            'swing_step_deg': SWING_STEP_DEG, 'swing_step_offset': step_off, 'goal_yaw_offset': data_off + 0x34,
            'goal_active_offset': data_off + 0x38, 'goal_step_offset': data_off + 0x3C, 'goal_dir_offset': data_off + 0x40,
            'dir_threshold_deg': DIR_THRESHOLD_DEG, 'dir_threshold_offset': thresh_off, 'step_min_deg': STEP_MIN_DEG, 'step_min_offset': min_off,
            'default_sensitivity_patch_line': patch[default_off // 4], 'swing_step_patch_line': patch[step_off // 4],
            'dir_threshold_patch_line': patch[thresh_off // 4], 'step_min_patch_line': patch[min_off // 4],
            'patch_entries': len(patch)}
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps({k: v for k, v in manifest.items() if k in ('bytes', 'sha256', 'region', 'hook_word', 'return_word', 'patch_entries', 'data_offset', 'data_end', 'swing_step_deg', 'dir_threshold_deg', 'swing_step_patch_line', 'dir_threshold_patch_line')}, indent=2))
