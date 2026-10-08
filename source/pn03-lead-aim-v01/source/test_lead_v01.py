"""Unicorn tests for Lead Aim v0.1 (tracker / aim / record hooks)."""
from pathlib import Path
import json, struct, sys
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
import unicorn as u
import unicorn.ppc_const as p

build = Path(__file__).parent / 'lead-v01-build'
m = json.loads((build / 'manifest.json').read_text())
code = (build / 'lead.bin').read_bytes()
REGION, PARAMS, P = m['region'], m['params'], m['param_offsets']
(H1, H1_ORIG, H1_WORD, TRACKER) = m['hooks']['tracker']
(H2, H2_ORIG, H2_WORD, AIM) = m['hooks']['aim']
(H3, H3_ORIG, H3_WORD, RECORD) = m['hooks']['record']
H1_RESUME, H2_TARGET, H2_RETURN, H3_RESUME = 0x800AFE88, 0x800CC574, 0x800AF170, 0x800AF1B4
NODE_LOOKUP = m['node_lookup']
PLAYER, TARGET, TARGET2, NODE, SHOT = 0x80D00000, 0x80D10000, 0x80D18000, 0x80D20000, 0x80D30000
SP = 0x80500000

mem = u.Uc(u.UC_ARCH_PPC, u.UC_MODE_32 | u.UC_MODE_BIG_ENDIAN)
mem.mem_map(0x80000000, 0x1800000)
mem.mem_write(REGION, code)
for line in (build / 'patch.txt').read_text().splitlines():
    a, _, v, c = line.split(':')
    a, v = int(a, 16), int(v, 16)
    mem.mem_write(a, v.to_bytes(4, 'big'))
mem.mem_write(H1_RESUME, bytes.fromhex('4c620b82'))
# node lookup stub: lis r3, NODE@h ; ori r3, r3, NODE@l ; blr
mem.mem_write(NODE_LOOKUP, bytes.fromhex('3c60%04x' % (NODE >> 16)) + bytes.fromhex('6063%04x' % (NODE & 0xFFFF)) + bytes.fromhex('4e800020'))
mem.reg_write(p.UC_PPC_REG_MSR, 0x2000)


def wf(a, *vals):
    mem.mem_write(a, b''.join(struct.pack('>f', v) for v in vals))
def rf(a): return struct.unpack('>f', mem.mem_read(a, 4))[0]
def rw(a): return int.from_bytes(mem.mem_read(a, 4), 'big')
def ww(a, v): mem.mem_write(a, (v & 0xFFFFFFFF).to_bytes(4, 'big'))
def pf(name): return rf(PARAMS + P[name])
def pw(name): return rw(PARAMS + P[name])
def reg(n): return p.UC_PPC_REG_0 + n


def fresh_regs():
    for i in range(32):
        mem.reg_write(reg(i), 0x11110000 + i)
    mem.reg_write(reg(1), SP); mem.reg_write(reg(13), 0x8026E820); mem.reg_write(reg(31), PLAYER)


def run_tracker(f0=2.0, f13=1.0):
    fresh_regs()
    mem.reg_write(p.UC_PPC_REG_FPR0, struct.unpack('<Q', struct.pack('<d', f0))[0])
    mem.reg_write(p.UC_PPC_REG_FPR13, struct.unpack('<Q', struct.pack('<d', f13))[0])
    mem.reg_write(p.UC_PPC_REG_LR, 0x800AF000)
    mem.emu_start(H1, H1_RESUME, count=5000)
    assert mem.reg_read(p.UC_PPC_REG_PC) == H1_RESUME, hex(mem.reg_read(p.UC_PPC_REG_PC))
    assert struct.unpack('<d', struct.pack('<Q', mem.reg_read(p.UC_PPC_REG_FPR0)))[0] == f0
    assert struct.unpack('<d', struct.pack('<Q', mem.reg_read(p.UC_PPC_REG_FPR13)))[0] == f13
    assert mem.reg_read(p.UC_PPC_REG_LR) == 0x800AF000
    cr = mem.reg_read(p.UC_PPC_REG_CR)
    assert (cr >> 28) & 0xF == (8 if f13 < f0 else 4 if f13 > f0 else 2), hex(cr)     # cr0 from fcmpu f13, f0
    assert mem.reg_read(reg(31)) == PLAYER


