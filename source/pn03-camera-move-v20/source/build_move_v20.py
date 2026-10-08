"""Build the camera-relative movement v0.20 for GPNJ08 (P.N.03 Japan).
v0.20 (2026-10-08): the tuning menu loses the RUN / HOLD toggle (Y) and the MODE text on line 3 (user:
"nobody else needs to touch it"; RUN has been the confirmed behaviour since v0.11 and HOLD only existed
for the A/B comparison). Line 3 now reads "JUMP WIN nn A/B". Y is still cleared from the pad words in
tuning mode so Vanessa does not crouch. Config flags bit2 (hold) can no longer be set from the menu;
the hold branches of the jump window stay in the code but are unreachable (a fresh block clears
flags), so the window always runs the RUN rule. The four data words that held the mode strings are
gone (the words after them move up by 0x10).
v0.19 (2026-10-08): the Z-turn camera request is sent on the turn's first frame and the camera paces the
swing itself. The live sample showed the 180-degree turn rotating her 18 degrees per frame on average
(peak 26.6), so the constant 12-degree step of v0.17/v0.18 left the camera 84 degrees behind when she
had finished and it arrived 7 frames later (user: "the follow seems a little late"). Now the entry frame
(sub-state 8 phase 0) writes config +0x30 = wrap(her yaw + rotation), +0x38 = 0 and raises flags bit3 and
bit5 (0x20, "paced"); camera v0.11 then measures her yaw change every frame and turns by exactly that
amount, one frame behind her, in her spin direction. The direction detection of v0.17 and the words
turn_cam_step / turn_detect are gone. The end-of-turn follow (follow_frames = 1) now fires when the
camera lock countdown (`stick_block`) runs out, two frames after the turn state ends, so the paced swing
has finished before the follow checks her final facing.
v0.18 (2026-10-08): two fixes found with a live sample of her yaw during Z turns (sample_turn.py).
(1) The "90-degree" turn motions rotate her by 80.64 degrees (112 steps of 0.72 degrees, eased), the
180-degree turn by exactly 180; the quarter-turn request now aims at +-`turn_quarter` (80.64 degrees)
instead of +-90, so the end-of-turn follow has nothing left to correct. (2) The C-stick is held to
select the quarter turn, and it is also the free camera input: while held it rotated the camera about
10 degrees per frame and (as any C-stick push does) cancelled the turn's swing, so the camera overshot
her final facing by the time the stick was released and the end-of-turn follow pulled it back ("hit by
a counter", user report). The hook now raises config flags bit4 (0x10, camera lock) on every frame of
the turn state and for `stick_block` (2) frames after it; camera v0.10 ignores the C-stick entirely
while bit4 is set. Runtime word data +0xA0 stick_block (countdown).
v0.17 (2026-10-08): the camera request for the Z quick turn aims at her *final* facing instead of
following her current facing every frame (user report: a 180-degree turn started while she faces the
camera made the camera swing out and come back, "double processing"; the old per-frame follow chased
her intermediate facings by the shortest path). On the turn's first frame (sub-state 8 phase 0) the
hook records her yaw and the chosen motion's rotation (+pi for the plain turn, +pi/2 / -pi/2 for the
C-stick left / right turns) in its own data words. On the first later frame in which her yaw has moved
by more than `turn_detect` (0.5 degrees) the hook knows the spin direction and sends one camera yaw
request (config +0x30 = entry yaw + rotation, flags bit3) together with a signed camera step in the
new config word +0x38 (`turn_cam_step`, 12 degrees per frame, negative for a clockwise spin). Camera
v0.9 turns toward that goal at that step, in the spin direction when the goal is (almost) opposite
and by the shortest path otherwise; a goal that is already where the camera is means no motion at
all. The follow flag (bit1) is no longer raised during the turn; when the turn state ends the hook
sets follow_frames = 1 so one follow frame removes the animation's rounding. The X lock-on request
writes 0 to +0x38 (camera default step). Runtime words: data +0x8C turn_state (0 idle, 1 turning
with the direction unknown, 2 request sent), +0x90 entry yaw, +0x94 rotation; their patch lines write
0 only while the word is 0.

v0.15 plus the camera-relative crouch (user report, 2026-10-02: "while crouching, the movement
stick's left/right does something odd; make it behave like the L/R sidestep triggers, and take
care of diagonals too"). In the crouch state (sub-state 5, Y held) the game's phase 2 reads the raw
RC op-word bits: L/R triggers -> sidestep (sub-state 2 phase 8 / 0xA), UP -> crouch step forward
(sub-state 0xD phase 0), DOWN -> back step (0xD phase 2), LEFT/RIGHT -> turn in place (sub-state
0xB phase 3). The hook never converted the stick there, so the sector bits of the raw stick went
through and a sideways push produced the crouched turn (which the exploration rules then hijacked),
and diagonals picked whichever bit the game tests first. v0.16: with Y held and no trigger edge,
the stick direction is taken relative to Vanessa's facing (camera-relative intended direction minus
her yaw) and turned into exactly one crouch action: within `crouch_sector` (45 deg) of her facing
-> UP (forward step), beyond 180 - 45 deg -> DOWN (back step), otherwise the L or R trigger bits
(crouch sidestep to that side). The raw UP/DOWN/LEFT/RIGHT bits are cleared, her yaw is untouched.
A trigger edge in the same frame wins and follows the v0.15 rule. With Y released (standing up)
the exploration rules apply so the stand-up flows into a correctly oriented run.

v0.14 plus the screen-relative sidestep outside the exploration states (user report,
2026-10-02: "while shooting facing the camera, a sidestep goes to Vanessa's left/right
like the original RC controls"). The idle / run / turn / back-walk states (sub-states
0, 1, 0xB, 0xC) snap her facing to the camera yaw before the sidestep (v0.7), but the
shooting posture (sub-state 4) reaches the sidestep through its own transition routine
0x800AF950 (phase 4: L -> sidestep phase 0, R -> phase 2 from the op word's 0x8000 bit)
and the sidestep state itself chains further steps (0x800B13B0 / 0x800B14D8 / 0x800B1808,
reading 0x8000 / 0x4000), so there the step stayed relative to her facing. The hook
now swaps the L / R op-word bits (0x20000 <-> 0x10000, 0x8000 <-> 0x4000) in every
other category-1 sub-state when |wrap(facing - camera yaw)| > 90 degrees, i.e. when
her left is the screen's right. Her facing is not touched (she keeps aiming). The
default camera sensitivity is now 0.0036 (6x, the user's 2026-10-01 choice; the
`-sens6` patch variants are no longer needed).

v0.13 plus the X lock-on camera (user's idea): X cycles the lock-on target in the
original game (player update 0x800AFCF8: target list at player+0xC48, 12-byte entries
sorted by distance, count at player+0xDC8, index at +0xDCA, current target pointer at
player+0x5B4). The hook adds: X pressed with no targets -> follow_frames = 1 (camera
behind Vanessa); with targets -> pending_focus, and on the next frame the camera yaw
request (config +0x30, flags bit3) is set to the direction from Vanessa to the current
target's aim point (0x8009EFB0(target+0xF0, target+0x125) -> +0x108; fallback +0xC0).
Camera v0.6 applies the request once. Config version 3 adds +0x2C follow_frames,
+0x30 camera_yaw_request, +0x34 pending_focus.

v0.11 plus the Z quick turn driven by the C-stick (user's design): the game's Z-turn
entry (sub-state 8, phase 0, 0x800B29B4) picks the 90-degree left/right motion from the
pad buttons word's LEFT/RIGHT stick-sector bits (0x10000 / 0x20000). On that frame the
hook clears those bits and sets them from the C-stick X byte instead (< -40 left,
> 40 right, otherwise the 180-degree turn). The movement stick never influences the
turn, so it keeps its zero-frame response; the camera follows the yaw during the turn
(flags bit1) and ends up behind her, so the view turns 90 degrees with her.

v0.10 plus: the chord window applies only while the left stick is in the game's own
DOWN sector (pad buttons word bit 0x40000, within 70 deg of straight down), because
only that input can turn a chord into a back jump. Up / left / right pushes convert
immediately even within the window, and a B after them is a running jump (forward
jump in the run direction) instead of the camera-frame chord.

v0.9 plus the window fix from the playtest (2026-09-24): the user confirmed that the
v0.9 RC pass-through started the game's own back-walk (sub-state 0xC) / turn in place
(0xB) motions during the window, which were then cut at the end of the window (a
one-frame "faces front" glitch). v0.10 never routes the stick to those states: during
the window it either converts immediately (no extra flicker for a chord), passes UP
only when the stick is within 45 deg of the facing (same run motion as afterwards, so
no cut), or holds. Mode text RUN / HOLD (flags bit2 = hold).

v0.8 plus the chord-window changes from the playtest (2026-09-24):
  * Default jump window 4 frames (user: no misfires up to 4, back jump feels right).
  * No more input lag during the window: instead of clearing the direction bits
    ("hold"), the stick is converted to player-relative 8-way bits and passed to the
    game's own RC states (run forward / back-walk / turn in place), so Vanessa reacts
    immediately without turning. If turning toward the stick would not add any
    flicker for a chord (the stick direction lies on the arc from her yaw to the
    camera yaw) the camera-relative conversion is applied right away.
  * Config flags bit2 (0x4) = hold mode (the v0.8 behaviour) for comparison; Y toggles
    it in tuning mode and line 3 shows MODE RC / HOLD. Y is cleared from the pad words.
Everything below is v0.8 (camera-relative running, C-stick exclusivity, follow flag,
D-pad sensitivity steps, jump window / pending jump kinds, sidestep yaw snap, A/B
window tuning, three debug text lines). What changes is delivery and placement:

  * Dolphin's Gecko code list only has about 3.2 KB (0x80001800..0x80003000 minus the
    2,880-byte code handler). v0.7 (2,976 bytes) plus camera v0.4 (936 bytes) did not
    fit and Dolphin silently skipped v0.7 ("Too many GeckoCodes"). The body is now
    written by Dolphin [OnFrame] patches (conditional dword writes, applied only while
    the target word is still zero) into the top of the retail debug-text bump buffer
    (0x80188130..0x80191730; only the debug text allocator touches it), and the hook
    instruction is replaced by a branch to it (conditional on the original word).
    The body ends with the original instruction and a branch back to hook+4.
  * The config block moves from 0x817FFF00 to 0x801916C0. The apploader places the
    FST at (0x81800000 - FST size) & ~31 = 0x817FCC40..0x817FFFF6, so the old block
    sat inside the FST string table (room archive names ra13/stb/rb00..).
This does not modify the original DOL or ISO.
"""
from pathlib import Path
import struct, sys, json, hashlib, math
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
from keystone import Ks, KS_ARCH_PPC, KS_MODE_PPC32, KS_MODE_BIG_ENDIAN
from dol import read, md
from regions import R, hi, lo, hiu, lou

