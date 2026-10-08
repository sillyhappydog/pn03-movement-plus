"""Extract MRAM (0x80000000..0x81800000) from a Dolphin LZ4 savestate into a raw file.

Usage: py -3.13 dolphin_savestate_mram.py <GPNJ08.sNN> <out.bin>

Dolphin 2606a savestate layout (little endian):
  legacy header 24 bytes: game id[6], u16, u32 lzo_size (0), 4 pad, double time
  u32 version cookie, u32 version string length, version string
  extended header 16 bytes: u16 header version, u16 compression (1 = LZ4), u32 payload offset, u64 uncompressed size
  then repeated: s32 chunk length, LZ4 block (0 length ends)
MRAM is located inside the decompressed payload by the DOL text signature (section 0 + 0x100).
Needs the lz4 module (installed into deps/ on first use).
"""
import struct, sys, time
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'deps'))

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
b = src.read_bytes()
gid, res, lzo, pad, t = struct.unpack_from('<6sHIId', b, 0)
cookie, vlen = struct.unpack_from('<II', b, 24)
ver = b[32:32 + vlen].decode()
pos = 32 + vlen
hv, ctype, poff, usize = struct.unpack_from('<HHIQ', b, pos)
pos += 16
print('game', gid, 'version', ver, 'header_version', hv, 'compression', ctype, 'payload_offset', poff, 'uncompressed', usize)
assert ctype == 1, 'only LZ4 savestates are handled'
try:
    import lz4.block as lb
except ImportError:
    import subprocess
    print('installing lz4 ...')
    sys.stdout.flush()
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--quiet', '--target', str(HERE / 'deps'), 'lz4'], check=True)
    import lz4.block as lb
out = bytearray()
t0 = time.time()
while pos + 4 <= len(b):
    (clen,) = struct.unpack_from('<i', b, pos)
    pos += 4
    if clen <= 0:
        break
    chunk = b[pos:pos + clen]
    pos += clen
    out += lb.decompress(chunk, uncompressed_size=usize - len(out))
    print(f'chunk {clen} -> total {len(out)} ({time.time() - t0:.1f}s)')
    sys.stdout.flush()
assert len(out) == usize, (len(out), usize)
import dol
f0, a0, n0 = dol.sections[0]
sig = dol.data[f0 + 0x100:f0 + 0x140]
hits = []
start = 0
while True:
    i = out.find(sig, start)
    if i < 0:
        break
    hits.append(i)
    start = i + 1
print('signature hits', [hex(h) for h in hits], 'section0 addr', hex(a0))
assert hits, 'DOL text signature not found in the payload'
base = hits[0] - 0x100 - (a0 - 0x80000000)
mram = bytes(out[base:base + 0x1800000])
dst.write_bytes(mram)
print('wrote', dst, len(mram), 'bytes; payload offset', hex(base))
