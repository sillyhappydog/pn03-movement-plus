"""Execute the camera v0.11 payload against the real DOL math routines in Unicorn.

v0.11 adds the paced swing: a bit3 request with bit5 is paced to her per-frame rotation (goal step and
direction taken from her yaw change each frame, hold while nothing has moved, keep the last step once she
stops); bit3 and bit5 are both consumed; a follow or an unpaced request clears the paced state.

v0.10 adds the camera lock: with a valid config block whose flags bit4 is set, the C-stick is ignored
(no rotation, no cancel of a pending swing); without the block the stick works as before.

v0.7 checks (sensitivity from the config block, axis exclusivity, follow request, yaw request, the
rate-limited swing, cancel by C-stick / view reset / re-initialisation, swing without a config block)
plus the v0.9 per-request step and direction: a bit3 request reads config +0x38; a finite value of at
least `step_min` becomes the goal step and its sign the goal direction, anything else keeps the default
step and no direction; a follow request (bit1) always uses the default step and no direction. While a
direction is set and the remaining angle exceeds `dir_threshold`, the swing turns in that direction
even the long way round; otherwise it takes the shorter side (exactly 180 degrees goes +yaw).
The payload is loaded at its real region address; the final branch back to the hook is
replaced by a nop so the run stops at the end of the payload. Paired-single save/load and
GQR accesses are skipped because Unicorn does not emulate Gekko's paired-single extension.
Full Dolphin validation is still needed.
"""
import sys, struct, math, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
from regions import R as REG
import unicorn as u
import unicorn.ppc_const as p
import dol

build = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / ('camera-v11-build' + REG.suffix)
manifest = json.loads((build / 'manifest.json').read_text())
CODE = manifest['region']
STATE = CODE + manifest['data_offset']
GOAL_YAW = CODE + manifest['goal_yaw_offset']
GOAL_ACTIVE = CODE + manifest['goal_active_offset']
GOAL_STEP = CODE + manifest['goal_step_offset']
GOAL_DIR = CODE + manifest['goal_dir_offset']
CONFIG = manifest['config_block']
MAGIC = manifest['config_magic']
DEFAULT = manifest['default_sensitivity']
HOOK = manifest['hook']
REQ_STEP = manifest['request_step_offset']
LOCK = manifest['lock_flag_bit']
PACED_BIT = manifest['paced_flag_bit']
HER_LAST = CODE + manifest['her_last_yaw_offset']
PACED = CODE + manifest['paced_offset']
ACTOR = 0x81000000
SP = 0x817f0000
machine = u.Uc(u.UC_ARCH_PPC, u.UC_MODE_32 | u.UC_MODE_BIG_ENDIAN)
machine.mem_map(0x80000000, 0x1800000)
for f, a, n in dol.sections:
    machine.mem_write(a, dol.data[f:f + n])
