"""Inspect the P.N.03 effect (ESP) system in a main-RAM image (0x80000000..0x81800000, 24 MB).

Usage: py -3.13 esp_inspect.py <mram.bin> [--all]

Prints the player, the Sprint Run / Sprint Trail parameter blocks, the effect group table,
(element pool = [esp_sys + 0x8538], count at +0x8540, 0x150 per element),
the live generators and the live elements (with --all also free slots that still hold data).
Get the image with dolphin_savestate_mram.py from a Dolphin savestate, or from Dolphin's
Memory widget "Dump MRAM" (Dump/ram.raw).
"""
import struct, sys
from pathlib import Path

m = Path(sys.argv[1]).read_bytes()
show_all = '--all' in sys.argv
assert len(m) >= 0x1800000, 'expected a 24 MB MRAM image'
R13 = 0x8026E820


def ok(a): return 0x80000000 <= a < 0x80000000 + len(m)
def rw(a): return struct.unpack_from('>I', m, a - 0x80000000)[0]
def rh(a): return struct.unpack_from('>H', m, a - 0x80000000)[0]
def rb(a): return m[a - 0x80000000]
def rf(a): return struct.unpack_from('>f', m, a - 0x80000000)[0]
def hx(a, n): return m[a - 0x80000000:a - 0x80000000 + n].hex()
def fourcc(v): return v.to_bytes(4, 'big').decode('ascii', 'replace')


print('== player')
root = rw(R13 - 0x74AC)
player = None
try:
    player = rw(rw(rw(root + 0x50)))
    print(f'root {root:08X} player {player:08X} cat/sub/phase {rb(player + 0xF8)}/{rb(player + 0xF9)}/{rb(player + 0xFA)} '
          f'pos ({rf(player + 0xC0):.0f}, {rf(player + 0xC4):.0f}, {rf(player + 0xC8):.0f}) yaw {rf(player + 0xD0):.3f} parts {rw(player + 0xF0):08X} x{rb(player + 0xFE)}')
except Exception as e:
    print('player not resolvable:', e)

print('== patch parameter blocks')
for name, addr, layout in (
        ('Sprint Run v0.3 (SPR3)', 0x8018DD80, [('flags', 4, 'u'), ('threshold', 8, 'u'), ('ramp', 0xC, 'u'), ('max', 0x10, 'f'), ('turn', 0x14, 'f'), ('dist', 0x18, 'f'),
                                                ('counter', 0x20, 'u'), ('tag', 0x24, 'u'), ('acc', 0x2C, 'f'), ('factor', 0x30, 'f'), ('player', 0x34, 'x'), ('footsteps', 0x38, 'u')]),
        ('Sprint Trail v0.1 (TRL1)', 0x8018D300, [('flags', 4, 'u'), ('target', 8, 'x'), ('match', 0xC, 'x'), ('t', 0x14, 'f'), ('tinted', 0x18, 'u'), ('last_def', 0x1C, 'x')]),
        ('Sprint Trail v0.2 (TRL2)', 0x8018D700, [('flags', 4, 'u'), ('target', 8, 'x'), ('match', 0xC, 'x'), ('id', 0x10, 'x'), ('t', 0x14, 'f'), ('tinted', 0x18, 'u'), ('dirty', 0x1C, 'u'), ('total', 0x20, 'u')])):
    marker = rw(addr)
    fields = []
    for fname, off, kind in layout:
        v = rw(addr + off)
        fields.append(f'{fname}={rf(addr + off):.4f}' if kind == 'f' else f'{fname}={v:#x}' if kind == 'x' else f'{fname}={v}')
    print(f'  {name} @{addr:08X} marker {fourcc(marker)!r} ' + ' '.join(fields))
for name, addr in (('Sprint Trail v0.1 body', 0x8018D000), ('Sprint Trail v0.2 body', 0x8018D400), ('Sprint Run body', 0x8018D800), ('ED terrain body', 0x8018DF00)):
    print(f'  {name} @{addr:08X} first words {hx(addr, 16)}')
for name, addr in (('trail v0.1 hook 0x8008E470', 0x8008E470), ('trail v0.2 hook 0x800AFE7C', 0x800AFE7C), ('sprint hook1 0x800AFE78', 0x800AFE78), ('sprint hook2 0x800A08E8', 0x800A08E8)):
    print(f'  {name}: {hx(addr, 4)}')

print('== effect groups')
esp = rw(R13 - 0x74F4)
print(f'esp_sys {esp:08X}')
records = {}
if ok(esp):
    for g in range(46):
        ent = esp + g * 12 + 0x80B8
        base, idt, st = rw(ent), rw(ent + 4), rw(ent + 8)
        if st == 0x2D and not ok(base):
            continue
        n = rw(idt) if ok(idt) else -1
        ids = [rh(idt + 8 * i + 4) for i in range(min(max(n, 0), 300))]
        print(f'  group {g:#04x} owner {rw(esp + g * 4):08X} base {base:08X} status {st} ids({n}): ' + ' '.join(f'{i:X}' for i in ids))
        for i, id_ in enumerate(ids):
            records[base + rw(base + 4 + i * 4)] = (g, id_)

print('== generators (in use)')
gen_base, gen_n = rw(R13 - 0x7F58), rw(R13 - 0x7F54)
print(f'pool {gen_base:08X} x{gen_n}')
if ok(gen_base):
    for i in range(gen_n):
        g = gen_base + i * 0xA8
        if not (rb(g + 0xC) & 1):
            continue
        rec = rw(g + 0x30)
        tag = records.get(rec, ('?', '?'))
        print(f'  gen {g:08X} flags {rb(g + 0xC):02X}/{rb(g + 0xD):02X} owner {rw(g + 0x14):08X} record {rec:08X} = group {tag[0]} id {tag[1]} parent {rw(g + 0x34):08X} '
              f'list {rw(g + 0x1C):08X} pos ({rf(g + 0x74):.0f}, {rf(g + 0x78):.0f}, {rf(g + 0x7C):.0f})')

print('== elements')
if ok(esp):
    cnt = rw(esp + 0x8540)
    pool = rw(esp + 0x8538)          # pointer to the element pool; esp_sys + 0x8548 is the dummy element returned when the pool is full
    print(f'pool {pool:08X} x{cnt} (dummy element {esp + 0x8548:08X})')
    live = 0
    for i in range(cnt):
        e = pool + i * 0x150
        fl = rb(e + 0x18)
        if not (fl & 1) and not show_all:
            continue
        if not (fl & 1) and rw(e + 0x88) == 0:
            continue
        live += 1 if fl & 1 else 0
        parent = rw(e + 0x24)
        who = 'PLAYER' if parent == player else f'{parent:08X}'
        cf = struct.unpack_from('>4f', m, e + 0x8C - 0x80000000)
        print(f'  el[{i:4d}] {e:08X} flags {fl:02X} id {rb(e + 0x19):#04x} parent {who} parts {rb(e + 0x30):#04x} gen {rw(e + 0x14):08X} '
              f'start {hx(e + 0x88, 4)} live ({cf[0]:.1f}, {cf[1]:.1f}, {cf[2]:.1f}, a {cf[3]:.1f}) blend {hx(e + 0xAC, 4)} life {rh(e + 0xB8)}/{rh(e + 0xBA)} '
              f'pos ({rf(e + 0x34):.0f}, {rf(e + 0x38):.0f}, {rf(e + 0x3C):.0f})')
    print(f'live elements: {live}')
