"""Build Lead Aim v0.1 (偏差射撃) for GPNJ08 (P.N.03 Japan).

The normal (palm) shot is fired at the lock-on target's aim node position as it is at the moment of
firing (player code 0x800AEFB0: aim node = node (target+0x125) of the target, hand = player node 0x18,
angles = 0x800CC574(out, aim, hand), applied to the new shot by 0x8000EA38). Targets that move fast
(Orchidee on its rails, Birne rushing in) are no longer there when the shot arrives, so lock-on shots
miss. This patch aims at the point the target will reach when the shot gets there.

Three hooks, one parameter block ('LEAD' at PARAMS):
  * H1 0x800AFE84 (player update, chained after Dodge Absorb v0.2 which ends with `b 0x800AFE84`):
    per frame, (a) measure the speed of the most recent normal shot from its position deltas during its
    first frames (shot pointer recorded by H3) -> s_meas; (b) track the lock-on target (player+0x5B4):
    fetch its aim node position (0x8009EFB0(target+0xF0, target+0x125) -> +0x108) and keep a smoothed
    per-frame velocity. Target change resets the velocity; implausible jumps (teleport, respawn) are
    ignored for that frame. f0/f13 (live at the hook) are preserved; the body ends with the original
    `fcmpu cr0, f13, f0`.
  * H2 0x800AF16C (`bl 0x800CC574` in the lock-on branch of the shooting code): when the current target
    is the tracked one and its velocity is valid, flight time t = |aim - hand| / S (S = measured speed,
    else s_default), clamped to max_t, scaled by `lead`, and the aim vector at r4 (stack copy) is moved
    by velocity * t. Then the original helper is entered with LR = 0x800AF170 as the `bl` would have.
  * H3 0x800AF1B0 (`cmpwi r3, 0` right after the shot spawn 0x80010448): record the new shot actor for
    the speed measurement, execute the original compare.

Delivery: Dolphin [OnFrame] conditional dword patches, bodies at 0x8018C100..0x8018C4FF, params at
0x8018C500 (debug text bump buffer, below Dodge Absorb v0.2 at 0x8018C800), hook words conditional on
the original instructions. Does not modify the DOL or ISO.
"""
from pathlib import Path
import struct, sys, json, hashlib
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
from keystone import Ks, KS_ARCH_PPC, KS_MODE_PPC32, KS_MODE_BIG_ENDIAN
from dol import read, md

H1, H1_ORIG, H1_RESUME = 0x800AFE84, 0xFC0D0000, 0x800AFE88      # fcmpu cr0, f13, f0
H2, H2_ORIG = 0x800AF16C, 0x4801D409                               # bl 0x800cc574
H2_TARGET, H2_RETURN = 0x800CC574, 0x800AF170
H3, H3_ORIG, H3_RESUME = 0x800AF1B0, 0x2C030000, 0x800AF1B4        # cmpwi r3, 0
NODE_LOOKUP = 0x8009EFB0
REGION = 0x8018C100
PARAMS = 0x8018C500
REGION_END = 0x8018C600                                            # params end; Dodge Absorb v0.2 at 0x8018C800
TARGET = 0x5B4                                                     # player+0x5B4 current lock-on target
AIM_NODE = 0x125                                                   # target+0x125 aim node index (u8)
NODE_TABLE = 0xF0                                                  # object+0xF0 node table

DEFAULTS = dict(lead=1.0, max_t=90.0, s_default=100.0, smooth=0.5, max_vel2=400.0 ** 2, min_vel2=0.25)
ARGS = dict(a.split('=') for a in sys.argv[1:])
for k in ARGS:
    assert k in DEFAULTS, k
    DEFAULTS[k] = float(ARGS[k])