HOOK = R.a(0x800AFBBC)
ORIGINAL = R.w(0x800AFBBC, 0x816D8B54)            # lwz r11, -0x74ac(r13)
GUARD_BEFORE = (R.a(0x800AFBB8), R.w(0x800AFBB8, 0x48004BFD))   # bl 0x800b47b4
GUARD_AFTER = (R.a(0x800AFBC0), R.w(0x800AFBC0, 0x800B0058))    # lwz r0, 0x58(r11)
REGION = R.a(0x8018E000)              # body load address (top part of the debug text bump buffer)
REGION_END = R.a(0x80191000)          # exclusive; camera v0.5 lives above
CONFIG = R.config
MAGIC = 0x504E3034
CONFIG_VERSION = 3
CFG_HI = ((CONFIG + 0x8000) >> 16) & 0xFFFF
CFG_LO = CONFIG - (CFG_HI << 16)
assert -0x8000 <= CFG_LO < 0x8000 and CFG_LO + 0x3C < 0x8000
FIELDS = {'magic': 0, 'version': 4, 'sensitivity': 8, 'camera_deadzone': 12, 'deadzone_sq': 16, 'sign': 20,
          'offset': 24, 'flags': 28, 'jump_window': 32, 'push_frames': 36, 'pending_jump': 40,
          'follow_frames': 44, 'cam_yaw_request': 48, 'pending_focus': 52, 'cam_yaw_step': 56}
C = {k: CFG_LO + v for k, v in FIELDS.items()}
RESERVED = [CFG_LO + o for o in range(60, 64, 4)]
AIM_POINT = R.a(0x8009EFB0)
assert read(AIM_POINT, 4).hex() == R.w(AIM_POINT, '3924ffff') and read(R.a(0x800AFCF8), 4).hex() == R.w(0x800AFCF8, 'a11e085c')
ATAN2F = R.a(0x800DEDB0)
DEBUG_PRINTF = R.a(0x80080178)
SET_DEBUG_PAGE = R.a(0x80080164)
CAMERA_PRESET_ROUTINE = R.a(0x800AC128)
JUMP_HANDLER = R.a(0x800B1854)
TRANSITION_CHECKER = R.a(0x800B5230)
TEXT_X, TEXT_Y1, TEXT_Y3, TEXT_Y2 = 16, 396, 412, 428
# Text encoding per build: the JP debug drawer (0x800809C4) only draws 2-byte Shift-JIS characters (ASCII comes out
# blank), so the JP lines are full-width. The US drawer (0x800821A4) hands each character to OSGetFontTexture, which
# uses the ANSI encoding / western IPL font on a US console or in Dolphin, so the US lines are plain ASCII.
ASCII_TEXT = R.name == 'US'
CH = 1 if ASCII_TEXT else 2          # bytes per displayed character
ZERO_CH, DOT_CH = ('0', '.') if ASCII_TEXT else ('０', '．')
US_CW = 16                           # US record cell width (see the drawer geometry note below)

# US only: DebugPrintf (0x800817E4) zeroes the record's +0xA byte and the US drawer (0x800821A4) draws a record only
# when that byte is non-zero (the JP drawer has no such flag), so the three records we just queued are flagged
# visible: scan the debug queue (R.debug_queue, up to 192 pointers) and set +0xA = 1 on the last three entries.
FLAG_RECORDS = '' if not ASCII_TEXT else f'''
lis 9,{hi(R.debug_queue)}
addi 9,9,{lo(R.debug_queue)}
li 10,0
dq_scan:
lwz 0,0(9)
cmpwi 0,0
beq dq_end
addi 9,9,4
addi 10,10,1
cmpwi 10,192
blt dq_scan
dq_end:
li 11,3
dq_flag:
cmpwi 10,0
ble dq_done
cmpwi 11,0
ble dq_done
addi 9,9,-4
addi 10,10,-1
addi 11,11,-1
lwz 8,0(9)
li 7,1
stb 7,10(8)
li 7,{US_CW}
stb 7,8(8)
b dq_flag
dq_done:
'''


