"""Run the Sprint Run v0.3 bodies in Unicorn against the real DOL frame-advance routine.

Hook 1 (post-dispatch) is driven frame by frame like the v0.1 test: the game's own advance
0x800A1770 (real code) then the body. The run handler's footstep routine 0x800B5564 is
stubbed and its calls counted with the layer frame at call time. Hook 2 (root apply) is
driven with a fake layer / delta vector and a stub for 0x800A15AC that records its
arguments, and additionally in the real per-frame order (hook 2 -> game advance -> hook 1)
over 260 ticks, which is the sequence that exposed the v0.2 warp. Dolphin validation is
still needed.
"""
import sys, struct, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
import unicorn as u
import unicorn.ppc_const as p
import dol

build = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / 'sprint-v03-build'
m = json.loads((build / 'manifest.json').read_text())
CODE = m['region']
HOOK1, RESUME1, HOOK2, RESUME2, BODY2 = m['hook1'], m['resume1'], m['hook2'], m['resume2'], m['body2']
ADVANCE, FOOTSTEP, APPLY = m['advance'], m['footstep'], m['apply_root']
PRM = m['params']
DEF = m['defaults']
MARKER = m['marker']
SENTINEL = 0x80004000
R13 = 0x8026e820
PLAYER = 0x81200000
LAYER = PLAYER + 0x17C
OTHER = 0x81300000
SP = 0x817f0000
TOTAL = 16
CYCLE_Z = 3508.6

machine = u.Uc(u.UC_ARCH_PPC, u.UC_MODE_32 | u.UC_MODE_BIG_ENDIAN)
machine.mem_map(0x80000000, 0x1800000)
for f, a, n in dol.sections:
    machine.mem_write(a, dol.data[f:f + n])
code = (build / 'sprint.bin').read_bytes()
data = (build / 'sprint.data.bin').read_bytes()

# --- static checks ---
code1 = code[:m['body1_bytes']]
assert code1[-8:-4] == m['original1'].to_bytes(4, 'big')
for ret, end, resume in ((int.from_bytes(code1[-4:], 'big'), CODE + len(code1), RESUME1),
                         (int.from_bytes(code[-4:], 'big'), CODE + len(code), RESUME2)):
    d = ret & 0x03FFFFFC
    d = d - 0x04000000 if d & 0x02000000 else d
    assert ret >> 26 == 18 and (ret & 3) == 0 and end - 4 + d == resume
for hook, word, target in ((HOOK1, m['hook1_word'], CODE), (HOOK2, m['hook2_word'], BODY2)):
    hd = word & 0x03FFFFFC
    hd = hd - 0x04000000 if hd & 0x02000000 else hd
    assert word >> 26 == 18 and (word & 3) == 0 and hook + hd == target
    assert int.from_bytes(dol.read(hook, 4), 'big') == (m['original1'] if hook == HOOK1 else m['original2'])