assert int.from_bytes(read(H1, 4), 'big') == H1_ORIG
assert int.from_bytes(read(H2, 4), 'big') == H2_ORIG
assert int.from_bytes(read(H3, 4), 'big') == H3_ORIG
assert read(0x800AFE80, 4).hex() == 'c00991f8'      # lfs f0, -0x6e08(r9)  (Dodge Absorb v0.2 chain end)
assert read(0x800AFE88, 4).hex() == '4c620b82'      # cror
assert read(0x800AF144, 4).hex() == '7fa4eb78'      # mr r4, r29 (aim vector)
assert read(0x800AF154, 4).hex() == '38a10048'      # addi r5, r1, 0x48 (hand vector)
assert read(0x800AF108, 4).hex() == '3ba10028'      # addi r29, r1, 0x28
assert read(0x800AF0FC, 4).hex() == '88890125'      # lbz r4, 0x125(r9) (aim node index)
assert read(0x800AF1AC, 4).hex() == '4bf6129d'      # bl 0x80010448 (shot spawn)
assert read(0x8009EFB0, 4).hex() == '3924ffff'      # node lookup entry
assert read(0x800CC574, 4).hex() == '9421ff90'      # angle helper entry

# ---- parameter block layout (offsets from PARAMS)
P = dict(tag=0x00, flags=0x04, lead=0x08, max_t=0x0C, s_default=0x10, s_meas=0x14, smooth=0x18, max_vel2=0x1C,
         min_vel2=0x20, tgt=0x24, prev=0x28, vel=0x34, valid=0x40, save_f0=0x44, save_f13=0x48, save_lr=0x4C,
         shot=0x50, shot_age=0x54, sprev=0x58, frame=0x64, shots_total=0x68, shots_led=0x6C, last_t=0x70,
         last_d=0x74, pred=0x78, half=0x84, onehalf=0x88, zero=0x8C, s_last_d=0x90, max_t_hits=0x94)
P_HI = (PARAMS + 0x8000) >> 16
P_LO = PARAMS & 0xFFFF
if P_LO >= 0x8000:
    P_LO -= 0x10000
ks = Ks(KS_ARCH_PPC, KS_MODE_PPC32 | KS_MODE_BIG_ENDIAN)

# ---- shared: f1 = sqrt(f1) (frsqrte + two Newton steps); f1 == 0 stays 0. Clobbers f2-f4 (callers reload what they need); needs f10 = 0.5, f11 = 1.5, f12 = 0.
SQRT = '''
sqrt_sub:
fcmpu 0,1,12
beqlr
frsqrte 2,1
fmuls 3,1,10
fmuls 4,2,2
fnmsubs 4,3,4,11
fmuls 2,2,4
fmuls 4,2,2
fnmsubs 4,3,4,11
fmuls 2,2,4
fmuls 1,1,2
blr
'''

