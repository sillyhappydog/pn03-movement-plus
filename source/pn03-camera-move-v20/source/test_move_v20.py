"""Execute the movement v0.16 payload in Unicorn against the real DOL atan2f.

v0.16 adds the camera-relative crouch: in sub-state 5 with Y held the stick becomes one crouch action
(forward / back step or the L / R trigger bits) relative to her facing; Y released -> exploration rules.

v0.15 adds the L/R op-word swap outside the exploration states (sidestep from the shooting posture,
chained sidesteps, jump landing, Y stance, Z turn ...) when Vanessa faces the camera, with her yaw
untouched, and the 6x default camera sensitivity (0.0036).

v0.14 adds the X lock-on camera: follow_frames / cam_yaw_request / pending_focus (config v3); the
real aim-point accessor 0x8009EFB0 runs against a mocked target object.

v0.13 adds the C-stick driven Z quick turn direction (pad LEFT/RIGHT sector bits rewritten on sub-state 8 phase 0).

v0.11: the window (hold / run pass-through / kind 1) only applies while the game's DOWN sector bit
(pad buttons 0x40000) is set; other pushes convert immediately and B after them is kind 2.

v0.10: the window never passes turn/back-walk bits; only UP (run) within 45 deg of the facing,
immediate conversion on the arc, hold otherwise.

v0.9 adds: default window from the manifest, RC pass-through during the window (player-relative
bits) with the immediate-conversion arc test, hold mode via flags bit2, Y toggle and the MODE text.

v0.8 = v0.7 relocated to its RAM region (loaded at the real address, config block at
its new address) with the OnFrame delivery words checked statically.

Covers v0.6 behaviour plus: config version 2 upgrade, the stick push counter, the
jump window hold, pending jump kinds, the jump entry yaw snap, player-relative
8-way conversion during jumps, the sidestep yaw snap and the A/B window tuning.
DebugPrintf / SetDebugPage are stubbed; paired-single and GQR instructions are nops.
"""
import sys, struct, math, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
from regions import R as REG
import unicorn as u
import unicorn.ppc_const as p
import dol

build = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / ('move-v20-build' + REG.suffix)
manifest = json.loads((build / 'manifest.json').read_text(encoding='utf-8'))
CODE = manifest['region']
HOOK = manifest['hook']
WORDS = {k: CODE + v for k, v in manifest['data_words'].items()}
CONFIG = manifest['config_block']
MAGIC = manifest['config_magic']
VERSION = manifest['config_version']
CO = manifest['config_offsets']
DEF = manifest['defaults']
STEPS = manifest['steps']
JUMP = manifest['jump']
TEXT = manifest['text']
PRINTF = manifest['debug_printf']
SETPAGE = manifest['set_debug_page']
TURN_T = manifest['turn']['threshold']
ACTOR = 0x81000000
CTRL = ACTOR + 0x56C
CAMERA = 0x81100000
CAMERA_PTR = REG.camera_ptr
PAD = REG.pad
ROOT_PTR = REG.r13 + REG.root_sda
ROOT = 0x81300000
PAGE = ROOT + REG.root_debug_page
SP = 0x817f0000
machine = u.Uc(u.UC_ARCH_PPC, u.UC_MODE_32 | u.UC_MODE_BIG_ENDIAN)
machine.mem_map(0x80000000, 0x1800000)
for f, a, n in dol.sections:
    machine.mem_write(a, dol.data[f:f + n])
code = bytearray((build / 'move.bin').read_bytes())
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
assert CODE + len(code) <= manifest['region_end']
skipped = []
for off in range(0, len(code) - 4, 4):
    w = int.from_bytes(code[off:off + 4], 'big')
    if manifest['data_offset'] <= off < manifest['data_end']:
        continue
    if w >> 26 in [56, 60] or w in [0x7c10e2a6, 0x7c10e3a6]:
        skipped.append(off)
        code[off:off + 4] = bytes.fromhex('60000000')
code[-4:] = bytes.fromhex('60000000')   # the branch back to the hook
machine.mem_write(CODE, bytes(code))
machine.reg_write(p.UC_PPC_REG_MSR, 0x2000)
machine.mem_write(PRINTF, bytes.fromhex('4e800020'))
machine.mem_write(SETPAGE, bytes.fromhex('4e800020'))
prints = []
page_log = []


def read_cstr(a):
    out = b''
    while True:
        c = bytes(machine.mem_read(a, 1))
        if c == b'\0':
            return out
        out += c
        a += 1


def hook_code(uc, address, size, user):
    if address == PRINTF:
        cr = uc.reg_read(p.UC_PPC_REG_CR)
        raw = read_cstr(uc.reg_read(p.UC_PPC_REG_7))
        prints.append(dict(x=uc.reg_read(p.UC_PPC_REG_3), y=uc.reg_read(p.UC_PPC_REG_4),
                           attr=uc.reg_read(p.UC_PPC_REG_5), page_arg=uc.reg_read(p.UC_PPC_REG_6),
                           raw=raw, text=raw.decode('cp932'), fp_args=bool((cr >> (31 - 6)) & 1),
                           page_now=bytes(uc.mem_read(PAGE, 1))[0]))
    elif address == SETPAGE:
        old = bytes(uc.mem_read(PAGE, 1))[0]
        new = uc.reg_read(p.UC_PPC_REG_3) & 0xFF
        uc.mem_write(PAGE, bytes([new]))
        uc.reg_write(p.UC_PPC_REG_3, old if old < 128 else old - 256)
        page_log.append((old, new))


machine.hook_add(u.UC_HOOK_CODE, hook_code, begin=PRINTF, end=PRINTF + 4)
machine.hook_add(u.UC_HOOK_CODE, hook_code, begin=SETPAGE, end=SETPAGE + 4)


def wf(a, f):
    machine.mem_write(a, struct.pack('>f', f))


def rf(a):
    return struct.unpack('>f', machine.mem_read(a, 4))[0]


def rw(a):
    return int.from_bytes(machine.mem_read(a, 4), 'big')


def f32(f):
    return struct.unpack('>f', struct.pack('>f', f))[0]


def packf(f):
    return int.from_bytes(struct.pack('>d', f), 'big')


QUARTER = f32(math.radians(manifest['turn']['quarter_deg']))
STICK_BLOCK = manifest['turn']['stick_block_frames']
LOCK = manifest['turn']['camera_lock_flag_bit']
PACED = manifest['turn']['paced_flag_bit']


def wb(a, n):
    machine.mem_write(a, bytes([n & 255]))


def ww(a, n):
    machine.mem_write(a, n.to_bytes(4, 'big'))


def wrap(t):
    while t > f32(math.pi):
        t = f32(t - f32(2 * math.pi))
    while t < f32(-math.pi):
        t = f32(t + f32(2 * math.pi))
    return t


checks = 0


def block(sens=DEF['camera_sensitivity'], dz=DEF['move_deadzone_squared'], sign=DEF['move_stick_sign'],
          off=DEF['move_camera_offset'], flags=0, magic=MAGIC, version=VERSION, window=DEF['jump_window'],
          counter=0, pending=0, follow=0, request=0.0, focus=0, step=0.0):
    machine.mem_write(CONFIG, bytes(64))
    ww(CONFIG, magic)
    ww(CONFIG + 4, version)
    wf(CONFIG + 8, sens)
    wf(CONFIG + 12, DEF['camera_deadzone'])
    wf(CONFIG + 16, dz)
    wf(CONFIG + 20, sign)
    wf(CONFIG + 24, off)
    ww(CONFIG + 28, flags)
    ww(CONFIG + CO['jump_window'], window)
    ww(CONFIG + CO['push_frames'], counter)
    ww(CONFIG + CO['pending_jump'], pending)
    ww(CONFIG + CO['follow_frames'], follow)
    wf(CONFIG + CO['cam_yaw_request'], request)
    ww(CONFIG + CO['pending_focus'], focus)
    wf(CONFIG + CO['cam_yaw_step'], step)


def expected_pad(pad, tuning, turn_bits=None):
    """Apply the payload's pad-word edits to a 0x64-byte pad image."""
    b = bytearray(pad)
    if turn_bits is not None:
        b[0x10:0x14] = ((int.from_bytes(b[0x10:0x14], 'big') & ~0x30000) | turn_bits).to_bytes(4, 'big')
    subx = int.from_bytes(b[2:3], 'big', signed=True)
    suby = int.from_bytes(b[3:4], 'big', signed=True)
    pressed = int.from_bytes(b[0x14:0x18], 'big') & ~0x300000
    if abs(subx) >= abs(suby):
        pressed &= ~0xC00000
    b[0x14:0x18] = pressed.to_bytes(4, 'big')
    if tuning:
        for off in (0x10, 0x14, 0x18):
            b[off:off + 4] = (int.from_bytes(b[off:off + 4], 'big') & ~0xB0F).to_bytes(4, 'big')
    return bytes(b)


def sector_bits(sx, sy):
    """The game's stick sector bits in the pad buttons word (radius 30 dead zone, atan2 sectors)."""
    if sx * sx + sy * sy <= 900:
        return 0
    phi = -math.degrees(math.atan2(sx, sy))
    bits = 0
    if abs(phi) < 70:
        bits |= 0x80000
    if abs(phi) > 110:
        bits |= 0x40000
    if -150 < phi < -30:
        bits |= 0x20000
    if 30 < phi < 150:
        bits |= 0x10000
    return bits


