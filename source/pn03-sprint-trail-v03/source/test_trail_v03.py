"""Run the Sprint Trail Colour v0.3 body in Unicorn on a synthetic element pool.

The pool layout (esp_sys = [r13 - 0x74F4], count at +0x8540, pool pointer at +0x8538, dummy
element at +0x8548, 0x150 each) and the element fields (+0x18 flags, +0x19 id, +0x24 parent, +0x88 start colour
bytes, +0x8C live colour floats) come from the DOL (allocator 0x800814D4, trans loop
0x80082188, init 0x8008E2D0, id 9 trans 0x800876B8) and were confirmed on a Dolphin
savestate taken during a sprint (the four id 9 trail elements at 0x80D60200..). Dolphin
validation is still needed.
"""
import sys, struct, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
import unicorn as u
import unicorn.ppc_const as p
import dol

build = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / 'trail-v03-build'
m = json.loads((build / 'manifest.json').read_text())
CODE, HOOK, RESUME, ORIGINAL = m['region'], m['hook'], m['resume'], m['original']
PRM, DEF = m['params'], m['defaults']
SPR = m['sprint_params']
F = m['elem_fields']
SENTINEL = 0x80004000
R13 = 0x8026e820
SP = 0x817f0000
PLAYER = 0x80D2D020
OTHER = 0x80D40000
ESP_SYS = 0x80D57B40
POOL = 0x80D60200                 # where the savestate had it
DUMMY = ESP_SYS + m['dummy_elem']
N = 8
BLUE = bytes.fromhex('5064ff55')

machine = u.Uc(u.UC_ARCH_PPC, u.UC_MODE_32 | u.UC_MODE_BIG_ENDIAN)
machine.mem_map(0x80000000, 0x1800000)
for f, a, n in dol.sections:
    machine.mem_write(a, dol.data[f:f + n])
code = (build / 'trail.bin').read_bytes()
data = (build / 'trail.data.bin').read_bytes()

