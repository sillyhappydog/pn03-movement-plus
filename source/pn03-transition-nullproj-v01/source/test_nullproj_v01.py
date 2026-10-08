"""Unicorn tests for Transition Null Projection v0.1.

Cases:
  1. all-zero 4x4 matrix (perspective type)  -> the null orthographic projection is written to the
     write-gather pipe (0x10, 0x00061020, 0, 10.0, 0, 10.0, 0, 0, 1), __GXData+2 = 1, return to LR.
  2. matrix whose tested entries are -0.0      -> same as 1 (sign bit ignored).
  3. the real game perspective matrix          -> falls through: original first instruction executed
     (r5 = __GXData) and control continues at 0x80121348 with r0/r3/r4 untouched.
  4. ortho matrix with zero diagonal but non-zero m23 -> treated as valid (falls through).
"""
from pathlib import Path
import json, struct, sys
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
import unicorn as u
import unicorn.ppc_const as p

build = Path(__file__).parent / 'nullproj-v01-build'
m = json.loads((build / 'manifest.json').read_text())
code = (build / 'nullproj.bin').read_bytes()
HOOK, REGION, RESUME = m['hook'], m['region'], m['resume']
R13 = 0x8026E820
GXDATA = 0x80300000
WGPIPE = 0xCC008000

mem = u.Uc(u.UC_ARCH_PPC, u.UC_MODE_32 | u.UC_MODE_BIG_ENDIAN)
mem.mem_map(0x80000000, 0x1800000)
mem.mem_map(0xCC000000, 0x10000)
mem.mem_write(REGION, code)
mem.mem_write(HOOK, m['hook_word'].to_bytes(4, 'big'))
mem.mem_write(HOOK + 4, bytes.fromhex('2c040001'))                     # cmpwi r4, 1 (original next instruction)
mem.mem_write(R13 - 0x5A80, GXDATA.to_bytes(4, 'big'))
mem.reg_write(p.UC_PPC_REG_MSR, 0x2000)
writes = []


def on_write(uc, access, address, size, value, user):
    if address == WGPIPE:
        writes.append((size, value & ((1 << (8 * size)) - 1)))
mem.hook_add(u.UC_HOOK_MEM_WRITE, on_write, begin=0xCC000000, end=0xCC00FFFF)

MTX = 0x80400000
LR = 0x800172EC
cases = 0


def run(matrix_words, mtx_type, stop=LR):
    writes.clear()
    mem.mem_write(MTX, b''.join(w.to_bytes(4, 'big') for w in matrix_words))
    mem.mem_write(GXDATA, bytes(0x440))
    for i in range(32):
        mem.reg_write(p.UC_PPC_REG_0 + i, 0x11110000 + i)
    mem.reg_write(p.UC_PPC_REG_1, 0x80500000); mem.reg_write(p.UC_PPC_REG_13, R13)
    mem.reg_write(p.UC_PPC_REG_3, MTX); mem.reg_write(p.UC_PPC_REG_4, mtx_type); mem.reg_write(p.UC_PPC_REG_LR, LR)
    try:
        mem.emu_start(HOOK, stop, count=200)
    except u.UcError:
        pass
    return mem.reg_read(p.UC_PPC_REG_PC)


zero16 = [0] * 16
persp = [0x3FB86A0E, 0, 0, 0, 0, 0x3FF5E2BE, 0, 0, 0, 0, 0xB8D1BC76, 0xC2C8051F, 0, 0, 0xBF800000, 0]
NULL_SEQ = [(1, 0x10), (4, 0x00061020), (4, 0), (4, 0x41200000), (4, 0), (4, 0x41200000), (4, 0), (4, 0), (4, 1)]

# 1. all zero
pc = run(zero16, 0)
assert pc == LR, hex(pc)
assert writes == NULL_SEQ, writes
assert int.from_bytes(mem.mem_read(GXDATA + 2, 2), 'big') == 1
cases += 1
# 2. negative zeros on the tested entries
neg = list(zero16); neg[0] = neg[5] = neg[10] = neg[11] = 0x80000000
pc = run(neg, 0)
assert pc == LR and writes == NULL_SEQ, (hex(pc), writes)
cases += 1
# 3. real perspective matrix: falls through to the original function
pc = run(persp, 0, RESUME)
assert pc == RESUME, hex(pc)
assert mem.reg_read(p.UC_PPC_REG_5) == GXDATA
assert mem.reg_read(p.UC_PPC_REG_3) == MTX and mem.reg_read(p.UC_PPC_REG_4) == 0
assert writes == [], writes
cases += 1
# 4. zero diagonal but non-zero m23 (not a null matrix): falls through
odd = list(zero16); odd[11] = 0x3F800000
pc = run(odd, 1, RESUME)
assert pc == RESUME and writes == [], (hex(pc), writes)
cases += 1
# 5. tiny but non-zero m00 is not null
tiny = list(zero16); tiny[0] = 0x00000001
pc = run(tiny, 0, RESUME)
assert pc == RESUME, hex(pc)
cases += 1

(build / 'unit-test-results.json').write_text(json.dumps({'cases': cases, 'status': 'pass'}, indent=2))
print(f'all {cases} cases passed')