def run(stick_x, stick_y, eye, target, category=1, sub=1, phase=0, ctrl=0x12345270, yaw=0.3, error=0, last_yaw=0.7,
        camera_null=False, buttons=0, pressed=0, released=0, subx=0, suby=0, prepare_block=True, page=1, auto_sector=True,
        targets=0, lock_target=0, turn=None):
    """turn: None zeroes the payload's turn words before the frame, (state, entry_yaw, delta) sets them, 'keep' leaves them."""
    global checks
    if auto_sector:
        buttons |= sector_bits(stick_x, stick_y)
    prints.clear()
    page_log.clear()
    before = {p.UC_PPC_REG_0 + i: 0x12340000 + i for i in range(32)}
    before[p.UC_PPC_REG_1] = SP
    before[p.UC_PPC_REG_2] = REG.r2
    before[p.UC_PPC_REG_13] = REG.r13
    before[p.UC_PPC_REG_30] = CTRL
    before[p.UC_PPC_REG_31] = 0x81200000
    for i in range(32):
        before[p.UC_PPC_REG_FPR0 + i] = packf(i + .125)
    before.update({p.UC_PPC_REG_CR: 0xa5927310, p.UC_PPC_REG_LR: 0x80004000, p.UC_PPC_REG_CTR: 0x27,
                   p.UC_PPC_REG_XER: 0xa0000000, p.UC_PPC_REG_FPSCR: 0})
    for r, v in before.items():
        machine.reg_write(r, v)
    machine.mem_write(ACTOR, bytes(0x1000))
    machine.mem_write(CAMERA, bytes(0x200))
    if prepare_block is True:
        block()
    elif prepare_block is False:
        machine.mem_write(CONFIG, bytes(64))
    valid = rw(CONFIG) == MAGIC
    flags_before = rw(CONFIG + 28) if valid else 0
    v3 = valid and rw(CONFIG + 4) == VERSION
    ff_before = rw(CONFIG + CO['follow_frames']) if v3 else 0
    config_before = bytes(machine.mem_read(CONFIG, 64))
    machine.mem_write(ACTOR + 0xDC8, targets.to_bytes(2, 'big'))
    ww(ACTOR + 0x5B4, lock_target)
    wb(ACTOR + 0xF8, category)
    wb(ACTOR + 0xF9, sub)
    wb(ACTOR + 0xFA, phase)
    ww(ACTOR + 0x5F8, ctrl)
    wf(ACTOR + 0xD0, yaw)
    for k, v in enumerate(eye):
        wf(CAMERA + 0x100 + 4 * k, v)
    for k, v in enumerate(target):
        wf(CAMERA + 0x10C + 4 * k, v)
    ww(CAMERA_PTR, 0 if camera_null else CAMERA)
    ww(ROOT_PTR, ROOT)
    wb(PAGE, page)
    machine.mem_write(PAD, bytes(0x64))
    wb(PAD, stick_x)
    wb(PAD + 1, stick_y)
    wb(PAD + 2, subx)
    wb(PAD + 3, suby)
    wb(PAD + 8, error)
    ww(PAD + 0x10, buttons)
    ww(PAD + 0x14, pressed)
    ww(PAD + 0x18, released)
    wf(WORDS['last_camera_yaw'], last_yaw)
    if turn is None:
        turn = (0, 0.0, 0.0, 0)
    if turn != 'keep':
        ww(WORDS['turn_state'], turn[0])
        wf(WORDS['turn_entry_yaw'], turn[1])
        wf(WORDS['turn_delta'], turn[2])
        ww(WORDS['stick_block'], turn[3] if len(turn) > 3 else 0)
    ts0, te0, td0, sb0 = rw(WORDS['turn_state']), rf(WORDS['turn_entry_yaw']), rf(WORDS['turn_delta']), rw(WORDS['stick_block'])
    req0, step0 = (rf(CONFIG + CO['cam_yaw_request']), rf(CONFIG + CO['cam_yaw_step'])) if v3 else (0.0, 0.0)
    actor_before = bytes(machine.mem_read(ACTOR, 0x1000))
    pad_before = bytes(machine.mem_read(PAD, 0x64))
    camera_before = bytes(machine.mem_read(CAMERA, 0x200))
    try:
        machine.emu_start(CODE, CODE + len(code), count=80000)
    except u.UcError:
        print('pc', hex(machine.reg_read(p.UC_PPC_REG_PC)))
        raise
    assert machine.reg_read(p.UC_PPC_REG_PC) == CODE + len(code)
    for r, v in before.items():
        if r == p.UC_PPC_REG_XER:
            continue
        want = ROOT if r == p.UC_PPC_REG_11 else v
        assert machine.reg_read(r) == want, (r, hex(machine.reg_read(r)), hex(want))
    machine.mem_write(0x80004000, bytes.fromhex('7c6102a6'))
    machine.emu_start(0x80004000, 0x80004004)
    assert machine.reg_read(p.UC_PPC_REG_3) == before[p.UC_PPC_REG_XER]
    actor_after = bytes(machine.mem_read(ACTOR, 0x1000))
    for off in range(0, 0x1000, 4):
        if off in (0xD0, 0x5F8):
            continue
        assert actor_before[off:off + 4] == actor_after[off:off + 4], hex(off)
    toggle = (buttons & 0x60) == 0x60 and bool(pressed & 0x10)
    tuning = valid and bool(flags_before & 1) and not toggle
    turn_apply = not tuning and not toggle and not error and category == 1 and sub == 8 and phase == 0
    sx_signed = ((subx & 0xFF) ^ 0x80) - 0x80
    turn_bits = (0x10000 if sx_signed < -TURN_T else 0x20000 if sx_signed > TURN_T else 0) if turn_apply else None
    assert bytes(machine.mem_read(PAD, 0x64)) == expected_pad(pad_before, tuning, turn_bits), 'pad edits differ'
    assert bytes(machine.mem_read(CAMERA, 0x200)) == camera_before
    assert rw(CONFIG) == MAGIC and rw(CONFIG + 4) == VERSION
    assert bytes(machine.mem_read(PAGE, 1))[0] == page, 'debug page not restored'
    flags = rw(CONFIG + 28)
    assert bool(flags & 2) == (ff_before > 0), ('follow flag', category, sub, flags, ff_before)
    # ---- v0.17 turn tracking model (runs after the follow flag, before the tuning checks; then the entry in the dispatch)
    in_turn = category == 1 and sub == 8
    exp_ts, exp_te, exp_td = ts0, te0, td0
    exp_req, exp_step, turn_bit3, end_follow = None, None, False, False
    exp_sb, exp_lock = sb0, False
    if in_turn:
        exp_sb, exp_lock = STICK_BLOCK, True
    else:
        if sb0 > 0:
            exp_sb, exp_lock = sb0 - 1, True
        if exp_sb == 0 and ts0 != 0:
            exp_ts, end_follow = 0, True
    if turn_apply:
        exp_ts, exp_te = 1, f32(yaw)
        exp_td = QUARTER if sx_signed < -TURN_T else f32(-QUARTER) if sx_signed > TURN_T else f32(math.pi)
        exp_req, exp_step, turn_bit3 = wrap(f32(f32(yaw) + exp_td)), 0.0, True
    assert rw(WORDS['turn_state']) == exp_ts, ('turn_state', rw(WORDS['turn_state']), exp_ts, category, sub, phase)
    assert rw(WORDS['stick_block']) == exp_sb, ('stick_block', rw(WORDS['stick_block']), exp_sb, category, sub)
    if valid and not toggle:
        assert bool(flags & LOCK) == exp_lock, ('camera lock bit', hex(flags), exp_lock, category, sub, sb0)
    assert abs(rf(WORDS['turn_entry_yaw']) - exp_te) < 1e-6 and abs(rf(WORDS['turn_delta']) - exp_td) < 1e-6, ('turn words', rf(WORDS['turn_entry_yaw']), exp_te, rf(WORDS['turn_delta']), exp_td)
    if v3:
        if exp_req is not None:
            assert abs(rf(CONFIG + CO['cam_yaw_request']) - exp_req) < 1e-6 and abs(rf(CONFIG + CO['cam_yaw_step']) - exp_step) < 1e-7, ('turn request', rf(CONFIG + CO['cam_yaw_request']), exp_req, rf(CONFIG + CO['cam_yaw_step']), exp_step)
            assert (flags & 8) and (flags & PACED), 'turn request without bit3 | bit5'
        elif in_turn:
            assert rf(CONFIG + CO['cam_yaw_request']) == req0 and rf(CONFIG + CO['cam_yaw_step']) == step0, 'request words changed without a turn request'
        if end_follow:
            assert rw(CONFIG + CO['follow_frames']) == 1, ('end-of-turn follow', rw(CONFIG + CO['follow_frames']))
    assert not (flags & 2) or not in_turn or ff_before > 0, 'follow flag raised by the turn state'
    config_after = bytes(machine.mem_read(CONFIG, 64))
    if valid and rw(CONFIG + 4) == VERSION and config_before[4:8] == VERSION.to_bytes(4, 'big'):
        # a valid v2 block only changes at: sensitivity/window (tuning), flags, counter, pending
        for off in range(0, 64, 4):
            if off in (8, 28, CO['jump_window'], CO['push_frames'], CO['pending_jump'], CO['follow_frames'], CO['cam_yaw_request'], CO['pending_focus'], CO['cam_yaw_step']):
                continue
            assert config_before[off:off + 4] == config_after[off:off + 4], ('config changed at', off)
    checks += 1
    return dict(yaw=rf(ACTOR + 0xD0), ctrl=rw(ACTOR + 0x5F8), last=rf(WORDS['last_camera_yaw']),
                sens=rf(CONFIG + 8), dz=rf(CONFIG + 16), sign=rf(CONFIG + 20), off=rf(CONFIG + 24),
                flags=flags, window=rw(CONFIG + CO['jump_window']), counter=rw(CONFIG + CO['push_frames']),
                pending=rw(CONFIG + CO['pending_jump']), tail=bytes(machine.mem_read(CONFIG + 56, 8)),
                follow=rw(CONFIG + CO['follow_frames']), request=rf(CONFIG + CO['cam_yaw_request']), focus=rw(CONFIG + CO['pending_focus']),
                step=rf(CONFIG + CO['cam_yaw_step']), tstate=rw(WORDS['turn_state']), tentry=rf(WORDS['turn_entry_yaw']), tdelta=rf(WORDS['turn_delta']),
                prints=list(prints), pages=list(page_log), pad=bytes(machine.mem_read(PAD, 0x64)))