def fw(s):
    if ASCII_TEXT:
        return s.replace(' ', '  ')      # a native space is 5 px in the western font; two of them read like the JP full-width space
    return ''.join('　' if c == ' ' else chr(ord(c) + 0xFEE0) for c in s)


# US drawer geometry: each glyph is drawn into a record-cw x record-lh quad and x advances by glyph_width * cw / cell (24).
# DebugPrintf's default cw = 8 squeezes the 24 px cell to a third; 16 matches the JP look (16 x 14 quads).
WESTERN_WIDTHS = {' ': 5, '!': 5, '"': 8, '#': 13, '$': 11, '%': 17, '&': 14, "'": 5, '(': 6, ')': 6, '*': 11, '+': 11, ',': 5, '-': 6,
                  '.': 5, '/': 7, '0': 11, '1': 11, '2': 11, '3': 11, '4': 11, '5': 11, '6': 11, '7': 11, '8': 11, '9': 11, ':': 5,
                  ';': 5, '<': 11, '=': 11, '>': 11, '?': 9, '@': 17, 'A': 13, 'B': 12, 'C': 12, 'D': 14, 'E': 11, 'F': 10, 'G': 14,
                  'H': 13, 'I': 7, 'J': 6, 'K': 11, 'L': 10, 'M': 17, 'N': 14, 'O': 16, 'P': 12, 'Q': 16, 'R': 12, 'S': 11, 'T': 11,
                  'U': 13, 'V': 12, 'W': 18, 'X': 11, 'Y': 11, 'Z': 11}   # IPL font_western.bin width table (cell 24 px)


def us_px(line):
    return sum(int(WESTERN_WIDTHS[c] * US_CW / 24) for c in line)


LINE1_PREFIX = fw('DEBUG CAM SENS 0.')
LINE1_MID = fw(' X')


LINE2 = fw('DPAD=SENS X=RESET L+R+Z=EXIT')
LINE3_PREFIX = fw('JUMP WIN ')
LINE3_MID = fw(' A/B')
LINE3_SUFFIX = fw('')
if ASCII_TEXT:
    for _line in (LINE1_PREFIX + '0000' + LINE1_MID + '00.00', LINE3_PREFIX + '00' + LINE3_MID + LINE3_SUFFIX, LINE2):
        assert 16 + us_px(_line) <= 496, (_line, us_px(_line))     # 512 px orthographic screen, text starts at x = 16
else:
    assert len(LINE2) <= 31 and len(LINE3_PREFIX) + 2 + len(LINE3_MID) + len(LINE3_SUFFIX) <= 31
DEFAULTS = dict(camera_sensitivity=0.0036, camera_deadzone=10.0, move_deadzone_squared=900.0,
                move_stick_sign=1.0, move_camera_offset=0.0, jump_window=4)
ARC_EPSILON = 0.02
PACED_FLAG_BIT = 0x20      # v0.19: config flags bit5, sent with bit3: the camera paces the swing to her rotation
TURN_QUARTER_DEG = 80.64   # v0.18: the quarter-turn motions' real rotation (112 x 0.72 degrees, sampled 2026-10-08)
STICK_BLOCK_FRAMES = 2     # v0.18: frames after the turn state during which the camera still ignores the C-stick   # radians of extra turn tolerated before the window falls back to RC pass-through
JUMP_WINDOW_MAX = 30
COUNTER_MAX = 1000
assert int.from_bytes(read(HOOK, 4), 'big') == ORIGINAL
assert int.from_bytes(read(GUARD_BEFORE[0], 4), 'big') == GUARD_BEFORE[1]
assert int.from_bytes(read(GUARD_AFTER[0], 4), 'big') == GUARD_AFTER[1]
assert read(ATAN2F, 4).hex() == R.w(ATAN2F, '9421ffe8')
assert read(DEBUG_PRINTF, 4).hex() == R.w(DEBUG_PRINTF, '9421ff40')
assert read(SET_DEBUG_PAGE, 4).hex() == R.w(SET_DEBUG_PAGE, '812d8b54')
assert read(CAMERA_PRESET_ROUTINE, 4).hex() == R.w(CAMERA_PRESET_ROUTINE, '9421ff38')
assert read(R.a(0x800AC1C8), 4).hex() == R.w(0x800AC1C8, '80099714')   # the preset routine reads the pressed word
assert read(JUMP_HANDLER, 4).hex() == R.w(JUMP_HANDLER, '9421ffa8')
assert read(R.a(0x800B191C), 4).hex() == R.w(0x800B191C, '801d008c')   # jump entry reads the control word
assert read(R.a(0x800B1920), 4).hex() == R.w(0x800B1920, '70090001')   # UP -> forward jump
assert read(R.a(0x800B1970), 4).hex() == R.w(0x800B1970, '70090002')   # DOWN -> back jump
assert read(TRANSITION_CHECKER, 4).hex() == R.w(TRANSITION_CHECKER, '9421fff0')
assert read(R.a(0x800B5358), 4).hex() == R.w(0x800B5358, '75200003')   # sidestep trigger: control word bits 0x30000
assert read(R.a(0x80080588), 4).hex() == R.w(0x80080588, '3d208019') and read(R.a(0x8008058c), 4).hex() == R.w(0x8008058c, '39291730')   # bump limit 0x80191730
assert read(R.a(0x800805b8), 4).hex() == R.w(0x800805b8, '39298130')                                                # bump base 0x80188130

ks = Ks(KS_ARCH_PPC, KS_MODE_PPC32 | KS_MODE_BIG_ENDIAN)


def fword(f):
    return struct.unpack('>I', struct.pack('>f', f))[0]


def sjis(s):
    b = s.encode('ascii' if ASCII_TEXT else 'cp932')
    assert not any(x in (0x00, 0x0A, 0x25) for x in b), 'text must not contain NUL, LF or %'
    return b


FRAME = 416
lines = []


def emit(s):
    lines.extend(s.strip().splitlines())


emit(f'''
stwu 1,-{FRAME}(1)
stw 0,8(1)
''')
for r in range(3, 13):
    emit(f'stw {r},{12 + (r - 3) * 4}(1)')
emit('''
mflr 0
stw 0,52(1)
mfcr 0
stw 0,56(1)
mfctr 0
stw 0,60(1)
mfxer 0
stw 0,64(1)
mfspr 0,912
stw 0,68(1)
li 0,0
mtspr 912,0
''')
for f in range(14):
    o = 80 + f * 16
    emit(f'stfd {f},{o}(1)')
    emit(f'.long 0x{(60 << 26) | (f << 21) | (1 << 16) | (o + 8):08x}')  # psq_st
