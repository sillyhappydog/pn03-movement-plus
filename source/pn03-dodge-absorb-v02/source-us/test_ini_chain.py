"""Integration check of a deployed Dolphin INI (GameSettings/<GameID>.ini) for the region selected by PN03_REGION.

Applies every enabled OnFrame patch to the region's DOL image the way Dolphin does (conditional dword writes, in file
order), then runs in Unicorn:
  1. the per-frame hook chain in the player update (sprint -> trail -> absorb -> lead) from the first hooked
     instruction to the first unhooked one, with the player in a sidestep;
  2. the shot-hit path of the game (target fetch, invincibility test, our stub, the game's own gauge routine).
This catches what the per-patch tests cannot see: patches overlapping each other, a chain link that returns to the
wrong place, a body that was not written because its target was not zero, and a gauge struct that differs from the one
the game's own orb pickup uses (the US build passed 0x801957A0, the screen-fade table, until 2026-10-06).

Usage (from work/):  [PN03_REGION=US] py -3.13 test_ini_chain.py [path/to/GameID.ini]
"""
import sys, struct, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
from regions import R as REG, lo
import unicorn as u
import unicorn.ppc_const as p
import dol
import apply_gecko

INI = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / 'Documents' / 'Dolphin Emulator' / 'GameSettings' / f'{REG.game_id}.ini'
WORK = Path(__file__).parent
absorb = json.loads((WORK / ('absorb-v02-build' + REG.suffix) / 'manifest.json').read_text())
PRM, DEF = absorb['params'], absorb['defaults']
X = DEF['energy_per_hit']

R13 = REG.r13
ROOT = 0x80600000
VEC, PPTR = 0x80610000, 0x80610100
PLAYER, SHOT = 0x80D2D020, 0x80D40000
SP = 0x817F0000
FAKE_RECORD, FAKE_OWNER, FAKE_GEN = 0x80770000, 0x80520120, 0x80DB4220

machine = u.Uc(u.UC_ARCH_PPC, u.UC_MODE_32 | u.UC_MODE_BIG_ENDIAN)
machine.mem_map(0x80000000, 0x1800000)
for f, a, n in dol.sections:
    machine.mem_write(a, dol.data[f:f + n])
machine.reg_write(p.UC_PPC_REG_MSR, 0x2000)


def ww(a, n): machine.mem_write(a, (n & 0xFFFFFFFF).to_bytes(4, 'big'))
def wh(a, n): machine.mem_write(a, (n & 0xFFFF).to_bytes(2, 'big'))
def wb(a, n): machine.mem_write(a, bytes([n & 255]))
def wf(a, f): machine.mem_write(a, struct.pack('>f', f))
def rw(a): return int.from_bytes(machine.mem_read(a, 4), 'big')
def rh(a): return int.from_bytes(machine.mem_read(a, 2), 'big', signed=True)
def rb(a): return machine.mem_read(a, 1)[0]


# ---- 1. apply the INI like Dolphin's PatchEngine (write when unconditional or when the current value equals the comparand)
sections = dict(apply_gecko.parse_ini(INI.read_text(encoding='utf-8-sig')))
patches = apply_gecko.parse_entries(sections.get('OnFrame', []))
enabled = [l[1:].strip() for l in sections.get('OnFrame_Enabled', []) if l.startswith('$')]
assert enabled, f'no enabled OnFrame patches in {INI}'


def apply_frame():
    written, skipped = 0, []
    for name in patches:
        if name not in enabled:
            continue
        for line in patches[name]:
            f = line.split(':')
            assert f[1] == 'dword', line
            addr, val = int(f[0], 16), int(f[2], 16)
            if len(f) > 3 and rw(addr) != int(f[3], 16):
                skipped.append((name, line, rw(addr)))
                continue
            ww(addr, val)
            written += 1
    return written, skipped


owners = {}
for name in enabled:
    for line in patches[name]:
        a = int(line.split(':')[0], 16)
        assert a not in owners, f'{a:08X} is written by both {owners[a]} and {name}'
        owners[a] = name
written, skipped = apply_frame()
assert not skipped, skipped[:5]
snapshot = bytes(machine.mem_read(0x80000000, 0x300000))
w2, s2 = apply_frame()                      # the next frame: nothing may change (hooks no longer hold the original word)
assert bytes(machine.mem_read(0x80000000, 0x300000)) == snapshot
print(f'{INI.name}: {len(enabled)} patches, {written} words written on the first frame, {w2} rewritten on the second (idempotent)')