def cam_yaw(eye, target, last_yaw=0.7):
    dx, dz = target[0] - eye[0], target[2] - eye[2]
    return f32(math.atan2(dx, dz)) if dx * dx + dz * dz > 1.0 else f32(last_yaw)


def intended(stick_x, stick_y, eye, target, last_yaw=0.7, sign=1.0, off=0.0):
    cam = cam_yaw(eye, target, last_yaw)
    stick = f32(math.atan2(f32(stick_x * sign), stick_y))
    return wrap(f32(f32(cam + f32(off)) - stick)), cam


SECT = [f32(math.radians(d)) for d in JUMP['sectors_deg']]


def relative_bits(a, yaw):
    """Expected 8-way bits for intended direction a and player yaw; None if on a sector boundary."""
    r = wrap(f32(a - f32(yaw)))
    m = abs(r)
    if any(abs(m - s) < 2e-3 for s in SECT):
        return None
    bits = 0
    if m < SECT[1]:
        bits |= 1
    if m > SECT[2]:
        bits |= 2
    if SECT[0] < m < SECT[3]:
        bits |= 8 if r > 0 else 4
    return bits


def pushed(sx, sy):
    return sx * sx + sy * sy > 900


ASCII_TEXT = TEXT.get('encoding') == 'ascii'
FW = str.maketrans('', '') if ASCII_TEXT else str.maketrans('0123456789.', '０１２３４５６７８９．')
BLANK = ' ' if ASCII_TEXT else '　'
DOT = '.' if ASCII_TEXT else '．'


def expected_line1(sens):
    s = f32(sens)
    n1 = min(9999, max(0, int(f32(f32(s * f32(10000.0)) + f32(0.5)))))
    n2 = min(9999, max(0, int(f32(f32(f32(s / f32(0.0006)) * f32(100.0)) + f32(0.5)))))
    frac = f'{n1:04d}'.translate(FW)
    tens, ones, tenths, hundredths = f'{n2:04d}'
    mult = (BLANK if tens == '0' else tens.translate(FW)) + ones.translate(FW) + DOT + (tenths + hundredths).translate(FW)
    return TEXT['line1_prefix'] + frac + TEXT['line1_mid'] + mult


def expected_line3(window, hold=False):
    return TEXT['line3_prefix'] + f'{min(99, max(0, window)):02d}'.translate(FW) + TEXT['line3_mid'] + TEXT['line3_suffix']   # v0.20: no MODE text


def check_prints(r, sens, window, page, hold=False):
    assert len(r['prints']) == 3, r['prints']
    a, c, b = r['prints']
    assert (a['x'], a['y'], a['attr'], a['page_arg']) == (TEXT['x'], TEXT['y1'], 0, 0)
    assert (c['x'], c['y'], c['attr'], c['page_arg']) == (TEXT['x'], TEXT['y3'], 0, 0)
    assert (b['x'], b['y'], b['attr'], b['page_arg']) == (TEXT['x'], TEXT['y2'], 0, 0)
    assert a['text'] == expected_line1(sens), (a['text'], expected_line1(sens), sens)
    assert c['text'] == expected_line3(window, hold), (c['text'], expected_line3(window, hold))
    assert b['text'] == TEXT['line2'], b['text']
    assert all(len(ch.encode('cp932')) == TEXT['bytes_per_char'] for ch in a['text'] + b['text'] + c['text'])
    assert not a['fp_args'] and not b['fp_args'] and not c['fp_args']
    assert a['page_now'] == 1 and b['page_now'] == 1 and c['page_now'] == 1
    assert r['pages'] == [(page, 1), (1, page)], r['pages']


def clamp(v):
    return f32(min(f32(STEPS['maximum']), max(f32(STEPS['minimum']), v)))


def expected_steps(sens, pressed):
    s = f32(sens)
    if pressed & 8:
        s = clamp(f32(s + f32(STEPS['coarse'])))
    if pressed & 4:
        s = clamp(f32(s - f32(STEPS['coarse'])))
    if pressed & 2:
        s = clamp(f32(s + f32(STEPS['fine'])))
    if pressed & 1:
        s = clamp(f32(s - f32(STEPS['fine'])))
    if pressed & 0x400:
        s = f32(DEF['camera_sensitivity'])
    return s


def expected_window(window, pressed):
    w = window
    if pressed & 0x400:
        w = DEF['jump_window']
    if pressed & 0x100 and w < JUMP['window_max']:
        w += 1
    if pressed & 0x200 and w > 0:
        w -= 1
    return w


BEHIND = ((0.0, 300.0, -1000.0), (0.0, 100.0, 0.0))
deg = math.radians
L, R, Z, A, B, X, Y = 0x40, 0x20, 0x10, 0x100, 0x200, 0x400, 0x800
HOLD = JUMP['hold_flag_bit']
EPS = f32(JUMP['arc_epsilon'])
RUN_DEG = f32(math.radians(JUMP['run_passthrough_deg']))


def arc_extra(a, f, c):
    """Extra flicker of turning to a first: |a-f| + |c-a| - |c-f| (f32 like the payload)."""
    r1 = wrap(f32(a - f32(f)))
    r2 = wrap(f32(f32(c) - a))
    r3 = wrap(f32(f32(c) - f32(f)))
    return f32(f32(abs(r1) + abs(r2)) - abs(r3))


def window_expect(r, sx, sy, eye, target, yaw, ctrl):
    """Check the RUN-mode window outcome inside the chord zone (DOWN sector); outside it: immediate."""
    want, cam = intended(sx, sy, eye, target)
    if not (sector_bits(sx, sy) & 0x40000):
        assert abs(r['yaw'] - want) < 2e-5 and r['ctrl'] == (ctrl & 0xFFFFFFF0) | 1, ('outside zone', sx, sy, yaw, r)
        return
    extra = arc_extra(want, yaw, cam)
    if abs(extra - EPS) < 0.05:
        return
    if extra < EPS:
        assert abs(r['yaw'] - want) < 2e-5 and r['ctrl'] == (ctrl & 0xFFFFFFF0) | 1, ('immediate', sx, sy, yaw, r)
        return
    rel = abs(wrap(f32(want - f32(yaw))))
    assert r['yaw'] == f32(yaw), ('window yaw', sx, sy, yaw, r['yaw'])
    if abs(rel - RUN_DEG) < 2e-3:
        return
    if rel < RUN_DEG:
        assert r['ctrl'] == (ctrl & 0xFFFFFFF0) | 1, ('run pass-through', sx, sy, yaw, hex(r['ctrl']))
    else:
        assert r['ctrl'] == (ctrl & 0xFFFFFFF0), ('hold', sx, sy, yaw, hex(r['ctrl']))
DU, DD, DR, DL = 0x8, 0x4, 0x2, 0x1
CL, CR, CD, CU = 0x100000, 0x200000, 0x400000, 0x800000
CTRL_B = 0x2000
CTRL_L = 0x8000 | 0x20000
CTRL_R = 0x4000 | 0x10000
WIN = DEF['jump_window']
EXPLORE = (0, 1, 0xB, 0xC)
cameras = {0.0: ((0.0, 300.0, -1000.0), (0.0, 100.0, 0.0)), deg(90): ((-1000.0, 300.0, 0.0), (0.0, 100.0, 0.0)),
           deg(180): ((0.0, 300.0, 1000.0), (0.0, 100.0, 0.0)), deg(-90): ((1000.0, 300.0, 0.0), (0.0, 100.0, 0.0))}
sticks = {'up': (0, 100), 'down': (0, -100), 'right': (100, 0), 'left': (-100, 0), 'up_right': (70, 70),
          'up_left': (-70, 70), 'down_right': (70, -70), 'down_left': (-70, -70)}

# 1. Block initialisation, upgrade and preservation.
for prep in (False, 'wrong'):
    if prep == 'wrong':
        block(sens=0.03, magic=0x11111111)
    r = run(0, 0, *BEHIND, prepare_block=None if prep == 'wrong' else False)
    assert (r['sens'], r['dz'], r['sign'], r['off'], r['flags']) == (f32(DEF['camera_sensitivity']), 900.0, 1.0, 0.0, 0)
    assert (r['window'], r['counter'], r['pending']) == (WIN, 0, 0) and r['tail'] == bytes(8) and r['prints'] == []
    assert (r['follow'], r['request'], r['focus']) == (0, 0.0, 0)
block(sens=0.0077, dz=400.0, sign=-1.0, off=math.pi, version=1, window=0, counter=77, pending=1, follow=9, request=1.5, focus=1, flags=8)
r = run(0, 100, *BEHIND, prepare_block=None, sub=3)   # v1 block: upgraded, tuned values kept, jump state ignores junk
assert (r['sens'], r['dz'], r['sign'], r['off']) == (f32(0.0077), 400.0, -1.0, f32(math.pi))
assert (r['window'], r['counter'], r['pending']) == (WIN, 1, 0) and r['yaw'] == f32(0.3)
assert (r['follow'], r['request'], r['focus']) == (0, 0.0, 0) and not (r['flags'] & 0xA)
block(sens=0.005, version=2, window=7, counter=3, pending=2, follow=4, request=2.5, focus=1, flags=8)
r = run(0, 0, *BEHIND, prepare_block=None, sub=8)     # v2 block: window kept, new fields zeroed, stale bit3 cleared
assert (r['sens'], r['window'], r['counter'], r['pending'], r['follow'], r['focus']) == (f32(0.005), 7, 0, 0, 0, 0)
assert r['flags'] == (LOCK | 8 | PACED)
block(window=12, counter=5, pending=2)
r = run(0, 0, *BEHIND, prepare_block=None, category=2)
assert (r['window'], r['counter'], r['pending']) == (12, 0, 0)

