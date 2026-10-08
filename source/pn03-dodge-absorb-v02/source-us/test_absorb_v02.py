"""Run the Dodge Absorb v0.2 bodies in Unicorn: v0.1's checks plus the orb pickup effect / sound
on absorb (effect record lookup, owner, generator create with the 9th argument on our own
stack frame, two sounds, once per frame), and an end-to-end pass on the sprint savestate RAM
image with the real effect system (a new generator must appear, attached to the player)."""
import sys, struct, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
from regions import R as REG
import unicorn as u
import unicorn.ppc_const as p
import dol

build = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / ('absorb-v02-build' + REG.suffix)
m = json.loads((build / 'manifest.json').read_text())
CODE = m['region']
HOOK0, RESUME0, HOOK_A, HOOK_B = m['hook0'], m['resume0'], m['hook_a'], m['hook_b']
A_DAMAGE, A_SKIP, B_CONT = m['a_damage'], m['a_skip'], m['b_cont']
HUD, HUD_STRUCT = m['hud_up'], m['hud_struct']
EST_GET, EST_OWNER, ESP_CREATE, SE_PLAY = m['est_get'], m['est_owner'], m['esp_create'], m['se_play']
PRM, DEF = m['params'], m['defaults']
X = DEF['energy_per_hit']
SENTINEL = 0x80004000
CALLER_B = 0x80004100
R13 = REG.r13
ROOT = 0x80600000          # fake root (clear of both regions' patch areas)
SP = 0x817f0000
PLAYER = 0x80D2D020
OTHER = 0x80D40000
FAKE_RECORD = 0x80770000
FAKE_OWNER = 0x80520120
FAKE_GEN = 0x80DB4220

machine = u.Uc(u.UC_ARCH_PPC, u.UC_MODE_32 | u.UC_MODE_BIG_ENDIAN)
machine.mem_map(0x80000000, 0x1800000)
for f, a, n in dol.sections:
    machine.mem_write(a, dol.data[f:f + n])
code = (build / 'absorb.bin').read_bytes()

# --- static checks ---
assert code[m['body0_bytes'] - 8:m['body0_bytes'] - 4] == m['orig0'].to_bytes(4, 'big')
patch = (build / 'patch.txt').read_text().splitlines()
HOOKS = [(HOOK0, m['orig0'], CODE), (HOOK_A, m['orig_a'], m['stub_a']), (HOOK_B, m['orig_b'], m['stub_b'])]
if 'hurtbox_hook' in m:
    HOOKS.append((m['hurtbox_hook'], m['hurtbox_orig'], m['hurtbox_stub']))