emit('''
mffs 0
stfd 0,72(1)
nop
bl data_end
data:
''')
DATA = [
    ('last_camera_yaw', 0x00000000),                          # +0x00
    ('default_camera_sensitivity', fword(DEFAULTS['camera_sensitivity'])),   # +0x04
    ('default_camera_deadzone', fword(DEFAULTS['camera_deadzone'])),         # +0x08
    ('default_move_deadzone_squared', fword(DEFAULTS['move_deadzone_squared'])),  # +0x0C
    ('default_move_stick_sign', fword(DEFAULTS['move_stick_sign'])),         # +0x10
    ('default_move_camera_offset', fword(DEFAULTS['move_camera_offset'])),   # +0x14
    ('pi', fword(3.141592653589793)),                          # +0x18
    ('two_pi', fword(6.283185307179586)),                      # +0x1C
    ('magic_hi', 0x43300000),                                  # +0x20
    ('magic_lo', 0x80000000),                                  # +0x24
    ('minus_pi', fword(-3.141592653589793)),                   # +0x28
    ('epsilon_squared', fword(1.0)),                           # +0x2C
    ('fine_step', fword(0.0001)),                              # +0x30
    ('sensitivity_min', fword(0.0002)),                        # +0x34
    ('sensitivity_max', fword(0.05)),                          # +0x38
    ('sensitivity_unit', fword(0.0006)),                       # +0x3C
    ('ten_thousand', fword(10000.0)),                          # +0x40
    ('hundred', fword(100.0)),                                 # +0x44
    ('half', fword(0.5)),                                      # +0x48
    ('default_jump_window', DEFAULTS['jump_window']),          # +0x4C
    ('jump_window_max', JUMP_WINDOW_MAX),                      # +0x50
    ('sector_22', fword(math.radians(22.5))),                  # +0x54
    ('sector_67', fword(math.radians(67.5))),                  # +0x58
    ('sector_112', fword(math.radians(112.5))),                # +0x5C
    ('sector_157', fword(math.radians(157.5))),                # +0x60
    ('zero', fword(0.0)),                                      # +0x64
    ('counter_max', COUNTER_MAX),                              # +0x68
    ('arc_epsilon', fword(ARC_EPSILON)),                       # +0x6C
    ('sector_45', fword(math.radians(45.0))),                 # +0x70
    ('half_pi', fword(math.pi / 2)),                           # +0x74 (v0.15: sidestep swap threshold)
    ('crouch_sector', fword(math.radians(45.0))),              # +0x78 (v0.16: crouch stick forward/back half-angle)
    ('turn_state', 0x00000000),                                # +0x7C (v0.17 runtime: 0 idle, 1 turning / direction unknown, 2 request sent)
    ('turn_entry_yaw', 0x00000000),                            # +0x80 (v0.17 runtime: her yaw on the turn's first frame)
    ('turn_delta', 0x00000000),                                # +0x84 (v0.17 runtime: +pi / +pi/2 / -pi/2 for the chosen motion)
    ('stick_block', 0x00000000),                               # +0x88 (v0.18 runtime: frames left of the camera lock after the turn)
    ('turn_quarter', fword(math.radians(TURN_QUARTER_DEG))),   # +0x8C (v0.18: rotation of the C-stick quarter turns)
]
for name, value in DATA:
    emit(f'.long 0x{value:08x}')
D = {name: 4 * k for k, (name, _) in enumerate(DATA)}
LINE1_OFF = 4 * len(DATA)
prefix = sjis(LINE1_PREFIX)
SENS_SLOT = LINE1_OFF + len(prefix)
mid = sjis(LINE1_MID)
MULT_SLOT = SENS_SLOT + 4 * CH + len(mid)
line1 = prefix + sjis(ZERO_CH * 4) + mid + sjis(ZERO_CH * 2 + DOT_CH + ZERO_CH * 2) + b'\0'
LINE3_OFF = LINE1_OFF + len(line1)
WIN_SLOT = LINE3_OFF + len(sjis(LINE3_PREFIX))
line3 = sjis(LINE3_PREFIX) + sjis(ZERO_CH * 2) + sjis(LINE3_MID) + sjis(LINE3_SUFFIX) + b'\0'
LINE2_OFF = LINE3_OFF + len(line3)
line2 = sjis(LINE2) + b'\0'
text = line1 + line3 + line2
text += b'\0' * (-len(text) % 8)
for i in range(0, len(text), 4):
    emit(f'.long 0x{int.from_bytes(text[i:i + 4], "big"):08x}')
DATA_END = LINE1_OFF + len(text)
PAD_BASE = R.pad - 0x801A0000      # pad image, addressed from lis 0x801a
PAD = {'subx': PAD_BASE + 2, 'suby': PAD_BASE + 3, 'error': PAD_BASE + 8, 'buttons': PAD_BASE + 0x10, 'pressed': PAD_BASE + 0x14,
       'released': PAD_BASE + 0x18, 'stickx': PAD_BASE, 'sticky': PAD_BASE + 1}
# stack slots: 320 data pointer, 328/332 int->float, 336 stick angle, 340 saved debug page, 344/348 fctiwz,
# 352 camera yaw, 356 pending jump kind (consumed), 360 stick pushed flag, 364 intended direction, 372 push frames


def digit_at(base_reg, offset, value_reg, divisor, blank_zero=False):
    s = f'''
li 0,{divisor}
divwu 10,{value_reg},0
mullw 0,10,0
subf {value_reg},0,{value_reg}
'''
    if blank_zero:
        blank = f'''
li 0,0x20
stb 0,{offset}({base_reg})
''' if ASCII_TEXT else f'''
li 0,0x81
stb 0,{offset}({base_reg})
li 0,0x40
stb 0,{offset + 1}({base_reg})
'''
        s += f'''
cmpwi 10,0
bne digit_{offset}
''' + blank + f'''
b digit_done_{offset}
digit_{offset}:
'''
    s += f'''
addi 0,10,0x30
stb 0,{offset}({base_reg})
''' if ASCII_TEXT else f'''
li 0,0x82
stb 0,{offset}({base_reg})
addi 0,10,0x4f
stb 0,{offset + 1}({base_reg})
'''
    if blank_zero:
        s += f'digit_done_{offset}:\n'
    return s


def last_digit(base_reg, offset, value_reg):
    if ASCII_TEXT:
        return f'''
addi 0,{value_reg},0x30
stb 0,{offset}({base_reg})
'''
    return f'''
li 0,0x82
stb 0,{offset}({base_reg})
addi 0,{value_reg},0x4f
stb 0,{offset + 1}({base_reg})
'''


def step(sign, offset_name):
    """sensitivity += sign * data[offset]; clamp. Uses f1-f3, r11 = config base, r12 = data."""
    op = 'fadds' if sign > 0 else 'fsubs'
    tag = ('up' if sign > 0 else 'down') + f'_{offset_name}'   # label-safe (no '-')
    return f'''
lfs 1,{C['sensitivity']}(11)
lfs 2,{offset_name}(12)
{op} 1,1,2
lfs 3,{D['sensitivity_max']}(12)
fcmpu 0,1,3
ble step_hi_ok_{tag}
fmr 1,3
step_hi_ok_{tag}:
lfs 3,{D['sensitivity_min']}(12)
fcmpu 0,1,3
bge step_lo_ok_{tag}
fmr 1,3
step_lo_ok_{tag}:
stfs 1,{C['sensitivity']}(11)
'''


def wrap(tag):
    """Wrap f1 into [-pi, pi]. Uses f5/f6, r12 = data."""
    return f'''
lfs 5,{D['two_pi']}(12)
lfs 6,{D['pi']}(12)
wrap_high_{tag}:
fcmpu 0,1,6
ble wrap_low_check_{tag}
fsubs 1,1,5
b wrap_high_{tag}
wrap_low_check_{tag}:
lfs 6,{D['minus_pi']}(12)
wrap_low_{tag}:
fcmpu 0,1,6
bge wrap_done_{tag}
fadds 1,1,5
b wrap_low_{tag}
wrap_done_{tag}:
'''


def clear_pad_bits(offset):
    """Clear D-pad (0xF), A (0x100), B (0x200) and Y (0x800) from one pad word. r8 = pad base."""
    return f'''
lwz 0,{offset}(8)
rlwinm 0,0,0,0,27
rlwinm 0,0,0,24,21
rlwinm 0,0,0,21,19
stw 0,{offset}(8)
'''