# 2. Push counter and pending consumption regardless of category / sub-state.
for cat, sub in [(0, 1), (2, 1), (1, 2), (1, 4), (1, 5), (1, 8), (1, 0xD)]:
    for counter in (0, 3, 40, 999, 1000):
        block(counter=counter, pending=1)
        r = run(0, 100, *BEHIND, category=cat, sub=sub, prepare_block=None)
        assert (r['counter'], r['pending']) == (min(1000, counter + 1), 0), (cat, sub, counter, r['counter'])
        want_ctrl = 0x12341271 if (cat, sub) == (1, 5) else 0x12345270   # v0.16: 0x12345270 holds Y, so the crouch turns stick-up into a forward step (stray 0x4000 cleared)
        assert (r['yaw'], r['ctrl']) == (f32(0.3), want_ctrl) and r['prints'] == []
        block(counter=counter, pending=2)
        r = run(0, 0, *BEHIND, category=cat, sub=sub, prepare_block=None)
        assert (r['counter'], r['pending']) == (0, 0)
for sx, sy in [(0, 0), (30, 0), (0, -30), (21, 21), (17, 24)]:
    block(counter=9)
    r = run(sx, sy, *BEHIND, prepare_block=None)
    assert (r['yaw'], r['ctrl'], r['counter']) == (f32(0.3), 0x12345270, 0)
block(counter=9, pending=2)
r = run(0, 100, *BEHIND, error=-1, prepare_block=None)
assert (r['yaw'], r['ctrl'], r['counter'], r['pending']) == (f32(0.3), 0x12345270, 0, 0)

# 3. Exploration: window (hold mode / RC mode) vs running conversion (no buttons).
for sub in EXPLORE:
    for counter in range(0, WIN + 3):
        block(counter=counter, flags=HOLD)
        r = run(20, -98, *BEHIND, sub=sub, ctrl=0x1234527F, prepare_block=None)   # DOWN sector: chord zone
        assert r['counter'] == counter + 1 and r['pending'] == 0 and r['flags'] == HOLD
        if counter + 1 <= WIN:
            assert (r['yaw'], r['ctrl']) == (f32(0.3), 0x12345270), (sub, counter, hex(r['ctrl']))
        else:
            want, cam = intended(20, -98, *BEHIND)
            assert abs(r['yaw'] - want) < 2e-5 and r['ctrl'] == 0x12345271 and abs(r['last'] - cam) < 2e-6
        block(counter=counter)   # RUN mode
        r = run(20, -98, *BEHIND, sub=sub, yaw=0.3, ctrl=0x1234527F, prepare_block=None)
        assert r['counter'] == counter + 1 and r['pending'] == 0 and r['flags'] == 0
        if counter + 1 <= WIN:
            window_expect(r, 20, -98, *BEHIND, 0.3, 0x1234527F)
        else:
            want, cam = intended(20, -98, *BEHIND)
            assert abs(r['yaw'] - want) < 2e-5 and r['ctrl'] == 0x12345271
        for mode in (0, HOLD):   # outside the DOWN sector the window never applies
            for sx, sy in ((70, 70), (-100, 0), (100, 0), (0, 100), (-95, -30)):
                block(counter=counter, flags=mode)
                r = run(sx, sy, *BEHIND, sub=sub, yaw=0.3, ctrl=0x1234527F, prepare_block=None)
                want, cam = intended(sx, sy, *BEHIND)
                assert abs(r['yaw'] - want) < 2e-5 and r['ctrl'] == 0x12345271, (mode, sub, counter, sx, sy, hex(r['ctrl']))
# RC-mode window: canonical cases with the camera behind (cam yaw 0)
for yaw, name, kind in ((0.0, 'down', 'hold'), (0.0, 'up', 'immediate'), (0.0, 'left', 'immediate'), (0.0, 'right', 'immediate'),
                        (math.pi, 'down', 'immediate'), (math.pi, 'up', 'immediate'), (math.pi / 2, 'up', 'immediate'),
                        (math.pi / 2, 'down', 'hold'), (math.pi / 2, 'left', 'immediate'), (math.pi / 2, 'right', 'immediate'),
                        (-0.3, 'up', 'immediate'), (math.pi / 2, 'down_right', 'hold'), (0.0, 'down_left', 'hold')):   # down_left would sit exactly on the 45 deg boundary
    block(counter=1)
    r = run(*sticks[name], *BEHIND, yaw=yaw, ctrl=0x1234527F, prepare_block=None)
    want, cam = intended(*sticks[name], *BEHIND)
    if kind == 'immediate':
        assert abs(r['yaw'] - want) < 2e-5 and r['ctrl'] == 0x12345271, (yaw, name, r)
    else:
        assert r['yaw'] == f32(yaw) and r['ctrl'] == 0x12345270, (yaw, name, hex(r['ctrl']))
    window_expect(r, *sticks[name], *BEHIND, yaw, 0x1234527F)
# run pass-through inside the zone: facing 150 deg (mostly toward the camera), stick straight down -> 30 deg off, not on the arc
block(counter=1)
r = run(0, -100, *BEHIND, yaw=math.radians(150), ctrl=0x1234527F, prepare_block=None)
want, cam = intended(0, -100, *BEHIND)
assert arc_extra(want, math.radians(150), cam) > EPS and abs(wrap(f32(want - f32(math.radians(150))))) < RUN_DEG
assert r['yaw'] == f32(math.radians(150)) and r['ctrl'] == 0x12345271, ('run pass-through', r)
block(counter=1)
r = run(0, -100, *BEHIND, yaw=math.radians(120), ctrl=0x1234527F, prepare_block=None)   # 60 deg off the facing -> hold
assert r['yaw'] == f32(math.radians(120)) and r['ctrl'] == 0x12345270, ('hold beyond 45', r)
block(counter=1)
r = run(87, 50, *BEHIND, yaw=-math.radians(30), ctrl=0x1234527F, prepare_block=None)   # not DOWN sector -> immediate
want, cam = intended(87, 50, *BEHIND)
assert abs(r['yaw'] - want) < 2e-5 and r['ctrl'] == 0x12345271, ('outside zone', r)
# turn / back-walk bits never appear during the window in RUN mode
for sx in range(-128, 128, 6):
    for sy in (-100, -50, 0, 50, 100):
        for yaw in (0.0, 1.0, -2.0, 3.0):
            if not pushed(sx, sy):
                continue
            block(counter=2)
            r = run(sx, sy, *BEHIND, yaw=yaw, ctrl=0x1234527F, prepare_block=None)
            assert (r['ctrl'] & 0xE) == 0, ('turn/back bits leaked', sx, sy, yaw, hex(r['ctrl']))
for cam_y, (eye, target) in cameras.items():
    for name, (sx, sy) in sticks.items():
        for yaw in (0.0, 0.8, -2.3, 3.0):
            block(counter=2)
            r = run(sx, sy, eye, target, yaw=yaw, ctrl=0x1234527F, prepare_block=None)
            window_expect(r, sx, sy, eye, target, yaw, 0x1234527F)
block(window=0)
r = run(0, 100, *BEHIND, prepare_block=None)
assert r['ctrl'] == 0x12345271 and r['counter'] == 1
block(window=30, counter=29, flags=HOLD)
r = run(0, -100, *BEHIND, prepare_block=None)   # DOWN sector: still inside the 30-frame window
assert r['ctrl'] == 0x12345270 and r['yaw'] == f32(0.3)
block(window=30, counter=30, flags=HOLD)
r = run(0, -100, *BEHIND, prepare_block=None)
assert r['ctrl'] == 0x12345271
block(window=30, counter=0, flags=HOLD)
r = run(0, 100, *BEHIND, prepare_block=None)     # up: never waits
assert r['ctrl'] == 0x12345271
for cam_y, (eye, target) in cameras.items():
    for name, (sx, sy) in sticks.items():
        for sub in EXPLORE:
            block(counter=50)
            r = run(sx, sy, eye, target, sub=sub, yaw=1.1, prepare_block=None)
            want, cam = intended(sx, sy, eye, target)
            assert abs(r['yaw'] - want) < 2e-5, (cam_y, name, sub, r['yaw'], want)
            assert abs(r['last'] - cam) < 2e-6 and r['ctrl'] == 0x12345271 and r['prints'] == []
for sign, off in [(-1.0, 0.0), (1.0, math.pi), (-1.0, math.pi)]:
    for name, (sx, sy) in sticks.items():
        block(sign=sign, off=off, counter=50)
        r = run(sx, sy, *BEHIND, prepare_block=None)
        want, cam = intended(sx, sy, *BEHIND, sign=sign, off=off)
        assert abs(r['yaw'] - want) < 2e-5 or abs(abs(r['yaw'] - want) - 2 * math.pi) < 2e-5, (sign, off, name)
for kwargs in (dict(eye=(5.0, 900.0, 5.0), target=(5.0, 100.0, 5.0)),
               dict(eye=(0.0, 300.0, -1000.0), target=(0.0, 100.0, 0.0), camera_null=True)):
    block(counter=50)
    r = run(100, 0, last_yaw=2.5, prepare_block=None, **kwargs)
    assert abs(r['yaw'] - wrap(f32(f32(2.5) - f32(math.atan2(100.0, 0.0))))) < 2e-5

