"""Read the Dodge Absorb state out of a main-RAM image (dolphin_live_mram.py or dolphin_savestate_mram.py output).

Prints, for the region selected by PN03_REGION: whether the three hooks and the per-frame chain are installed, whether
the body in RAM matches the build, the parameter block with its runtime counters (frame, steps, hits_seen, absorbed,
fx_spawned ...), the player's state, the energy, and the gauge struct the game uses next to the one the body passes.

Usage (from work/):  [PN03_REGION=US] py -3.13 absorb_inspect.py <mram.bin> [build dir]
"""
import sys, json, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
from regions import R, lo
import dol

img = Path(sys.argv[1]).read_bytes()
build = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent / ('absorb-v02-build' + R.suffix)
m = json.loads((build / 'manifest.json').read_text())
code = (build / 'absorb.bin').read_bytes()


def rw(a): return int.from_bytes(img[a - 0x80000000:a - 0x80000000 + 4], 'big')
def rh(a): return int.from_bytes(img[a - 0x80000000:a - 0x80000000 + 2], 'big', signed=True)
def rb(a): return img[a - 0x80000000]
def ok(a): return 0x80000000 <= a < 0x81800000


gid = img[:6].decode(errors='replace')
print(f'image game id {gid} (region setting {R.game_id})')
assert gid == R.game_id, 'set PN03_REGION to match the image'

print('--- hooks')
for label, hook, orig in (('per-frame', m['hook0'], m['orig0']), ('shot hit', m['hook_a'], m['orig_a']), ('area hit', m['hook_b'], m['orig_b'])):
    cur, want = rw(hook), m['hook_words'][hex(hook)]
    state = 'installed' if cur == want else 'ORIGINAL (not hooked)' if cur == orig else 'OTHER'
    print(f'  {label:9s} {hook:08X}: {cur:08X}  {state}')
if 'hurtbox_hook' in m:
    hook = m['hurtbox_hook']
    print(f"  hurtbox gate {hook:08X}: {rw(hook):08X}  {'installed' if rw(hook) == m['hook_words'][hex(hook)] else 'NOT installed'}")
chain = [('sprint', 0x800AFE78, 0x8018D800), ('trail', 0x800AFE7C, 0x8018D400), ('absorb', 0x800AFE80, 0x8018C800), ('lead', 0x800AFE84, 0x8018C100)]
for label, jp_hook, jp_body in chain:
    hook, body = R.a(jp_hook), R.a(jp_body)
    w = rw(hook)
    d = w & 0x03FFFFFC
    d = d - 0x04000000 if d & 0x02000000 else d
    tgt = hook + d if w >> 26 == 18 else None
    print(f'  chain {label:6s} {hook:08X}: {w:08X}' + (f' -> {tgt:08X} {"(body)" if tgt == body else "(NOT the body %08X)" % body}' if tgt else '  not a branch'))

print('--- body vs build')
base = m['region']
diff = [(base + o, rw(base + o), int.from_bytes(code[o:o + 4], 'big')) for o in range(0, len(code), 4) if rw(base + o) != int.from_bytes(code[o:o + 4], 'big')]
print(f'  {len(code) // 4} words, {len(diff)} differ from {build.name}')
for a, cur, want in diff[:12]:
    print(f'    {a:08X}: RAM {cur:08X}  build {want:08X}')

if 'diagnostics' in m:
    diag = m['diagnostics']
    blob = (build / diag['code_file']).read_bytes()
    addr = diag['code_address']
    differences = sum(rw(addr + o) != int.from_bytes(blob[o:o + 4], 'big') for o in range(0, len(blob), 4))
    print(f'--- diagnostic body: {len(blob) // 4} words, {differences} differ')
    for h in diag['hooks']:
        print(f"  {h['label']}: {rw(h['address']):08X} {'installed' if rw(h['address']) == h['word'] else 'NOT installed'}")
    for name, addr in diag['params'].items():
        value = rw(addr)
        extra = ''
        if name.endswith('_state'):
            extra = f'  category/substate/invincibility {value >> 24}/{(value >> 16) & 255}/{value & 255}'
        print(f'  {name:20s} {addr:08X}: {value:08X} ({value}){extra}')

print('--- parameters')
P = m['params']
for name, addr in P.items():
    v = rw(addr)
    extra = ''
    if name == 'marker':
        extra = '  ' + repr(v.to_bytes(4, 'big')) + ('' if v == m['marker'] else '  (NOT initialised)')
    print(f'  {name:15s} {addr:08X}: {v:08X} ({v}){extra}')

print('--- game state')
root = rw(R.r13 + R.root_sda)
print(f'  root {root:08X}')
if ok(root):
    print(f'  HP {rh(root + R.root_hp)} / {rh(root + R.root_hp_max)}')
    energy, emax = rh(root + R.root_energy), rh(root + R.root_energy_max)
    print(f'  energy {energy} / {emax}')
    vec = rw(root + R.root_player_vec)
    player = rw(rw(vec)) if ok(vec) and ok(rw(vec)) else 0
    print(f'  player (root vector) {player:08X}, params.player {rw(P["player"]):08X}')
    if ok(player):
        print(f'  player category/substate/phase {rb(player + 0xF8)}/{rb(player + 0xF9)}/{rb(player + 0xFA)}, invincibility counter {rb(player + 0x4E1)}, damage acc {rw(player + 0x4F0)}')
        record, visited = player + 0x474, set()
        while ok(record) and record not in visited and len(visited) < 32:
            visited.add(record)
            flags = rh(record + 0x24) & 0xFFFF
            print(f'  hurtbox {record:08X}: flags {flags:04X}, retail eligible {bool(flags & 1) if R.name == "US" else bool(flags)}')
            record = rw(record + 0x34)
orb = R.a(0x800A84FC)
lis_w, addi_w = int.from_bytes(dol.read(orb - 4, 4), 'big'), int.from_bytes(dol.read(orb, 4), 'big')
game_hud = ((lis_w & 0xFFFF) << 16) + lo(addi_w)
print(f'--- gauge struct: the game passes {game_hud:08X}, the build passes {m["hud_struct"]:08X}')
for label, hud in {'game': game_hud, 'build': m['hud_struct']}.items():
    print(f'  {label:5s} {hud:08X}: flags {rw(hud + 4):08X}  shown {rw(hud + 0x2C)}  target {rw(hud + 0x30)}  step {rw(hud + 0x34)}')
