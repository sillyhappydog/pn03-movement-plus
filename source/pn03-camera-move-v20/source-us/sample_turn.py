"""Sample Vanessa's yaw / state, the camera patch's goal words, the movement patch's turn words and the config
block from a running Dolphin at a few hundred Hz, for a few seconds, into a CSV. Read-only (ReadProcessMemory).
Usage:  py -3.13 sample_turn.py <out.csv> [seconds, default 30]
Then:   py -3.13 sample_turn.py --summarize <out.csv>   (collapses duplicate samples into frames and prints the turns)
"""
import sys, time, struct, csv, math, ctypes
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from dolphin_live_mram import dolphin_pids, read, k32, MBI, MEM_COMMIT, MEM_MAPPED, MEM1_VIEW, PROCESS_QUERY_INFORMATION, PROCESS_VM_READ
import re

LAYOUT = {   # per game: r13, root sda offset, root -> player-vec offset, movement turn words, camera data words, config block
    b'GPNJ08': dict(r13=0x8026E820, root_sda=-0x74AC, root_pv=0x50, move_turn=0x8018E16C, cam_data=0x801910E0, config=0x801916C0),
    b'GPNE08': dict(r13=0x80275BE0, root_sda=-0x748C, root_pv=0x144, move_turn=0x8018E16C + 0x3C00, cam_data=0x801910E0 + 0x3C00, config=0x801916C0 + 0x3C00),
}
FIELDS = ['t', 'yaw', 'state', 'sub', 'phase', 'cam_yaw', 'goal', 'active', 'gstep', 'gdir', 'flags', 'follow', 'req', 'req_step', 'tstate', 'entry', 'delta']


def find_view():
    for pid, exe in dolphin_pids():
        h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not h:
            continue
        addr, mbi = 0, MBI()
        while k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)) == ctypes.sizeof(mbi):
            base, size = mbi.BaseAddress or 0, mbi.RegionSize
            if mbi.State == MEM_COMMIT and mbi.Type == MEM_MAPPED and size == MEM1_VIEW:
                head = read(h, base, 8)
                if head and re.fullmatch(rb'[A-Z0-9]{6}', head[:6]) and head[:6] in LAYOUT:
                    return h, base, head[:6]
            addr = base + size
            if addr >= 0x7FFFFFFF0000:
                break
        k32.CloseHandle(h)
    raise SystemExit('no running P.N.03 found')


def sample(out, seconds):
    h, base, gid = find_view()
    L = LAYOUT[gid]
    host = lambda a: base + (a - 0x80000000)
    u32 = lambda a: struct.unpack('>I', read(h, host(a), 4))[0]
    rows = []
    t0 = time.perf_counter()
    player, last_resolve = None, -1.0
    while True:
        t = time.perf_counter() - t0
        if t > seconds:
            break
        if t - last_resolve > 0.5:
            try:
                root = u32(L['r13'] + L['root_sda']); pv = u32(root + L['root_pv']); p1 = u32(pv); player = u32(p1)
            except Exception:
                player = None
            last_resolve = t
        if not player or not (0x80000000 <= player < 0x81800000):
            time.sleep(0.01)
            continue
        pb = read(h, host(player + 0xC0), 0x40)
        cb = read(h, host(L['cam_data']), 0x48)
        mb = read(h, host(L['move_turn']), 0x0C)
        kb = read(h, host(L['config']), 0x40)
        if not (pb and cb and mb and kb):
            time.sleep(0.005)
            continue
        yaw = struct.unpack_from('>f', pb, 0x10)[0]
        state, sub, phase = pb[0x38], pb[0x39], pb[0x3A]
        cam_yaw, = struct.unpack_from('>f', cb, 4)
        goal, active, gstep, gdir = struct.unpack_from('>fIfi', cb, 0x34)
        flags, follow = struct.unpack_from('>I', kb, 0x1C)[0], struct.unpack_from('>I', kb, 0x2C)[0]
        req, = struct.unpack_from('>f', kb, 0x30); req_step, = struct.unpack_from('>f', kb, 0x38)
        tstate, entry, delta = struct.unpack_from('>Iff', mb, 0)
        rows.append((round(t, 4), yaw, state, sub, phase, cam_yaw, goal, active, gstep, gdir, flags, follow, req, req_step, tstate, entry, delta))
        time.sleep(0.002)
    k32.CloseHandle(h)
    with open(out, 'w', newline='') as f:
        w = csv.writer(f); w.writerow(FIELDS); w.writerows(rows)
    print(f'{gid.decode()}: {len(rows)} samples over {seconds} s -> {out}')


def summarize(path):
    rows = list(csv.DictReader(open(path)))
    frames = []
    last = None
    for r in rows:
        key = (r['yaw'], r['state'], r['sub'], r['phase'], r['cam_yaw'], r['goal'], r['active'], r['flags'], r['follow'], r['tstate'])
        if key != last:
            frames.append(r); last = key
    deg = lambda v: math.degrees(float(v))
    print(f'{len(rows)} samples -> {len(frames)} distinct frames')
    in_turn = False
    for i, r in enumerate(frames):
        turning = r['state'] == '1' and r['sub'] == '8'
        if turning and not in_turn:
            print(f'--- turn starts at t={r["t"]} (frame {i})')
        if turning or in_turn:
            prev = frames[i - 1] if i else r
            dy = (deg(r['yaw']) - deg(prev['yaw']) + 540) % 360 - 180
            dc = (deg(r['cam_yaw']) - deg(prev['cam_yaw']) + 540) % 360 - 180
            print(f'  t={r["t"]:>8} st={r["state"]}/{r["sub"]}/{r["phase"]:>2} yaw={deg(r["yaw"]):8.2f} ({dy:+6.2f})  cam={deg(r["cam_yaw"]):8.2f} ({dc:+6.2f})  goal={deg(r["goal"]):8.2f} act={r["active"]} gstep={deg(r["gstep"]):5.1f} dir={r["gdir"]}  flags={int(r["flags"]):#x} follow={r["follow"]} req={deg(r["req"]):8.2f} rstep={deg(r["req_step"]):+6.1f}  turn={r["tstate"]} entry={deg(r["entry"]):8.2f} delta={deg(r["delta"]):+7.1f}')
        if in_turn and not turning:
            # keep printing a few frames after the turn ends
            tail = frames[i + 1:i + 12]
            for j, q in enumerate(tail):
                prev = frames[i + j]
                dy = (deg(q['yaw']) - deg(prev['yaw']) + 540) % 360 - 180
                dc = (deg(q['cam_yaw']) - deg(prev['cam_yaw']) + 540) % 360 - 180
                print(f'  t={q["t"]:>8} st={q["state"]}/{q["sub"]}/{q["phase"]:>2} yaw={deg(q["yaw"]):8.2f} ({dy:+6.2f})  cam={deg(q["cam_yaw"]):8.2f} ({dc:+6.2f})  goal={deg(q["goal"]):8.2f} act={q["active"]} flags={int(q["flags"]):#x} follow={q["follow"]} turn={q["tstate"]}')
            print('--- turn ended')
        in_turn = turning


if __name__ == '__main__':
    if sys.argv[1] == '--summarize':
        summarize(sys.argv[2])
    else:
        sample(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 30.0)