patch = (build / 'patch.txt').read_text().splitlines()
assert len(patch) == len(code) // 4 + len(data) // 4 + 2
for o in range(0, len(code), 4):
    assert patch[o // 4] == f'0x{CODE + o:08X}:dword:0x{int.from_bytes(code[o:o + 4], "big"):08X}:0x00000000'
assert patch[-2] == f'0x{HOOK1:08X}:dword:0x{m["hook1_word"]:08X}:0x{m["original1"]:08X}'
assert patch[-1] == f'0x{HOOK2:08X}:dword:0x{m["hook2_word"]:08X}:0x{m["original2"]:08X}'
assert CODE + m['params_offset'] + 0x40 <= m['region_end'] <= 0x8018DF00

machine.mem_write(CODE, code)
machine.mem_write(CODE + m['data_offset'], data)
machine.mem_write(HOOK1, m['hook1_word'].to_bytes(4, 'big'))
machine.mem_write(HOOK2, m['hook2_word'].to_bytes(4, 'big'))
STUB = bytes.fromhex('38600000 4e800020'.replace(' ', ''))   # li r3,0 ; blr
machine.mem_write(FOOTSTEP, STUB)
machine.mem_write(APPLY, STUB)
machine.reg_write(p.UC_PPC_REG_MSR, 0x2000)
counts = {'advance': 0, 'footstep': [], 'apply': []}


def on_code(uc, address, size, user):
    if address == ADVANCE:
        counts['advance'] += 1
    elif address == FOOTSTEP:
        counts['footstep'].append((uc.reg_read(p.UC_PPC_REG_3), rh(LAYER + 0x2B0)))
    elif address == APPLY:
        r5 = uc.reg_read(p.UC_PPC_REG_5)
        counts['apply'].append((uc.reg_read(p.UC_PPC_REG_3), uc.reg_read(p.UC_PPC_REG_4), r5, uc.reg_read(p.UC_PPC_REG_6),
                                struct.unpack('>3f', uc.mem_read(r5, 12))))


machine.hook_add(u.UC_HOOK_CODE, on_code, begin=0x80000000, end=0x81800000)


def ww(a, n): machine.mem_write(a, (n & 0xFFFFFFFF).to_bytes(4, 'big'))
def wh(a, n): machine.mem_write(a, (n & 0xFFFF).to_bytes(2, 'big'))
def wb(a, n): machine.mem_write(a, bytes([n & 255]))
def wf(a, f): machine.mem_write(a, struct.pack('>f', f))
def rw(a): return int.from_bytes(machine.mem_read(a, 4), 'big')
def rh(a): return int.from_bytes(machine.mem_read(a, 2), 'big')
def rb(a): return machine.mem_read(a, 1)[0]
def rf(a): return struct.unpack('>f', machine.mem_read(a, 4))[0]
def packf(f): return int.from_bytes(struct.pack('>d', f), 'big')


NONVOL = {p.UC_PPC_REG_0 + i: 0x12340000 + i for i in range(14, 32)}
NONVOL[p.UC_PPC_REG_31] = PLAYER
NONVOL_F = {p.UC_PPC_REG_FPR0 + i: packf(i + .125) for i in range(14, 32)}


def set_regs():
    for i in range(32):
        machine.reg_write(p.UC_PPC_REG_0 + i, 0x12340000 + i)
        machine.reg_write(p.UC_PPC_REG_FPR0 + i, packf(i + .125))
    for r, v in NONVOL.items():
        machine.reg_write(r, v)
    machine.reg_write(p.UC_PPC_REG_1, SP)
    machine.reg_write(p.UC_PPC_REG_13, R13)
    machine.reg_write(p.UC_PPC_REG_CR, 0xa5927310)
    machine.reg_write(p.UC_PPC_REG_LR, SENTINEL)
    machine.reg_write(p.UC_PPC_REG_CTR, 0x27)
    machine.reg_write(p.UC_PPC_REG_XER, 0)


def check_nonvol():
    for r, v in NONVOL.items():
        assert machine.reg_read(r) == v, f'non-volatile r{r - p.UC_PPC_REG_0} changed'
    for r, v in NONVOL_F.items():
        assert machine.reg_read(r) == v, f'non-volatile f{r - p.UC_PPC_REG_FPR0} changed'
    assert machine.reg_read(p.UC_PPC_REG_1) == SP and machine.reg_read(p.UC_PPC_REG_13) == R13


def reset_world(params=True, flags=None):
    machine.mem_write(PLAYER, bytes(0x1000))
    machine.mem_write(CODE + m['params_offset'], bytes(0x40))
    if params:
        ww(PRM['marker'], MARKER)
        ww(PRM['flags'], DEF['flags'] if flags is None else flags)
        ww(PRM['threshold'], DEF['threshold'])
        ww(PRM['ramp'], DEF['ramp'])
        wf(PRM['max'], DEF['max_factor'])
        wf(PRM['turn'], DEF['turn_cancel_rad'])
        wf(PRM['dist'], DEF['dist_scale'])
        wf(PRM['factor'], 1.0)
    wh(LAYER + 0x2B2, TOTAL)
    wh(LAYER + 0x2B0, 0)
    wh(LAYER + 0x2A8, 0)
    ww(LAYER + 0x2AC, 0)
    wh(LAYER + 0x23C, 0x5)
    ww(LAYER + 0x2A4, 0)
    wb(LAYER + 0x23E, 0)
    wf(LAYER + 0x25C + 8, CYCLE_Z)
    wb(PLAYER + 0xF8, 1)


def game_tick():
    set_regs()
    machine.reg_write(p.UC_PPC_REG_3, LAYER)
    machine.emu_start(ADVANCE, SENTINEL, count=200)
    assert machine.reg_read(p.UC_PPC_REG_PC) == SENTINEL


def run_body1():
    set_regs()
    machine.emu_start(CODE, RESUME1, count=5000)
    assert machine.reg_read(p.UC_PPC_REG_PC) == RESUME1, hex(machine.reg_read(p.UC_PPC_REG_PC))
    assert machine.reg_read(p.UC_PPC_REG_9) == 0x80170000
    check_nonvol()


def state():
    return {'counter': rw(PRM['counter']), 'tag': rw(PRM['tag']), 'factor': rf(PRM['factor']), 'acc': rf(PRM['acc']),
            'frame': rh(LAYER + 0x2B0), 'time': rh(LAYER + 0x2A8), 'looped': rb(LAYER + 0x23E), 'jump_speed': rf(PLAYER + 0x108),
            'footsteps': rw(PRM['footsteps']), 'player': rw(PRM['player'])}


def frame(cat=1, sub=1, phase=1, up=True, yaw=None, tick=True):
    wb(PLAYER + 0xF8, cat)
    wb(PLAYER + 0xF9, sub)
    wb(PLAYER + 0xFA, phase)
    ww(PLAYER + 0x5F8, 1 if up else 0)
    if yaw is not None:
        wf(PLAYER + 0xD0, yaw)
    post_tick = None
    if tick:
        game_tick()
        post_tick = rh(LAYER + 0x2B0)
    looped_after_tick = rb(LAYER + 0x23E)
    frame_after_tick = rh(LAYER + 0x2B0)
    time_before = rh(LAYER + 0x2A8)
    n0 = counts['advance']
    f0 = len(counts['footstep'])
    run_body1()
    s = state()
    s['post_tick'] = post_tick
    s['extra'] = counts['advance'] - n0
    s['foot_calls'] = counts['footstep'][f0:]
    if s['extra']:
        assert s['frame'] == (frame_after_tick + 1) % TOTAL
        # the loop flag survives the extra advance when the game's own advance looped
        if looped_after_tick == 1 or frame_after_tick + 1 == TOTAL:
            assert s['looped'] == 1, (looped_after_tick, frame_after_tick, s['looped'])
        else:
            assert s['looped'] == 0
        if s['frame'] in m['footstep_frames']:
            assert s['foot_calls'] == [(PLAYER, s['frame'])], s['foot_calls']
        else:
            assert s['foot_calls'] == []
    else:
        assert s['foot_calls'] == []
        if tick:
            assert s['looped'] == looped_after_tick
    assert s['time'] >> 6 == s['frame'] and (s['time'] & 63) < 64
    return s


def sampled_time(s):
    return s['frame'] + (s['time'] & 63) / 64


cases = 0

# 1. no params marker: initialised with defaults, then runs
reset_world(params=False)
s = frame()
assert rw(PRM['marker']) == MARKER and rw(PRM['flags']) == DEF['flags'] and rw(PRM['threshold']) == DEF['threshold']
assert rw(PRM['ramp']) == DEF['ramp'] and abs(rf(PRM['max']) - DEF['max_factor']) < 1e-6 and abs(rf(PRM['dist']) - 1.0) < 1e-6
assert s['counter'] == 1 and s['tag'] == 1 and s['factor'] == 1.0 and s['player'] == PLAYER
cases += 1

# 2. disabled flag: counter and layer untouched (player pointer still recorded)
reset_world(flags=0)
s = frame()
assert s['counter'] == 0 and s['tag'] == 0 and s['time'] == (1 << 6) and s['extra'] == 0 and s['player'] == PLAYER
cases += 1

# 3. long run: ramp, exact rate, footsteps, loop flag, monotonic time
reset_world()
seen = []
prev_t = None
total_advance = 0.0
for i in range(400):
    s = frame(yaw=0.3)
    seen.append(s)
    cases += 1
assert seen[DEF['threshold'] - 1]['factor'] == 1.0
assert 1.0 < seen[DEF['threshold'] + 5]['factor'] < DEF['max_factor']
assert abs(seen[DEF['threshold'] + DEF['ramp'] + 1]['factor'] - DEF['max_factor']) < 1e-5
# per-tick sampled time step is exactly the factor once ramped (within 1/64)
steps = []
for a, b in zip(seen[100:], seen[101:]):
    ta, tb = sampled_time(a), sampled_time(b)
    if tb < ta:
        tb += TOTAL
    steps.append(tb - ta)
assert all(abs(st - DEF['max_factor']) <= 1 / 64 + 1e-6 for st in steps), (min(steps), max(steps))
# every footstep frame is seen exactly once per cycle, either by the handler (post_tick) or by our call
events = []
for s in seen[100:]:
    if s['post_tick'] in m['footstep_frames']:
        events.append(('game', s['post_tick']))
    for _, fr in s['foot_calls']:
        events.append(('hook', fr))
frames_seq = [e[1] for e in events]
assert frames_seq[:2] in ([6, 15], [15, 6])
for a, b in zip(frames_seq, frames_seq[1:]):
    assert a != b, frames_seq
assert any(e[0] == 'hook' for e in events) and any(e[0] == 'game' for e in events)
assert seen[-1]['footsteps'] == sum(1 for e in events if e[0] == 'hook') + sum(1 for s in seen[:100] for _ in s['foot_calls'])
cases += 4

# 4. sharp turn cancels, gentle turn does not, wrap-around handled
reset_world()
for i in range(70):
    frame(yaw=0.0)
s = frame(yaw=0.05)
assert s['counter'] == 71
s = frame(yaw=1.5)
assert s['counter'] == 0 and s['factor'] == 1.0 and s['acc'] == 0.0
for i in range(60):
    s = frame(yaw=3.0)
before = s['counter']
assert before == 59
s = frame(yaw=-3.0)
assert s['counter'] == before + 1
s = frame(yaw=-1.0)
assert s['counter'] == 0
cases += 5

# 5. stick released resets
reset_world()
for i in range(70):
    frame()
s = frame(up=False)
assert s['counter'] == 0 and s['tag'] == 0
cases += 1

# 6. jump inherit and persistence
reset_world()
for i in range(80):
    frame(yaw=0.7)
wf(PLAYER + 0x108, -260.0)
s = frame(sub=3, phase=5, yaw=0.7)
assert s['tag'] == 3 and s['counter'] == 80 and abs(s['jump_speed'] + 260.0) < 1e-4
s = frame(sub=3, phase=6, yaw=0.7)
assert abs(s['jump_speed'] + 260.0 * DEF['max_factor']) < 1e-3
for i in range(20):
    s = frame(sub=3, phase=7, yaw=0.7)
    assert abs(s['jump_speed'] + 260.0 * DEF['max_factor']) < 1e-3 and s['counter'] == 80 and s['extra'] == 0
s = frame(sub=0, phase=0, yaw=0.7)
assert s['tag'] == 0x30 and s['counter'] == 80
s = frame(sub=1, phase=0, yaw=0.7)
assert s['tag'] == 1 and s['counter'] == 81 and abs(s['factor'] - DEF['max_factor']) < 1e-5
s = frame(sub=0, phase=0)
s = frame(sub=0, phase=0)
assert s['counter'] == 0
cases += 25
reset_world(flags=5)
for i in range(80):
    frame()
wf(PLAYER + 0x108, -260.0)
s = frame(sub=3, phase=6)
assert abs(s['jump_speed'] + 260.0) < 1e-4
cases += 1

# 7. other states / categories reset
for sub in (2, 4, 5, 8, 9, 0xB, 0xC):
    reset_world()
    for i in range(70):
        frame()
    s = frame(sub=sub, tick=False)
    assert s['counter'] == 0 and s['tag'] == 0 and s['acc'] == 0.0
    cases += 1
reset_world()
for i in range(70):
    frame()
s = frame(cat=2, tick=False)
assert s['counter'] == 0
cases += 1

# 8. ramp 0 -> straight to max
reset_world()
ww(PRM['ramp'], 0)
for i in range(DEF['threshold'] - 1):
    frame()
s = frame()
assert abs(s['factor'] - DEF['max_factor']) < 1e-5
cases += 1


# ---- hook 2: root linearisation ----
def run_body2(actor, layer, vec, rot=(0.1, 0.2, 0.3), tag=1, factor=1.4, flags=7, dist=1.0, marker=True,
              cat=1, sub=1, layer_flags=0x5, total=TOTAL, cycle_z=CYCLE_Z,
              time_now=(3 << 6), time_prev=(2 << 6) << 16, looped=0):
    machine.mem_write(CODE + m['params_offset'], bytes(0x40))
    if marker:
        ww(PRM['marker'], MARKER)
    ww(PRM['flags'], flags)
    ww(PRM['tag'], tag)
    wf(PRM['factor'], factor)
    wf(PRM['dist'], dist)
    ww(PRM['player'], PLAYER)
    wb(PLAYER + 0xF8, cat)
    wb(PLAYER + 0xF9, sub)
    VEC, ROT = SP + 0x100, SP + 0x110
    machine.mem_write(VEC, struct.pack('>3f', *vec))
    machine.mem_write(ROT, struct.pack('>3f', *rot))
    wh(layer + 0x23C, layer_flags)
    wh(layer + 0x2A8, time_now)
    ww(layer + 0x2AC, time_prev)
    wb(layer + 0x23E, looped)
    wh(layer + 0x2B2, total)
    wf(layer + 0x25C + 8, cycle_z)
    set_regs()
    machine.reg_write(p.UC_PPC_REG_3, actor)
    machine.reg_write(p.UC_PPC_REG_4, layer)
    machine.reg_write(p.UC_PPC_REG_5, VEC)
    machine.reg_write(p.UC_PPC_REG_6, ROT)
    n0 = len(counts['apply'])
    machine.emu_start(BODY2, RESUME2, count=5000)
    assert machine.reg_read(p.UC_PPC_REG_PC) == RESUME2, hex(machine.reg_read(p.UC_PPC_REG_PC))
    check_nonvol()
    calls = counts['apply'][n0:]
    assert len(calls) == 1 and calls[0][:4] == (actor, layer, VEC, ROT), calls
    return calls[0][4]


reset_world()
mean = CYCLE_Z / TOTAL
# sprinting: z = mean * factor * dist, x/y untouched, independent of the layer's time fields
v = run_body2(PLAYER, LAYER, (-20.0, 0.0, 300.0))
assert abs(v[0] + 20.0) < 1e-5 and abs(v[1]) < 1e-6 and abs(v[2] - mean * 1.4) < 1e-2, v
# the v0.2 warp state (loop flag set, +0x2AC already past the wrap): no longer matters
v = run_body2(PLAYER, LAYER, (0.0, 0.0, 300.0), factor=1.2, time_now=(1 << 6) | 25, time_prev=0, looped=1)
assert abs(v[2] - mean * 1.2) < 1e-2, v
v = run_body2(PLAYER, LAYER, (0.0, 0.0, 300.0), dist=1.25)
assert abs(v[2] - mean * 1.4 * 1.25) < 1e-2, v
v = run_body2(PLAYER, LAYER, (0.0, 0.0, 300.0), total=20, cycle_z=4000.0, factor=1.1)
assert abs(v[2] - 4000.0 / 20 * 1.1) < 1e-2, v
# untouched when: not the player / flag off / tag not run / the player's own state already left the run /
# factor 1 / no marker / non-looping layer / zero total
for kw in (dict(actor=OTHER), dict(flags=3), dict(tag=3), dict(sub=3), dict(sub=0), dict(cat=2), dict(factor=1.0),
           dict(marker=False), dict(layer_flags=0x1), dict(total=0)):
    args = dict(actor=PLAYER, layer=LAYER, vec=(1.0, 2.0, 300.0))
    args.update(kw)
    v = run_body2(**args)
    assert tuple(round(x, 4) for x in v) == (1.0, 2.0, 300.0), (kw, v)
    cases += 1
cases += 4


# ---- regression: real per-frame order (hook 2 -> game advance -> hook 1) ----
# v0.2 derived dt from the layer's +0x2A8 - +0x2AC (+ one cycle when +0x23E == 1). When the game's advance
# looped and the extra advance ran in the same tick, +0x2AC already held the post-wrap time while the flag
# was restored to 1: dt = 17 frames, i.e. one full cycle of forward movement in one tick (the warp seen in
# Dolphin). Plain extra-advance ticks were short by up to 0.4 frames (hitch). The rows below also compute
# what the v0.2 formula would have given, to prove the sequence contains the failing case.
def hook2_in_place(vec=(-20.0, 0.0, 300.0)):
    VEC, ROT = SP + 0x100, SP + 0x110
    machine.mem_write(VEC, struct.pack('>3f', *vec))
    machine.mem_write(ROT, struct.pack('>3f', 0.0, 0.0, 0.0))
    set_regs()
    machine.reg_write(p.UC_PPC_REG_3, PLAYER)
    machine.reg_write(p.UC_PPC_REG_4, LAYER)
    machine.reg_write(p.UC_PPC_REG_5, VEC)
    machine.reg_write(p.UC_PPC_REG_6, ROT)
    n0 = len(counts['apply'])
    machine.emu_start(BODY2, RESUME2, count=5000)
    assert machine.reg_read(p.UC_PPC_REG_PC) == RESUME2, hex(machine.reg_read(p.UC_PPC_REG_PC))
    check_nonvol()
    return counts['apply'][n0][4]


def sequence(dist, flags=7, ticks=260):
    reset_world(flags=flags)
    wf(PRM['dist'], dist)
    wb(PLAYER + 0xF9, 1)
    wb(PLAYER + 0xFA, 1)
    ww(PLAYER + 0x5F8, 1)
    wf(PLAYER + 0xD0, 0.3)
    rows = []
    prev_t = None
    for k in range(ticks):
        t_now = rh(LAYER + 0x2A8)
        v02_dt = (t_now - (rw(LAYER + 0x2AC) >> 16) + ((TOTAL << 6) if rb(LAYER + 0x23E) == 1 else 0)) / 64
        factor_used = rf(PRM['factor'])
        v = hook2_in_place()
        step = None
        if prev_t is not None:
            step = (t_now - prev_t) / 64
            if step < 0:
                step += TOTAL
        rows.append((k, factor_used, step, v, v02_dt))
        prev_t = t_now
        game_tick()
        run_body1()
    return rows


rows = sequence(1.0)
sprint_rows = [r for r in rows if r[1] > 1.0 and r[2] is not None]
assert len(sprint_rows) > 150
for k, fac, step, v, _ in sprint_rows:
    assert abs(v[0] + 20.0) < 1e-5 and abs(v[1]) < 1e-6
    assert abs(v[2] / mean - step) <= 1 / 64 + 1e-3, (k, fac, step, v[2] / mean)
    assert v[2] < 2 * mean, (k, v)
    cases += 1
v02_warps = sum(1 for r in sprint_rows if r[4] > TOTAL)
assert v02_warps >= 3, v02_warps                  # the v0.2 formula warps in this very sequence
steady = [r for r in rows if abs(r[1] - DEF['max_factor']) < 1e-5 and r[2] is not None]
assert abs(sum(r[3][2] for r in steady) / (sum(r[2] for r in steady) * mean) - 1.0) < 0.01
cases += 2
rows = sequence(1.25)
for k, fac, step, v, _ in [r for r in rows if r[1] > 1.0 and r[2] is not None]:
    assert abs(v[2] / mean - step * 1.25) <= 1.25 / 64 + 1e-3, (k, fac, step, v[2] / mean)
cases += 1
rows = sequence(1.0, flags=3)
assert all(abs(r[3][2] - 300.0) < 1e-4 for r in rows)
cases += 1

(build / 'unit-test-results.json').write_text(json.dumps({'cases': cases, 'step_min': min(steps), 'step_max': max(steps),
                                                          'footstep_events': len(events), 'sequence_ticks': len(sprint_rows),
                                                          'v02_warp_ticks': v02_warps}, indent=2))
print(f'ok: {cases} cases, sampled-time step {min(steps):.4f}..{max(steps):.4f} (target {DEF["max_factor"]}), '
      f'footstep events {len(events)}, sequence ticks {len(sprint_rows)} (v0.2 formula would warp on {v02_warps})')