reserved_init = '\n'.join(f'stw 0,{o}(11)' for o in RESERVED)
emit(f'''
data_end:
mflr 12
stw 12,320(1)
lis 11,{CFG_HI}
lwz 0,{C['magic']}(11)
lis 9,0x504e
ori 9,9,0x3034
cmpw 0,9
beq config_ok
stw 9,{C['magic']}(11)
li 0,{CONFIG_VERSION}
stw 0,{C['version']}(11)
lwz 0,{D['default_camera_sensitivity']}(12)
stw 0,{C['sensitivity']}(11)
lwz 0,{D['default_camera_deadzone']}(12)
stw 0,{C['camera_deadzone']}(11)
lwz 0,{D['default_move_deadzone_squared']}(12)
stw 0,{C['deadzone_sq']}(11)
lwz 0,{D['default_move_stick_sign']}(12)
stw 0,{C['sign']}(11)
lwz 0,{D['default_move_camera_offset']}(12)
stw 0,{C['offset']}(11)
lwz 0,{D['default_jump_window']}(12)
stw 0,{C['jump_window']}(11)
li 0,0
stw 0,{C['flags']}(11)
stw 0,{C['push_frames']}(11)
stw 0,{C['pending_jump']}(11)
stw 0,{C['follow_frames']}(11)
stw 0,{C['cam_yaw_request']}(11)
stw 0,{C['pending_focus']}(11)
stw 0,{C['cam_yaw_step']}(11)
{reserved_init}
b config_ready
config_ok:
lwz 0,{C['version']}(11)
cmpwi 0,{CONFIG_VERSION}
bge config_ready
cmpwi 0,2
bge upgrade_v3
lwz 0,{D['default_jump_window']}(12)
stw 0,{C['jump_window']}(11)
upgrade_v3:
li 0,{CONFIG_VERSION}
stw 0,{C['version']}(11)
li 0,0
stw 0,{C['push_frames']}(11)
stw 0,{C['pending_jump']}(11)
stw 0,{C['follow_frames']}(11)
stw 0,{C['cam_yaw_request']}(11)
stw 0,{C['pending_focus']}(11)
stw 0,{C['cam_yaw_step']}(11)
lwz 0,{C['flags']}(11)
rlwinm 0,0,0,29,27
stw 0,{C['flags']}(11)
config_ready:
lis 8,0x801a
lwz 0,{PAD['pressed']}(8)
rlwinm 0,0,0,12,9
lbz 9,{PAD['subx']}(8)
extsb 9,9
lbz 10,{PAD['suby']}(8)
extsb 10,10
srawi 7,9,31
xor 9,9,7
subf 9,7,9
srawi 7,10,31
xor 10,10,7
subf 10,7,10
cmpw 9,10
blt cstick_done
rlwinm 0,0,0,10,7
cstick_done:
stw 0,{PAD['pressed']}(8)
addi 10,30,-1388
lwz 0,{C['flags']}(11)
rlwinm 0,0,0,31,29
rlwinm 0,0,0,28,26
lwz 9,{C['follow_frames']}(11)
cmpwi 9,0
beq follow_done
addi 9,9,-1
stw 9,{C['follow_frames']}(11)
ori 0,0,2
follow_done:
stw 0,{C['flags']}(11)
lwz 12,320(1)
lbz 9,248(10)
cmpwi 9,1
bne turn_not_active
lbz 9,249(10)
cmpwi 9,8
bne turn_not_active
lwz 0,{C['flags']}(11)
ori 0,0,16
stw 0,{C['flags']}(11)
li 9,{STICK_BLOCK_FRAMES}
stw 9,{D['stick_block']}(12)
b turn_track_done
turn_not_active:
lwz 9,{D['stick_block']}(12)
cmpwi 9,0
beq turn_end_check
addi 9,9,-1
stw 9,{D['stick_block']}(12)
lwz 0,{C['flags']}(11)
ori 0,0,16
stw 0,{C['flags']}(11)
cmpwi 9,0
bne turn_track_done
turn_end_check:
lwz 9,{D['turn_state']}(12)
cmpwi 9,0
beq turn_track_done
li 9,0
stw 9,{D['turn_state']}(12)
li 9,1
stw 9,{C['follow_frames']}(11)
turn_track_done:
lwz 0,{PAD['buttons']}(8)
andi. 7,0,0x60
cmpwi 7,0x60
bne no_toggle
lwz 0,{PAD['pressed']}(8)
andi. 0,0,0x10
beq no_toggle
lwz 0,{C['flags']}(11)
xori 0,0,1
stw 0,{C['flags']}(11)
li 0,0
stw 0,140(30)
b done
no_toggle:
lwz 0,{C['flags']}(11)
andi. 0,0,1
beq normal_mode
li 0,0
stw 0,140(30)
lwz 9,{PAD['pressed']}(8)
andi. 0,9,8
beq no_dpad_up
{step(+1, D['sensitivity_unit'])}
no_dpad_up:
andi. 0,9,4
beq no_dpad_down
{step(-1, D['sensitivity_unit'])}
no_dpad_down:
andi. 0,9,2
beq no_dpad_right
{step(+1, D['fine_step'])}
no_dpad_right:
andi. 0,9,1
beq no_dpad_left
{step(-1, D['fine_step'])}
no_dpad_left:
andi. 0,9,0x400
beq no_x_reset
lwz 0,{D['default_camera_sensitivity']}(12)
stw 0,{C['sensitivity']}(11)
lwz 0,{D['default_jump_window']}(12)
stw 0,{C['jump_window']}(11)
no_x_reset:
andi. 0,9,0x100
beq no_a_step
lwz 7,{C['jump_window']}(11)
lwz 0,{D['jump_window_max']}(12)
cmpw 7,0
bge no_a_step
addi 7,7,1
stw 7,{C['jump_window']}(11)
no_a_step:
andi. 0,9,0x200
beq no_b_step
lwz 7,{C['jump_window']}(11)
cmpwi 7,0
ble no_b_step
addi 7,7,-1
stw 7,{C['jump_window']}(11)
no_b_step:
{clear_pad_bits(PAD['buttons'])}
{clear_pad_bits(PAD['pressed'])}
{clear_pad_bits(PAD['released'])}
compose_text:
lfs 1,{C['sensitivity']}(11)
lfs 2,{D['ten_thousand']}(12)
fmuls 3,1,2
lfs 2,{D['half']}(12)
fadds 3,3,2
fctiwz 3,3
stfd 3,344(1)
lwz 9,348(1)
cmpwi 9,9999
ble sens_clamped
li 9,9999
sens_clamped:
cmpwi 9,0
bge sens_positive
li 9,0
sens_positive:
''')
emit(digit_at(12, SENS_SLOT, 9, 1000))
emit(digit_at(12, SENS_SLOT + CH, 9, 100))
emit(digit_at(12, SENS_SLOT + 2 * CH, 9, 10))
emit(last_digit(12, SENS_SLOT + 3 * CH, 9))
emit(f'''
lfs 2,{D['sensitivity_unit']}(12)
fdivs 3,1,2
lfs 2,{D['hundred']}(12)
fmuls 3,3,2
lfs 2,{D['half']}(12)
fadds 3,3,2
fctiwz 3,3
stfd 3,344(1)
lwz 9,348(1)
cmpwi 9,9999
ble mult_clamped
li 9,9999
mult_clamped:
cmpwi 9,0
bge mult_positive
li 9,0
mult_positive:
''')
emit(digit_at(12, MULT_SLOT, 9, 1000, blank_zero=True))
emit(digit_at(12, MULT_SLOT + CH, 9, 100))
emit(digit_at(12, MULT_SLOT + 3 * CH, 9, 10))
emit(last_digit(12, MULT_SLOT + 4 * CH, 9))
emit(f'''
lwz 9,{C['jump_window']}(11)
cmpwi 9,99
ble win_clamped
li 9,99
win_clamped:
cmpwi 9,0
bge win_positive
li 9,0
win_positive:
''')
emit(digit_at(12, WIN_SLOT, 9, 10))
emit(last_digit(12, WIN_SLOT + CH, 9))
emit(f'''
li 3,1
lis 11,{hiu(SET_DEBUG_PAGE)}
ori 11,11,{lou(SET_DEBUG_PAGE)}
mtctr 11
bctrl
stw 3,340(1)
lwz 12,320(1)
li 3,{TEXT_X}
li 4,{TEXT_Y1}
li 5,0
li 6,0
addi 7,12,{LINE1_OFF}
crxor 6,6,6
lis 11,{hiu(DEBUG_PRINTF)}
ori 11,11,{lou(DEBUG_PRINTF)}
mtctr 11
bctrl
lwz 12,320(1)
li 3,{TEXT_X}
li 4,{TEXT_Y3}
li 5,0
li 6,0
addi 7,12,{LINE3_OFF}
crxor 6,6,6
lis 11,{hiu(DEBUG_PRINTF)}
ori 11,11,{lou(DEBUG_PRINTF)}
mtctr 11
bctrl
lwz 12,320(1)
li 3,{TEXT_X}
li 4,{TEXT_Y2}
li 5,0
li 6,0
addi 7,12,{LINE2_OFF}
crxor 6,6,6
lis 11,{hiu(DEBUG_PRINTF)}
ori 11,11,{lou(DEBUG_PRINTF)}
mtctr 11
bctrl
{FLAG_RECORDS}
lwz 3,340(1)
lis 11,{hiu(SET_DEBUG_PAGE)}
ori 11,11,{lou(SET_DEBUG_PAGE)}
mtctr 11
bctrl
b done
normal_mode:
lis 8,0x801a
lis 11,{CFG_HI}
lbz 0,{PAD['error']}(8)
cmpwi 0,0
beq pad_ok
li 0,0
stw 0,{C['push_frames']}(11)
stw 0,{C['pending_jump']}(11)
b done
pad_ok:
lwz 0,{C['pending_focus']}(11)
li 9,0
stw 9,{C['pending_focus']}(11)
addi 10,30,-1388
lbz 9,248(10)
cmpwi 9,1
bne focus_done
cmpwi 0,0
beq focus_press
lwz 3,72(30)
cmpwi 3,0
beq focus_reset
lwz 0,1236(3)
cmpwi 0,0
ble focus_reset
stw 3,380(1)
lwz 5,240(3)
cmpwi 5,0
beq focus_actor_pos
lbz 4,293(3)
mr 3,5
lis 11,{hiu(AIM_POINT)}
ori 11,11,{lou(AIM_POINT)}
mtctr 11
bctrl
addi 3,3,264
b focus_have_pos
focus_actor_pos:
addi 3,3,192
focus_have_pos:
lwz 12,320(1)
addi 10,30,-1388
lfs 1,0(3)
lfs 2,192(10)
fsubs 1,1,2
lfs 2,8(3)
lfs 3,200(10)
fsubs 2,2,3
lis 11,{hiu(ATAN2F)}
ori 11,11,{lou(ATAN2F)}
mtctr 11
bctrl
lwz 12,320(1)
addi 10,30,-1388
lis 11,{CFG_HI}
stfs 1,{C['cam_yaw_request']}(11)
li 0,0
stw 0,{C['cam_yaw_step']}(11)
lwz 0,{C['flags']}(11)
ori 0,0,8
stw 0,{C['flags']}(11)
b focus_press
focus_reset:
lis 11,{CFG_HI}
li 0,1
stw 0,{C['follow_frames']}(11)
focus_press:
lis 8,0x801a
lis 11,{CFG_HI}
lwz 0,140(30)
andi. 0,0,0x400
beq focus_done
lhz 0,2140(30)
cmpwi 0,0
bne focus_targets
li 0,1
stw 0,{C['follow_frames']}(11)
b focus_done
focus_targets:
li 0,1
stw 0,{C['pending_focus']}(11)
focus_done:
lbz 9,{PAD['stickx']}(8)
extsb 9,9
lbz 7,{PAD['sticky']}(8)
extsb 7,7
lis 0,0x4330
stw 0,328(1)
xoris 0,9,0x8000
stw 0,332(1)
lfd 3,328(1)
lfd 5,{D['magic_hi']}(12)
fsub 3,3,5
frsp 3,3
xoris 0,7,0x8000
stw 0,332(1)
lfd 4,328(1)
fsub 4,4,5
frsp 4,4
fmuls 6,3,3
fmadds 6,4,4,6
lfs 7,{C['deadzone_sq']}(11)
lwz 9,{C['push_frames']}(11)
fcmpu 0,6,7
ble stick_idle
addi 9,9,1
lwz 0,{D['counter_max']}(12)
cmpw 9,0
ble counter_ok
mr 9,0
counter_ok:
li 0,1
b counter_store
stick_idle:
li 9,0
li 0,0
counter_store:
stw 9,{C['push_frames']}(11)
stw 9,372(1)
stw 0,360(1)
lwz 0,{C['pending_jump']}(11)
stw 0,356(1)
li 0,0
stw 0,{C['pending_jump']}(11)
addi 10,30,-1388
lbz 0,248(10)
cmpwi 0,1
bne done
lwz 0,360(1)
cmpwi 0,0
beq no_stick_angle
lfs 7,{C['sign']}(11)
fmuls 1,3,7
fmr 2,4
lis 11,{hiu(ATAN2F)}
ori 11,11,{lou(ATAN2F)}
mtctr 11
bctrl
stfs 1,336(1)
no_stick_angle:
lwz 12,320(1)
lis 11,{hi(R.camera_ptr)}
lwz 11,{lo(R.camera_ptr)}(11)
cmpwi 11,0
beq use_last
lfs 1,268(11)
lfs 2,256(11)
fsubs 1,1,2
lfs 2,276(11)
lfs 3,264(11)
fsubs 2,2,3
fmuls 6,1,1
fmadds 6,2,2,6
lfs 7,{D['epsilon_squared']}(12)
fcmpu 0,6,7
ble use_last
lis 11,{hiu(ATAN2F)}
ori 11,11,{lou(ATAN2F)}
mtctr 11
bctrl
lwz 12,320(1)
stfs 1,0(12)
b have_camera
use_last:
lfs 1,0(12)
have_camera:
stfs 1,352(1)
lwz 0,360(1)
cmpwi 0,0
beq no_intended
lis 9,{CFG_HI}
lfs 2,{C['offset']}(9)
fadds 1,1,2
lfs 2,336(1)
fsubs 1,1,2
{wrap('intended')}
stfs 1,364(1)
no_intended:
addi 10,30,-1388
lbz 0,249(10)
cmpwi 0,0
beq explore
cmpwi 0,1
beq explore
cmpwi 0,11
beq explore
cmpwi 0,12
beq explore
cmpwi 0,5
beq crouch_state
side_swap:
lwz 9,140(30)
andis. 0,9,3
beq side_done
lfs 1,208(10)
lfs 2,352(1)
fsubs 1,1,2
{wrap('side')}
fabs 1,1
lfs 3,{D['half_pi']}(12)
fcmpu 0,1,3
ble side_done
andis. 11,9,2
andis. 7,9,1
andi. 8,9,0x8000
andi. 6,9,0x4000
rlwinm 9,9,0,18,13
rlwinm 11,11,31,1,31
rlwinm 7,7,1,0,30
rlwinm 8,8,31,1,31
rlwinm 6,6,1,0,30
or 9,9,11
or 9,9,7
or 9,9,8
or 9,9,6
stw 9,140(30)
side_done:
lbz 0,249(10)
cmpwi 0,3
beq jump_state
cmpwi 0,8
beq turn_state
b done
crouch_state:
lwz 9,140(30)
andis. 0,9,4
beq explore
andis. 0,9,3
bne side_swap
rlwinm 9,9,0,0,27
lwz 0,360(1)
cmpwi 0,0
beq crouch_store
rlwinm 9,9,0,18,13
lfs 1,364(1)
lfs 2,208(10)
fsubs 1,1,2
{wrap('crouch')}
fabs 2,1
lfs 3,{D['crouch_sector']}(12)
fcmpu 0,2,3
bge crouch_not_forward
ori 9,9,1
b crouch_store
crouch_not_forward:
lfs 4,{D['pi']}(12)
fsubs 3,4,3
fcmpu 0,2,3
ble crouch_side
ori 9,9,2
b crouch_store
crouch_side:
lfs 3,{D['zero']}(12)
fcmpu 0,1,3
blt crouch_right
oris 9,9,2
ori 9,9,0x8000
b crouch_store
crouch_right:
oris 9,9,1
ori 9,9,0x4000
crouch_store:
stw 9,140(30)
b done
turn_state:
lbz 0,250(10)
cmpwi 0,0
bne done
lwz 12,320(1)
lis 8,0x801a
lbz 9,{PAD['subx']}(8)
extsb 9,9
lwz 0,{PAD['buttons']}(8)
rlwinm 0,0,0,16,13
lfs 1,208(10)
stfs 1,{D['turn_entry_yaw']}(12)
lfs 2,{D['pi']}(12)
cmpwi 9,-40
bge turn_not_left
oris 0,0,1
lfs 2,{D['turn_quarter']}(12)
b turn_store
turn_not_left:
cmpwi 9,40
ble turn_store
oris 0,0,2
lfs 2,{D['turn_quarter']}(12)
fneg 2,2
turn_store:
stw 0,{PAD['buttons']}(8)
stfs 2,{D['turn_delta']}(12)
li 9,1
stw 9,{D['turn_state']}(12)
fadds 1,1,2
{wrap('turn_goal')}
lis 11,{CFG_HI}
stfs 1,{C['cam_yaw_request']}(11)
li 0,0
stw 0,{C['cam_yaw_step']}(11)
lwz 0,{C['flags']}(11)
ori 0,0,{8 | PACED_FLAG_BIT}
stw 0,{C['flags']}(11)
b done
jump_state:
lbz 0,250(10)
cmpwi 0,0
bne air_control
lwz 0,356(1)
cmpwi 0,1
bne kind_not_camera
lfs 1,352(1)
stfs 1,208(10)
b air_control
kind_not_camera:
cmpwi 0,2
bne air_control
lwz 0,360(1)
cmpwi 0,0
beq air_control
lfs 1,364(1)
stfs 1,208(10)
air_control:
lwz 0,140(30)
rlwinm 0,0,0,0,27
lwz 9,360(1)
cmpwi 9,0
beq store_ctrl_jump
lfs 1,364(1)
lfs 2,208(10)
fsubs 1,1,2
{wrap('relative')}
fabs 2,1
lfs 3,{D['sector_67']}(12)
fcmpu 0,2,3
bge not_up
ori 0,0,1
not_up:
lfs 3,{D['sector_112']}(12)
fcmpu 0,2,3
ble not_down
ori 0,0,2
not_down:
lfs 3,{D['sector_22']}(12)
fcmpu 0,2,3
ble store_ctrl_jump
lfs 3,{D['sector_157']}(12)
fcmpu 0,2,3
bge store_ctrl_jump
lfs 3,{D['zero']}(12)
fcmpu 0,1,3
blt right_side
ori 0,0,8
b store_ctrl_jump
right_side:
ori 0,0,4
store_ctrl_jump:
stw 0,140(30)
b done
explore:
lwz 9,140(30)
andis. 0,9,3
beq no_sidestep
lfs 1,352(1)
stfs 1,208(10)
rlwinm 9,9,0,0,27
stw 9,140(30)
b done
no_sidestep:
lwz 7,360(1)
lwz 8,372(1)
lis 11,{CFG_HI}
lwz 0,{C['jump_window']}(11)
li 6,0
cmpwi 7,0
beq zone_done
cmpw 8,0
bgt zone_done
lis 5,0x801a
lwz 5,{PAD['buttons']}(5)
andis. 5,5,4
beq zone_done
li 6,1
zone_done:
andi. 9,9,0x2000
beq no_jump_press
cmpwi 7,0
beq kind_zero
cmpwi 6,0
beq kind_running
li 0,1
stw 0,{C['pending_jump']}(11)
b hold
kind_running:
li 0,2
stw 0,{C['pending_jump']}(11)
b run_convert
kind_zero:
li 0,0
stw 0,{C['pending_jump']}(11)
b done
no_jump_press:
cmpwi 7,0
beq done
cmpwi 6,0
beq run_convert
lwz 0,{C['flags']}(11)
andi. 0,0,4
bne hold
lfs 1,364(1)
lfs 2,208(10)
fsubs 1,1,2
{wrap('arc_turn')}
fabs 7,1
fmr 9,7
lfs 1,352(1)
lfs 2,364(1)
fsubs 1,1,2
{wrap('arc_snap')}
fabs 8,1
fadds 7,7,8
lfs 1,352(1)
lfs 2,208(10)
fsubs 1,1,2
{wrap('arc_direct')}
fabs 8,1
fsubs 7,7,8
lfs 8,{D['arc_epsilon']}(12)
fcmpu 0,7,8
blt run_convert
lfs 3,{D['sector_45']}(12)
fcmpu 0,9,3
bge hold
lwz 0,140(30)
rlwinm 0,0,0,0,27
ori 0,0,1
stw 0,140(30)
b done
hold:
lwz 0,140(30)
rlwinm 0,0,0,0,27
stw 0,140(30)
b done
run_convert:
lwz 0,140(30)
rlwinm 0,0,0,0,27
ori 0,0,1
stw 0,140(30)
lfs 1,364(1)
stfs 1,208(10)
done:
lfd 0,72(1)
mtfsf 255,0
''')
for f in range(14):
    o = 80 + f * 16
    emit(f'.long 0x{(56 << 26) | (f << 21) | (1 << 16) | (o + 8):08x}')  # psq_l
    emit(f'lfd {f},{o}(1)')