code = bytearray((build / 'camera.bin').read_bytes())
# static checks on the delivery words
assert code[-8:-4] == manifest['original'].to_bytes(4, 'big')
ret = int.from_bytes(code[-4:], 'big')
assert ret >> 26 == 18 and (ret & 3) == 0
disp = ret & 0x03FFFFFC
disp = disp - 0x04000000 if disp & 0x02000000 else disp
assert CODE + len(code) - 4 + disp == HOOK + 4, hex(CODE + len(code) - 4 + disp)
hw = manifest['hook_word']
hd = hw & 0x03FFFFFC
hd = hd - 0x04000000 if hd & 0x02000000 else hd
assert hw >> 26 == 18 and HOOK + hd == CODE
patch = (build / 'patch.txt').read_text().splitlines()
assert len(patch) == len(code) // 4 + 1
for o in range(0, len(code), 4):
    assert patch[o // 4] == f'0x{CODE + o:08X}:dword:0x{int.from_bytes(code[o:o + 4], "big"):08X}:0x00000000'
assert patch[-1] == f'0x{HOOK:08X}:dword:0x{hw:08X}:0x{manifest["original"]:08X}'


def code_f32(off):
    return struct.unpack('>f', code[off:off + 4])[0]


# the constant words are the configured values; the runtime words start at zero (their patch lines never overwrite a running goal)
STEP = code_f32(manifest['swing_step_offset'])
THRESH = code_f32(manifest['dir_threshold_offset'])
STEP_MIN = code_f32(manifest['step_min_offset'])
assert abs(STEP - math.radians(manifest['swing_step_deg'])) < 1e-6 and 0 < STEP < math.pi
assert abs(THRESH - math.radians(manifest['dir_threshold_deg'])) < 1e-6 and abs(STEP_MIN - math.radians(manifest['step_min_deg'])) < 1e-7
for off in (manifest['goal_yaw_offset'], manifest['goal_active_offset'], manifest['goal_step_offset'], manifest['goal_dir_offset'], manifest['her_last_yaw_offset'], manifest['paced_offset']):
    assert code[off:off + 4] == bytes(4)
    assert patch[off // 4].endswith(':dword:0x00000000:0x00000000')
skipped = []
for off in range(0, len(code) - 4, 4):
    if manifest['data_offset'] <= off < manifest['data_end']:
        continue
    w = int.from_bytes(code[off:off + 4], 'big')
    if w >> 26 in [56, 60] or w in [0x7c10e2a6, 0x7c10e3a6]:
        skipped.append(off)
        code[off:off + 4] = bytes.fromhex('60000000')
code[-4:] = bytes.fromhex('60000000')   # the branch back to the hook
machine.mem_write(CODE, bytes(code))
machine.reg_write(p.UC_PPC_REG_MSR, 0x2000)


def wf(a, f):
    machine.mem_write(a, struct.pack('>f', f))


def rf(a):
    return struct.unpack('>f', machine.mem_read(a, 4))[0]


def f32(f):
    return struct.unpack('>f', struct.pack('>f', f))[0]


def packf(f):
    return int.from_bytes(struct.pack('>d', f), 'big')


def wb(a, n):
    machine.mem_write(a, bytes([n & 255]))


def ww(a, n):
    machine.mem_write(a, (n & 0xFFFFFFFF).to_bytes(4, 'big'))


def rw(a):
    return int.from_bytes(machine.mem_read(a, 4), 'big')


def rws(a):
    v = rw(a)
    return v - 0x100000000 if v & 0x80000000 else v


def word(f):
    return struct.unpack('>I', struct.pack('>f', f))[0]


PI, TWO_PI = f32(math.pi), f32(2 * math.pi)


def wrap(v):
    """The payload's wrap after a stick or step update: above pi -> -2pi, below -pi -> +2pi."""
    v = f32(v)
    if v > PI:
        v = f32(v - TWO_PI)
    if v < -PI:
        v = f32(v + TWO_PI)
    return v


def wrap_d(v):
    """The goal difference: above pi -> -2pi, -pi and below -> +2pi (so exactly 180 degrees goes +yaw)."""
    v = f32(v)
    if v > PI:
        v = f32(v - TWO_PI)
    if v <= -PI:
        v = f32(v + TWO_PI)
    return v


def request_step(step):
    """The payload's reading of config +0x38 at a bit3 latch: (goal_step, goal_dir)."""
    s = f32(step)
    if math.isnan(s) or abs(s) < STEP_MIN or abs(s) > PI:
        return STEP, 0
    return f32(abs(s)), (-1 if s < 0 else 1)


checks = 0


def run(stick, yaw, actor_yaw=1.25, error=0, reset=0, init=False, position=(13400.0, -120.0, -3765.5),
        config=None, flags=0, suby=0, request=0.0, step=0.0, goal=(0, 0.0)):
    """config: None (no block) or (magic_word, sensitivity_word); flags written at +0x1C when config given, request at +0x30,
    step at +0x38. goal: (active, goal_yaw[, goal_step, goal_dir]) written into the payload's goal words before the run,
    or 'keep' to leave them."""
    global checks
    before = {p.UC_PPC_REG_0 + i: 0x12340000 + i for i in range(32)}
    before[p.UC_PPC_REG_1] = SP
    before[p.UC_PPC_REG_2] = REG.r2
    before[p.UC_PPC_REG_13] = REG.r13
    before[p.UC_PPC_REG_31] = ACTOR
    for i in range(32):
        before[p.UC_PPC_REG_FPR0 + i] = packf(i + .125)
    before.update({p.UC_PPC_REG_CR: 0xa5927310, p.UC_PPC_REG_LR: 0x80004000, p.UC_PPC_REG_CTR: 0x27,
                   p.UC_PPC_REG_XER: 0xa0000000, p.UC_PPC_REG_FPSCR: 0})
    for r, v in before.items():
        machine.reg_write(r, v)
    machine.mem_write(CONFIG, bytes(64))
    expected_sens = DEFAULT
    valid = False
    if config is not None:
        magic, sens_word = config
        ww(CONFIG, magic)
        ww(CONFIG + 8, sens_word)
        ww(CONFIG + 28, flags)
        wf(CONFIG + 0x30, request)
        if isinstance(step, int):
            ww(CONFIG + REQ_STEP, step)          # raw word (NaN patterns)
        else:
            wf(CONFIG + REQ_STEP, step)
        sens = struct.unpack('>f', struct.pack('>I', sens_word))[0]
        valid = magic == MAGIC
        if valid and not math.isnan(sens) and f32(0.00001) <= sens <= f32(0.1):
            expected_sens = sens
    requested = valid and bool(flags & 8)
    paced_req = requested and bool(flags & PACED_BIT)
    config_before = bytearray(machine.mem_read(CONFIG, 64))
    if requested:
        config_before[28:32] = (flags & ~(8 | PACED_BIT)).to_bytes(4, 'big')
    config_before = bytes(config_before)
    if goal != 'keep':
        ww(GOAL_ACTIVE, goal[0])
        wf(GOAL_YAW, goal[1])
        wf(GOAL_STEP, goal[2] if len(goal) > 2 else STEP)
        ww(GOAL_DIR, goal[3] if len(goal) > 3 else 0)
        ww(PACED, goal[4] if len(goal) > 4 else 0)
        wf(HER_LAST, goal[5] if len(goal) > 5 else 0.0)
    ga, gy, gs, gd = rw(GOAL_ACTIVE), rf(GOAL_YAW), rf(GOAL_STEP), rws(GOAL_DIR)
    pc, hl = rw(PACED), rf(HER_LAST)
    ww(STATE, 0 if init else ACTOR)
    wf(STATE + 4, yaw)
    wf(ACTOR + 0xd0, actor_yaw)
    for off, value in zip([0xc08, 0xc18, 0xc28], position):
        wf(ACTOR + off, value)
    wb(REG.pad + 2, stick)
    wb(REG.pad + 3, suby)
    wb(REG.pad + 8, error)
    wb(REG.r13 + REG.snap_sda, reset)
    actor_before = bytes(machine.mem_read(ACTOR, 0x1000))
    input_before = bytes(machine.mem_read(REG.pad, 0x64))
    step_word_before = rw(CONFIG + REQ_STEP)
    try:
        machine.emu_start(CODE, CODE + len(code), count=20000)
    except u.UcError:
        print('pc', hex(machine.reg_read(p.UC_PPC_REG_PC)))
        raise
    assert machine.reg_read(p.UC_PPC_REG_PC) == CODE + len(code)
    for r, v in before.items():
        if r == p.UC_PPC_REG_XER:
            continue
        want = ACTOR + 0x56c if r == p.UC_PPC_REG_28 else v
        assert machine.reg_read(r) == want, (r, hex(machine.reg_read(r)), hex(want))
    machine.mem_write(0x80004000, bytes.fromhex('7c6102a6'))
    machine.emu_start(0x80004000, 0x80004004)
    assert machine.reg_read(p.UC_PPC_REG_3) == before[p.UC_PPC_REG_XER]
    # ---- reference model of the payload
    y = f32(actor_yaw if init or reset else yaw)
    if init or reset:
        ga, pc = 0, 0
    locked = valid and bool(flags & LOCK)
    if not locked and not error and abs(stick) > 10 and abs(suby) <= abs(stick):
        d = stick - math.copysign(10, stick)
        y = wrap(f32(y - f32(d * f32(expected_sens))))
        ga, pc = 0, 0
    if requested:
        raw = rw(CONFIG + REQ_STEP)
        gy, ga = f32(request), 1
        if paced_req:
            gs, gd, pc, hl = STEP_MIN, 0, 1, f32(actor_yaw)
        else:
            gs, gd = request_step(struct.unpack('>f', raw.to_bytes(4, 'big'))[0])
            pc = 0
    elif valid and flags & 2:
        gy, ga = f32(actor_yaw), 1
        gs, gd, pc = STEP, 0, 0
    hold = False
    if ga:
        d = wrap_d(f32(gy - y))
        if pc:
            delta = wrap_d(f32(f32(actor_yaw) - hl))
            hl = f32(actor_yaw)
            if abs(delta) >= STEP_MIN:
                gs, gd = f32(abs(delta)), (-1 if delta < 0 else 1)
            elif gd == 0:
                hold = abs(d) > gs       # nothing seen yet: snap only if already within the (minimal) step
        if hold:
            pass
        elif abs(d) <= gs:
            y, ga, pc = gy, 0, 0
        else:
            if gd != 0 and abs(d) > THRESH:
                positive = gd > 0
            else:
                positive = d >= 0
            y = wrap(f32(y + gs) if positive else f32(y - gs))
    expected = y
    assert abs(rf(STATE + 4) - expected) < 1e-6, (stick, yaw, rf(STATE + 4), expected, expected_sens, flags, goal, step)
    assert rw(GOAL_ACTIVE) == ga, (rw(GOAL_ACTIVE), ga, flags, goal)
    if ga or requested or (valid and flags & 2):
        assert abs(rf(GOAL_STEP) - gs) < 1e-7 and rws(GOAL_DIR) == gd, (rf(GOAL_STEP), gs, rws(GOAL_DIR), gd, step, flags)
    assert rw(PACED) == pc, ('paced', rw(PACED), pc, flags, goal)
    if pc:
        assert abs(rf(HER_LAST) - hl) < 1e-7, ('her_last', rf(HER_LAST), hl)
    if ga:
        assert abs(rf(GOAL_YAW) - gy) < 1e-6, (rf(GOAL_YAW), gy)
    mat = struct.unpack('>12f', machine.mem_read(ACTOR + 0xbfc, 48))
    want = (math.cos(expected), 0, math.sin(expected), position[0], 0, 1, 0, position[1],
            -math.sin(expected), 0, math.cos(expected), position[2])
    assert max(abs(a - b) for a, b in zip(mat, want)) < 2e-6, (mat, want)
    actor_after = bytes(machine.mem_read(ACTOR, 0x1000))
    assert actor_before[:0xbfc] == actor_after[:0xbfc]
    assert actor_before[0xc2c:] == actor_after[0xc2c:]
    for off in [0xc08, 0xc18, 0xc28]:
        assert actor_after[off:off + 4] == actor_before[off:off + 4]
    assert bytes(machine.mem_read(REG.pad, 0x64)) == input_before
    assert bytes(machine.mem_read(CONFIG, 64)) == config_before
    assert rw(CONFIG + REQ_STEP) == step_word_before    # the step word is read, never written, by the camera
    checks += 1
    return expected


configs = [None, (MAGIC, word(0.0024)), (MAGIC, word(0.0048)), (MAGIC, word(0.0006)), (MAGIC, word(0.05)),
           (0x12345678, word(0.0048)), (MAGIC, word(0.0)), (MAGIC, word(1.0)), (MAGIC, 0x7FC00000), (MAGIC, word(-0.0024))]
for cfg in configs:
    for x in range(-128, 128, 3):
        for yaw in [0, 3.14, -3.14, 1.27]:
            run(x, yaw, config=cfg)
for flags in (2, 3, 0xFF):
    for x in (-128, -11, 0, 11, 127):
        for actor_yaw in (-3.0, -1.0, 0.0, 1.0, 3.0):
            run(x, 0.4, actor_yaw=actor_yaw, config=(MAGIC, word(0.0024)), flags=flags)
            run(x, 0.4, actor_yaw=actor_yaw, config=(MAGIC, word(0.0024)), flags=flags, error=-1)
            run(x, 0.4, actor_yaw=actor_yaw, config=(MAGIC, word(0.0024)), flags=flags, reset=1)
for flags in (1, 4, 0xFD):
    for x in (-128, 0, 127):
        run(x, 0.4, actor_yaw=2.0, config=(MAGIC, word(0.0024)), flags=flags)
for x in (-128, 0, 127):
    run(x, 0.4, actor_yaw=2.0, config=(0x11111111, word(0.0024)), flags=2)
for x in [-128, -11, 0, 11, 127]:
    for err in [-1, -2, -3]:
        run(x, .4, error=err, config=(MAGIC, word(0.01)))
    run(x, .4, reset=1)
    run(x, .4, init=True)
for position in [(0, 0, 0), (100000, 1200, -100000), (-50000, -1200, 50000), (0.125, -0.0, -0.25)]:
    for x in [-128, -11, 0, 11, 127]:
        run(x, .45, position=position, config=(MAGIC, word(0.0036)))
        run(x, .45, position=position, config=(MAGIC, word(0.0036)), flags=2, actor_yaw=-2.5)
for suby in range(-128, 128, 5):
    for x in (-128, -60, -40, -11, 0, 11, 40, 60, 127):
        run(x, 0.9, config=(MAGIC, word(0.0024)), suby=suby)
        run(x, 0.9, config=(MAGIC, word(0.0024)), suby=suby, flags=2, actor_yaw=-1.5)
for x, suby in ((-128, -128), (127, 127), (-128, 127), (127, -128), (11, 11), (11, 12), (12, 11), (-11, 11)):
    run(x, -0.2, suby=suby)
# yaw request: latched as the goal (bit3 cleared), wins over the follow flag, ignored without a valid magic
for req in (0.0, 1.0, -2.5, 3.1, -3.1):
    for flags in (8, 9, 10, 0xF):
        for x in (-128, 0, 127):
            run(x, 0.4, actor_yaw=2.0, config=(MAGIC, word(0.0024)), flags=flags, request=req)
            run(x, 0.4, actor_yaw=2.0, config=(MAGIC, word(0.0024)), flags=flags, request=req, error=-1)
for x in (-128, 0, 127):
    run(x, 0.4, actor_yaw=2.0, config=(0x11111111, word(0.0024)), flags=8, request=1.0)
    run(x, 0.4, actor_yaw=2.0, config=(MAGIC, word(0.0024)), flags=4, request=1.0)
yaw = 0
for _ in range(1000):
    yaw = run(59, yaw, config=(MAGIC, word(0.0024)))


# ---- the swing: one request frame, then the payload keeps turning on its own until it reaches the goal
def swing(start, target, flags, request=0.0, stick=0, step=0.0):
    y = run(stick, start, actor_yaw=target, config=(MAGIC, word(0.0024)), flags=flags, request=request, step=step)
    frames = 1
    path = [y]
    while rw(GOAL_ACTIVE):
        y = run(stick, y, actor_yaw=9.9, config=(MAGIC, word(0.0024)), flags=0, goal='keep')   # her yaw is irrelevant without a request
        frames += 1
        path.append(y)
        assert frames < 400
    return y, frames, path


for start, target in ((0.0, 3.0), (3.0, 0.0), (-3.0, 3.0), (0.4, -2.5), (2.9, -2.9), (-0.1, 0.05), (1.0, 1.0 + STEP), (1.0, 1.0 + 1.5 * STEP)):
    for flags, request in ((2, 0.0), (8, target), (10, target)):
        y, frames, path = swing(start, target, flags, request)
        d = abs(wrap_d(f32(f32(target) - f32(start))))
        assert abs(y - f32(target)) < 1e-6, (start, target, y)
        assert frames == max(1, math.ceil(d / STEP - 1e-6)), (start, target, frames, d / STEP)
        steps = [abs(wrap_d(f32(b - a))) for a, b in zip([f32(start)] + path, path)]
        assert all(s <= STEP + 1e-6 for s in steps), steps                      # never more than one step per frame
        assert all(s >= STEP - 1e-6 for s in steps[:-1]), steps                  # full steps until the final snap
        checks += 1
# exactly 180 degrees: the default swing goes +yaw whichever way the difference is expressed
for start, target, flags, request in ((0.0, math.pi, 2, 0.0), (0.0, -math.pi, 2, 0.0), (0.0, math.pi, 8, math.pi), (0.0, -math.pi, 8, -math.pi), (1.0, 1.0 - math.pi, 2, 0.0)):
    y, frames, path = swing(start, target, flags, request)
    assert path[0] > f32(start) - 1e-6 and abs(path[0] - wrap(f32(start) + STEP)) < 1e-6, (start, target, path[:2])
    assert abs(wrap_d(f32(y - f32(target)))) < 1e-6
    checks += 1
# the Z quick turn of movement v0.16 (a follow request every frame with her yaw advancing less than a step) is still tracked exactly
y, her = 0.5, 0.5
for _ in range(40):
    her = wrap(her + 0.2)
    y = run(0, y, actor_yaw=her, config=(MAGIC, word(0.0024)), flags=2, goal='keep')
    assert abs(y - her) < 1e-6 and rw(GOAL_ACTIVE) == 0
checks += 1
# a C-stick push cancels a pending swing; the game's own view reset and a re-initialisation cancel it too
y = run(0, 0.0, actor_yaw=3.0, config=(MAGIC, word(0.0024)), flags=2)
assert rw(GOAL_ACTIVE) == 1
y = run(60, y, actor_yaw=3.0, config=(MAGIC, word(0.0024)), flags=0, goal='keep')
assert rw(GOAL_ACTIVE) == 0 and abs(y - wrap(f32(STEP) - f32(50 * f32(0.0024)))) < 1e-6
run(0, 0.0, actor_yaw=3.0, config=(MAGIC, word(0.0024)), flags=2)
run(0, 0.2, actor_yaw=2.5, reset=1, goal='keep')
assert rw(GOAL_ACTIVE) == 0 and abs(rf(STATE + 4) - f32(2.5)) < 1e-6
run(0, 0.0, actor_yaw=3.0, config=(MAGIC, word(0.0024)), flags=2)
run(0, 0.2, actor_yaw=-2.5, init=True, goal='keep')
assert rw(GOAL_ACTIVE) == 0 and abs(rf(STATE + 4) - f32(-2.5)) < 1e-6
# a pending swing continues even when the config block is missing or invalid, and a pad error does not stop it
run(0, 0.0, actor_yaw=3.0, config=(MAGIC, word(0.0024)), flags=2)
y = run(0, STEP, config=None, goal='keep')
assert rw(GOAL_ACTIVE) == 1 and abs(y - f32(2 * STEP)) < 1e-6
y = run(90, y, config=(0x11111111, word(0.0024)), error=-1, goal='keep')
assert rw(GOAL_ACTIVE) == 1 and abs(y - f32(3 * STEP)) < 1e-6
checks += 3

# ---- v0.9: the requested step and direction
TURN = f32(math.radians(12.0))
# latch: finite steps of at least step_min are honoured with their sign; 0, tiny, NaN and the follow flag give the default
for step in (TURN, -TURN, 0.3, -0.3, math.radians(1.0), -math.radians(1.0), math.radians(0.9), 0.0, -0.0, 1e-9, 0x7FC00000, 0xFFC00000, 0x7F800000, 0xFF800000, 3.14, -3.14, 3.15, 100.0, -100.0):
    for req in (1.0, -2.0, 3.1):
        run(0, 0.4, config=(MAGIC, word(0.0024)), flags=8, request=req, step=step)
        run(0, 0.4, config=(MAGIC, word(0.0024)), flags=10, request=req, step=step)
        run(0, 0.4, actor_yaw=2.0, config=(MAGIC, word(0.0024)), flags=2, step=step)       # follow: default step, no direction
        run(0, 0.4, config=(0x11111111, word(0.0024)), flags=8, request=req, step=step)   # ignored without the magic
# a request at the camera's own yaw moves nothing, whatever the step says (the facing-the-camera 180 turn)
for yaw in (0.0, 1.5, -3.0, 3.1):
    for step in (TURN, -TURN, 0.0):
        y = run(0, yaw, config=(MAGIC, word(0.0024)), flags=8, request=yaw, step=step)
        assert y == f32(yaw) and rw(GOAL_ACTIVE) == 0
        checks += 1


def swing_frames(start, goal, step):
    """Run one request with the given step, then free frames until the goal is reached; returns the path."""
    y = run(0, start, config=(MAGIC, word(0.0024)), flags=8, request=goal, step=step)
    path = [y]
    while rw(GOAL_ACTIVE):
        y = run(0, y, config=(MAGIC, word(0.0024)), flags=0, goal='keep')
        path.append(y)
        assert len(path) < 400
    return path


# exactly opposite goal: the requested sign decides the direction and the pace is the requested step
for start in (0.0, 1.0, -2.0, 3.0):
    goal = wrap(start + math.pi)
    for step in (TURN, -TURN):
        path = swing_frames(start, goal, step)
        deltas = [wrap_d(f32(b - a)) for a, b in zip([f32(start)] + path, path)]
        assert all((dd > 0) == (step > 0) for dd in deltas[:-1]) and all(abs(abs(dd) - abs(step)) < 1e-6 for dd in deltas[:-1]), (start, step, deltas)
        assert math.ceil(math.pi / abs(step) - 1e-6) <= len(path) <= math.ceil(math.pi / abs(step) - 1e-6) + 1 and abs(wrap_d(f32(path[-1] - goal))) < 1e-6, (start, step, len(path))   # +1: f32 rounding can leave a sliver for a 16th frame
        checks += 1
# nearly opposite (175 degrees): a requested direction is forced even the long way round; a goal within the threshold takes the shorter side
for start in (0.0, 2.0):
    for off_deg, forced in ((175.0, True), (-175.0, True), (160.0, False), (-160.0, False), (90.0, False), (-90.0, False), (30.0, False)):
        goal = wrap(start + math.radians(off_deg))
        for step in (TURN, -TURN):
            path = swing_frames(start, goal, step)
            first = wrap_d(f32(path[0] - f32(start)))
            want_positive = (step > 0) if forced else (off_deg > 0)
            assert (first > 0) == want_positive, (start, off_deg, step, first)
            assert abs(wrap_d(f32(path[-1] - goal))) < 1e-6
            travelled = abs(off_deg) if (not forced or (step > 0) == (off_deg > 0)) else 360.0 - abs(off_deg)
            assert math.ceil(math.radians(travelled) / abs(step) - 1e-6) <= len(path) <= math.ceil(math.radians(travelled) / abs(step) - 1e-6) + 1, (start, off_deg, step, len(path), travelled)
            checks += 1
# the movement v0.17 sequence: entry, one request two frames later with her spin direction, free frames, then one follow frame
for start, spin in ((0.0, -1), (0.0, 1), (1.3, -1), (-2.8, 1)):
    her0 = f32(start + math.pi)                      # she faces the camera; the goal is her final facing = the camera's yaw
    y = run(0, start, actor_yaw=her0, config=(MAGIC, word(0.0024)), flags=0)
    y = run(0, y, actor_yaw=wrap(her0 + spin * 0.2), config=(MAGIC, word(0.0024)), flags=8, request=wrap(her0 + math.pi), step=spin * TURN, goal='keep')
    assert rw(GOAL_ACTIVE) == 0 and abs(wrap_d(f32(y - f32(start)))) < 1e-6      # already there (up to f32 rounding of her0 + pi): nothing moves
    y0 = y
    for k in range(2, 16):
        y = run(0, y, actor_yaw=wrap(her0 + spin * 0.2 * k), config=(MAGIC, word(0.0024)), flags=0, goal='keep')
        assert y == y0
    y = run(0, y, actor_yaw=wrap(her0 + math.pi), config=(MAGIC, word(0.0024)), flags=2, goal='keep')   # the end-of-turn follow
    assert abs(wrap_d(f32(y - f32(start)))) < 1e-6 and rw(GOAL_ACTIVE) == 0 and rws(GOAL_DIR) == 0 and abs(rf(GOAL_STEP) - STEP) < 1e-7
    checks += 1
# a follow after a directed swing resets to the default step and no direction; a new request mid-swing replaces step and direction
y = run(0, 0.0, config=(MAGIC, word(0.0024)), flags=8, request=3.0, step=-TURN)
assert rws(GOAL_DIR) == -1 and abs(rf(GOAL_STEP) - TURN) < 1e-7 and rw(GOAL_ACTIVE) == 1
y = run(0, y, config=(MAGIC, word(0.0024)), flags=8, request=-1.0, step=0.0, goal='keep')
assert rws(GOAL_DIR) == 0 and abs(rf(GOAL_STEP) - STEP) < 1e-7 and rw(GOAL_ACTIVE) == 1
y = run(0, y, actor_yaw=2.0, config=(MAGIC, word(0.0024)), flags=2, goal='keep')
assert rws(GOAL_DIR) == 0 and abs(rf(GOAL_STEP) - STEP) < 1e-7
# a directed swing keeps its step and direction without the config block
y = run(0, 0.0, config=(MAGIC, word(0.0024)), flags=8, request=math.pi, step=-TURN)
y = run(0, y, config=None, goal='keep')
assert rw(GOAL_ACTIVE) == 1 and abs(y - wrap(f32(-2 * TURN))) < 1e-6 and rws(GOAL_DIR) == -1
checks += 3
# ---- v0.10: the camera lock ignores the C-stick while a valid block has bit4 set
for x in range(-128, 128, 7):
    for suby in (0, 100, -100):
        for flags in (LOCK, LOCK | 2, LOCK | 8, LOCK | 0xF, LOCK | 1):
            run(x, 0.9, actor_yaw=2.0, config=(MAGIC, word(0.0024)), flags=flags, suby=suby, request=1.0)
            run(x, 0.9, actor_yaw=2.0, config=(0x11111111, word(0.0024)), flags=flags, suby=suby)     # no magic: the stick works
            run(x, 0.9, actor_yaw=2.0, config=(MAGIC, word(0.0024)), flags=flags & ~LOCK, suby=suby)   # no lock: the stick works
# a pending directed swing is not cancelled by the stick while locked, and resumes being cancellable afterwards
y = run(0, 0.0, config=(MAGIC, word(0.0024)), flags=8, request=math.pi, step=-TURN)
assert rw(GOAL_ACTIVE) == 1
for _ in range(3):
    y = run(100, y, config=(MAGIC, word(0.0024)), flags=LOCK, goal='keep')
    assert rw(GOAL_ACTIVE) == 1 and rws(GOAL_DIR) == -1
y = run(100, y, config=(MAGIC, word(0.0024)), flags=0, goal='keep')
assert rw(GOAL_ACTIVE) == 0
checks += 2
# ---- v0.11: the paced swing
PROFILE_180 = [5.04, 13.68, 20.16, 24.48, 26.64, 26.64, 24.48, 20.16, 13.68, 5.04]
PROFILE_90 = [2.52, 6.84, 10.08, 12.24, 13.32, 13.32, 12.24, 10.08]
paced_cases = 0
for start in (0.0, 1.0, -2.5, 3.0):
    for profile, total_deg in ((PROFILE_180, 180.0), (PROFILE_90, 80.64)):
        for sign in (1, -1):
            her = f32(start)
            goal = wrap(start + sign * math.radians(total_deg))
            y = run(0, start, actor_yaw=her, config=(MAGIC, word(0.0024)), flags=8 | PACED_BIT | LOCK, request=goal, step=0.0)
            assert rw(PACED) == 1 and rw(GOAL_ACTIVE) == 1 and y == f32(start), 'latch: hold until she moves'
            cam = [y]
            for k, r in enumerate(profile):
                her = wrap(her + sign * math.radians(r))
                y = run(0, y, actor_yaw=her, config=(MAGIC, word(0.0024)), flags=LOCK, goal='keep')
                cam.append(y)
                moved = wrap_d(f32(y - cam[-2]))
                # the harness hands the payload her new yaw in the same run, so the camera turns by this frame's rotation here
                # (in the game the hook runs before her update and sees it one frame later)
                assert abs(abs(moved) - math.radians(r)) < 2e-6 and (moved > 0) == (sign > 0), (k, moved, r)
            frames_after = 0
            while rw(GOAL_ACTIVE):
                y = run(0, y, actor_yaw=her, config=(MAGIC, word(0.0024)), flags=LOCK, goal='keep')
                frames_after += 1
                assert frames_after <= 3, 'the paced swing should finish within a few frames of her'
            assert abs(wrap_d(f32(y - goal))) < 1e-6 and rw(PACED) == 0, (start, total_deg, sign, y, goal)
            paced_cases += 1
# a paced request at the camera's own yaw snaps at once (she faces the camera and turns 180)
for yaw in (0.0, 1.5, -3.0):
    y = run(0, yaw, actor_yaw=wrap(yaw + math.pi), config=(MAGIC, word(0.0024)), flags=8 | PACED_BIT, request=yaw, step=0.0)
    assert y == f32(yaw) and rw(GOAL_ACTIVE) == 0 and rw(PACED) == 0
    paced_cases += 1
# tiny rotations (below step_min) keep the camera waiting; a follow or an unpaced request ends the paced state; bit5 alone is ignored
y = run(0, 0.0, actor_yaw=0.0, config=(MAGIC, word(0.0024)), flags=8 | PACED_BIT, request=math.pi, step=0.0)
for k in range(1, 4):
    y = run(0, y, actor_yaw=f32(k * 0.005), config=(MAGIC, word(0.0024)), flags=0, goal='keep')
    assert y == 0.0 and rw(GOAL_ACTIVE) == 1 and rw(PACED) == 1
y = run(0, y, actor_yaw=f32(0.015 + 0.3), config=(MAGIC, word(0.0024)), flags=0, goal='keep')
assert abs(y - f32(0.3)) < 1e-6 and rws(GOAL_DIR) == 1
y = run(0, y, actor_yaw=2.0, config=(MAGIC, word(0.0024)), flags=2, goal='keep')
assert rw(PACED) == 0 and abs(rf(GOAL_STEP) - STEP) < 1e-7
y = run(0, 0.0, config=(MAGIC, word(0.0024)), flags=8 | PACED_BIT, request=2.0, step=0.0)
y = run(0, y, config=(MAGIC, word(0.0024)), flags=8, request=-2.0, step=TURN, goal='keep')
assert rw(PACED) == 0 and rws(GOAL_DIR) == 1 and abs(rf(GOAL_STEP) - TURN) < 1e-7
for x in (-128, 0, 127):
    run(x, 0.4, actor_yaw=2.0, config=(MAGIC, word(0.0024)), flags=PACED_BIT, request=1.0)
    run(x, 0.4, actor_yaw=2.0, config=(MAGIC, word(0.0024)), flags=PACED_BIT | 2, request=1.0)
# a C-stick push cancels a paced swing unless the lock is on; the game's view reset cancels it too
y = run(0, 0.0, config=(MAGIC, word(0.0024)), flags=8 | PACED_BIT, request=math.pi, step=0.0)
y = run(100, y, actor_yaw=0.3, config=(MAGIC, word(0.0024)), flags=LOCK, goal='keep')
assert rw(PACED) == 1 and rw(GOAL_ACTIVE) == 1
y = run(100, y, actor_yaw=0.6, config=(MAGIC, word(0.0024)), flags=0, goal='keep')
assert rw(PACED) == 0 and rw(GOAL_ACTIVE) == 0
run(0, 0.0, config=(MAGIC, word(0.0024)), flags=8 | PACED_BIT, request=math.pi, step=0.0)
run(0, 0.2, actor_yaw=2.5, reset=1, goal='keep')
assert rw(PACED) == 0 and rw(GOAL_ACTIVE) == 0
paced_cases += 4
checks += paced_cases
result = {'passed_cases': checks, 'paced_cases': paced_cases, 'engine': 'Unicorn 2.1.4, PPC32 big endian',
          'real_dol_math': 'C_MTXRotRad at 0x800FC494 plus original sin/cos routines',
          'loaded_at': hex(CODE), 'delivery_words_checked': True, 'swing_step_deg': manifest['swing_step_deg'],
          'dir_threshold_deg': manifest['dir_threshold_deg'], 'step_min_deg': manifest['step_min_deg'],
          'affine_translation_preserved_bitwise': True, 'config_block_read_only': True, 'follow_request_checked': True,
          'axis_exclusivity_checked': True, 'yaw_request_checked': True, 'swing_checked': True, 'request_step_checked': True, 'camera_lock_checked': True, 'paced_swing_checked': True,
          'paired_single_instructions_skipped': len(skipped), 'full_hook_test_in_dolphin_required': True}
(build / 'unit-test-results.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
