"""Apply Gecko codes and OnFrame patches to a Dolphin per-game INI (GameSettings/<GameID>.ini).

Rewrites only the [Gecko] / [Gecko_Enabled] / [Gecko_Disabled] and [OnFrame] /
[OnFrame_Enabled] / [OnFrame_Disabled] sections in the same format Dolphin itself
writes (LF, UTF-8 without BOM, '$Name' headers followed by body lines). Every other
section is kept verbatim. A backup of the previous file is stored under --backup-dir
before writing.

Gecko code files contain 'XXXXXXXX YYYYYYYY' lines. Patch files contain Dolphin
OnFrame entries, one per line: '0xADDRESS:dword:0xVALUE' or the conditional form
'0xADDRESS:dword:0xVALUE:0xCOMPARAND' (byte/word/dword).

Examples:
  py -3.13 work/apply_gecko.py --ini "%USERPROFILE%/Documents/Dolphin Emulator/GameSettings/GPNJ08.ini" \
      --patch "Camera Relative Movement v0.8=outputs/pn03-camera-move-v08/GPNJ08-camera-move-v08.patch.txt" \
      --enable-patch "Camera Relative Movement v0.8" --disable "Camera Relative Movement v0.7" --list

Dolphin reads the file when the game boots (and when the properties dialog opens).
Close the game properties dialog before running this, and restart the game afterwards.
Note: Dolphin's Gecko code list only has about 3.2 KB of room (0x80001800..0x80003000
minus the code handler); codes that do not fit are silently skipped. Large payloads
go through OnFrame patches instead.
"""
import argparse
import datetime as dt
import re
import shutil
from pathlib import Path

CODE_LINE = re.compile(r'^[0-9A-Fa-f]{8} [0-9A-Fa-f]{8}$')
PATCH_LINE = re.compile(r'^0x[0-9A-Fa-f]{8}:(byte|word|dword):0x[0-9A-Fa-f]{1,8}(:0x[0-9A-Fa-f]{1,8})?$')
FAMILIES = {
    'code': ('Gecko', 'Gecko_Enabled', 'Gecko_Disabled', CODE_LINE, 'Gecko code'),
    'patch': ('OnFrame', 'OnFrame_Enabled', 'OnFrame_Disabled', PATCH_LINE, 'OnFrame patch'),
}


def parse_ini(text):
    """Return an ordered list of (section_name, lines); lines exclude the header."""
    sections = []
    name = None
    lines = []
    for raw in text.split('\n'):
        line = raw.rstrip('\r')
        if line.startswith('[') and line.endswith(']'):
            if name is not None or lines:
                sections.append((name, lines))
            name = line[1:-1]
            lines = []
        else:
            lines.append(line)
    sections.append((name, lines))
    return sections


def parse_entries(lines):
    """'$Name' + body lines -> ordered dict name -> list of body lines."""
    entries = {}
    current = None
    for line in lines:
        if not line.strip():
            continue
        if line[0] in '$+':
            current = line[1:].split('[')[0].strip()
            entries[current] = []
        elif current is not None:
            entries[current].append(line)
    return entries


def load_body(path, pattern, kind):
    body = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if not pattern.match(line):
            raise SystemExit(f'not a {kind} line in {path}: {line!r}')
        body.append(line.upper() if kind == 'Gecko code' else line)
    if not body:
        raise SystemExit(f'empty {kind} file: {path}')
    return body