# ---- game functions the absorb routine calls that need loaded effect / sound data (the gauge routine stays real)
EST_GET, EST_OWNER, ESP_CREATE, SE_PLAY, HUD_UP = (absorb[k] for k in ('est_get', 'est_owner', 'esp_create', 'se_play', 'hud_up'))
RET = bytes.fromhex('4e800020')
machine.mem_write(EST_GET, bytes.fromhex('3c608077') + bytes.fromhex('60630000') + RET)
machine.mem_write(EST_OWNER, bytes.fromhex('3c608052') + bytes.fromhex('60630120') + RET)
machine.mem_write(ESP_CREATE, bytes.fromhex('3c6080db') + bytes.fromhex('60634220') + RET)
machine.mem_write(SE_PLAY, bytes.fromhex('38600000') + RET)
# the gauge struct, read from the game's own small-orb pickup (lis r3 / addi r3 / bl gauge) - not from our manifest
orb = REG.a(0x800A84FC)
lis_w, addi_w = int.from_bytes(dol.read(orb - 4, 4), 'big'), int.from_bytes(dol.read(orb, 4), 'big')
assert lis_w >> 16 == 0x3C60 and addi_w >> 16 == 0x3863
GAME_HUD = ((lis_w & 0xFFFF) << 16) + lo(addi_w)
FADE_TABLE = GAME_HUD - 0xA0                 # 4 x 0x24 screen-fade channels sit right below the gauge struct in both builds

BODIES = {'sprint': REG.a(0x8018D800), 'trail': REG.a(0x8018D400), 'absorb': REG.a(0x8018C800), 'lead': REG.a(0x8018C100)}
trace, calls = [], []


def on_code(uc, address, size, user):
    r = lambda n: uc.reg_read(p.UC_PPC_REG_0 + n)
    for k, v in BODIES.items():
        if address == v:
            trace.append(k)
    if address == HUD_UP:
        calls.append(('hud', r(3)))
    elif address == EST_GET:
        calls.append(('est', r(3), r(4)))
    elif address == EST_OWNER:
        calls.append(('owner', r(3)))
    elif address == ESP_CREATE:
        calls.append(('create', r(3), r(4), r(5), r(6), r(7), r(8), r(9), r(10), rw(r(1) + 8)))
    elif address == SE_PLAY:
        calls.append(('se', r(3), r(4), r(5), r(6)))


machine.hook_add(u.UC_HOOK_CODE, on_code, begin=0x80000000, end=0x81800000)


def world(sub, counter, energy=400, emax=1000):
    machine.mem_write(PLAYER, bytes(0x1000))
    machine.mem_write(SHOT, bytes(0x400))
    machine.mem_write(ROOT, bytes(0x8000))
    machine.mem_write(GAME_HUD - 0x100, bytes(0x200))
    machine.mem_write(SP - 0x400, bytes(0x400))
    ww(R13 + REG.root_sda, ROOT)
    ww(ROOT + REG.root_player_vec, VEC); ww(VEC, PPTR); ww(PPTR, PLAYER)
    wh(ROOT + REG.root_energy, energy); wh(ROOT + REG.root_energy_max, emax)
    wb(PLAYER + 0xF8, 1); wb(PLAYER + 0xF9, sub); wb(PLAYER + 0x4E1, counter)
    wf(PLAYER + 0xD0, 0.5)
    ww(SHOT + 0x128, PLAYER); ww(SHOT + 0x178, 100)
    del trace[:], calls[:]


def regs(r31):
    for i in range(32):
        machine.reg_write(p.UC_PPC_REG_0 + i, 0x12340000 + i)
    machine.reg_write(p.UC_PPC_REG_1, SP)
    machine.reg_write(p.UC_PPC_REG_13, R13)
    machine.reg_write(p.UC_PPC_REG_2, REG.r2)
    machine.reg_write(p.UC_PPC_REG_31, r31)
    machine.reg_write(p.UC_PPC_REG_LR, 0x80004000)


CHAIN_START, CHAIN_END = REG.a(0x800AFE78), REG.a(0x800AFE88)


def frame():
    regs(PLAYER)
    del trace[:]
    machine.emu_start(CHAIN_START, CHAIN_END, count=20000)
    assert machine.reg_read(p.UC_PPC_REG_PC) == CHAIN_END, hex(machine.reg_read(p.UC_PPC_REG_PC))
    assert trace == ['sprint', 'trail', 'absorb', 'lead'], trace          # every link runs once, in this order
    assert machine.reg_read(p.UC_PPC_REG_1) == SP and machine.reg_read(p.UC_PPC_REG_31) == PLAYER


HIT_START, A_DAMAGE, A_SKIP = REG.a(0x8000B948) - 0x1C, absorb['a_damage'], absorb['a_skip']


def hit():
    """The game's shot-hit tail from `lhz r0, 0xEC(shot)` (target fetch + invincibility test) to the common exit."""
    regs(SHOT)
    n0 = len(calls)
    machine.emu_start(HIT_START, A_SKIP, count=20000)
    assert machine.reg_read(p.UC_PPC_REG_PC) == A_SKIP, hex(machine.reg_read(p.UC_PPC_REG_PC))
    assert machine.reg_read(p.UC_PPC_REG_1) == SP and machine.reg_read(p.UC_PPC_REG_31) == SHOT
    return calls[n0:]


