"""Print the enclosing function of an address from work/main.dis.txt.

Usage:
  py -3.13 work/fn.py <hexaddr>            print the whole enclosing function
  py -3.13 work/fn.py <hexaddr> --bounds   print only start/end
  py -3.13 work/fn.py <hexaddr> --callers  list bl sites targeting the function start
  py -3.13 work/fn.py <hexaddr> --around N print N lines before/after the address
Function start = nearest preceding 'stwu r1' prologue (or a preceding blr+1 for leaf code).
"""
import bisect
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LINES = ROOT.joinpath('main.dis.txt').read_text(encoding='utf-8', errors='replace').splitlines()
ADDR = [int(l[:8], 16) for l in LINES]
PRO = re.compile(r'stwu\s+r1, -(0x)?[0-9a-fA-F]+\(r1\)')


def index(a):
    i = bisect.bisect_left(ADDR, a)
    if i >= len(ADDR) or ADDR[i] != a:
        raise SystemExit('address not in disassembly: %08x' % a)
    return i


def bounds(a):
    i = index(a)
    s = i
    while s > 0 and not PRO.search(LINES[s]):
        # a leaf function without stwu: stop right after a preceding blr if the
        # line before it is a blr and we passed a mflr-less region (heuristic)
        s -= 1
    e = i + 1
    while e < len(LINES) and not PRO.search(LINES[e]):
        e += 1
    # trim trailing padding after the last blr
    last = e - 1
    while last > i and 'blr' not in LINES[last] and 'nop' in LINES[last]:
        last -= 1
    return s, e


def callers(a):
    pat = 'bl        0x%08x' % a
    return [LINES[i] for i in range(len(LINES)) if pat in LINES[i]]


if __name__ == '__main__':
    a = int(sys.argv[1], 16)
    opt = sys.argv[2] if len(sys.argv) > 2 else ''
    if opt == '--around':
        n = int(sys.argv[3])
        i = index(a)
        print('\n'.join(LINES[max(0, i - n):i + n + 1]))
    else:
        s, e = bounds(a)
        if opt == '--bounds':
            print('function %08x .. %08x (%d lines)' % (ADDR[s], ADDR[e - 1], e - s))
        elif opt == '--callers':
            print('function start %08x' % ADDR[s])
            for l in callers(ADDR[s]):
                print(l)
        else:
            print('\n'.join(LINES[s:e]))