asm = f'''
tracker:
lis 12,{P_HI}
addi 12,12,{P_LO}
stfs 0,{P['save_f0']}(12)
stfs 13,{P['save_f13']}(12)
mflr 11
stw 11,{P['save_lr']}(12)
lwz 11,{P['frame']}(12)
addi 11,11,1
stw 11,{P['frame']}(12)
lwz 11,{P['flags']}(12)
andi. 11,11,1
beq tracker_done
lfs 10,{P['half']}(12)
lfs 11,{P['onehalf']}(12)
lfs 12,{P['zero']}(12)
# ---- (a) measure the latest normal shot's per-frame displacement during its first frames
lwz 3,{P['shot']}(12)
cmpwi 3,0
beq shot_done
lwz 11,0xF4(3)
andi. 11,11,1
beq shot_drop
lwz 11,0xE4(3)
cmpw 11,31
bne shot_drop
lwz 11,{P['shot_age']}(12)
addi 11,11,1
stw 11,{P['shot_age']}(12)
cmpwi 11,8
bgt shot_drop
lfs 1,0xC0(3)
lfs 2,0xC4(3)
lfs 3,0xC8(3)
cmpwi 11,2
blt shot_setprev
lfs 4,{P['sprev']}(12)
lfs 5,{P['sprev'] + 4}(12)
lfs 6,{P['sprev'] + 8}(12)
fsubs 4,1,4
fsubs 5,2,5
fsubs 6,3,6
stfs 1,{P['sprev']}(12)
stfs 2,{P['sprev'] + 4}(12)
stfs 3,{P['sprev'] + 8}(12)
fmuls 1,4,4
fmadds 1,5,5,1
fmadds 1,6,6,1
bl sqrt_sub
stfs 1,{P['s_last_d']}(12)
lfs 2,{P['s_meas']}(12)
fcmpu 0,1,2
ble shot_done
stfs 1,{P['s_meas']}(12)
b shot_done
shot_setprev:
stfs 1,{P['sprev']}(12)
stfs 2,{P['sprev'] + 4}(12)
stfs 3,{P['sprev'] + 8}(12)
b shot_done
shot_drop:
li 11,0
stw 11,{P['shot']}(12)
shot_done:
# ---- (b) lock-on target aim-node velocity
lwz 7,{TARGET}(31)
cmpwi 7,0
beq tgt_clear
stw 7,{P['tgt'] - 0}(12)
lwz 3,{NODE_TABLE}(7)
cmpwi 3,0
beq tgt_clear
lbz 4,{AIM_NODE}(7)
lis 11,{(NODE_LOOKUP + 0x8000) >> 16}
addi 11,11,{(NODE_LOOKUP & 0xFFFF) - (0x10000 if NODE_LOOKUP & 0x8000 else 0)}
mtctr 11
bctrl
lis 12,{P_HI}
addi 12,12,{P_LO}
cmpwi 3,0
beq tgt_clear
lwz 7,{P['tgt']}(12)
lfs 1,0x108(3)
lfs 2,0x10C(3)
lfs 3,0x110(3)
lwz 8,{P['tgt'] + 0x74}(12)
cmpw 7,8
bne tgt_reset
lfs 4,{P['prev']}(12)
lfs 5,{P['prev'] + 4}(12)
lfs 6,{P['prev'] + 8}(12)
fsubs 4,1,4
fsubs 5,2,5
fsubs 6,3,6
stfs 1,{P['prev']}(12)
stfs 2,{P['prev'] + 4}(12)
stfs 3,{P['prev'] + 8}(12)
fmuls 7,4,4
fmadds 7,5,5,7
fmadds 7,6,6,7
lfs 8,{P['max_vel2']}(12)
fcmpu 0,7,8
bgt tgt_done
lfs 8,{P['smooth']}(12)
lfs 1,{P['vel']}(12)
lfs 2,{P['vel'] + 4}(12)
lfs 3,{P['vel'] + 8}(12)
fsubs 4,4,1
fsubs 5,5,2
fsubs 6,6,3
fmadds 1,4,8,1
fmadds 2,5,8,2
fmadds 3,6,8,3
stfs 1,{P['vel']}(12)
stfs 2,{P['vel'] + 4}(12)
stfs 3,{P['vel'] + 8}(12)
li 11,1
stw 11,{P['valid']}(12)
b tgt_done
tgt_reset:
stw 7,{P['tgt'] + 0x74}(12)
stfs 1,{P['prev']}(12)
stfs 2,{P['prev'] + 4}(12)
stfs 3,{P['prev'] + 8}(12)
lfs 12,{P['zero']}(12)
stfs 12,{P['vel']}(12)
stfs 12,{P['vel'] + 4}(12)
stfs 12,{P['vel'] + 8}(12)
li 11,0
stw 11,{P['valid']}(12)
b tgt_done
tgt_clear:
li 11,0
stw 11,{P['tgt'] + 0x74}(12)
stw 11,{P['valid']}(12)
tgt_done:
tracker_done:
lis 12,{P_HI}
addi 12,12,{P_LO}
lwz 11,{P['save_lr']}(12)
mtlr 11
lfs 0,{P['save_f0']}(12)
lfs 13,{P['save_f13']}(12)
fcmpu 0,13,0
b {H1_RESUME}

aim:
lis 12,{P_HI}
addi 12,12,{P_LO}
lwz 11,{P['shots_total']}(12)
addi 11,11,1
stw 11,{P['shots_total']}(12)
lwz 11,{P['flags']}(12)
andi. 11,11,1
beq aim_pass
lwz 7,{TARGET}(31)
cmpwi 7,0
beq aim_pass
lwz 8,{P['tgt'] + 0x74}(12)
cmpw 7,8
bne aim_pass
lwz 11,{P['valid']}(12)
cmpwi 11,0
beq aim_pass
lfs 10,{P['half']}(12)
lfs 11,{P['onehalf']}(12)
lfs 12,{P['zero']}(12)
lfs 4,{P['vel']}(12)
lfs 5,{P['vel'] + 4}(12)
lfs 6,{P['vel'] + 8}(12)
fmuls 7,4,4
fmadds 7,5,5,7
fmadds 7,6,6,7
lfs 8,{P['min_vel2']}(12)
fcmpu 0,7,8
blt aim_pass
lfs 1,0(4)
lfs 2,4(4)
lfs 3,8(4)
lfs 7,0(5)
lfs 8,4(5)
lfs 9,8(5)
fsubs 1,1,7
fsubs 2,2,8
fsubs 3,3,9
fmuls 1,1,1
fmadds 1,2,2,1
fmadds 1,3,3,1
bl sqrt_sub
stfs 1,{P['last_d']}(12)
lfs 4,{P['vel']}(12)
lfs 5,{P['vel'] + 4}(12)
lfs 6,{P['vel'] + 8}(12)
lfs 2,{P['s_meas']}(12)
lwz 11,{P['flags']}(12)
andi. 11,11,2
beq aim_default_speed
fcmpu 0,2,12
bgt aim_have_speed
aim_default_speed:
lfs 2,{P['s_default']}(12)
aim_have_speed:
fdivs 1,1,2
lfs 2,{P['max_t']}(12)
fcmpu 0,1,2
ble aim_t_ok
fmr 1,2
lwz 11,{P['max_t_hits']}(12)
addi 11,11,1
stw 11,{P['max_t_hits']}(12)
aim_t_ok:
stfs 1,{P['last_t']}(12)
lfs 2,{P['lead']}(12)
fmuls 1,1,2
lfs 7,0(4)
lfs 8,4(4)
lfs 9,8(4)
fmadds 7,4,1,7
fmadds 8,5,1,8
fmadds 9,6,1,9
stfs 7,0(4)
stfs 8,4(4)
stfs 9,8(4)
stfs 7,{P['pred']}(12)
stfs 8,{P['pred'] + 4}(12)
stfs 9,{P['pred'] + 8}(12)
lwz 11,{P['shots_led']}(12)
addi 11,11,1
stw 11,{P['shots_led']}(12)
aim_pass:
lis 11,{(H2_RETURN + 0x8000) >> 16}
addi 11,11,{(H2_RETURN & 0xFFFF) - (0x10000 if H2_RETURN & 0x8000 else 0)}
mtlr 11
b {H2_TARGET}

record:
lis 12,{P_HI}
addi 12,12,{P_LO}
stw 3,{P['shot']}(12)
li 11,0
stw 11,{P['shot_age']}(12)
cmpwi 3,0
b {H3_RESUME}
''' + SQRT