cases = 0
# ---- 2. per-frame chain: idle, then a sidestep
world(sub=0, counter=0)
frame()
assert rw(PRM['marker']) == absorb['marker'] and rw(PRM['player']) == PLAYER and rw(PRM['frame']) == 1 and rw(PRM['steps']) == 0
assert rb(PLAYER + 0x4E1) == 0
wb(PLAYER + 0xF9, 2)
frame()
assert rw(PRM['frame']) == 2 and rw(PRM['steps']) == 1 and rb(PLAYER + 0x4E1) == DEF['keep_frames']
cases += 2

if REG.name == 'US':
    # Main marks invincible hurtboxes as 2; require the installed INI to let an
    # absorbing player reach geometry without changing the stored shape flags.
    gate = REG.a(0x8000BAC0)
    wh(PLAYER + 0x498, 2)
    regs(PLAYER)
    machine.reg_write(p.UC_PPC_REG_27, PLAYER + 0x474)
    def stop_gate(uc, address, size, user):
        if address in (gate + 8, gate + 0x280):
            uc.emu_stop()
    handle = machine.hook_add(u.UC_HOOK_CODE, stop_gate, begin=gate + 8, end=gate + 0x280)
    machine.emu_start(gate - 4, 0x80004000, count=300)
    machine.hook_del(handle)
    assert machine.reg_read(p.UC_PPC_REG_PC) == gate + 8, 'deployed INI still rejects the invincible player before absorption'
    assert rh(PLAYER + 0x498) == 2
    cases += 1

# The real BltDmageSet query made by BltHitEm must not award energy in either region; its
# enclosing BltHitCk commits the same shot at hook A immediately afterward (step 3 below).
regs(SHOT)
args = {3: SHOT, 4: 0, 5: PLAYER, 6: SP - 0x100, 7: PLAYER + 0x474, 8: 0, 9: 0}
for reg, value in args.items():
    machine.reg_write(p.UC_PPC_REG_0 + reg, value)
machine.emu_start(absorb['hook_b'] - 0x74, 0x80004000, count=500)
assert machine.reg_read(p.UC_PPC_REG_PC) == 0x80004000
assert rh(ROOT + REG.root_energy) == 400 and rw(PRM['total_absorbed']) == 0 and rw(PRM['hits_seen']) == 0 and calls == [], \
    'the deployed INI counts the preliminary BltDmageSet query (double count per shot)'
cases += 1

# ---- 3. a shot hits during the sidestep: absorbed, gauge told through the game's own struct, nothing else touched
fade_before = bytes(machine.mem_read(FADE_TABLE, 0x90))
c = hit()
assert [k[0] for k in c] == ['hud', 'est', 'owner', 'create', 'se', 'se'], c
assert c[0] == ('hud', GAME_HUD), f'gauge routine got {c[0][1]:08X}, the game uses {GAME_HUD:08X}'
assert c[1] == ('est', DEF['fx_group'], DEF['fx_id']) and c[2] == ('owner', DEF['fx_group'])
assert c[3][1:] == (PLAYER, 0, 0, FAKE_RECORD, FAKE_OWNER, 0, 0, PLAYER, 0), c[3]
assert c[4] == ('se', 0, DEF['se1'], 0, 0) and c[5] == ('se', 0, DEF['se2'], 0, 0)
assert rh(ROOT + REG.root_energy) == 400 + X
assert rw(GAME_HUD + 0x30) == 400 + X and rw(GAME_HUD + 4) & 8          # gauge target raised, "increasing" flag set
assert bytes(machine.mem_read(FADE_TABLE, 0x90)) == fade_before, 'the screen-fade table below the gauge struct was written'
assert rw(PLAYER + 0x4F0) == 0 and rb(PLAYER + 0x4E0) == 0              # no damage, no hit reaction
assert rw(PRM['hits_seen']) == 1 and rw(PRM['total_absorbed']) == 1 and rw(PRM['total_energy']) == X and rw(PRM['fx_spawned']) == 1
cases += 1
# a second shot in the same frame: energy again, effect / sound once per frame; next frame: effect again
c = hit()
assert [k[0] for k in c] == ['hud'] and rh(ROOT + REG.root_energy) == 400 + 2 * X
frame()
c = hit()
assert [k[0] for k in c] == ['hud', 'est', 'owner', 'create', 'se', 'se'] and rh(ROOT + REG.root_energy) == 400 + 3 * X
cases += 2

# ---- 4. not invincible (no sidestep): the game's damage path runs, nothing is absorbed
world(sub=0, counter=0)
frame()
c = hit()
assert c == [] and rh(ROOT + REG.root_energy) == 400 and rw(PLAYER + 0x4F0) == 100 and rb(PLAYER + 0x4E0) == 1
# invincible but not sidestepping (hit recovery): the shot is discarded as in the original game, nothing is absorbed
world(sub=0, counter=30)
frame()
absorbed_so_far = rw(PRM['total_absorbed'])
c = hit()
assert c == [] and rh(ROOT + REG.root_energy) == 400 and rw(PLAYER + 0x4F0) == 0 and rw(PRM['total_absorbed']) == absorbed_so_far
cases += 2
print(f'ok: {cases} cases ({REG.game_id}, gauge struct {GAME_HUD:08X}, chain {" -> ".join(BODIES)})')
