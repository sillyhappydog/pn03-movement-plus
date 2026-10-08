"""Simulate P.N.03's follow camera (camctrlBehind, JP 0x80018198) against the camera-patch yaw schedules.

Game model per frame (from the disassembly, JP addresses):
  L_des = P + M * la_off                      look-at target (player+0xBF0 + M*(player+0xBE4))
  L     = 0.7*L + 0.3*L_des                   0x80018324.. (coefficient 0x80160544 = 0.7)
  E_des = M * eye_off                         presets A[+0xC2C] + B[+0xC2E] + player+0xBD8, through player+0xBFC
  D = E_des - L ; C = E - L ; th = angle(D, C)
  if th > 0.00314: K = L + RotAxis(C x D, -0.3*th) * D      0x80018458.. (PSMTXRotAxisRad, 0x80160554 = -0.3)
  else:            K = E
  E     = 0.7*E + 0.3*K                       0x80018510..
Patch schedules set the yaw of M each frame. Wall check (ScrHitCheck2) is ignored.
"""
import math, sys
import numpy as np

def rot_y(yaw):
    s, c = math.sin(yaw), math.cos(yaw)
    # forward of yaw t is (sin t, 0, cos t); rotate local (x, y, z) into world
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])

def rot_axis(axis, rad):
    n = np.linalg.norm(axis)
    if n < 1e-12:
        return np.eye(3)
    a = axis / n
    x, y, z = a
    c, s = math.cos(rad), math.sin(rad)
    t = 1 - c
    return np.array([[t*x*x + c, t*x*y - s*z, t*x*z + s*y],
                     [t*x*y + s*z, t*y*y + c, t*y*z - s*x],
                     [t*x*z - s*y, t*y*z + s*x, t*z*z + c]])

def vec_angle(a, b):
    d = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return math.acos(max(-1.0, min(1.0, d)))

def simulate(schedule, eye_off, la_off, frames=24, direct=False):
    """schedule(frame) -> yaw (rad) of the camera matrix for that frame. frame 0 = before the request.
    direct=True: the patch also writes E and L to the goal orbit each frame (proposed v0.8)."""
    P = np.zeros(3)
    M = rot_y(schedule(0))
    L = P + M @ la_off
    E = M @ eye_off
    rel0 = E - L
    h0 = math.degrees(math.atan2(rel0[0], rel0[2]))
    elev0 = math.degrees(math.atan2(rel0[1], math.hypot(rel0[0], rel0[2])))
    R0 = np.linalg.norm(rel0)
    out = []
    for f in range(1, frames + 1):
        yaw = schedule(f)
        M = rot_y(yaw)
        L_des = P + M @ la_off
        E_des = M @ eye_off
        if direct:
            L, E = L_des.copy(), E_des.copy()
        L = 0.7 * L + 0.3 * L_des
        D = E_des - L
        C = E - L
        th = vec_angle(D, C)
        if th > 0.0031415927:
            K = L + rot_axis(np.cross(C, D), -0.3 * th) @ D
        else:
            K = E.copy()
        E = 0.7 * E + 0.3 * K
        rel = E - L
        h = (math.degrees(math.atan2(rel[0], rel[2])) - h0) % 360.0   # horizontal angle travelled around the look-at
        if h > 359.0: h = 0.0
        elev = math.degrees(math.atan2(rel[1], math.hypot(rel[0], rel[2]))) - elev0   # elevation change (over-the-top symptom)
        out.append((f, math.degrees(yaw), h, elev, np.linalg.norm(rel) / R0, math.degrees(th)))
    return out

def step_schedule(total_deg, step_deg):
    total = math.radians(total_deg)
    step = math.radians(step_deg)
    def s(f):
        if f == 0:
            return 0.0
        y = min(total, step * f)
        return y
    return s

def instant_schedule(total_deg):
    total = math.radians(total_deg)
    return lambda f: 0.0 if f == 0 else total

def easeout_schedule(total_deg, first_deg, k, floor_deg):
    """first frame moves first_deg, then k*remaining per frame with a floor; snap when within floor."""
    total = math.radians(total_deg)
    vals = [0.0]
    y = 0.0
    while y < total - 1e-9:
        rem = total - y
        st = math.radians(first_deg) if len(vals) == 1 else max(math.radians(floor_deg), k * rem)
        y = total if rem <= st else y + st
        vals.append(y)
    return lambda f: vals[min(f, len(vals) - 1)]

def summarize(rows, total_deg):
    """frames until the eye is within 10% / 5 deg of the goal (and level), peak elevation change, min radius, max gap."""
    t90 = t5 = None
    for f, yaw, h, elev, r, th in rows:
        level = abs(elev) < 10
        if t90 is None and h >= 0.9 * total_deg and level: t90 = f
        if t5 is None and h >= total_deg - 5 and level: t5 = f
    peak_elev = max(abs(e) for _, _, _, e, _, _ in rows)
    min_r = min(r for *_, r, _ in rows)
    max_gap = max(th for *_, th in rows)
    return t90, t5, peak_elev, min_r, max_gap

if __name__ == '__main__':
    # eye_off: local offset of the eye from the player origin (x right?, y up, z forward; behind = -z)
    # la_off: local offset of the look-at point from the player origin
    ex, ey, ez, lx, ly, lz = (float(v) for v in sys.argv[1:7])
    total = float(sys.argv[7]) if len(sys.argv) > 7 else 180.0
    eye_off = np.array([ex, ey, ez]); la_off = np.array([lx, ly, lz])
    R = np.linalg.norm(eye_off - la_off)
    print(f'eye_off={eye_off} la_off={la_off} |E-L|={R:.0f} total={total}  (track: angle travelled, +elev change if >10)')
    cases = [('v0.6 instant', instant_schedule(total), False)]
    for st in (15, 20, 30, 45, 60, 90, 120):
        cases.append((f'v0.7 step {st}', step_schedule(total, st), False))
    cases.append(('direct 90/0.5/20', easeout_schedule(total, 90, 0.5, 20), True))
    cases.append(('direct 60/0.5/20', easeout_schedule(total, 60, 0.5, 20), True))
    cases.append(('direct step 45', step_schedule(total, 45), True))
    cases.append(('direct step 60', step_schedule(total, 60), True))
    print(f'{"case":20} {"90%":>4} {"<5deg":>5} {"peak elev":>9} {"min r/R":>7} {"max gap":>7}   eye angle per frame')
    for name, sch, direct in cases:
        rows = simulate(sch, eye_off, la_off, direct=direct)
        t90, t5, pe, mr, mg = summarize(rows, total)
        track = ' '.join(f'{h:.0f}' + (f'({e:+.0f})' if abs(e) > 10 else '') for _, _, h, e, _, _ in rows[:14])
        print(f'{name:20} {str(t90):>4} {str(t5):>5} {pe:9.1f} {mr:7.2f} {mg:7.0f}   {track}')