# the tracker stores the raw target pointer at P.tgt and the tracked one at P.tgt+0x74 (= 0x98); keep the block consistent
P['tgt_tracked'] = P['tgt'] + 0x74
code = bytes(ks.asm(asm, addr=REGION)[0])
assert len(code) % 4 == 0 and REGION + len(code) <= PARAMS, (len(code), PARAMS - REGION)
insns = list(md.disasm(code, REGION))
for prev, cur in zip(insns, insns[1:]):
    assert not (cur.mnemonic == 'li' and cur.op_str.startswith('r0,') and prev.mnemonic == 'lwz' and prev.op_str.startswith('r0,')), 'r0 add trap'
# label addresses
def label(name):
    # recover from a second assembly pass with a marker is overkill; locate by disassembly pattern instead
    raise NotImplementedError
# find entry offsets: tracker = 0; aim = first `lis r12` after the tracker's final branch; record = after aim's final branch
def find_block_starts():
    starts = [0]
    for i, ins in enumerate(insns):
        if ins.mnemonic == 'b' and i + 1 < len(insns) and insns[i + 1].mnemonic == 'lis' and insns[i + 1].op_str.startswith('r12,'):
            starts.append(insns[i + 1].address - REGION)
    return starts
starts = find_block_starts()
assert len(starts) >= 3, starts
TRACKER, AIM, RECORD = REGION + starts[0], REGION + starts[1], REGION + starts[2]
def hookword(hook, target):
    disp = target - hook
    assert -0x2000000 <= disp < 0x2000000
    return 0x48000000 | (disp & 0x03FFFFFC)