emit('''
lwz 0,68(1)
mtspr 912,0
lwz 0,64(1)
mtxer 0
lwz 0,60(1)
mtctr 0
lwz 0,56(1)
mtcrf 255,0
lwz 0,52(1)
mtlr 0
''')
for r in range(3, 13):
    emit(f'lwz {r},{12 + (r - 3) * 4}(1)')
emit(f'''
lwz 0,8(1)
addi 1,1,{FRAME}
lwz 11,{R.root_sda}(13)
''')
asm = '\n'.join(lines) + '\n'
code = bytes(ks.asm(asm, addr=REGION)[0])
assert code[-4:] == ORIGINAL.to_bytes(4, 'big')
disp = (HOOK + 4) - (REGION + len(code))
assert disp % 4 == 0 and -0x2000000 <= disp < 0x2000000
RETURN_WORD = 0x48000000 | (disp & 0x03FFFFFC)
code += RETURN_WORD.to_bytes(4, 'big')
assert REGION + len(code) <= REGION_END, (len(code), REGION_END - REGION)
disp = REGION - HOOK
assert disp % 4 == 0 and -0x2000000 <= disp < 0x2000000
HOOK_WORD = 0x48000000 | (disp & 0x03FFFFFC)
out = Path(__file__).parent / ('move-v20-build' + R.suffix)
out.mkdir(exist_ok=True)
(out / 'move.s').write_text(asm)
(out / 'move.bin').write_bytes(code)
insns = list(md.disasm(code, REGION))
data_off = next(i.address + 4 - REGION for i in insns if i.mnemonic == 'bl')
assert data_off % 4 == 0, data_off
assert code[data_off + LINE1_OFF:data_off + LINE1_OFF + len(line1)] == line1
assert code[data_off + LINE3_OFF:data_off + LINE3_OFF + len(line3)] == line3
assert code[data_off + LINE2_OFF:data_off + LINE2_OFF + len(line2)] == line2
data_words = {name: data_off + 4 * k for k, (name, _) in enumerate(DATA)}
patch = [f'0x{REGION + o:08X}:dword:0x{int.from_bytes(code[o:o + 4], "big"):08X}:0x00000000' for o in range(0, len(code), 4)]
patch.append(f'0x{HOOK:08X}:dword:0x{HOOK_WORD:08X}:0x{ORIGINAL:08X}')
(out / 'patch.txt').write_text('\n'.join(patch) + '\n')
(out / 'move.dis.txt').write_text('\n'.join(f'{i.address:08x}: {i.bytes.hex()} {i.mnemonic} {i.op_str}' for i in insns))
config_lines = {}
for name in ('default_camera_sensitivity', 'default_move_stick_sign', 'default_move_camera_offset', 'fine_step',
             'sensitivity_unit', 'default_jump_window', 'jump_window_max', 'half_pi', 'crouch_sector', 'turn_quarter'):
    off = data_words[name]
    config_lines[name] = dict(payload_offset=off, address=REGION + off, patch_line=patch[off // 4])
manifest = dict(hook=HOOK, original=ORIGINAL, hook_word=HOOK_WORD, return_word=RETURN_WORD, guards=[GUARD_BEFORE, GUARD_AFTER],
                region=REGION, region_end=REGION_END, delivery='OnFrame conditional dword patches',
                data_offset=data_off, data_end=data_off + DATA_END, data_words=data_words,
                line1_offset=data_off + LINE1_OFF, line2_offset=data_off + LINE2_OFF, line3_offset=data_off + LINE3_OFF,
                sens_slot=data_off + SENS_SLOT, mult_slot=data_off + MULT_SLOT, win_slot=data_off + WIN_SLOT,
                text=dict(x=TEXT_X, y1=TEXT_Y1, y2=TEXT_Y2, y3=TEXT_Y3, line1_prefix=LINE1_PREFIX, line1_mid=LINE1_MID,
                          line2=LINE2, line3_prefix=LINE3_PREFIX, line3_mid=LINE3_MID, line3_suffix=LINE3_SUFFIX,
                          encoding='ascii' if ASCII_TEXT else 'sjis', bytes_per_char=CH, flags_records_visible=ASCII_TEXT,
                          cell_width=US_CW if ASCII_TEXT else 8,
                          px_widths=[us_px(LINE1_PREFIX + '0000' + LINE1_MID + '00.00'), us_px(LINE3_PREFIX + '00' + LINE3_MID + LINE3_SUFFIX), us_px(LINE2)] if ASCII_TEXT else None),
                debug_printf=DEBUG_PRINTF, set_debug_page=SET_DEBUG_PAGE, config_block=CONFIG, config_magic=MAGIC,
                config_version=CONFIG_VERSION, config_offsets=FIELDS,
                defaults=DEFAULTS, steps=dict(coarse=0.0006, fine=0.0001, minimum=0.0002, maximum=0.05),
                jump=dict(window_default=DEFAULTS['jump_window'], window_max=JUMP_WINDOW_MAX, counter_max=COUNTER_MAX,
                          sectors_deg=[22.5, 67.5, 112.5, 157.5], kinds={0: 'neutral', 1: 'camera_frame', 2: 'running'},
                          arc_epsilon=ARC_EPSILON, hold_flag_bit=4, hold_toggle_in_menu=False, run_passthrough_deg=45.0,
                          chord_zone='pad buttons bit 0x40000 (game DOWN sector, |angle from down| < 70 deg)'),
                turn=dict(source='C-stick X byte 0x80199702 on the first frame of sub-state 8', threshold=40,
                          left_bit=0x10000, right_bit=0x20000, movement_stick_bits_cleared=True,
                          entry='0x800B29B4 reads 0x80199710: LEFT -> motion +0x64/+0x68 (mirror global), RIGHT -> the other, none -> +0x30 (180)',
                          quarter_deg=TURN_QUARTER_DEG, stick_block_frames=STICK_BLOCK_FRAMES, camera_lock_flag_bit=16, paced_flag_bit=PACED_FLAG_BIT,
                          camera_request_v19='entry frame: config +0x30 = wrap(entry yaw + rotation), +0x38 = 0, flags bit3 | bit5; camera v0.11 paces the swing to her per-frame rotation; follow_frames = 1 when stick_block runs out (2 frames after the turn state)',
                          camera_request='v0.17: entry frame records her yaw and the rotation (+pi / +pi/2 left / -pi/2 right) in data words; the first later frame with |yaw - entry| > detect writes config +0x30 = wrap(entry + rotation), +0x38 = +-camera step (sign = spin direction) and flags bit3; bit1 is not raised during the turn; follow_frames = 1 when the turn state ends'),
                lockon=dict(button='X (control word 0x400, pressed edge)', target_count='player+0xDC8 (u16)', target_index='player+0xDCA',
                            current_target='player+0x5B4', target_list='player+0xC48, 12-byte entries (ptr, ?, distance) sorted ascending',
                            aim_point='0x8009EFB0(target+0xF0, target+0x125) -> +0x108 (x,y,z); fallback target+0xC0', hp='target+0x4D4 > 0',
                            request='config +0x30 yaw (atan2f(dx, dz) from Vanessa), flags bit3; camera v0.6 applies once',
                            no_target='follow_frames = 1 (camera behind Vanessa)'),
                sidestep_swap=dict(states='category 1 sub-states other than 0/1/0xB/0xC (those snap the facing instead)',
                                   rule='swap op-word bits 0x20000<->0x10000 and 0x8000<->0x4000 when |wrap(facing - camera yaw)| > pi/2',
                                   threshold_word='half_pi', facing_untouched=True),
                crouch=dict(state='sub-state 5 with Y held (op word 0x40000) and no L/R trigger edge',
                            rule='rel = wrap(intended - facing); |rel| < crouch_sector -> UP, |rel| > pi - crouch_sector -> DOWN, else L (rel >= 0) / R trigger bits; raw direction bits cleared; yaw untouched',
                            sector_word='crouch_sector', sector_deg=45.0, y_released='exploration rules'),
                follow_flag_bit=2, config_lines=config_lines, patch_entries=len(patch),
                bytes=len(code), sha256=hashlib.sha256(code).hexdigest(), stack_frame=FRAME)
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({k: v for k, v in manifest.items() if k in ('bytes', 'sha256', 'region', 'hook_word', 'return_word', 'patch_entries', 'data_offset', 'data_end')}, indent=2))