def update_family(by_name, family, adds, enables, disables, removes):
    section, sec_enabled, sec_disabled, pattern, kind = FAMILIES[family]
    entries = parse_entries(by_name.get(section, []))
    enabled = {l[1:].strip() for l in by_name.get(sec_enabled, []) if l.startswith('$')}
    disabled = {l[1:].strip() for l in by_name.get(sec_disabled, []) if l.startswith('$')}
    for item in adds:
        name, _, file = item.partition('=')
        name = name.strip()
        if not name or not file:
            raise SystemExit(f'expected NAME=FILE, got {item!r}')
        if any(ch in name for ch in '[]$'):
            raise SystemExit(f'name must not contain [ ] or $: {name!r}')
        entries[name] = load_body(file, pattern, kind)
    for name in removes:
        entries.pop(name, None)
        enabled.discard(name)
        disabled.discard(name)
    for name in disables:
        if name not in entries:
            raise SystemExit(f'cannot disable unknown {kind} {name!r}')
        enabled.discard(name)
        disabled.add(name)
    for name in enables:
        if name not in entries:
            raise SystemExit(f'cannot enable unknown {kind} {name!r}')
        enabled.add(name)
        disabled.discard(name)
    enabled &= set(entries)
    disabled = (disabled & set(entries)) - enabled
    body_lines = []
    for name, body in entries.items():
        body_lines.append('$' + name)
        body_lines.extend(body)
    out = [(section, body_lines), (sec_enabled, ['$' + n for n in entries if n in enabled])]
    if disabled or sec_disabled in by_name:
        out.append((sec_disabled, ['$' + n for n in entries if n in disabled]))
    return entries, enabled, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ini', required=True, type=Path)
    ap.add_argument('--code', action='append', default=[], metavar='NAME=FILE', help='add or replace a Gecko code')
    ap.add_argument('--enable', action='append', default=[], metavar='NAME', help='enable a Gecko code')
    ap.add_argument('--disable', action='append', default=[], metavar='NAME', help='disable a Gecko code')
    ap.add_argument('--remove', action='append', default=[], metavar='NAME', help='remove a Gecko code')
    ap.add_argument('--patch', action='append', default=[], metavar='NAME=FILE', help='add or replace an OnFrame patch')
    ap.add_argument('--enable-patch', action='append', default=[], metavar='NAME')
    ap.add_argument('--disable-patch', action='append', default=[], metavar='NAME')
    ap.add_argument('--remove-patch', action='append', default=[], metavar='NAME')
    ap.add_argument('--backup-dir', type=Path, default=Path(__file__).parent / 'ini-backups')
    ap.add_argument('--list', action='store_true', help='print the resulting code and patch lists')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    original = a.ini.read_text(encoding='utf-8-sig') if a.ini.exists() else ''
    sections = parse_ini(original) if original else [(None, [])]
    by_name = {name: lines for name, lines in sections}
    codes, codes_enabled, code_sections = update_family(by_name, 'code', a.code, a.enable, a.disable, a.remove)
    patches, patches_enabled, patch_sections = update_family(by_name, 'patch', a.patch, a.enable_patch,
                                                             a.disable_patch, a.remove_patch)
    managed = {s for fam in FAMILIES.values() for s in fam[:3]}
    out_sections = [(name, lines) for name, lines in sections if name not in managed]
    out_sections += code_sections + patch_sections

    chunks = []
    for name, lines in out_sections:
        if name is None:
            if any(l.strip() for l in lines):
                chunks.append('\n'.join(lines).rstrip('\n'))
            continue
        chunks.append('[' + name + ']\n' + '\n'.join(lines))
    text = '\n'.join(chunks).rstrip('\n') + '\n'

    if a.list:
        for name, body in codes.items():
            print(f'{"ENABLED " if name in codes_enabled else "disabled"} gecko  {name}  ({len(body)} lines)')
        for name, body in patches.items():
            print(f'{"ENABLED " if name in patches_enabled else "disabled"} patch  {name}  ({len(body)} entries)')
    if a.dry_run:
        print(text)
        return
    if a.ini.exists():
        a.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
        shutil.copy2(a.ini, a.backup_dir / f'{a.ini.name}.{stamp}.bak')
    a.ini.write_text(text, encoding='utf-8', newline='\n')
    back = dict(parse_ini(a.ini.read_text(encoding='utf-8')))
    assert parse_entries(back.get('Gecko', [])) == codes, 'Gecko read-back mismatch'
    assert parse_entries(back.get('OnFrame', [])) == patches, 'OnFrame read-back mismatch'
    print(f'written {a.ini} ({len(text)} bytes, {len(codes)} codes / {len(codes_enabled)} enabled, '
          f'{len(patches)} patches / {len(patches_enabled)} enabled)')


if __name__ == '__main__':
    main()