# 4. B pressed in exploration: pending kind and same-frame behaviour.
for sub in EXPLORE:
    for counter in (0, 2, WIN - 1):          # within the window -> kind 1, hold (both modes)
        for flags in (0, HOLD):
            block(counter=counter, flags=flags)
            r = run(0, -100, *BEHIND, sub=sub, ctrl=0x1234527F | CTRL_B, prepare_block=None)
            assert (r['pending'], r['yaw'], r['ctrl']) == (1, f32(0.3), 0x12345270 | CTRL_B), (sub, counter, r)
    for counter in (WIN, 50, 1000):          # held -> kind 2, running conversion
        block(counter=counter)
        r = run(0, -100, *BEHIND, sub=sub, ctrl=0x1234527F | CTRL_B, prepare_block=None)
        want, cam = intended(0, -100, *BEHIND)
        assert r['pending'] == 2 and abs(r['yaw'] - want) < 2e-5 and r['ctrl'] == 0x12345271 | CTRL_B
    for counter in (0, 2):                   # within the window but not DOWN sector -> kind 2 (running jump)
        for sx, sy in ((0, 100), (-100, 0), (100, 0), (-95, -30)):
            block(counter=counter)
            r = run(sx, sy, *BEHIND, sub=sub, ctrl=0x1234527F | CTRL_B, prepare_block=None)
            want, cam = intended(sx, sy, *BEHIND)
            assert r['pending'] == 2 and abs(r['yaw'] - want) < 2e-5 and r['ctrl'] == 0x12345271 | CTRL_B, (sub, counter, sx, sy, r)
    block(counter=50)                         # neutral stick -> kind 0, untouched
    r = run(0, 0, *BEHIND, sub=sub, ctrl=0x12345270 | CTRL_B, prepare_block=None)
    assert (r['pending'], r['yaw'], r['ctrl'], r['counter']) == (0, f32(0.3), 0x12345270 | CTRL_B, 0)
block(counter=2, window=0)
r = run(0, -100, *BEHIND, ctrl=CTRL_B, prepare_block=None)
assert r['pending'] == 2

# 5. Sidestep press in exploration: yaw snaps to the camera yaw, direction bits cleared, B ignored.
for cam_y, (eye, target) in cameras.items():
    for sub in EXPLORE:
        for bits in (CTRL_L, CTRL_R, CTRL_L | CTRL_R, CTRL_L | CTRL_B):
            for sx, sy, counter in ((0, 0, 0), (100, 0, 2), (0, -100, 50)):
                block(counter=counter)
                r = run(sx, sy, eye, target, sub=sub, yaw=1.1, ctrl=0x1234527F | bits, prepare_block=None)
                assert abs(r['yaw'] - cam_yaw(eye, target)) < 2e-6, (cam_y, sub, hex(bits))
                assert r['ctrl'] == (0x12345270 | bits) and r['pending'] == 0
block(counter=3)
r = run(0, 0, *BEHIND, camera_null=True, last_yaw=2.2, ctrl=CTRL_R, prepare_block=None)
assert r['yaw'] == f32(2.2)

# 6. Jump entry (sub 3, phase 0): pending kinds.
for cam_y, (eye, target) in cameras.items():
    cam = cam_yaw(eye, target)
    for name, (sx, sy) in sticks.items():
        for yaw in (0.3, -2.0, 2.9):
            want, _ = intended(sx, sy, eye, target)
            block(pending=1, counter=3)   # camera-frame jump: yaw := camera yaw, bits in the camera frame
            r = run(sx, sy, eye, target, sub=3, phase=0, yaw=yaw, ctrl=0x1234527F, prepare_block=None)
            bits = relative_bits(want, cam)
            assert abs(r['yaw'] - cam) < 2e-6 and r['pending'] == 0
            if bits is not None:
                assert r['ctrl'] == 0x12345270 | bits, (cam_y, name, hex(r['ctrl']), bits)
            block(pending=2, counter=50)  # running jump: yaw := stick direction, forward
            r = run(sx, sy, eye, target, sub=3, phase=0, yaw=yaw, ctrl=0x1234527F, prepare_block=None)
            assert abs(r['yaw'] - want) < 2e-5 and r['ctrl'] == 0x12345271 and r['pending'] == 0
            block(pending=0, counter=50)  # no kind: yaw unchanged, bits relative to the old yaw
            r = run(sx, sy, eye, target, sub=3, phase=0, yaw=yaw, ctrl=0x1234527F, prepare_block=None)
            bits = relative_bits(want, yaw)
            assert r['yaw'] == f32(yaw)
            if bits is not None:
                assert r['ctrl'] == 0x12345270 | bits, (cam_y, name, yaw, hex(r['ctrl']), bits)
# camera-frame jump with the canonical inputs
cam = cam_yaw(*BEHIND)
for name, bits in (('up', 1), ('down', 2), ('left', 8), ('right', 4), ('up_left', 9), ('down_right', 6)):
    block(pending=1)
    r = run(*sticks[name], *BEHIND, sub=3, phase=0, yaw=-1.0, prepare_block=None)
    assert r['ctrl'] == 0x12345270 | bits and abs(r['yaw'] - cam) < 2e-6, (name, hex(r['ctrl']))
for kind in (0, 1, 2):     # neutral stick at entry: vertical jump, yaw per kind
    block(pending=kind)
    r = run(0, 0, *BEHIND, sub=3, phase=0, yaw=-1.0, ctrl=0x1234527F, prepare_block=None)
    assert r['ctrl'] == 0x12345270 and r['yaw'] == (f32(cam) if kind == 1 else f32(-1.0)) and r['pending'] == 0

# 7. Jump air control (phase >= 1): yaw unchanged, bits relative to the player, pending consumed.
for phase in (1, 2, 6, 0xB, 0xE):
    for name, (sx, sy) in sticks.items():
        for yaw in (0.0, 1.0, -2.5):
            for kind in (0, 1, 2):
                block(pending=kind, counter=7)
                r = run(sx, sy, *BEHIND, sub=3, phase=phase, yaw=yaw, ctrl=0x1234527F, prepare_block=None)
                want, _ = intended(sx, sy, *BEHIND)
                bits = relative_bits(want, yaw)
                assert r['yaw'] == f32(yaw) and r['pending'] == 0 and r['counter'] == 8
                if bits is not None:
                    assert r['ctrl'] == 0x12345270 | bits, (phase, name, yaw, hex(r['ctrl']), bits)
    block(pending=1)
    r = run(0, 0, *BEHIND, sub=3, phase=phase, yaw=1.0, ctrl=0x1234527F, prepare_block=None)
    assert r['ctrl'] == 0x12345270 and r['yaw'] == f32(1.0)
# full sweep of stick angles in the jump state: bits are a clean 8-way partition
for sx in range(-128, 128, 8):
    for sy in (-100, -40, 40, 100):
        block(pending=0)
        r = run(sx, sy, *BEHIND, sub=3, phase=1, yaw=0.5, ctrl=0x1234527F, prepare_block=None)
        want, _ = intended(sx, sy, *BEHIND)
        bits = relative_bits(want, 0.5)
        if bits is not None:
            assert r['ctrl'] == 0x12345270 | bits, (sx, sy, hex(r['ctrl']), bits)
        assert (r['ctrl'] & 3) != 3 and (r['ctrl'] & 0xC) != 0xC

# 8. Toggle frames.
r = run(0, 100, *BEHIND, buttons=L | R | Z, pressed=Z)
assert r['flags'] == 1 and r['ctrl'] == 0 and r['yaw'] == f32(0.3) and r['prints'] == [] and r['counter'] == 0
block(flags=1, counter=4, pending=1)
r = run(0, 100, *BEHIND, buttons=L | R | Z, pressed=Z, prepare_block=None)
assert r['flags'] == 0 and r['ctrl'] == 0 and r['prints'] == [] and (r['counter'], r['pending']) == (4, 1)
for buttons, pressed in [(L | Z, Z), (R | Z, Z), (L | R | Z, 0), (Z, Z), (L | R | Z, A)]:
    block(counter=50)
    r = run(0, 100, *BEHIND, buttons=buttons, pressed=pressed, prepare_block=None)
    assert r['flags'] == 0 and r['ctrl'] == 0x12345271 and r['prints'] == [], (buttons, pressed)

# 9. Tuning mode: D-pad steps, A/B window, X reset, pad bits cleared, three text lines, counter frozen.
for pressed in (DU, DD, DR, DL, X, A, B, Y, A | B, DU | A, X | A, X | B, Y | A, DL | DR | DU | DD | A | B | Y, 0):
    for sens in (0.0024, 0.0006, 0.0002, 0.05, 0.01):
        for window in (0, 1, 6, 29, 30):
            for mode in (0, HOLD):
                block(flags=1 | mode, sens=sens, window=window, counter=9, pending=2)
                r = run(70, 70, *BEHIND, prepare_block=None, pressed=pressed, buttons=pressed | DU, released=DL | Z | A | Y)
                assert abs(r['sens'] - expected_steps(sens, pressed)) < 1e-9, (pressed, sens, r['sens'])
                assert r['window'] == expected_window(window, pressed), (pressed, window, r['window'])
                want_mode = mode   # v0.20: Y no longer toggles the hold flag
                assert r['ctrl'] == 0 and r['yaw'] == f32(0.3) and r['flags'] == 1 | want_mode, (pressed, mode, r['flags'])
                assert (r['counter'], r['pending']) == (9, 2)
                assert int.from_bytes(r['pad'][0x10:0x14], 'big') == ((pressed | DU | sector_bits(70, 70)) & ~0xB0F)
                assert int.from_bytes(r['pad'][0x14:0x18], 'big') == (pressed & ~0xB0F)
                assert int.from_bytes(r['pad'][0x18:0x1C], 'big') == Z
                check_prints(r, r['sens'], r['window'], 1, hold=bool(want_mode))
block(flags=1)
for _ in range(40):
    r = run(0, 0, *BEHIND, prepare_block=None, pressed=A)
assert r['window'] == JUMP['window_max']
for _ in range(40):
    r = run(0, 0, *BEHIND, prepare_block=None, pressed=B)
assert r['window'] == 0
r = run(0, 0, *BEHIND, prepare_block=None, pressed=X)
assert r['window'] == WIN and r['sens'] == f32(DEF['camera_sensitivity'])
for page in (0x1B, 0, 5):
    block(flags=1)
    r = run(0, 0, *BEHIND, prepare_block=None, page=page, pressed=DU | A)
    check_prints(r, r['sens'], r['window'], page)