assert len(patch) == len(code) // 4 + len(HOOKS)
for o in range(0, len(code), 4):
    assert patch[o // 4] == f'0x{CODE + o:08X}:dword:0x{int.from_bytes(code[o:o + 4], "big"):08X}:0x00000000'
for hook, orig, target in HOOKS:
    assert int.from_bytes(dol.read(hook, 4), 'big') == orig
    w = m['hook_words'][hex(hook)]
    d = w & 0x03FFFFFC
    d = d - 0x04000000 if d & 0x02000000 else d
    assert w >> 26 == 18 and hook + d == target
    assert f'0x{hook:08X}:dword:0x{w:08X}:0x{orig:08X}' in patch
assert CODE + m['params_offset'] + 0x60 <= m['region_end'] <= REG.a(0x8018D000)
trail = (Path(__file__).parent / ('trail-v03-build' + REG.suffix) / 'trail.bin').read_bytes()
assert trail[-12:-8] == bytes.fromhex('3d208017') and trail[-8:-4] == bytes.fromhex('c1bf00d0')
td = int.from_bytes(trail[-4:], 'big') & 0x03FFFFFC
td = td - 0x04000000 if td & 0x02000000 else td
assert json.loads((Path(__file__).parent / ('trail-v03-build' + REG.suffix) / 'manifest.json').read_text())['region'] + len(trail) - 4 + td == HOOK0

machine.mem_write(CODE, code)
for hook, _, _ in HOOKS:
    machine.mem_write(hook, m['hook_words'][hex(hook)].to_bytes(4, 'big'))
# stubs for the game functions the absorb routine calls (the HUD update stays real)
RET = bytes.fromhex('4e800020')
machine.mem_write(EST_GET, bytes.fromhex('3c608077') + bytes.fromhex('60630000') + RET)      # lis r3,0x8077; ori r3,r3,0  -> FAKE_RECORD
machine.mem_write(EST_OWNER, bytes.fromhex('3c608052') + bytes.fromhex('60630120') + RET)    # -> FAKE_OWNER
machine.mem_write(ESP_CREATE, bytes.fromhex('3c6080db') + bytes.fromhex('60634220') + RET)   # -> FAKE_GEN
machine.mem_write(SE_PLAY, bytes.fromhex('38600000') + RET)
machine.reg_write(p.UC_PPC_REG_MSR, 0x2000)
calls = []


def on_code(uc, address, size, user):
    r = lambda n: uc.reg_read(p.UC_PPC_REG_0 + n)
    if address == HUD:
        calls.append(('hud', r(3)))
    elif address == EST_GET:
        calls.append(('est', r(3), r(4)))
    elif address == EST_OWNER:
        calls.append(('owner', r(3)))
    elif address == ESP_CREATE:
        sp = r(1)
        calls.append(('create', r(3), r(4), r(5), r(6), r(7), r(8), r(9), r(10), int.from_bytes(uc.mem_read(sp + 8, 4), 'big'), sp))
    elif address == SE_PLAY:
        calls.append(('se', r(3), r(4), r(5), r(6)))


machine.hook_add(u.UC_HOOK_CODE, on_code, begin=0x80000000, end=0x81800000)


def ww(a, n): machine.mem_write(a, (n & 0xFFFFFFFF).to_bytes(4, 'big'))
def wh(a, n): machine.mem_write(a, (n & 0xFFFF).to_bytes(2, 'big'))
def wb(a, n): machine.mem_write(a, bytes([n & 255]))
def wf(a, f): machine.mem_write(a, struct.pack('>f', f))
def rw(a): return int.from_bytes(machine.mem_read(a, 4), 'big')
def rh(a): return int.from_bytes(machine.mem_read(a, 2), 'big', signed=True)
def rb(a): return machine.mem_read(a, 1)[0]
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


def check_nonvol():
    for r, v in NONVOL.items():
        assert machine.reg_read(r) == v, f'non-volatile r{r - p.UC_PPC_REG_0} changed'
    for r, v in NONVOL_F.items():
        assert machine.reg_read(r) == v, f'non-volatile f{r - p.UC_PPC_REG_FPR0} changed'
    assert machine.reg_read(p.UC_PPC_REG_1) == SP and machine.reg_read(p.UC_PPC_REG_13) == R13


def world(params=True, flags=None, energy=400, emax=1000, cat=1, sub=1, counter=0, x=None, cap=None, keep=None, frame=5, last_fx=0, se1=None, se2=None):
    machine.mem_write(PLAYER, bytes(0x600))
    machine.mem_write(OTHER, bytes(0x600))
    machine.mem_write(ROOT, bytes(0x7000))
    machine.mem_write(HUD_STRUCT, bytes(0x40))
    machine.mem_write(SP - 0x100, bytes(0x100))
    ww(R13 + m['root_r13'], ROOT)
    wh(ROOT + m['energy'], energy)
    wh(ROOT + m['energy_max'], emax)
    wb(PLAYER + 0xF8, cat)
    wb(PLAYER + 0xF9, sub)
    wb(PLAYER + 0x4E1, counter)
    wf(PLAYER + 0xD0, 0.5)
    machine.mem_write(CODE + m['params_offset'], bytes(0x60))
    if params:
        ww(PRM['marker'], m['marker'])
        ww(PRM['flags'], DEF['flags'] if flags is None else flags)
        ww(PRM['energy_per_hit'], X if x is None else x)
        ww(PRM['cap_per_step'], DEF['cap_per_step'] if cap is None else cap)
        ww(PRM['keep_frames'], DEF['keep_frames'] if keep is None else keep)
        ww(PRM['fx_group'], DEF['fx_group'])
        ww(PRM['fx_id'], DEF['fx_id'])
        ww(PRM['se1'], DEF['se1'] if se1 is None else se1)
        ww(PRM['se2'], DEF['se2'] if se2 is None else se2)
        ww(PRM['player'], PLAYER)
        ww(PRM['frame'], frame)
        ww(PRM['last_fx_frame'], last_fx)
    del calls[:]


def frame():
    set_regs()
    machine.reg_write(p.UC_PPC_REG_9, 0x80170000)
    machine.reg_write(p.UC_PPC_REG_FPR13, packf(13.5))
    machine.emu_start(HOOK0, RESUME0, count=2000)
    assert machine.reg_read(p.UC_PPC_REG_PC) == RESUME0, hex(machine.reg_read(p.UC_PPC_REG_PC))
    check_nonvol()
    assert machine.reg_read(p.UC_PPC_REG_9) == 0x80170000 and machine.reg_read(p.UC_PPC_REG_FPR13) == packf(13.5)
    f0 = struct.unpack('>d', machine.reg_read(p.UC_PPC_REG_FPR0).to_bytes(8, 'big'))[0]
    assert f0 == struct.unpack('>f', dol.read(0x80170000 + ((m['orig0'] & 0xFFFF) - 0x10000), 4))[0]   # the re-executed original lfs f0, d(r9)
    return {'counter': rb(PLAYER + 0x4E1), 'prev': rw(PRM['in_step_prev']), 'steps': rw(PRM['steps']), 'step_absorbed': rw(PRM['step_absorbed']),
            'player': rw(PRM['player']), 'frame': rw(PRM['frame'])}


def hit_a(target, counter):
    set_regs()
    machine.reg_write(p.UC_PPC_REG_0, counter)
    machine.reg_write(p.UC_PPC_REG_11, target)
    n0 = len(calls)
    machine.emu_start(HOOK_A, A_DAMAGE if counter == 0 else A_SKIP, count=20000)
    pc = machine.reg_read(p.UC_PPC_REG_PC)
    check_nonvol()
    return {'pc': pc, 'r0': machine.reg_read(p.UC_PPC_REG_0), 'r11': machine.reg_read(p.UC_PPC_REG_11), 'calls': calls[n0:],
            'energy': rh(ROOT + m['energy']), 'step_absorbed': rw(PRM['step_absorbed']), 'total': rw(PRM['total_absorbed']),
            'total_energy': rw(PRM['total_energy']), 'seen': rw(PRM['hits_seen']), 'last': rw(PRM['last_target']),
            'fx': rw(PRM['fx_spawned']), 'last_fx': rw(PRM['last_fx_frame'])}


def hit_b(target, counter, damage_enabled=1):
    set_regs()
    machine.reg_write(p.UC_PPC_REG_0, counter)
    machine.reg_write(p.UC_PPC_REG_12, target)
    machine.reg_write(p.UC_PPC_REG_6, damage_enabled)
    machine.reg_write(p.UC_PPC_REG_LR, CALLER_B)
    n0 = len(calls)
    machine.emu_start(HOOK_B, B_CONT if counter == 0 else CALLER_B, count=20000)
    pc = machine.reg_read(p.UC_PPC_REG_PC)
    check_nonvol()
    return {'pc': pc, 'lr': machine.reg_read(p.UC_PPC_REG_LR), 'r12': machine.reg_read(p.UC_PPC_REG_12), 'calls': calls[n0:],
            'energy': rh(ROOT + m['energy']), 'total': rw(PRM['total_absorbed']), 'seen': rw(PRM['hits_seen']), 'fx': rw(PRM['fx_spawned'])}


def kinds(cs):
    return [c[0] for c in cs]


FULL = ['hud', 'est', 'owner', 'create', 'se', 'se']
cases = 0
# ---- per-frame body (unchanged from v0.1 except the frame counter)
world(params=False)
s = frame()
assert rw(PRM['marker']) == m['marker'] and rw(PRM['flags']) == DEF['flags'] and rw(PRM['energy_per_hit']) == X
assert rw(PRM['fx_group']) == DEF['fx_group'] and rw(PRM['fx_id']) == DEF['fx_id'] and rw(PRM['se1']) == DEF['se1'] and rw(PRM['se2']) == DEF['se2']
assert s['counter'] == 0 and s['prev'] == 0 and s['steps'] == 0 and s['player'] == PLAYER and s['frame'] == 1
s = frame()
assert s['frame'] == 2
cases += 2
world(sub=1, counter=0)
frame()
wb(PLAYER + 0xF9, 2)
s = frame()
assert s['counter'] == 2 and s['prev'] == 1 and s['steps'] == 1 and s['step_absorbed'] == 0
for cur, want in ((3, 3), (30, 30), (0x85, 0x85), (1, 2), (0, 2)):
    wb(PLAYER + 0x4E1, cur)
    assert frame()['counter'] == want
    cases += 1
wb(PLAYER + 0xF9, 0)
wb(PLAYER + 0x4E1, 1)
s = frame()
assert s['counter'] == 1 and s['prev'] == 0
world(flags=0, sub=2)
assert frame()['steps'] == 0
cases += 2

# ---- hit stub A: energy + effect + sounds
world(sub=2)
r = hit_a(PLAYER, 0)
assert r['pc'] == A_DAMAGE and r['r0'] == 0 and r['r11'] == PLAYER and r['calls'] == [] and r['energy'] == 400
cases += 1
world(sub=2, frame=7)
r = hit_a(PLAYER, 2)
assert r['pc'] == A_SKIP and r['energy'] == 400 + X and r['total'] == 1 and r['fx'] == 1 and r['last_fx'] == 7
assert kinds(r['calls']) == FULL, r['calls']
c = {k: v for k, *v in [(x[0], *x[1:]) for x in r['calls']]}
assert r['calls'][0] == ('hud', HUD_STRUCT)
assert r['calls'][1] == ('est', DEF['fx_group'], DEF['fx_id'])
assert r['calls'][2] == ('owner', DEF['fx_group'])
create = r['calls'][3]
assert create[1:9] == (PLAYER, 0, 0, FAKE_RECORD, FAKE_OWNER, 0, 0, PLAYER), create           # same arguments as the orb pickup
assert create[9] == 0 and create[10] == SP - 32 and create[10] % 16 == 0                         # 9th argument on our own frame
assert r['calls'][4] == ('se', 0, DEF['se1'], 0, 0) and r['calls'][5] == ('se', 0, DEF['se2'], 0, 0)
assert rw(HUD_STRUCT + 0x30) == 400 + X and rw(HUD_STRUCT + 4) & 8
cases += 6
# 7. a second absorb in the same frame: energy yes, effect / sound no (once per frame); next frame: again
r = hit_a(PLAYER, 2)
assert r['energy'] == 400 + 2 * X and kinds(r['calls']) == ['hud'] and r['fx'] == 1
ww(PRM['frame'], 8)
r = hit_a(PLAYER, 2)
assert r['energy'] == 400 + 3 * X and kinds(r['calls']) == FULL and r['fx'] == 2 and r['last_fx'] == 8
cases += 2
# 8. flag variants: no once-per-frame -> every hit; effect off; sound off; both off
world(sub=2, flags=0x1F)
hit_a(PLAYER, 2); r = hit_a(PLAYER, 2)
assert kinds(r['calls']) == FULL and r['fx'] == 2
world(sub=2, flags=0x37)
r = hit_a(PLAYER, 2)
assert kinds(r['calls']) == ['hud', 'se', 'se'] and r['fx'] == 0 and r['last_fx'] == 5
world(sub=2, flags=0x2F)
r = hit_a(PLAYER, 2)
assert kinds(r['calls']) == ['hud', 'est', 'owner', 'create'] and r['fx'] == 1
world(sub=2, flags=0x07)
r = hit_a(PLAYER, 2)
assert kinds(r['calls']) == ['hud'] and r['energy'] == 400 + X and r['last_fx'] == 0
world(sub=2, se1=0)
r = hit_a(PLAYER, 2)
assert kinds(r['calls']) == ['hud', 'est', 'owner', 'create', 'se'] and r['calls'][-1][2] == DEF['se2']
world(sub=2, se2=0)
r = hit_a(PLAYER, 2)
assert kinds(r['calls']) == ['hud', 'est', 'owner', 'create', 'se'] and r['calls'][-1][2] == DEF['se1']
cases += 6
# 9. record lookup failed (0): no create, sounds still play
machine.mem_write(EST_GET, bytes.fromhex('38600000') + RET)
machine.ctl_remove_cache(EST_GET, EST_GET + 16)          # the stub changed under Unicorn's translation cache
world(sub=2)
r = hit_a(PLAYER, 2)
assert kinds(r['calls']) == ['hud', 'est', 'se', 'se'] and r['fx'] == 0 and r['energy'] == 400 + X
machine.mem_write(EST_GET, bytes.fromhex('3c608077') + bytes.fromhex('60630000') + RET)
machine.ctl_remove_cache(EST_GET, EST_GET + 16)
cases += 1
# 10. clamp, cap, non-absorbing contexts (as in v0.1)
world(sub=2, energy=950)
r = hit_a(PLAYER, 2)
assert r['energy'] == 1000 and kinds(r['calls']) == FULL
world(sub=2, cap=1)
hit_a(PLAYER, 2); r = hit_a(PLAYER, 2)
assert r['energy'] == 400 + X and r['step_absorbed'] == 1 and kinds(r['calls']) == []
world(sub=2)
r = hit_a(OTHER, 2)
assert r['pc'] == A_SKIP and r['energy'] == 400 and r['calls'] == [] and r['seen'] == 1
for sub in (0, 1, 9, 3):
    world(sub=sub)
    r = hit_a(PLAYER, 30)
    assert r['pc'] == A_SKIP and r['energy'] == 400 and r['calls'] == [], sub
    cases += 1
world(sub=2, params=False)
r = hit_a(PLAYER, 2)
assert r['energy'] == 400 and r['calls'] == []
cases += 4
# 11. the game's own small-orb pickup (energy +250, then the gauge routine) must hand the gauge routine the same struct
# as the absorb routine; without this a wrong HUD_STRUCT is only checked against the manifest that carries it
world(sub=2, energy=100)
set_regs()
ORB_ADD = REG.a(0x800A84FC) - 0x2C
machine.emu_start(ORB_ADD, ORB_ADD + 0x34, count=200)
assert machine.reg_read(p.UC_PPC_REG_PC) == ORB_ADD + 0x34 and calls == [('hud', HUD_STRUCT)], [(k, hex(v)) for k, v in calls]
assert rh(ROOT + m['energy']) == 350 and rw(HUD_STRUCT + 0x30) == 350 and rw(HUD_STRUCT + 4) & 8
cases += 1

# ---- hit stub B
world(sub=2)
r = hit_b(PLAYER, 0)
assert r['pc'] == B_CONT and r['r12'] == PLAYER and r['calls'] == []
r = hit_b(PLAYER, 2)
assert r['pc'] == CALLER_B and r['lr'] == CALLER_B and r['energy'] == 400 + X and kinds(r['calls']) == FULL and r['fx'] == 1
world(sub=2, flags=0x3D)
r = hit_b(PLAYER, 2)
assert r['pc'] == CALLER_B and r['energy'] == 400 and r['calls'] == [] and r['seen'] == 1
cases += 3

# ---- retail update -> retail hurtbox eligibility -> absorb (2026-10-06 regression)
# The original tests started AFTER BltHitEm had accepted the target. US rejects
# flags=2 here, while JP's cmpwi accepts it; Main writes exactly 2 when invincible.
GATE = REG.a(0x8000BAC0)
GATE_PASS, GATE_SKIP = GATE + 8, GATE + 0x280


def hurtbox_gate(target, record):
    set_regs()
    machine.reg_write(p.UC_PPC_REG_31, target)
    machine.reg_write(p.UC_PPC_REG_27, record)
    r9_before = machine.reg_read(p.UC_PPC_REG_9)
    stops = {GATE_PASS, GATE_SKIP}
    def stop_gate(uc, address, size, user):
        if address in stops:
            uc.emu_stop()
    handle = machine.hook_add(u.UC_HOOK_CODE, stop_gate, begin=GATE_PASS, end=GATE_SKIP)
    try:
        machine.emu_start(GATE - 4, SENTINEL, count=300)
    finally:
        machine.hook_del(handle)
    pc = machine.reg_read(p.UC_PPC_REG_PC)
    assert pc in stops, hex(pc)
    assert machine.reg_read(p.UC_PPC_REG_1) == SP and machine.reg_read(p.UC_PPC_REG_9) == r9_before
    assert machine.reg_read(p.UC_PPC_REG_0) == int.from_bytes(machine.mem_read(record + 0x24, 2), 'big')
    return pc == GATE_PASS


world(sub=2, counter=2)
records = [PLAYER + 0x474] + [PLAYER + 0xDD8 + 0x38 * i for i in range(4)]
for i, record in enumerate(records):
    machine.mem_write(record, bytes(0x38))
    wh(record + 0x24, 1)
    ww(record + 0x34, records[i + 1] if i + 1 < len(records) else 0)
set_regs()
UPDATE = REG.a(0x800AFBF8)
machine.emu_start(UPDATE, UPDATE + 0x70, count=200)
assert rb(PLAYER + 0x4E1) == 1 and all(rh(record + 0x24) == 2 for record in records)
frame()
assert rb(PLAYER + 0x4E1) == 2
for record in records:
    assert hurtbox_gate(PLAYER, record), 'invincible sidestep rejected before the absorb hooks'
    assert rh(record + 0x24) == 2, 'eligibility must not mutate hurtbox flags or geometry'
cases += 1

if REG.name == 'US':
    for name, target, flags, cat, sub, counter, marker, hurtbox_flags, expected in (
        ('ordinary active', OTHER, 0, 1, 0, 0, False, 1, True),
        ('disabled shape', PLAYER, 0x3F, 1, 2, 2, True, 0, False),
        ('other actor', OTHER, 0x3F, 1, 2, 2, True, 2, False),
        ('feature off', PLAYER, 0, 1, 2, 2, True, 2, False),
        ('not initialized', PLAYER, 0x3F, 1, 2, 2, False, 2, False),
        ('not normal action', PLAYER, 0x3F, 2, 2, 2, True, 2, False),
        ('not sidestepping', PLAYER, 0x3F, 1, 0, 30, True, 2, False),
        ('not invincible', PLAYER, 0x3F, 1, 2, 0, True, 2, False)):
        world(params=marker, flags=flags, cat=cat, sub=sub, counter=counter)
        wh(PLAYER + 0x498, hurtbox_flags)
        assert hurtbox_gate(target, PLAYER + 0x474) == expected, name
        cases += 1

# A regular shot first performs BltDmageSet(..., damage_enabled=0), then commits in BltHitCk. Both hooks used to award
# energy for this one shot (JP until 2026-10-06); now the query returns to the caller untouched and only the commit counts.
world(sub=2, counter=2)
r = hit_b(PLAYER, 2, damage_enabled=0)
assert r['pc'] == CALLER_B and r['lr'] == CALLER_B and r['r12'] == PLAYER
assert r['energy'] == 400 and r['total'] == 0 and r['seen'] == 0 and r['calls'] == []
r = hit_a(PLAYER, 2)
assert r['energy'] == 400 + X and r['total'] == 1 and r['seen'] == 1 and kinds(r['calls']) == FULL
# an attack that arrives committed at hook B (area, piercing, effect) is still counted there, once
world(sub=2, counter=2)
r = hit_b(PLAYER, 2, damage_enabled=1)
assert r['energy'] == 400 + X and r['total'] == 1 and r['seen'] == 1 and kinds(r['calls']) == FULL
cases += 2

# ---- end to end on a real RAM image of the region (JP: the sprint savestate, slot 3; US: a live dump taken with
# dolphin_live_mram.py on 2026-10-06): real record lookup / owner tables, real HUD; the generator create and the sound are
# stubbed (the game's create path runs paired-single instructions that Unicorn cannot execute) and their arguments are
# checked against the real effect tables.
FIXTURES = Path(__file__).parent / 'fixtures'
E2E_IMAGES = {'JP': [FIXTURES / 'GPNJ08_s03_mram.bin'],
              'US': [FIXTURES / 'GPNE08_live_2026-10-06_mram.bin']}
img = next((path for path in E2E_IMAGES[REG.name] if path.exists()), None)
if img is None:
    print('end-to-end section skipped: no RAM image for', REG.name)
else:
    data = bytearray(img.read_bytes())
    R = CODE - 0x80000000
    data[R:R + 0x800] = bytes(0x800)
    data[R:R + len(code)] = code
    for hook, _, _ in HOOKS:
        data[hook - 0x80000000:hook - 0x80000000 + 4] = m['hook_words'][hex(hook)].to_bytes(4, 'big')
    data[SE_PLAY - 0x80000000:SE_PLAY - 0x80000000 + 8] = bytes.fromhex('38600000') + RET
    data[ESP_CREATE - 0x80000000:ESP_CREATE - 0x80000000 + 12] = bytes.fromhex('3c6080db') + bytes.fromhex('60634220') + RET
    mc = u.Uc(u.UC_ARCH_PPC, u.UC_MODE_32 | u.UC_MODE_BIG_ENDIAN)
    mc.mem_map(0x80000000, 0x1800000)
    mc.mem_write(0x80000000, bytes(data))
    mc.reg_write(p.UC_PPC_REG_MSR, 0x2000)
    seen = []

    def on_code2(uc, address, size, user):
        r = lambda n: uc.reg_read(p.UC_PPC_REG_0 + n)
        if address == ESP_CREATE:
            seen.append(('create', r(3), r(4), r(5), r(6), r(7), r(8), r(9), r(10), int.from_bytes(uc.mem_read(r(1) + 8, 4), 'big')))
        elif address == SE_PLAY:
            seen.append(('se', r(3), r(4), r(5), r(6)))
        elif address == HUD:
            seen.append(('hud', r(3)))
    mc.hook_add(u.UC_HOOK_CODE, on_code2, begin=0x80000000, end=0x81800000)
    rw2 = lambda a: int.from_bytes(mc.mem_read(a, 4), 'big')
    root = rw2(R13 + REG.root_sda)
    player = rw2(rw2(rw2(root + REG.root_player_vec)))
    e0 = int.from_bytes(mc.mem_read(root + REG.root_energy, 2), 'big', signed=True)
    emax = int.from_bytes(mc.mem_read(root + REG.root_energy_max, 2), 'big', signed=True)
    esp = rw2(R13 + REG.esp_sda)
    base, idt = rw2(esp + 0x80B8), rw2(esp + 0x80B8 + 4)                          # group 0 data base / id table
    rec_by_id = {int.from_bytes(mc.mem_read(idt + 8 * i + 4, 2), 'big'): base + rw2(base + 4 + i * 4) for i in range(rw2(idt))}
    for i in range(32):
        mc.reg_write(p.UC_PPC_REG_0 + i, 0x11110000 + i)
    mc.reg_write(p.UC_PPC_REG_1, SP); mc.reg_write(p.UC_PPC_REG_13, R13); mc.reg_write(p.UC_PPC_REG_31, player); mc.reg_write(p.UC_PPC_REG_9, 0x80170000)
    mc.mem_write(player + 0xF9, bytes([2]))
    mc.emu_start(HOOK0, RESUME0, count=2000)
    assert mc.reg_read(p.UC_PPC_REG_PC) == RESUME0 and mc.mem_read(player + 0x4E1, 1)[0] == 2
    mc.reg_write(p.UC_PPC_REG_0, 2); mc.reg_write(p.UC_PPC_REG_11, player); mc.reg_write(p.UC_PPC_REG_1, SP)
    mc.emu_start(HOOK_A, A_SKIP, count=200000)
    assert mc.reg_read(p.UC_PPC_REG_PC) == A_SKIP
    e1 = int.from_bytes(mc.mem_read(root + REG.root_energy, 2), 'big', signed=True)
    assert e1 == min(e0 + X, emax)
    assert [k[0] for k in seen] == ['hud', 'create', 'se', 'se'], seen
    create = seen[1]
    assert create[1] == player and create[4] == rec_by_id[DEF['fx_id']] and create[5] == rw2(esp + 4 * DEF['fx_group']) and create[8] == player, create
    assert create[2:4] == (0, 0) and create[6:8] == (0, 0) and create[9] == 0
    assert seen[2] == ('se', 0, DEF['se1'], 0, 0) and seen[3] == ('se', 0, DEF['se2'], 0, 0)
    assert rw2(CODE + m['params_offset'] + 0x4C) == 1
    assert seen[0] == ('hud', HUD_STRUCT)
    print(f'end-to-end on {img.name}: energy {e0} -> {e1}, create(player {player:08X}, record {create[4]:08X} = (0, 0x{DEF["fx_id"]:X}), owner {create[5]:08X})')
    cases += 1

(build / 'unit-test-results.json').write_text(json.dumps({'cases': cases}, indent=2))
print(f'ok: {cases} cases')
