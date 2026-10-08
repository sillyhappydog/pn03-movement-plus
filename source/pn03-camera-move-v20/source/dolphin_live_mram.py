"""Dump the emulated main RAM (MEM1, 24 MB) of a running Dolphin to a file. Read-only: the process is opened with
PROCESS_QUERY_INFORMATION | PROCESS_VM_READ and nothing is written to it.

Dolphin maps MEM1 as a 32 MB MEM_MAPPED view (the same criterion Dolphin Memory Engine uses); several such views of
the same memory exist, so the first one whose first six bytes are a plausible game ID is taken (the disc header sits
at 0x80000000). The result has the same layout as work/dolphin_savestate_mram.py's output, so esp_inspect.py and the
other RAM-image tools work on it.

Usage:  py -3.13 dolphin_live_mram.py <out.bin> [expected game id, e.g. GPNE08]
"""
import ctypes, ctypes.wintypes as wt, sys, re
from pathlib import Path

PROCESS_QUERY_INFORMATION, PROCESS_VM_READ = 0x0400, 0x0010
MEM_COMMIT, MEM_MAPPED = 0x1000, 0x40000
MEM1_VIEW, MEM1_SIZE = 0x2000000, 0x1800000
k32 = ctypes.WinDLL('kernel32', use_last_error=True)


class MBI(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p), ('AllocationProtect', wt.DWORD),
                ('PartitionId', wt.WORD), ('RegionSize', ctypes.c_size_t), ('State', wt.DWORD), ('Protect', wt.DWORD),
                ('Type', wt.DWORD)]


class PE32(ctypes.Structure):
    _fields_ = [('dwSize', wt.DWORD), ('cntUsage', wt.DWORD), ('th32ProcessID', wt.DWORD), ('th32DefaultHeapID', ctypes.c_void_p),
                ('th32ModuleID', wt.DWORD), ('cntThreads', wt.DWORD), ('th32ParentProcessID', wt.DWORD), ('pcPriClassBase', wt.LONG),
                ('dwFlags', wt.DWORD), ('szExeFile', ctypes.c_char * 260)]


k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
k32.Process32First.argtypes = [wt.HANDLE, ctypes.POINTER(PE32)]
k32.Process32Next.argtypes = [wt.HANDLE, ctypes.POINTER(PE32)]
k32.CloseHandle.argtypes = [wt.HANDLE]


def dolphin_pids():
    snap = k32.CreateToolhelp32Snapshot(2, 0)
    pe = PE32(); pe.dwSize = ctypes.sizeof(PE32)
    out = []
    ok = k32.Process32First(snap, ctypes.byref(pe))
    while ok:
        if pe.szExeFile.lower().startswith(b'dolphin'):
            out.append((pe.th32ProcessID, pe.szExeFile.decode(errors='replace')))
        ok = k32.Process32Next(snap, ctypes.byref(pe))
    k32.CloseHandle(snap)
    return out


def read(h, addr, n):
    buf = (ctypes.c_char * n)()
    got = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)) or got.value != n:
        return None
    return bytes(buf)


def dump(out, want_id=None):
    pids = dolphin_pids()
    if not pids:
        raise SystemExit('Dolphin is not running')
    for pid, exe in pids:
        h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not h:
            print(f'cannot open {exe} (pid {pid}): error {ctypes.get_last_error()}')
            continue
        addr, mbi = 0, MBI()
        while k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)) == ctypes.sizeof(mbi):
            base, size = mbi.BaseAddress or 0, mbi.RegionSize
            if mbi.State == MEM_COMMIT and mbi.Type == MEM_MAPPED and size == MEM1_VIEW:
                head = read(h, base, 8)
                if head and re.fullmatch(rb'[A-Z0-9]{6}', head[:6]) and (want_id is None or head[:6] == want_id.encode()):
                    data = read(h, base, MEM1_SIZE)
                    if data:
                        Path(out).write_bytes(data)
                        k32.CloseHandle(h)
                        return pid, base, head[:6].decode()
            addr = base + size
            if addr >= 0x7FFFFFFF0000:
                break
        k32.CloseHandle(h)
    raise SystemExit('no MEM1 view with a game ID found (is a game running?)')


if __name__ == '__main__':
    pid, base, gid = dump(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(f'pid {pid}: MEM1 view at {base:#x}, game {gid}, {MEM1_SIZE:#x} bytes -> {sys.argv[1]}')