H1_WORD, H2_WORD, H3_WORD = hookword(H1, TRACKER), hookword(H2, AIM), hookword(H3, RECORD)

# ---- params block image
def fw(x): return struct.unpack('>I', struct.pack('>f', x))[0]
params = [0] * (0x98 // 4)
def setw(off, val): params[off // 4] = val & 0xFFFFFFFF
setw(P['tag'], 0x4C454144)                        # 'LEAD'
setw(P['flags'], 0x3)                             # bit0 enable, bit1 use measured speed
setw(P['lead'], fw(DEFAULTS['lead']))
setw(P['max_t'], fw(DEFAULTS['max_t']))
setw(P['s_default'], fw(DEFAULTS['s_default']))
setw(P['smooth'], fw(DEFAULTS['smooth']))
setw(P['max_vel2'], fw(DEFAULTS['max_vel2']))
setw(P['min_vel2'], fw(DEFAULTS['min_vel2']))
setw(P['half'], fw(0.5))
setw(P['onehalf'], fw(1.5))
setw(P['zero'], 0)
assert PARAMS + 4 * len(params) + 4 <= REGION_END + 0x100

out = Path(__file__).parent / 'lead-v01-build'
out.mkdir(exist_ok=True)
(out / 'lead.s').write_text(asm)
(out / 'lead.bin').write_bytes(code)
(out / 'lead.dis.txt').write_text('\n'.join(f'{i.address:08x}: {i.bytes.hex()} {i.mnemonic} {i.op_str}' for i in insns))
patch = [f'0x{REGION + o:08X}:dword:0x{int.from_bytes(code[o:o + 4], "big"):08X}:0x00000000' for o in range(0, len(code), 4)]
patch += [f'0x{PARAMS + 4 * i:08X}:dword:0x{w:08X}:0x00000000' for i, w in enumerate(params) if w]
patch.append(f'0x{H1:08X}:dword:0x{H1_WORD:08X}:0x{H1_ORIG:08X}')
patch.append(f'0x{H2:08X}:dword:0x{H2_WORD:08X}:0x{H2_ORIG:08X}')
patch.append(f'0x{H3:08X}:dword:0x{H3_WORD:08X}:0x{H3_ORIG:08X}')
(out / 'patch.txt').write_text('\n'.join(patch) + '\n')
manifest = {'hooks': {'tracker': [H1, H1_ORIG, H1_WORD, TRACKER], 'aim': [H2, H2_ORIG, H2_WORD, AIM], 'record': [H3, H3_ORIG, H3_WORD, RECORD]},
            'region': REGION, 'params': PARAMS, 'bytes': len(code), 'sha256': hashlib.sha256(code).hexdigest(),
            'patch_entries': len(patch), 'param_offsets': P, 'defaults': DEFAULTS, 'flags': 3,
            'delivery': 'OnFrame conditional dword patches', 'node_lookup': NODE_LOOKUP, 'angle_helper': H2_TARGET}
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps({k: v for k, v in manifest.items() if k in ('hooks', 'bytes', 'sha256', 'patch_entries', 'defaults')}, indent=2))