def run_aim(aim, hand):
    fresh_regs()
    wf(SP + 0x28, *aim); wf(SP + 0x48, *hand)
    mem.reg_write(reg(3), SP + 0x18); mem.reg_write(reg(4), SP + 0x28); mem.reg_write(reg(5), SP + 0x48)
    mem.reg_write(p.UC_PPC_REG_LR, 0xDEADBEEF)
    mem.emu_start(H2, H2_TARGET, count=5000)
    assert mem.reg_read(p.UC_PPC_REG_PC) == H2_TARGET, hex(mem.reg_read(p.UC_PPC_REG_PC))
    assert mem.reg_read(p.UC_PPC_REG_LR) == H2_RETURN
    assert mem.reg_read(reg(3)) == SP + 0x18 and mem.reg_read(reg(4)) == SP + 0x28 and mem.reg_read(reg(5)) == SP + 0x48
    return tuple(rf(SP + 0x28 + 4 * i) for i in range(3))


cases = 0
# ---------------- tracker: shot speed measurement + target velocity
ww(PLAYER + 0x5B4, TARGET)
ww(TARGET + 0xF0, 0x80D11000); mem.mem_write(TARGET + 0x125, bytes([3]))
ww(SHOT + 0xF4, 1); ww(SHOT + 0xE4, PLAYER)
# record the shot (H3)
fresh_regs(); mem.reg_write(reg(3), SHOT)
mem.emu_start(H3, H3_RESUME, count=100)
assert mem.reg_read(p.UC_PPC_REG_PC) == H3_RESUME and pw('shot') == SHOT and pw('shot_age') == 0
assert (mem.reg_read(p.UC_PPC_REG_CR) >> 28) & 0xF == 8            # cmpwi r3, 0 with r3 = 0x80D30000 -> LT (signed), not EQ
cases += 1
pos = [1000.0, 50.0, -2000.0]
spos = [10.0, 20.0, 30.0]
for frame in range(1, 8):
    pos = [pos[0] + 30.0, pos[1], pos[2] + 40.0]
    spos = [spos[0] + 20.0, spos[1], spos[2] + 15.0]
    wf(NODE + 0x108, *pos); wf(SHOT + 0xC0, *spos)
    run_tracker()
    assert pw('frame') == frame
    if frame == 1:
        assert pw('tgt_tracked') == TARGET and pw('valid') == 0 and pf('vel') == 0.0
    else:
        assert pw('valid') == 1
        expect = 30.0 * (1 - 0.5 ** (frame - 1))
        assert abs(pf('vel') - expect) < 1e-3 and abs(rf(PARAMS + P['vel'] + 8) - expect * 40 / 30) < 1e-3, (frame, pf('vel'), expect)
    assert tuple(rf(PARAMS + P['prev'] + 4 * i) for i in range(3)) == tuple(pos)
assert abs(pf('s_meas') - 25.0) < 1e-3, pf('s_meas')          # sqrt(20^2 + 15^2)
assert pw('shot') == 0 or pw('shot_age') <= 8
cases += 1
# teleport: a 1000-unit jump is ignored (velocity and valid unchanged, prev updated)
vel_before = pf('vel')
pos = [pos[0] + 1000.0, pos[1], pos[2]]
wf(NODE + 0x108, *pos); run_tracker()
assert pw('valid') == 1 and pf('vel') == vel_before and rf(PARAMS + P['prev']) == pos[0]
cases += 1
# shot pointer dropped once the actor is no longer in use
ww(SHOT + 0xF4, 0); run_tracker(); assert pw('shot') == 0
cases += 1
# target change -> reset
ww(PLAYER + 0x5B4, TARGET2); ww(TARGET2 + 0xF0, 0x80D19000); mem.mem_write(TARGET2 + 0x125, bytes([1]))
wf(NODE + 0x108, 0.0, 0.0, 0.0); run_tracker()
assert pw('tgt_tracked') == TARGET2 and pw('valid') == 0 and pf('vel') == 0.0
wf(NODE + 0x108, -10.0, 0.0, 0.0); run_tracker()
assert pw('valid') == 1 and abs(pf('vel') + 5.0) < 1e-6
cases += 1
# target without a node table -> cleared (no call)
ww(TARGET2 + 0xF0, 0); run_tracker(); assert pw('tgt_tracked') == 0 and pw('valid') == 0; ww(TARGET2 + 0xF0, 0x80D19000)
cases += 1
# no target -> cleared
ww(PLAYER + 0x5B4, 0); run_tracker(); assert pw('tgt_tracked') == 0 and pw('valid') == 0
cases += 1
# disabled -> frame counter only
ww(PLAYER + 0x5B4, TARGET); ww(PARAMS + P['flags'], 0); run_tracker(); assert pw('tgt_tracked') == 0
ww(PARAMS + P['flags'], 3)
cases += 1

