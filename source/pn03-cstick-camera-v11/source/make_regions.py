"""Generate regions.py: every address the build scripts use, for GPNJ08 (JP) and GPNE08 (US).

Run from work/:  py -3.13 make_regions.py
It scans the current build scripts for 0x80xxxxxx literals, maps each one to the US build with portmap
(code by instruction-shape matching, data through lis/lo anchors, our own buffer addresses by a constant
shift), applies the manual overrides below, and writes regions.py plus a review table on stdout.
"""
from pathlib import Path
import re, hashlib, json
import portmap as pm

HERE = Path(__file__).parent
SCRIPTS = ('build_camera_v11.py', 'build_move_v19.py', 'build_ed_terrain_v01.py', 'build_sprint_v03.py', 'build_trail_v03.py',
           'build_absorb_v02.py', 'build_nullproj_v01.py', 'build_lead_v01.py', 'build_speed_v01.py')
OURS_LO, OURS_HI = 0x8018C000, 0x80191800      # our bodies / params / config block (JP addresses)
OURS_SHIFT_US = 0x3C00                          # US debug-text buffer is 0x8018BDD0..0x801953D0; we use 0x8018FC00..0x80195300

# Addresses portmap cannot map on its own (reviewed by hand, 2026-10-02).
MANUAL_US = {
    0x8000BAC0: 0x8000BC40,   # BltHitEm+0x114: JP tests flags != 0; US tests bit 0 (MEKA.sym/alignment)
    0x800B5C28: 0x800B788C,   # PlDamageCk(cEm *) entry; MEKA.sym and aligned player code (+0x1C64)
    0x80010448: 0x800105E8,   # shot spawn (register allocation differs in the US build; same prologue)
    0x800814D4: 0x80082D84,   # ESP element allocator (loop bound differs: count - [r13-0x7F60] instead of count - 0x100)
    0x800814F8: 0x80082DA8,   # lwz r0, -0x7ac8(r9)  pool pointer esp_sys+0x8538 (same)
    0x80081500: 0x80082DB0,   # addi r9, r9, -0x7ab8 dummy element esp_sys+0x8548 (same)
    0x8008151C: 0x80082DCC,   # lwz r0, -0x7ac0(r29) pool count esp_sys+0x8540 (same offset, different register)
    0x80199702: 0x8019D682,   # pad C-stick X byte (pad base 0x80199700 -> 0x8019D680)
    0x80000000: 0x80000000, 0x80001800: 0x80001800, 0x80003000: 0x80003000,
    0x80191730: 0x801953D0,   # debug-text buffer end (game constant, not one of ours)
    0x80190000: 0x80190000,   # base for the lis 0x8019 addressing in sprint / trail / absorb (offsets stay in range)
}
# The HUD struct 0x80191BA0 used to be listed above as 0x801957A0 (JP + our 0x3C00 shift). That was wrong: the game data
# past the debug buffer moves by 0x3CA0 like the buffer itself, so the US struct is 0x80195840 and 0x801957A0 is the
# screen-fade table (JP 0x80191B00). It is game data, so it is mapped through the code anchors like any other address.
MANUAL_UNCHECKED = {0x80000000, 0x80001800, 0x80003000, 0x80190000}   # not game data: no anchors to compare against
NOT_ADDRESSES = {0x80ADA580, 0x80D60200,        # instruction word / test value that merely look like addresses
                 0x800817E4, 0x800821A4}        # US-side addresses quoted in build_move_v16.py comments (not JP literals)