block(flags=1 | HOLD)
r = run(0, 0, *BEHIND, prepare_block=None, pressed=Y)   # v0.20: Y does nothing to the flags (a stale hold bit stays as it is)
assert r['flags'] == 1 | HOLD
check_prints(r, r['sens'], r['window'], 1)
r = run(0, 0, *BEHIND, prepare_block=None, pressed=Y)
assert r['flags'] == 1 | HOLD
check_prints(r, r['sens'], r['window'], 1)
block(flags=1)
r = run(0, 100, *BEHIND, buttons=L | R | Z, pressed=Z, prepare_block=None)
assert r['flags'] == 0 and r['ctrl'] == 0 and r['prints'] == []

# 10. C-stick exclusivity and follow flag (unchanged from v0.6).
r = run(0, 0, *BEHIND, subx=50, suby=0, pressed=CL | CR | CD | CU | Z | DU)
assert int.from_bytes(r['pad'][0x14:0x18], 'big') == Z | DU
r = run(0, 0, *BEHIND, subx=0, suby=50, pressed=CL | CR | CD | CU | A)
assert int.from_bytes(r['pad'][0x14:0x18], 'big') == CD | CU | A
r = run(0, 0, *BEHIND, subx=-128, suby=127, pressed=CD)
assert int.from_bytes(r['pad'][0x14:0x18], 'big') == 0
block(flags=2)
r = run(0, 0, *BEHIND, sub=1, prepare_block=None)
assert r['flags'] == 0
r = run(0, 0, *BEHIND, sub=8)
assert r['flags'] == (LOCK | 8 | PACED)
block(flags=1)
r = run(0, 0, *BEHIND, sub=8, prepare_block=None)
assert r['flags'] == (1 | LOCK) and r['ctrl'] == 0

# 11. Frame sequences: idle -> stick down + B within the window -> jump entry (back jump toward the camera),
#     and stick held -> B -> running jump.
for mode in (0, HOLD):
    block(flags=mode)
    for frame in range(3):
        r = run(0, -100, *BEHIND, sub=0, yaw=0.0, ctrl=0x1234527F | (CTRL_B if frame == 2 else 0), prepare_block=None)
        assert r['yaw'] == f32(0.0)
        assert (r['ctrl'] & 0xF) == 0, (mode, frame, hex(r['ctrl']))   # no back-walk in either mode
    assert r['pending'] == 1 and r['counter'] == 3
    r = run(0, -100, *BEHIND, sub=3, phase=0, yaw=0.0, ctrl=0x1234527F, prepare_block=None)
    assert r['ctrl'] == 0x12345272 and abs(r['yaw'] - cam_yaw(*BEHIND)) < 2e-6 and r['pending'] == 0   # DOWN -> back jump
block()
yaw = 0.0
for frame in range(WIN + 5):
    r = run(0, -100, *BEHIND, sub=0 if frame < 2 else 1, yaw=yaw, ctrl=0x1234527F, prepare_block=None)
    yaw = r['yaw']
want, _ = intended(0, -100, *BEHIND)
assert abs(yaw - want) < 2e-5 and r['ctrl'] == 0x12345271
r = run(0, -100, *BEHIND, sub=1, yaw=yaw, ctrl=0x1234527F | CTRL_B, prepare_block=None)
assert r['pending'] == 2
r = run(0, -100, *BEHIND, sub=3, phase=0, yaw=r['yaw'], ctrl=0x1234527F, prepare_block=None)
assert r['ctrl'] == 0x12345271 and abs(r['yaw'] - want) < 2e-5    # UP -> forward jump toward the camera

# 12. All stick values in exploration (held) remain finite and wrapped.
for sx in range(-128, 128):
    for sy in (-100, 100):
        block(counter=50)
        r = run(sx, sy, *BEHIND, prepare_block=None)
        assert -math.pi - 1e-5 <= r['yaw'] <= math.pi + 1e-5 and r['ctrl'] == 0x12345271

# 13. Z quick turn direction from the C-stick (first frame of sub-state 8).
for x in (-128, -100, -41, -40, -39, -10, 0, 10, 39, 40, 41, 100, 127):
    for buttons in (0, 0x12345278, 0x30000 | Z, sector_bits(-100, 0) | 0x8):
        for suby in (0, 100, -100):
            r = run(0, 0, *BEHIND, sub=8, phase=0, yaw=-1.0, subx=x, suby=suby, buttons=buttons)
            want = (buttons & ~0x30000) | (0x10000 if x < -TURN_T else 0x20000 if x > TURN_T else 0)
            assert int.from_bytes(r['pad'][0x10:0x14], 'big') == want, (x, hex(buttons), hex(int.from_bytes(r['pad'][0x10:0x14], 'big')))
            assert r['yaw'] == f32(-1.0) and r['ctrl'] == 0x12345270 and not (r['flags'] & 2) and (r['flags'] & 8) and (r['flags'] & PACED) and r['step'] == 0.0
            assert r['tstate'] == 1 and r['tentry'] == f32(-1.0) and r['tdelta'] == (QUARTER if x < -TURN_T else f32(-QUARTER) if x > TURN_T else f32(math.pi))
    for phase in (1, 2):   # later frames of the turn: untouched
        r = run(0, 0, *BEHIND, sub=8, phase=phase, yaw=-1.0, subx=x, buttons=0x12345278)
        assert int.from_bytes(r['pad'][0x10:0x14], 'big') == 0x12345278
    for sub in EXPLORE + (2, 3, 4):   # other states: the buttons word is never rewritten
        r = run(0, 0, *BEHIND, sub=sub, subx=x, buttons=0x12345278)
        assert int.from_bytes(r['pad'][0x10:0x14], 'big') == 0x12345278
# the movement stick held left/right during the turn's first frame no longer selects the 90-degree motion
for sx, sy in ((-100, 0), (100, 0), (-70, 70), (70, -70)):
    r = run(sx, sy, *BEHIND, sub=8, phase=0, yaw=0.5, subx=0)
    assert int.from_bytes(r['pad'][0x10:0x14], 'big') == (sector_bits(sx, sy) & ~0x30000)
    r = run(sx, sy, *BEHIND, sub=8, phase=0, yaw=0.5, subx=-100)
    assert int.from_bytes(r['pad'][0x10:0x14], 'big') == (sector_bits(sx, sy) & ~0x30000) | 0x10000

# 14. X lock-on camera.
CTRL_X = 0x400
TARGET, MODEL = 0x81400000, 0x81410000


def place_target(pos, hp=100, model=True, index=0, actor_pos=(1.0, 2.0, 3.0)):
    """Mock enemy: actor at TARGET (+0xC0 pos, +0x4D4 hp, +0xF0 model, +0x125 aim index); model chain via +0xF0."""
    machine.mem_write(TARGET, bytes(0x600))
    machine.mem_write(MODEL, bytes(0x2000))
    for k, v in enumerate(actor_pos):
        wf(TARGET + 0xC0 + 4 * k, v)
    ww(TARGET + 0x4D4, hp & 0xFFFFFFFF)
    wb(TARGET + 0x125, index)
    if model:
        ww(TARGET + 0xF0, MODEL)
        node = MODEL
        for i in range(index):
            ww(node + 0xF0, MODEL + 0x400 * (i + 1))
            node = MODEL + 0x400 * (i + 1)
        for k, v in enumerate(pos):
            wf(node + 0x108 + 4 * k, v)
    else:
        ww(TARGET + 0xF0, 0)


for sub in EXPLORE + (2, 3, 4, 8):
    r = run(0, 0, *BEHIND, sub=sub, ctrl=0x1234527F | CTRL_X, targets=0)          # X, no targets -> camera reset
    assert (r['follow'], r['focus']) == (1, 0) and not (r['flags'] & 2), (sub, r)
    r = run(0, 0, *BEHIND, sub=sub, ctrl=0x1234527F | CTRL_X, targets=3)          # X, targets -> focus next frame
    assert (r['follow'], r['focus']) == (0, 1), (sub, r)
    r = run(0, 0, *BEHIND, sub=sub, ctrl=0x1234527F, targets=3)                   # no X -> nothing
    assert (r['follow'], r['focus']) == (0, 0)
r = run(0, 0, *BEHIND, category=2, ctrl=0x1234527F | CTRL_X, targets=0)            # other categories ignore X
assert (r['follow'], r['focus']) == (0, 0)
block(flags=1)
r = run(0, 0, *BEHIND, prepare_block=None, pressed=X, targets=0)                    # tuning mode: X is the reset key
assert (r['follow'], r['focus']) == (0, 0)
# pending focus: yaw request toward the target's aim point, with the real accessor
for index in (0, 1, 3):
    for pos, ppos in (((100.0, 0.0, 0.0), (0.0, 0.0, 0.0)), ((-50.0, 10.0, 50.0), (10.0, 0.0, -10.0)), ((0.0, 0.0, -300.0), (0.0, 5.0, 0.0))):
        place_target(pos, index=index)
        block(focus=1)
        r = run(0, 0, *BEHIND, prepare_block=None, lock_target=TARGET, targets=2)   # run() zeroes the player position
        want = f32(math.atan2(pos[0] - 0.0, pos[2] - 0.0))
        assert (r['flags'] & 8) and abs(r['request'] - want) < 2e-5 and r['focus'] == 0 and r['follow'] == 0, (index, pos, r['request'], want)
