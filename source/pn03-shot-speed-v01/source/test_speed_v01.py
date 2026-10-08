"""Unicorn tests for Shot Speed v0.1."""
from pathlib import Path
import json, struct, sys
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
import unicorn as u
import unicorn.ppc_const as p

build = Path(__file__).parent / 'speed-v01-build'
m = json.loads((build / 'manifest.json').read_text())
code = (build / 'speed.bin').read_bytes()
HOOK, REGION, PARAMS, RESUME, P = m['hook'], m['region'], m['params'], m['resume'], m['param_offsets']
R13 = 0x8026E820
ROOT, LIST, PLAYER, ACTOR, INST = 0x80191D20, 0x80E1F640, 0x80E0B5E0, 0x80EA9040, 0x80E42960

mem = u.Uc(u.UC_ARCH_PPC, u.UC_MODE_32 | u.UC_MODE_BIG_ENDIAN)
mem.mem_map(0x80000000, 0x1800000)
for line in (build / 'patch.txt').read_text().splitlines():
    a, _, v, c = line.split(':'); mem.mem_write(int(a, 16), int(v, 16).to_bytes(4, 'big'))
mem.mem_write(RESUME, bytes.fromhex('d1bf010c'))
mem.reg_write(p.UC_PPC_REG_MSR, 0x2000)
ww = lambda a, v: mem.mem_write(a, (v & 0xFFFFFFFF).to_bytes(4, 'big'))
rw = lambda a: int.from_bytes(mem.mem_read(a, 4), 'big')
rf = lambda a: struct.unpack('>f', mem.mem_read(a, 4))[0]
wf = lambda a, *vs: mem.mem_write(a, b''.join(struct.pack('>f', v) for v in vs))
ww(R13 - 0x74AC, ROOT); ww(ROOT + 0x50, LIST); ww(LIST, LIST + 0x40); ww(LIST + 0x40, PLAYER)
V0 = (-301.72, -49.959, 1773.829)


def run(cls=3, target=0, owner=PLAYER, flags=1):
    mem.mem_write(ACTOR + 0xFC, bytes([cls])); ww(ACTOR + 0x12C, target); ww(ACTOR + 0xE4, owner)
    ww(PARAMS + P['flags'], flags); wf(ACTOR + 0x100, *V0); wf(INST + 0x50, 7.25)
    for i in range(32):
        mem.reg_write(p.UC_PPC_REG_0 + i, 0x11110000 + i)
    mem.reg_write(p.UC_PPC_REG_1, 0x80500000); mem.reg_write(p.UC_PPC_REG_13, R13)
    mem.reg_write(p.UC_PPC_REG_31, ACTOR); mem.reg_write(p.UC_PPC_REG_28, INST); mem.reg_write(p.UC_PPC_REG_10, ACTOR + 0x100)
    mem.reg_write(p.UC_PPC_REG_FPR12, struct.unpack('<Q', struct.pack('<d', 1.0))[0]); mem.reg_write(p.UC_PPC_REG_FPR31, 0)
    mem.emu_start(HOOK, RESUME, count=200)
    assert mem.reg_read(p.UC_PPC_REG_PC) == RESUME
    assert struct.unpack('<d', struct.pack('<Q', mem.reg_read(p.UC_PPC_REG_FPR13)))[0] == 7.25         # original lfs f13, 0x50(r28)
    assert struct.unpack('<d', struct.pack('<Q', mem.reg_read(p.UC_PPC_REG_FPR12)))[0] == 1.0
    for r in (3, 4, 5, 6, 7, 8, 9, 29, 30):
        assert mem.reg_read(p.UC_PPC_REG_0 + r) == 0x11110000 + r, r
    assert mem.reg_read(p.UC_PPC_REG_10) == ACTOR + 0x100 and mem.reg_read(p.UC_PPC_REG_31) == ACTOR and mem.reg_read(p.UC_PPC_REG_28) == INST
    return tuple(rf(ACTOR + 0x100 + 4 * i) for i in range(3))


k = m['factor']
cases = 0
v = run(); assert all(abs(a - b * k) < 1e-2 for a, b in zip(v, V0)), v; assert rw(PARAMS + P['count']) == 1; cases += 1
assert abs(rf(PARAMS + P['last_v'] + 8) - V0[2] * k) < 1e-2; cases += 1
v = run(cls=8); assert all(abs(a - b) < 1e-3 for a, b in zip(v, V0)); cases += 1           # other class untouched
v = run(target=0x80F00000); assert all(abs(a - b) < 1e-3 for a, b in zip(v, V0)); cases += 1  # energy drive shot (has a target)
v = run(owner=0x80F10000); assert all(abs(a - b) < 1e-3 for a, b in zip(v, V0)); cases += 1   # enemy shot
v = run(flags=0); assert all(abs(a - b) < 1e-3 for a, b in zip(v, V0)); cases += 1          # disabled
assert rw(PARAMS + P['count']) == 1
(build / 'unit-test-results.json').write_text(json.dumps({'cases': cases, 'status': 'pass'}, indent=2))
print(f'all {cases} cases passed')