NAMED = {   # name: (JP, US)
    'game_id': ('GPNJ08', 'GPNE08'),
    'dol_path': (r'I:\PN03_extracted\sys\main.dol', r'I:\PN03_extracted_usa\sys\main.dol'),
    'r13': (0x8026E820, 0x80275BE0), 'r2': (0x8027E820, 0x80285BE0),
    'root_sda': (-0x74AC, -0x748C), 'esp_sda': (-0x74F4, -0x74D4), 'genpool_sda': (-0x7F58, -0x7F40),
    'gx_sda': (-0x5A80, -0x5A60), 'snap_sda': (-0x7FE0, -0x7FE0),
    'root_player_vec': (0x50, 0x144), 'root_flags': (0x54, 0x148), 'root_flags2': (0x58, 0x14C), 'root_flags3': (0x5C, 0x150),
    'root_motion_table': (0x24, 0x118), 'root_energy': (0x6734, 0x6814), 'root_energy_max': (0x6736, 0x6816),
    'root_hp': (0x6730, 0x6810), 'root_hp_max': (0x6732, 0x6812),
    'root_suit': (0x673A, 0x681A), 'root_debug_page': (0x79C4, 0x7C8C),
    'pad': (0x80199700, 0x8019D680), 'camera_ptr': (0x8016D60C, 0x8017108C), 'camera_request': (0x8016D618, 0x80171098),
    'debug_queue': (0x80187E30, 0x8018BAD0), 'debug_buffer': (0x80188130, 0x8018BDD0), 'debug_buffer_end': (0x80191730, 0x801953D0),
    'config': (0x801916C0, 0x801916C0 + OURS_SHIFT_US), 'ours_shift': (0, OURS_SHIFT_US),
    'substate_table': (0x80172FDC, 0x80176C20), 'shooting_table': (0x801725C4, 0x80176208), 'shooting_ctx': (0x801BD8A0, 0x801C4A98),
    # DOL placement (baked ISO / real hardware): our section sits at the default arena low bound (= _stack_addr + 0x20, the
    # value OSInit uses when the boot info word 0x80000030 is 0) and OSInit's two constants are raised past it.
    'stack_top': (0x802794C0, 0x802808A0), 'arena_lo_default': (0x802794E0, 0x802808C0),
    'dol_section_base': (0x802794E0, 0x802808C0), 'dol_section_size': (0x6000, 0x6000), 'dol_arena_lo': (0x80280000, 0x80287000),
    'arena_lo_sites': ((0x800EAF6C, 0x800EAFA4), (0x800EF87C, 0x800EF8B4)),   # lis r3 / addi r3 pairs in OSInit (default lo, argv variant)
    'bss_clears': (((0x80181F00, 0x8026680C), (0x802672C0, 0x80267B5C)), ((0x80185BA0, 0x8026DBCC), (0x8026E6A0, 0x8026EF3C))),
}

EXTRA_CODE = {0x800A1840: 'sprint_v03 ADVANCE+0xD0', 0x800B5578: 'sprint_v03 FOOTSTEP+0x14', 0x800FC494: 'camera_v06 math helper (lis/ori in asm)', 0x8000B9A8: 'test_ed_terrain FUNC_END (blr of 0x8000B770)', 0x8000B9AC: 'ed object hit test'}
lits = {a: {t} for a, t in EXTRA_CODE.items()}
lits[0x800B5C28] = {'absorb diagnostics: PlDamageCk entry'}
for f in SCRIPTS:
    for m in re.finditer(r'0x80[0-9A-Fa-f]{6}', (HERE / f).read_text(encoding='utf-8')):
        lits.setdefault(int(m.group(0), 16), set()).add(f)
A_US, W_US, notes = {}, {}, []
for a in sorted(lits):
    tag = ','.join(sorted(x.replace('build_', '').replace('.py', '') for x in lits[a]))
    if a in NOT_ADDRESSES:
        continue
    if a in MANUAL_US:
        us = MANUAL_US[a]; how = 'manual'
        if a not in MANUAL_UNCHECKED and not pm.JP.in_text(a):
            # a hand-entered data address must agree with what the game's own lis/lo pairs say, when there are any
            votes, n = pm.map_data(a)
            if votes:
                auto = max(votes.items(), key=lambda kv: len(kv[1]))[0]
                assert auto == us, f'manual {a:08X} -> {us:08X} disagrees with the code anchors: {auto:08X} ({len(votes[auto])}/{n} votes)'
                how = f'manual, anchors agree {len(votes[auto])}/{n}'
    elif OURS_LO <= a < OURS_HI:
        us = a + OURS_SHIFT_US; how = 'ours'
    elif pm.JP.in_text(a):
        us, w, note = pm.match_code(a)
        how = f'code w={w}'
        if us is None:
            notes.append(f'UNMAPPED code {a:08X} [{tag}] {note}'); continue
    else:
        votes, n = pm.map_data(a)
        if not votes:
            notes.append(f'UNMAPPED data {a:08X} [{tag}]'); continue
        us = max(votes.items(), key=lambda kv: len(kv[1]))[0]; how = f'data votes {len(votes[us])}/{n}'
    A_US[a] = us
    if pm.JP.in_text(a) and pm.US.in_text(us):
        W_US[a] = pm.US.word(us)
        d = pm.diff_words(a, us, 1)
        flag = '' if not d else ' <- ' + d[0][3]
        print(f'{a:08X} -> {us:08X}  {pm.JP.word(a):08X}/{W_US[a]:08X}{flag:8s} [{tag}] {how}')
    else:
        print(f'{a:08X} -> {us:08X}  (data) [{tag}] {how}')