# ---------------- aim
ww(PLAYER + 0x5B4, TARGET); ww(PARAMS + P['tgt_tracked'], TARGET); ww(PARAMS + P['valid'], 1)
wf(PARAMS + P['vel'], 30.0, 0.0, 40.0); wf(PARAMS + P['s_meas'], 25.0)
hand = (100.0, 200.0, 300.0); aim = (100.0, 200.0, 800.0)             # d = 500 -> t = 20 frames
res = run_aim(aim, hand)
assert all(abs(a - b) < 1e-3 for a, b in zip(res, (700.0, 200.0, 1600.0))), res
assert abs(pf('last_t') - 20.0) < 1e-5 and abs(pf('last_d') - 500.0) < 1e-3 and pw('shots_led') == 1 and pw('shots_total') == 1
cases += 1
# lead factor 0.5
wf(PARAMS + P['lead'], 0.5); res = run_aim(aim, hand)
assert all(abs(a - b) < 1e-3 for a, b in zip(res, (400.0, 200.0, 1200.0))), res
wf(PARAMS + P['lead'], 1.0)
cases += 1
# clamp to max_t (90 frames)
wf(PARAMS + P['s_meas'], 1.0); res = run_aim(aim, hand)
assert all(abs(a - b) < 1e-3 for a, b in zip(res, (100.0 + 30 * 90, 200.0, 800.0 + 40 * 90))), res
assert pw('max_t_hits') == 1
cases += 1
# measured speed disabled (flags bit1 off) -> s_default -> t = 500 / s_default
SD = m['defaults']['s_default']; TD = 500.0 / SD
ww(PARAMS + P['flags'], 1); res = run_aim(aim, hand)
assert all(abs(a - b) < 1e-2 for a, b in zip(res, (100.0 + 30 * TD, 200.0, 800.0 + 40 * TD))), res
ww(PARAMS + P['flags'], 3)
cases += 1
# no measured speed yet (0) -> default
wf(PARAMS + P['s_meas'], 0.0); res = run_aim(aim, hand)
assert all(abs(a - b) < 1e-2 for a, b in zip(res, (100.0 + 30 * TD, 200.0, 800.0 + 40 * TD))), res
wf(PARAMS + P['s_meas'], 25.0)
cases += 1
# velocity not valid / wrong target / tiny velocity / disabled -> pass through unchanged
ww(PARAMS + P['valid'], 0); assert run_aim(aim, hand) == aim; ww(PARAMS + P['valid'], 1)
ww(PARAMS + P['tgt_tracked'], TARGET2); assert run_aim(aim, hand) == aim; ww(PARAMS + P['tgt_tracked'], TARGET)
wf(PARAMS + P['vel'], 0.1, 0.0, 0.1); assert run_aim(aim, hand) == aim; wf(PARAMS + P['vel'], 30.0, 0.0, 40.0)
ww(PARAMS + P['flags'], 0); assert run_aim(aim, hand) == aim; ww(PARAMS + P['flags'], 3)
ww(PLAYER + 0x5B4, 0); assert run_aim(aim, hand) == aim; ww(PLAYER + 0x5B4, TARGET)
cases += 1
# zero distance (hand == aim): no NaN, aim unchanged
res = run_aim(hand, hand); assert res == hand, res
cases += 1

(build / 'unit-test-results.json').write_text(json.dumps({'cases': cases, 'status': 'pass'}, indent=2))
print(f'all {cases} cases passed')
