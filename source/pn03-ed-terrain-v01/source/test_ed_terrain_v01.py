"""Run the real 0x8000B770 (shot move-and-collide) with the terrain pass v0.1 hook in Unicorn.

The DOL is loaded into the emulator, the body is placed at its region address and the
hook word is written over 0x8000B7C8. The two callees are stubbed in emulator memory:
  * 0x80007960 (terrain raycast) -> `li r3,0; blr`, and a code hook counts its calls
  * 0x8000B9AC (object hit test) -> `li r3,0; blr`
Every case runs the function from its prologue to its blr (LR = sentinel) and checks:
  * whether the terrain raycast ran, and the +0x150 budget afterwards
  * the return value, the non-volatile registers, and that nothing else in the actor
    or the fake object list changed (except the fields the original code writes).
Static checks cover the patch words (body conditional on 0, hook conditional on the
original instruction, return branch to hook+4). Dolphin validation is still needed.
"""
import sys, struct, json, itertools
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
import unicorn as u
import unicorn.ppc_const as p
import dol

build = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / 'ed-terrain-v01-build'
manifest = json.loads((build / 'manifest.json').read_text())
CODE = manifest['region']
HOOK = manifest['hook']
RESUME = manifest['resume']
FUNC = 0x8000B770
FUNC_END = 0x8000B9A8            # blr
TERRAIN = manifest['terrain_raycast']
OBJECTS = manifest['object_hit_test']
SENTINEL = 0x80004000
R13 = 0x8026e820
ROOT_PTR = R13 + manifest['root_sda_offset']
ROOT = 0x81100000
LIST = 0x81100100
ARRAY = 0x81100200
PLAYER = 0x81200000
OTHER = 0x81300000
ACTOR = 0x81000000
ENEMY = 0x81400000
SP = 0x817f0000
FROM = 0x81500000
TO = 0x81500010

machine = u.Uc(u.UC_ARCH_PPC, u.UC_MODE_32 | u.UC_MODE_BIG_ENDIAN)
machine.mem_map(0x80000000, 0x1800000)
for f, a, n in dol.sections:
    machine.mem_write(a, dol.data[f:f + n])
code = bytes((build / 'ed.bin').read_bytes())