place_target((30.0, 0.0, 40.0), model=False, actor_pos=(-40.0, 0.0, 40.0))       # no model: actor position fallback
block(focus=1)
r = run(0, 0, *BEHIND, prepare_block=None, lock_target=TARGET, targets=1)
assert (r['flags'] & 8) and abs(r['request'] - f32(math.atan2(-40.0, 40.0))) < 2e-5
place_target((30.0, 0.0, 40.0), hp=0)                                                # dead target: camera reset instead
block(focus=1)
r = run(0, 0, *BEHIND, prepare_block=None, lock_target=TARGET, targets=1)
assert not (r['flags'] & 8) and r['follow'] == 1 and r['focus'] == 0
block(focus=1)
r = run(0, 0, *BEHIND, prepare_block=None, lock_target=0, targets=0)                # null target: camera reset
assert not (r['flags'] & 8) and r['follow'] == 1
place_target((100.0, 0.0, 0.0))
block(focus=1)
r = run(0, 0, *BEHIND, prepare_block=None, category=0, lock_target=TARGET, targets=1)   # not category 1: pending dropped
assert not (r['flags'] & 8) and r['follow'] == 0 and r['focus'] == 0
# follow frames count down and set bit1
block(follow=2)
r = run(0, 0, *BEHIND, sub=1, prepare_block=None)
assert (r['flags'] & 2) and r['follow'] == 1
r = run(0, 0, *BEHIND, sub=1, prepare_block=None)
assert (r['flags'] & 2) and r['follow'] == 0
r = run(0, 0, *BEHIND, sub=1, prepare_block=None)
assert not (r['flags'] & 2) and r['follow'] == 0
# X press and pending focus in the same frame (X pressed twice in a row): focus computed, then a new pending
place_target((0.0, 0.0, 100.0))
block(focus=1)
r = run(0, 100, *BEHIND, prepare_block=None, ctrl=0x1234527F | CTRL_X, lock_target=TARGET, targets=2)
assert (r['flags'] & 8) and abs(r['request'] - f32(math.atan2(0.0, 100.0))) < 2e-5 and r['focus'] == 1

# 10. v0.15: outside the exploration states the L/R bits are swapped when Vanessa faces the camera
#     (|wrap(facing - camera yaw)| > 90 deg): 0x20000 <-> 0x10000 and 0x8000 <-> 0x4000. Her yaw is untouched,
#     nothing happens without the 0x30000 bits, and the exploration states keep the v0.7 snap (section 5).
def swap_lr(ctrl):
    return (ctrl & ~0x3C000) | ((ctrl & 0x20000) >> 1) | ((ctrl & 0x10000) << 1) | ((ctrl & 0x8000) >> 1) | ((ctrl & 0x4000) << 1)
assert swap_lr(CTRL_L) == CTRL_R and swap_lr(CTRL_R) == CTRL_L and swap_lr(0x12345270) == (0x12345270 & ~0x4000) | 0x8000
SWAP_STATES = (2, 3, 4, 5, 6, 7, 8, 9, 0xA, 0xD)
swap_cases = 0
for cam_y, (eye, target) in cameras.items():
    cam = cam_yaw(eye, target)
    for sub in SWAP_STATES:
        for rel, swapped in ((0.0, False), (deg(80), False), (deg(-80), False), (deg(100), True), (deg(-100), True), (math.pi, True), (deg(-179), True)):
            yaw = wrap(cam + rel)
            for base in (0x12345270, 0x12345270 & ~0x4000):
                for bits in (CTRL_L, CTRL_R, CTRL_L | CTRL_R):
                    ctrl = base | bits
                    r = run(0, 0, eye, target, sub=sub, yaw=yaw, ctrl=ctrl)
                    want = swap_lr(ctrl) if swapped else ctrl
                    if sub == 3:
                        want &= ~0xF
                    assert r['ctrl'] == want, (cam_y, sub, rel, hex(ctrl), hex(r['ctrl']), hex(want))
                    assert r['yaw'] == f32(yaw), (cam_y, sub, rel, r['yaw'], yaw)
                    swap_cases += 1
                r = run(0, 0, eye, target, sub=sub, yaw=yaw, ctrl=base)   # no sidestep bits: untouched
                assert r['ctrl'] == (base & ~0xF if sub == 3 else base) and r['yaw'] == f32(yaw)
                swap_cases += 1
# the facing used is the camera yaw of this frame; with the camera struct missing the last known yaw is used
for last, swapped in ((2.2, True), (0.3, False), (math.pi, True), (-math.pi, True), (deg(100), True), (deg(85), False)):
    r = run(0, 0, *BEHIND, camera_null=True, last_yaw=last, sub=4, yaw=0.0, ctrl=0x12345270 | CTRL_L)
    assert r['ctrl'] == (swap_lr(0x12345270 | CTRL_L) if swapped else 0x12345270 | CTRL_L) and r['yaw'] == 0.0, (last, hex(r['ctrl']))
    swap_cases += 1
# the swap and the shooting-state phases: every phase of sub-state 4 gets the same word (the game reads it in phase 4)
for phase in range(5):
    r = run(0, 0, *BEHIND, sub=4, phase=phase, yaw=math.pi, ctrl=0x12345270 | CTRL_R)
    assert r['ctrl'] == swap_lr(0x12345270 | CTRL_R) and r['yaw'] == f32(math.pi)
    swap_cases += 1
# category != 1 (e.g. damage / cut-scene): nothing is touched
for cat in (0, 2, 3):
    r = run(0, 0, *BEHIND, category=cat, sub=4, yaw=math.pi, ctrl=0x12345270 | CTRL_L)
    assert r['ctrl'] == 0x12345270 | CTRL_L and r['yaw'] == f32(math.pi)
    swap_cases += 1
print('v0.15 sidestep swap cases:', swap_cases)

# 11. v0.16: crouch (sub 5, Y held = 0x40000). The stick becomes exactly one crouch action relative to her facing:
#     forward step (UP) within crouch_sector of the facing, back step (DOWN) beyond 180 - crouch_sector, otherwise the
#     L / R trigger bits (crouch sidestep) by side. Raw RC bits are cleared, her yaw is untouched, a trigger edge in the
#     same frame wins (v0.15 rule), and with Y released the exploration rules apply.
CROUCH_Y = 0x40000
CSEC = rf(WORDS['crouch_sector'])
assert abs(CSEC - math.radians(45)) < 1e-6
NOY = 0x12345270 & ~CROUCH_Y


def crouch_bits(rel):
    a = abs(rel)
    if a < CSEC:
        return 0x1
    if a > math.pi - CSEC:
        return 0x2
    return CTRL_L if rel >= 0 else CTRL_R


crouch_cases = 0
for cam_y, (eye, target) in cameras.items():
    for name, (sx, sy) in sticks.items():
        want, _ = intended(sx, sy, eye, target)
        for yaw in (0.3, -2.0, 2.9, 1.1, -1.1):
            rel = wrap(want - yaw)
            for base in (0x12345270, 0x1234527F, 0x12345270 & ~0x4000):
                ctrl = base | CROUCH_Y
                for phase in (0, 2):
                    block(counter=50)
                    r = run(sx, sy, eye, target, sub=5, phase=phase, yaw=yaw, ctrl=ctrl, prepare_block=None)
                    exp = (ctrl & ~0xF & ~0x3C000) | crouch_bits(rel)
                    assert r['ctrl'] == exp, (cam_y, name, yaw, phase, hex(ctrl), hex(r['ctrl']), hex(exp), math.degrees(rel))
                    assert r['yaw'] == f32(yaw) and r['pending'] == 0
                    crouch_cases += 1
# sector boundaries (stick up with the camera behind: intended = 0, so rel = -yaw) and diagonals
for rel_deg in (0, 10, -10, 44, -44, 46, -46, 89, -89, 90, -90, 91, -91, 134, -134, 136, -136, 170, -170, 180):
    rel = math.radians(rel_deg)
    yaw = wrap(-rel)
    r = run(0, 100, *BEHIND, sub=5, phase=2, yaw=yaw, ctrl=0x1234527F | CROUCH_Y)
    exp = ((0x12345270 | CROUCH_Y) & ~0x3C000) | crouch_bits(rel)
    assert r['ctrl'] == exp, (rel_deg, hex(r['ctrl']), hex(exp))
    crouch_cases += 1
for name in ('up_right', 'up_left', 'down_right', 'down_left'):   # diagonals: one action, decided by the 45-degree sectors
    sx, sy = sticks[name]
    want, _ = intended(sx, sy, *BEHIND)
    for yaw_deg in (10, 30, -30, 60, -60, 120, -120, 170):   # no exact 45 / 135 degree ties (those are f32 rounding coin flips)
        yaw = math.radians(yaw_deg)
        r = run(sx, sy, *BEHIND, sub=5, phase=2, yaw=yaw, ctrl=0x1234527F | CROUCH_Y)
        exp = ((0x12345270 | CROUCH_Y) & ~0x3C000) | crouch_bits(wrap(want - yaw))
        assert r['ctrl'] == exp, (name, yaw_deg, hex(r['ctrl']), hex(exp))
        assert not ((exp & 0x3) and (exp & 0x3C000)) and (exp & 0x3) != 0x3
        crouch_cases += 1
# stick idle or inside the dead zone: the raw direction bits are cleared, nothing else happens
for sx, sy in ((0, 0), (20, 20), (29, 0)):
    r = run(sx, sy, *BEHIND, sub=5, phase=2, yaw=2.0, ctrl=0x1234527F | CROUCH_Y)
    assert r['ctrl'] == (0x12345270 | CROUCH_Y) and r['yaw'] == f32(2.0)
    crouch_cases += 1
# a trigger edge in the same frame wins and follows the v0.15 rule (raw bits left alone)
for yaw, swapped in ((0.0, False), (math.pi, True)):
    for bits in (CTRL_L, CTRL_R):
        ctrl = 0x1234527F | CROUCH_Y | bits
        r = run(100, 0, *BEHIND, sub=5, phase=2, yaw=yaw, ctrl=ctrl)
        assert r['ctrl'] == (swap_lr(ctrl) if swapped else ctrl) and r['yaw'] == f32(yaw)
        crouch_cases += 1
