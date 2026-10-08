"""Print the root-position keys and the per-frame Hermite positions of a pl00.dat motion entry.

Usage: py -3.13 fcv_root.py <entry index> [<entry index> ...]

FCV layout (same as RE4, see I:\\re4-decomp\\tools\\motion\\fcv.py): u16 maxFrame, u8 nJoints,
u16 kind[n] (bits 0-7 kind, 12-15 Fcc key type), u8 partsNo[n], pad to 4, u32 size,
u32 keyOfs[n]; each joint's key block holds 3 axes {u16 n; u16 frame[n]; key[n]}. The root
position channel is kind 1. P.N.03 key blocks are not always contiguous in joint order, so
every joint is read through its keyOfs. Hermite: the game evaluates
h00*v0 + h10*out0 + h01*v1 + h11*in1 with t = (f - f0) / (f1 - f0) for f0 <= f < f1.
"""
import struct, sys
from pathlib import Path

PL00 = Path(r'I:\PN03_extracted\files\em\pl00.dat')
FCC = {0: ('f', 'f'), 1: ('f', 'h'), 2: ('f', 'b'), 4: ('h', 'f'), 5: ('h', 'h'), 6: ('h', 'b'),
       8: ('b', 'f'), 9: ('b', 'h'), 10: ('b', 'b'), 15: ('f', None)}
SIZE = {'f': 4, 'h': 2, 'b': 1}


def read_axis(buf, off, fcc):
    v, t = FCC[fcc]
    n = struct.unpack_from('>H', buf, off)[0]
    off += 2
    frames = list(struct.unpack_from('>%dH' % n, buf, off))
    off += 2 * n
    fmt = '>' + v + (t * 2 if t else '')
    st = struct.Struct(fmt)
    keys = []
    for _ in range(n):
        raw = st.unpack_from(buf, off)
        off += st.size
        scale = lambda f, x: x if f == 'f' else x * 0.0001
        val = scale(v, raw[0])
        tin = scale(t, raw[1]) if t else 0.0
        tout = scale(t, raw[2]) if t else 0.0
        keys.append((val, tin, tout))
    return frames, keys, off


def hermite(frames, keys, f):
    if f <= frames[0]:
        return keys[0][0]
    if f >= frames[-1]:
        return keys[-1][0]
    for i in range(len(frames) - 1):
        f0, f1 = frames[i], frames[i + 1]
        if f0 <= f < f1:
            t = (f - f0) / (f1 - f0)
            v0, _, out0 = keys[i]
            v1, in1, _ = keys[i + 1]
            h00 = 2 * t ** 3 - 3 * t ** 2 + 1
            h10 = t ** 3 - 2 * t ** 2 + t
            h01 = -2 * t ** 3 + 3 * t ** 2
            h11 = t ** 3 - t ** 2
            return h00 * v0 + h10 * out0 + h01 * v1 + h11 * in1
    return keys[-1][0]


data = PL00.read_bytes()
count = struct.unpack_from('>I', data, 0)[0]
offsets = struct.unpack_from('>%dI' % count, data, 4)
for arg in sys.argv[1:]:
    idx = int(arg)
    off = offsets[idx]
    end = offsets[idx + 1] if idx + 1 < count else len(data)
    buf = data[off:end]
    max_frame = struct.unpack_from('>H', buf, 0)[0] & 0x3FFF
    nj = buf[2]
    kinds = struct.unpack_from('>%dH' % nj, buf, 3)
    pos = 3 + 2 * nj + nj
    pos = (pos + 3) & ~3
    size = struct.unpack_from('>I', buf, pos)[0]
    key_ofs = struct.unpack_from('>%dI' % nj, buf, pos + 4)
    print(f'== entry [{idx}] @0x{off:08X} ({end - off} bytes): maxFrame {max_frame}, joints {nj}, size field {size}')
    roots = [j for j in range(nj) if kinds[j] & 0xFF == 1]
    if not roots:
        print('   no root position channel'); continue
    j = roots[0]
    fcc = kinds[j] >> 12
    axes = []
    o = key_ofs[j]
    for ax in 'XYZ':
        frames, keys, o = read_axis(buf, o, fcc)
        axes.append((ax, frames, keys))
        print(f'   root {ax}: keys at frames {frames}')
        print('      values ' + ', '.join(f'{k[0]:.2f}' for k in keys))
        print('      in-tan ' + ', '.join(f'{k[1]:.2f}' for k in keys) + ' | out-tan ' + ', '.join(f'{k[2]:.2f}' for k in keys))
    print('   per-frame root position and delta (X, Z):')
    prev = None
    for f in range(max_frame + 1):
        x = hermite(axes[0][1], axes[0][2], f)
        y = hermite(axes[1][1], axes[1][2], f)
        z = hermite(axes[2][1], axes[2][2], f)
        if prev is None:
            print(f'      f{f:2d}: X {x:9.2f}  Y {y:8.2f}  Z {z:9.2f}')
        else:
            print(f'      f{f:2d}: X {x:9.2f} ({x - prev[0]:+8.2f})  Y {y:8.2f}  Z {z:9.2f} ({z - prev[2]:+8.2f})')
        prev = (x, y, z)