for n in notes:
    print(n)

sha = {k: hashlib.sha256(Path(v).read_bytes()).hexdigest() for k, v in zip(('JP', 'US'), NAMED['dol_path'])}
out = ['"""Per-region addresses for the P.N.03 patches (generated by make_regions.py; edit MANUAL_US / NAMED there).', '',
       'Select the region with the environment variable PN03_REGION (JP = GPNJ08, default; US = GPNE08).', '"""', 'import os', '',
       f"DOL_SHA256 = {json.dumps(sha)}", '']
out.append('NAMED = {')
for k, (j, u) in NAMED.items():
    def fmt(v):
        if isinstance(v, str):
            return repr(v)
        if isinstance(v, tuple):
            return '(' + ', '.join(fmt(x) for x in v) + ('),' if len(v) == 1 else ')')
        return f'{v:#x}' if v >= 0 else f'-{-v:#x}'
    out.append(f"    {k!r}: ({fmt(j)}, {fmt(u)}),")
out.append('}')
out.append('A_US = {  # JP address -> US address')
for a, u in A_US.items():
    out.append(f'    {a:#010x}: {u:#010x},')
out.append('}')
out.append('W_US = {  # JP address -> US instruction word at the mapped address')
for a, u in W_US.items():
    out.append(f'    {a:#010x}: {u:#010x},')
out.append('}')
out.append('''

def hi(a):
    """lis immediate for a signed lo pair (addi / lwz ...)."""
    return ((a + 0x8000) >> 16) & 0xFFFF


def lo(a):
    v = a & 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def hiu(a):
    """lis immediate for an ori pair."""
    return (a >> 16) & 0xFFFF


def lou(a):
    return a & 0xFFFF


_US2JP = {u: j for j, u in A_US.items()}


class Region:
    def __init__(self, name, placement='onframe'):
        assert name in ('JP', 'US'), name
        assert placement in ('onframe', 'dol'), placement
        self.name = name
        self.placement = placement
        self.idx = 0 if name == 'JP' else 1
        for k, pair in NAMED.items():
            setattr(self, k, pair[self.idx])
        self.dol_sha256 = DOL_SHA256[name]
        self.suffix = ('' if name == 'JP' else '-us') + ('' if placement == 'onframe' else '-dol')
        if placement == 'dol':
            # bodies, params and the config block all move into the new DOL section (JP OnFrame layout + shift)
            self.ours_shift = self.dol_section_base - 0x8018C000
            self.config = 0x801916C0 + self.ours_shift

    def a(self, jp_addr):
        """Translate a JP OnFrame-layout address (code, data or one of our own buffer addresses)."""
        if 0x8018C000 <= jp_addr < 0x80191800:
            return jp_addr + self.ours_shift
        if self.name == 'JP':
            return jp_addr
        if jp_addr in A_US:
            return A_US[jp_addr]
        raise KeyError(f'no US mapping for {jp_addr:#010x}')

    def w(self, addr, jp_word):
        """Expected instruction word at the translated address; `addr` may be the JP address or the translated one.
        `jp_word` (int or hex string) is returned unchanged for JP."""
        if self.name == 'JP':
            return jp_word
        v = W_US.get(addr)
        if v is None:
            v = W_US[_US2JP[addr]]
        return f'{v:08x}' if isinstance(jp_word, str) else v


R = Region(os.environ.get('PN03_REGION', 'JP'), os.environ.get('PN03_PLACEMENT', 'onframe'))
''')
(HERE / 'regions.py').write_text('\n'.join(out), encoding='utf-8')
print(f'wrote regions.py: {len(A_US)} addresses, {len(W_US)} words; SHA {sha}')