# --- static checks on the delivery words ---
assert code[-8:-4] == manifest['original'].to_bytes(4, 'big')
ret = int.from_bytes(code[-4:], 'big')
assert ret >> 26 == 18 and (ret & 3) == 0
disp = ret & 0x03FFFFFC
disp = disp - 0x04000000 if disp & 0x02000000 else disp
assert CODE + len(code) - 4 + disp == RESUME == HOOK + 4, hex(CODE + len(code) - 4 + disp)
hw = manifest['hook_word']
hd = hw & 0x03FFFFFC
hd = hd - 0x04000000 if hd & 0x02000000 else hd
assert hw >> 26 == 18 and (hw & 3) == 0 and HOOK + hd == CODE
patch = (build / 'patch.txt').read_text().splitlines()
assert len(patch) == len(code) // 4 + 1
for o in range(0, len(code), 4):
    assert patch[o // 4] == f'0x{CODE + o:08X}:dword:0x{int.from_bytes(code[o:o + 4], "big"):08X}:0x00000000'
assert patch[-1] == f'0x{HOOK:08X}:dword:0x{hw:08X}:0x{manifest["original"]:08X}'
assert int.from_bytes(dol.read(HOOK, 4), 'big') == manifest['original']
assert CODE + len(code) <= manifest['region_end'] <= 0x8018E000

# --- install body, hook and stubs ---
machine.mem_write(CODE, code)
machine.mem_write(HOOK, hw.to_bytes(4, 'big'))
STUB = bytes.fromhex('38600000 4e800020'.replace(' ', ''))   # li r3,0 ; blr
machine.mem_write(TERRAIN, STUB)
machine.mem_write(OBJECTS, STUB)
machine.reg_write(p.UC_PPC_REG_MSR, 0x2000)
calls = {'terrain': 0, 'objects': 0, 'body': 0}


def on_code(uc, address, size, user):
    if address == TERRAIN:
        calls['terrain'] += 1
    elif address == OBJECTS:
        calls['objects'] += 1
    elif address == CODE:
        calls['body'] += 1


machine.hook_add(u.UC_HOOK_CODE, on_code)


def ww(a, n):
    machine.mem_write(a, (n & 0xFFFFFFFF).to_bytes(4, 'big'))


def wh(a, n):
    machine.mem_write(a, (n & 0xFFFF).to_bytes(2, 'big'))


def rw(a):
    return int.from_bytes(machine.mem_read(a, 4), 'big')


def rh(a):
    return int.from_bytes(machine.mem_read(a, 2), 'big')


def packf(f):
    return int.from_bytes(struct.pack('>d', f), 'big')


results = []


def run(owner, target, budget, do_terrain, list_state='ok', root_state='ok', flags=0x0205):
    """Run one call and return (terrain_called, budget_after, return_value)."""
    calls.update(terrain=0, objects=0, body=0)
    before = {p.UC_PPC_REG_0 + i: 0x12340000 + i for i in range(32)}
    before[p.UC_PPC_REG_1] = SP
    before[p.UC_PPC_REG_2] = 0x8027e820
    before[p.UC_PPC_REG_13] = R13
    before[p.UC_PPC_REG_3] = ACTOR
    before[p.UC_PPC_REG_4] = FROM
    before[p.UC_PPC_REG_5] = TO
    before[p.UC_PPC_REG_6] = ACTOR + 0x134
    before[p.UC_PPC_REG_7] = do_terrain
    for i in range(32):
        before[p.UC_PPC_REG_FPR0 + i] = packf(i + .125)
    before[p.UC_PPC_REG_FPR1] = packf(0.0)
    before.update({p.UC_PPC_REG_CR: 0xa5927310, p.UC_PPC_REG_LR: SENTINEL, p.UC_PPC_REG_CTR: 0x27,
                   p.UC_PPC_REG_XER: 0x00000000, p.UC_PPC_REG_FPSCR: 0})
    for r, v in before.items():
        machine.reg_write(r, v)
    # fake root / object list / player
    machine.mem_write(ROOT, bytes(0x100))
    machine.mem_write(LIST, bytes(0x100))
    machine.mem_write(ARRAY, bytes(0x100))
    ww(ROOT_PTR, 0 if root_state == 'null' else ROOT)
    ww(ROOT + 0x50, 0 if list_state == 'null' else LIST)
    ww(LIST, ARRAY)
    ww(LIST + 4, ARRAY if list_state == 'empty' else ARRAY + 8)
    ww(ARRAY, PLAYER)
    ww(ARRAY + 4, OTHER)
    # actor
    machine.mem_write(ACTOR, bytes([0x5A]) * 0x1B0)
    wh(ACTOR + 0xEC, flags)
    ww(ACTOR + 0xE4, owner)
    ww(ACTOR + 0x12C, target)
    wh(ACTOR + 0x150, budget)
    ww(ACTOR + 0x154, 0xDEADBEEF)
    for i in range(3):
        ww(ACTOR + 0x138 + i * 4, 0xCAFE0000 + i)
    machine.mem_write(FROM, struct.pack('>3f', 1.0, 2.0, 3.0))
    machine.mem_write(TO, struct.pack('>3f', 4.0, 5.0, 6.0))
    actor_before = bytes(machine.mem_read(ACTOR, 0x1B0))
    tables_before = bytes(machine.mem_read(ROOT, 0x300))
    vec_before = bytes(machine.mem_read(FROM, 0x20))
    try:
        machine.emu_start(FUNC, SENTINEL, count=2000)
    except u.UcError as e:
        raise AssertionError(f'emulation fault at pc={hex(machine.reg_read(p.UC_PPC_REG_PC))}: {e}')
    assert machine.reg_read(p.UC_PPC_REG_PC) == SENTINEL, hex(machine.reg_read(p.UC_PPC_REG_PC))
    # what the original function is expected to do with the stubbed callees
    player_shot = owner == PLAYER and root_state == 'ok' and list_state == 'ok'
    skip = bool(do_terrain) and player_shot and target != 0 and 0 < budget < 0x8000
    expect_terrain = bool(do_terrain) and not skip
    expect_budget = (budget - 1) & 0xFFFF if skip else budget
    assert calls['body'] == 1, calls
    assert calls['terrain'] == (1 if expect_terrain else 0), (calls, owner == PLAYER, target, budget, do_terrain)
    assert calls['objects'] == 1, calls
    assert machine.reg_read(p.UC_PPC_REG_3) == 0
    assert rh(ACTOR + 0x150) == expect_budget, (rh(ACTOR + 0x150), expect_budget)
    assert rh(ACTOR + 0xEC) == (flags & 0xFFF0)                      # original clears the low nibble
    assert rw(ACTOR + 0x154) == (0 if expect_terrain else 0xDEADBEEF)  # written only by the terrain branch
    actor_after = bytearray(machine.mem_read(ACTOR, 0x1B0))
    for off in (0xEC, 0xED, 0x150, 0x151, 0x154, 0x155, 0x156, 0x157):
        actor_after[off] = actor_before[off]
    assert bytes(actor_after) == actor_before, 'unexpected actor write'
    assert bytes(machine.mem_read(ROOT, 0x300)) == tables_before
    assert bytes(machine.mem_read(FROM, 0x20)) == vec_before
    for i in range(14, 32):
        assert machine.reg_read(p.UC_PPC_REG_0 + i) == before[p.UC_PPC_REG_0 + i], f'r{i} changed'
    assert machine.reg_read(p.UC_PPC_REG_1) == SP
    assert machine.reg_read(p.UC_PPC_REG_13) == R13
    results.append({'owner': 'player' if owner == PLAYER else 'other', 'target': hex(target), 'budget': budget,
                    'do_terrain': do_terrain, 'list': list_state, 'root': root_state,
                    'terrain_called': calls['terrain'], 'budget_after': rh(ACTOR + 0x150)})
    return calls['terrain'], rh(ACTOR + 0x150)


cases = 0
for owner, target, budget, do_terrain in itertools.product([PLAYER, OTHER], [0, ENEMY], [0, 1, 2, 0x78, 0x96, 0x12C, 0xFFFF, 0x8000], [0, 1]):
    run(owner, target, budget, do_terrain)
    cases += 1
for list_state in ('empty', 'null'):
    for do_terrain in (0, 1):
        run(PLAYER, ENEMY, 0x96, do_terrain, list_state=list_state)
        cases += 1
for do_terrain in (0, 1):
    run(PLAYER, ENEMY, 0x96, do_terrain, root_state='null')
    cases += 1
# the budget really counts down call by call and then terrain resumes
wh(ACTOR + 0x150, 3)
seq = []
b = 3
for _ in range(5):
    t, b = run(PLAYER, ENEMY, b, 1)
    seq.append((t, b))
    cases += 1
assert seq == [(0, 2), (0, 1), (0, 0), (1, 0), (1, 0)], seq
# a second player-owned object later in the list is not "the player"
run(OTHER, ENEMY, 0x96, 1)
cases += 1
(build / 'unit-test-results.json').write_text(json.dumps({'cases': cases, 'sample': results[:8], 'countdown': seq}, indent=2))
print(f'ok: {cases} cases')