# Y released in sub-state 5 (standing up): exploration rules (run conversion past the window, sidestep snap)
block(counter=50)
r = run(100, 0, *BEHIND, sub=5, phase=4, yaw=0.3, ctrl=NOY | 0xF, prepare_block=None)
want, _ = intended(100, 0, *BEHIND)
assert abs(r['yaw'] - want) < 2e-5 and r['ctrl'] == NOY | 1, (r['yaw'], hex(r['ctrl']))
block(counter=3)
r = run(0, 0, *BEHIND, sub=5, phase=4, yaw=1.1, ctrl=NOY | 0xF | CTRL_R, prepare_block=None)
assert abs(r['yaw'] - cam_yaw(*BEHIND)) < 2e-6 and r['ctrl'] == NOY | CTRL_R
crouch_cases += 2
# other states are unchanged by the crouch rule: sub-states 0xD (crouch step), 4 and 2 keep the raw stick bits
for sub in (0xD, 4, 2):
    r = run(100, 0, *BEHIND, sub=sub, yaw=0.3, ctrl=0x1234527F | CROUCH_Y)
    assert r['ctrl'] == (0x1234527F | CROUCH_Y) and r['yaw'] == f32(0.3)
    crouch_cases += 1
print('v0.16 crouch cases:', crouch_cases)

# 12. US debug records are flagged visible: with five fake records queued, the last three get +0xA = 1 after the
#     tuning-mode prints; JP leaves the queue alone. DebugPrintf itself is stubbed, so the queue holds only the fakes.
QUEUE = REG.debug_queue
FAKES = [0x80700000 + 0x40 * i for i in range(5)]
machine.mem_write(QUEUE, b''.join(a.to_bytes(4, 'big') for a in FAKES) + bytes(4))
for a in FAKES:
    machine.mem_write(a, bytes(0x40))
block(flags=1)
r = run(0, 0, *BEHIND, prepare_block=None)
assert len(r['prints']) == 3
flags = [bytes(machine.mem_read(a + 0xA, 1))[0] for a in FAKES]
assert flags == ([0, 0, 1, 1, 1] if TEXT.get('flags_records_visible') else [0, 0, 0, 0, 0]), flags
cws = [bytes(machine.mem_read(a + 0x8, 1))[0] for a in FAKES]
assert cws == ([0, 0, 16, 16, 16] if TEXT.get('flags_records_visible') else [0] * 5), cws
assert bytes(machine.mem_read(QUEUE, 24)) == b''.join(a.to_bytes(4, 'big') for a in FAKES) + bytes(4)   # queue itself untouched
machine.mem_write(QUEUE, bytes(24))
# only two entries queued: both flagged, nothing written below the queue start
machine.mem_write(QUEUE, b''.join(a.to_bytes(4, 'big') for a in FAKES[:2]) + bytes(4))
for a in FAKES:
    machine.mem_write(a, bytes(0x40))
block(flags=1)
r = run(0, 0, *BEHIND, prepare_block=None)
flags = [bytes(machine.mem_read(a + 0xA, 1))[0] for a in FAKES]
assert flags == ([1, 1, 0, 0, 0] if TEXT.get('flags_records_visible') else [0] * 5), flags
machine.mem_write(QUEUE, bytes(24))
print('debug record visibility cases ok')

# 15. v0.19: the Z quick turn sends the camera request on its first frame (bit3 | bit5, step 0); the lock covers the
#     turn and two frames after it, and the end-of-turn follow fires when the lock runs out.
turn_cases = 0
for h0 in (0.0, 1.0, -2.5, 3.0, -3.1):
    for spin, delta_kind, subx in ((-0.2, 'pi', 0), (0.2, 'pi', 0), (-0.21, 'left', -100), (0.21, 'left', -100), (-0.19, 'right', 100), (0.19, 'right', 100)):
        delta = {'pi': f32(math.pi), 'left': QUARTER, 'right': f32(-QUARTER)}[delta_kind]
        want = wrap(f32(f32(h0) + delta))
        block()
        r = run(0, 0, *BEHIND, sub=8, phase=0, yaw=h0, subx=subx, prepare_block=None)            # entry frame: request at once
        assert r['tstate'] == 1 and r['tentry'] == f32(h0) and r['tdelta'] == delta and (r['flags'] & 8) and (r['flags'] & PACED) and (r['flags'] & LOCK) and not (r['flags'] & 2)
        assert abs(r['request'] - want) < 1e-6 and r['step'] == 0.0 and r['follow'] == 0
        ww(CONFIG + 28, rw(CONFIG + 28) & ~(8 | PACED))                                            # the camera consumed the request
        for k in range(1, 9):                                                                      # the rest of the turn: nothing more is sent, lock on
            r = run(0, 0, *BEHIND, sub=8, phase=1, yaw=wrap(f32(h0 + spin * k)), prepare_block=None, turn='keep')
            assert r['tstate'] == 1 and abs(r['request'] - want) < 1e-6 and r['step'] == 0.0 and r['follow'] == 0 and (r['flags'] & LOCK) and not (r['flags'] & 8)
        r = run(0, 0, *BEHIND, sub=0, yaw=wrap(f32(h0 + delta)), prepare_block=None, turn='keep')  # turn over: lock stays, no follow yet
        assert r['tstate'] == 1 and r['follow'] == 0 and (r['flags'] & LOCK) and rw(WORDS['stick_block']) == STICK_BLOCK - 1
        for _ in range(STICK_BLOCK - 2):
            r = run(0, 0, *BEHIND, sub=0, yaw=wrap(f32(h0 + delta)), prepare_block=None, turn='keep')
            assert (r['flags'] & LOCK) and r['follow'] == 0
        r = run(0, 0, *BEHIND, sub=0, yaw=wrap(f32(h0 + delta)), prepare_block=None, turn='keep')  # lock runs out: one follow frame requested
        assert r['tstate'] == 0 and r['follow'] == 1 and (r['flags'] & LOCK) and rw(WORDS['stick_block']) == 0
        r = run(0, 0, *BEHIND, sub=0, yaw=wrap(f32(h0 + delta)), prepare_block=None, turn='keep')  # ... delivered: bit1, lock off
        assert r['tstate'] == 0 and r['follow'] == 0 and (r['flags'] & 2) and not (r['flags'] & LOCK)
        turn_cases += 1
# an interrupted turn (state leaves on the next frame): the request was already sent; the follow still comes when the lock runs out
block()
r = run(0, 0, *BEHIND, sub=8, phase=0, yaw=0.7, prepare_block=None)
assert (r['flags'] & 8) and (r['flags'] & PACED) and abs(r['request'] - wrap(f32(0.7 + math.pi))) < 1e-6
for _ in range(STICK_BLOCK):
    r = run(0, 0, *BEHIND, sub=2, yaw=0.7, prepare_block=None, turn='keep')
assert r['tstate'] == 0 and r['follow'] == 1
# other states never touch the turn words; a stale turn_state outside the turn is cleared with one follow frame
for sub in EXPLORE + (2, 3, 4, 5):
    block()
    r = run(0, 0, *BEHIND, sub=sub, yaw=0.4, prepare_block=None, turn=(1, 0.3, 3.14))
    assert r['tstate'] == 0 and r['follow'] == 1 and not (r['flags'] & 8)
    r = run(0, 0, *BEHIND, sub=sub, yaw=0.4, prepare_block=None, turn=(0, 0.3, 3.14))
    assert r['tstate'] == 0 and r['tentry'] == f32(0.3) and r['follow'] == 0
    turn_cases += 1
# the X lock-on request resets the camera step to the default (0) and does not raise bit5
place_target((100.0, 0.0, 0.0))
block(focus=1, step=0.25)
r = run(0, 0, *BEHIND, prepare_block=None, lock_target=TARGET, targets=2)
assert (r['flags'] & 8) and not (r['flags'] & PACED) and r['step'] == 0.0
# a fresh block and the v2 -> v3 upgrade start with a zero camera step
block(step=0.5, version=2)
r = run(0, 0, *BEHIND, prepare_block=None)
assert r['step'] == 0.0
turn_cases += 2
# the lock bit is raised on every turn frame (entry included), survives nothing else, and a stale countdown runs out
for sub in (8,):
    for phase in (0, 1, 2):
        r = run(0, 0, *BEHIND, sub=sub, phase=phase, yaw=0.2)
        assert (r['flags'] & LOCK) and rw(WORDS['stick_block']) == STICK_BLOCK
for sub in EXPLORE + (2, 3, 4, 5):
    r = run(0, 0, *BEHIND, sub=sub, yaw=0.2, turn=(0, 0.0, 0.0, 2))
    assert (r['flags'] & LOCK) and rw(WORDS['stick_block']) == 1
    r = run(0, 0, *BEHIND, sub=sub, yaw=0.2, turn='keep')
    assert (r['flags'] & LOCK) and rw(WORDS['stick_block']) == 0
    r = run(0, 0, *BEHIND, sub=sub, yaw=0.2, turn='keep')
    assert not (r['flags'] & LOCK)
    turn_cases += 1
# a block whose stale lock bit is set gets it cleared when nothing holds it
block(flags=LOCK | 4)
r = run(0, 0, *BEHIND, sub=1, prepare_block=None)
assert r['flags'] == 4
turn_cases += 1
print('v0.19 turn request cases:', turn_cases)

result = {'passed_cases': checks, 'engine': 'Unicorn 2.1.4, PPC32 big endian',
          'real_dol_math': 'atan2f at 0x800DEDB0 and its callees',
          'stubbed': 'DebugPrintf 0x80080178 and SetDebugPage 0x80080164',
          'loaded_at': hex(CODE), 'delivery_words_checked': True,
          'paired_single_instructions_skipped': len(skipped), 'sidestep_swap_cases': swap_cases, 'crouch_cases': crouch_cases, 'turn_request_cases': turn_cases, 'full_hook_test_in_dolphin_required': True}
(build / 'unit-test-results.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