# --- static checks ---
assert code[-8:-4] == ORIGINAL.to_bytes(4, 'big')
ret = int.from_bytes(code[-4:], 'big')
d = ret & 0x03FFFFFC
d = d - 0x04000000 if d & 0x02000000 else d
assert ret >> 26 == 18 and (ret & 3) == 0 and CODE + len(code) - 4 + d == RESUME
hd = m['hook_word'] & 0x03FFFFFC
hd = hd - 0x04000000 if hd & 0x02000000 else hd
assert m['hook_word'] >> 26 == 18 and HOOK + hd == CODE
assert int.from_bytes(dol.read(HOOK, 4), 'big') == ORIGINAL
patch = (build / 'patch.txt').read_text().splitlines()
assert len(patch) == len(code) // 4 + len(data) // 4 + 1
for o in range(0, len(code), 4):
    assert patch[o // 4] == f'0x{CODE + o:08X}:dword:0x{int.from_bytes(code[o:o + 4], "big"):08X}:0x00000000'
assert patch[-1] == f'0x{HOOK:08X}:dword:0x{m["hook_word"]:08X}:0x{ORIGINAL:08X}'
assert 0x8018D320 <= CODE and CODE + m['params_offset'] + 0x28 <= m['region_end'] <= 0x8018D800
# the Sprint Run v0.3 body returns to this hook: its last two words must be `lis r9,0x8017` and a branch to HOOK
sprint = json.loads((Path(__file__).parent / 'sprint-v03-build' / 'manifest.json').read_text())
sbin = (Path(__file__).parent / 'sprint-v03-build' / 'sprint.bin').read_bytes()
b1 = sbin[:sprint['body1_bytes']]
assert b1[-8:-4] == bytes.fromhex('3d208017')
sd = int.from_bytes(b1[-4:], 'big') & 0x03FFFFFC
sd = sd - 0x04000000 if sd & 0x02000000 else sd
assert sprint['region'] + len(b1) - 4 + sd == HOOK

machine.mem_write(CODE, code)
machine.mem_write(CODE + m['data_offset'], data)
machine.mem_write(HOOK, m['hook_word'].to_bytes(4, 'big'))
machine.reg_write(p.UC_PPC_REG_MSR, 0x2000)


def ww(a, n): machine.mem_write(a, (n & 0xFFFFFFFF).to_bytes(4, 'big'))
def wb(a, n): machine.mem_write(a, bytes([n & 255]))
def wf(a, f): machine.mem_write(a, struct.pack('>f', f))
def rw(a): return int.from_bytes(machine.mem_read(a, 4), 'big')
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
    assert machine.reg_read(p.UC_PPC_REG_LR) == SENTINEL and machine.reg_read(p.UC_PPC_REG_CTR) == 0x27


def elem(i):
    return POOL + i * m['elem_size']


def make_elem(i, flags=1, id_=9, parent=PLAYER, colour=BLUE, alpha=85.0):
    e = elem(i)
    machine.mem_write(e, bytes(m['elem_size']))
    wb(e + F['flags'], flags)
    wb(e + F['id'], id_)
    ww(e + F['parent'], parent)
    machine.mem_write(e + F['colour_bytes'], colour)
    machine.mem_write(e + F['colour_floats'], struct.pack('>4f', colour[0], colour[1], colour[2], alpha))


def floats(i):
    return struct.unpack('>4f', machine.mem_read(elem(i) + F['colour_floats'], 16))


def world(sprint=True, max_factor=1.4, factor=1.4, params=True, flags=None, target=None, match=None, id_=None, esp_sys=ESP_SYS, pool=POOL):
    ww(R13 + m['esp_sys_r13'], esp_sys)
    ww(ESP_SYS + m['pool_count'], N)
    ww(ESP_SYS + m['pool_ptr'], pool)
    # the dummy element (what v0.2 mistook for the pool) looks exactly like a trail element and must never be touched
    machine.mem_write(DUMMY, bytes(m['elem_size']))
    wb(DUMMY + F['flags'], 1)
    wb(DUMMY + F['id'], 9)
    ww(DUMMY + F['parent'], PLAYER)
    machine.mem_write(DUMMY + F['colour_bytes'], BLUE)
    machine.mem_write(DUMMY + F['colour_floats'], struct.pack('>4f', 80.0, 100.0, 255.0, 85.0))
    make_elem(0)                                   # trail element of the player
    make_elem(1, parent=OTHER)                     # same colour, another actor
    make_elem(2, flags=0)                          # free slot with stale data
    make_elem(3, flags=3)                          # in use but suspended
    make_elem(4, id_=1)                            # another effect kind with the same colour
    make_elem(5, colour=bytes.fromhex('11223344'))  # another colour
    make_elem(6)                                   # second trail element
    make_elem(7, alpha=40.0)                       # trail element whose alpha already faded
    machine.mem_write(PLAYER, bytes(0x100))
    wf(PLAYER + 0xD0, 1.2345)
    machine.mem_write(SPR, bytes(0x40))
    if sprint:
        ww(SPR, m['sprint_marker'])
        wf(SPR + 0x10, max_factor)
        wf(SPR + 0x30, factor)
    machine.mem_write(CODE + m['params_offset'], bytes(0x28))
    if params:
        ww(PRM['marker'], m['marker'])
        ww(PRM['flags'], DEF['flags'] if flags is None else flags)
        ww(PRM['target'], DEF['target'] if target is None else target)
        ww(PRM['match'], DEF['match'] if match is None else match)
        ww(PRM['id'], DEF['id'] if id_ is None else id_)


def run(factor=None):
    if factor is not None:
        wf(SPR + 0x30, factor)
    set_regs()
    machine.reg_write(p.UC_PPC_REG_9, 0xDEADBEEF)
    machine.emu_start(HOOK, RESUME, count=200000)
    assert machine.reg_read(p.UC_PPC_REG_PC) == RESUME, hex(machine.reg_read(p.UC_PPC_REG_PC))
    check_nonvol()
    assert machine.reg_read(p.UC_PPC_REG_9) == 0x80170000                                   # what the game expects at 0x800AFE80
    assert struct.unpack('>4f', machine.mem_read(DUMMY + F['colour_floats'], 16)) == (80.0, 100.0, 255.0, 85.0)   # dummy element untouched
    assert struct.unpack('>d', machine.reg_read(p.UC_PPC_REG_FPR13).to_bytes(8, 'big'))[0] == struct.unpack('>f', struct.pack('>f', 1.2345))[0]
    return {'t': rf(PRM['t']), 'tinted': rw(PRM['tinted']), 'dirty': rw(PRM['dirty']), 'total': rw(PRM['total'])}


def near(a, b, tol=1e-3):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


ORANGE = (255.0, 136.0, 0.0)
cases = 0

# 1. no params marker, no sprint patch: defaults written, nothing scanned
world(sprint=False, params=False)
s = run()
assert rw(PRM['marker']) == m['marker'] and rw(PRM['flags']) == DEF['flags'] and rw(PRM['target']) == DEF['target']
assert rw(PRM['match']) == DEF['match'] and rw(PRM['id']) == DEF['id']
assert s == {'t': 0.0, 'tinted': 0, 'dirty': 0, 'total': 0}
assert floats(0) == (80.0, 100.0, 255.0, 85.0)
cases += 1

# 2. full sprint: the player's trail elements go orange, alpha and start bytes untouched, others untouched
world()
s = run()
assert s['t'] == 1.0 and s['tinted'] == 3 and s['dirty'] == 1 and s['total'] == 3, s
for i in (0, 6):
    assert floats(i) == ORANGE + (85.0,), (i, floats(i))
assert floats(7) == ORANGE + (40.0,), floats(7)
for i in (0, 6, 7):
    assert bytes(machine.mem_read(elem(i) + F['colour_bytes'], 4)) == BLUE
for i in (1, 2, 3, 4):
    assert floats(i) == (80.0, 100.0, 255.0, 85.0), (i, floats(i))
assert floats(5) == (17.0, 34.0, 51.0, 85.0)
cases += 8

# 3. ramp: half way
world()
s = run(factor=1.2)
assert abs(s['t'] - 0.5) < 1e-6 and s['tinted'] == 3
assert near(floats(0)[:3], (167.5, 118.0, 127.5)) and floats(0)[3] == 85.0
cases += 1

# 4. back to t = 0: one restore pass, then no more scanning
world()
run()
assert floats(0)[:3] == ORANGE
s = run(factor=1.0)
assert s['t'] == 0.0 and s['tinted'] == 3 and s['dirty'] == 0 and floats(0) == (80.0, 100.0, 255.0, 85.0) and floats(7) == (80.0, 100.0, 255.0, 40.0)
machine.mem_write(elem(0) + F['colour_floats'], struct.pack('>4f', 1.0, 2.0, 3.0, 4.0))   # poison: a scan would overwrite it
s = run(factor=1.0)
assert s['tinted'] == 0 and s['dirty'] == 0 and floats(0) == (1.0, 2.0, 3.0, 4.0)
cases += 3

# 5. clamps and degenerate max
world()
s = run(factor=2.0)
assert s['t'] == 1.0 and floats(0)[:3] == ORANGE
world(max_factor=1.0)
s = run(factor=1.3)
assert s['t'] == 0.0 and s['tinted'] == 0
cases += 2

# 6. step mode (flags bit1 + parent check bit2 = 7)
for factor, want in ((1.2, (80.0, 100.0, 255.0)), (1.399, (80.0, 100.0, 255.0)), (1.4, ORANGE), (1.6, ORANGE)):
    world(flags=7)
    run(factor=factor)
    assert floats(0)[:3] == want, (factor, floats(0))
    cases += 1

# 7. parent check off: the other actor's element is tinted too
world(flags=1)
s = run()
assert s['tinted'] == 4 and floats(1)[:3] == ORANGE
cases += 1

# 8. id any / match any
world(id_=0xFFFFFFFF)
s = run()
assert s['tinted'] == 4 and floats(4)[:3] == ORANGE and floats(5)[:3] == (17.0, 34.0, 51.0)
world(match=0)
s = run()
assert s['tinted'] == 4 and floats(5)[:3] == ORANGE and floats(4)[:3] == (80.0, 100.0, 255.0)
cases += 2

# 9. other targets
world(target=0x00FF40FF)
run(factor=1.2)
assert near(floats(0)[:3], (40.0, 177.5, 159.5)) and floats(0)[3] == 85.0
cases += 1

# 10. disabled flag, no effect system yet, zero slots
world(flags=0)
assert run() == {'t': 0.0, 'tinted': 0, 'dirty': 0, 'total': 0}
world(esp_sys=0)
s = run()
assert s['t'] == 1.0 and s['tinted'] == 0 and s['dirty'] == 0      # nothing scanned, nothing to restore later
world(pool=0)
s = run()
assert s['t'] == 1.0 and s['tinted'] == 0 and s['dirty'] == 0 and floats(0)[:3] == (80.0, 100.0, 255.0)
cases += 1
world()
ww(ESP_SYS + m['pool_count'], 0)
s = run()
assert s['tinted'] == 0 and floats(0)[:3] == (80.0, 100.0, 255.0)
cases += 3

# 11. no sprint marker while params exist: t = 0, nothing scanned
world(sprint=False)
s = run()
assert s == {'t': 0.0, 'tinted': 0, 'dirty': 0, 'total': 0}
cases += 1

# 12. 400 frames of alternating sprint / idle: counters consistent, colours follow t
world()
total = 0
for k in range(400):
    f = 1.4 if (k // 50) % 2 == 0 else 1.0
    s = run(factor=f)
    if f > 1.0 or k % 50 == 0:
        assert s['tinted'] == 3
        total += 3
    else:
        assert s['tinted'] == 0
    assert s['total'] == total
    assert floats(0)[:3] == (ORANGE if f > 1.0 else (80.0, 100.0, 255.0))
cases += 1

(build / 'unit-test-results.json').write_text(json.dumps({'cases': cases}, indent=2))
print(f'ok: {cases} cases')
