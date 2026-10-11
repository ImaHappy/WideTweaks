#!/usr/bin/env python3
"""WideFix: ultrawide / any-aspect-ratio patcher for PC games.

Each supported game is one file in fixes/ that says where its executable is and which bytes to change. WideFix
finds the game in your Steam libraries, backs up the executable, and writes values computed from your resolution.

  widefix list                                  supported games
  widefix patch <game> [--res 3440x1440] [--path DIR]
  widefix restore <game> [--path DIR]           put the original executable back

Never distributes game files: it only edits your own copy, and keeps the original next to it (*.widefix-backup).
"""
import argparse, json, os, pathlib, platform, re, shutil, struct, sys

HERE = pathlib.Path(getattr(sys, '_MEIPASS', pathlib.Path(__file__).resolve().parent))   # also inside the .exe build
FIXES = HERE / 'fixes'
BACKUP = '.widefix-backup'


def fixes():
    """{id: fix definition} from fixes/*.json (id = file name)."""
    return {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in sorted(FIXES.glob('*.json'))}


def steam_libraries():
    """Steam library folders on this machine (Linux, Steam Deck, Windows)."""
    roots = [pathlib.Path.home() / p for p in ('.local/share/Steam', '.steam/steam', '.var/app/com.valvesoftware.Steam/.local/share/Steam')]
    if platform.system() == 'Windows':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as k:
                roots.insert(0, pathlib.Path(winreg.QueryValueEx(k, 'SteamPath')[0]))
        except OSError:
            pass
        roots.append(pathlib.Path(r'C:\Program Files (x86)\Steam'))
    libs = []
    for root in roots:
        vdf = root / 'steamapps' / 'libraryfolders.vdf'
        if vdf.is_file():
            libs += [pathlib.Path(p.replace('\\\\', '\\')) for p in re.findall(r'"path"\s*"([^"]+)"', vdf.read_text(errors='ignore'))]
            libs.append(root)
    return list(dict.fromkeys(libs))


def find_game(fix):
    """The game's install folder from its Steam app id, or None."""
    for lib in steam_libraries():
        manifest = lib / 'steamapps' / f"appmanifest_{fix['steam_appid']}.acf"
        if manifest.is_file():
            m = re.search(r'"installdir"\s*"([^"]+)"', manifest.read_text(errors='ignore'))
            if m and (lib / 'steamapps' / 'common' / m.group(1)).is_dir():
                return lib / 'steamapps' / 'common' / m.group(1)
    return None


def screen_resolution():
    """The main screen's resolution on Windows; None elsewhere (pass --res)."""
    if platform.system() != 'Windows':
        return None
    import ctypes
    ctypes.windll.user32.SetProcessDPIAware()
    return ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)


def value(kind, width, height):
    """The bytes a patch writes: kind 'float:aspect' is width/height as a 32-bit float."""
    if kind == 'float:aspect':
        return struct.pack('<f', width / height)
    raise ValueError(f'unknown value kind {kind!r}')


def apply(data, patches, width, height):
    """Patched copy of an executable's bytes. Each patch's pattern ("AB AA ?? 40", ?? = any byte) must occur exactly
    once; its value is written `offset` bytes from where the pattern starts. Raises ValueError otherwise."""
    out = bytearray(data)
    for p in patches:
        rx = re.compile(b''.join(b'.' if h == '??' else re.escape(bytes.fromhex(h)) for h in p['pattern'].split()), re.S)
        hits = [m.start() for m in rx.finditer(data)]
        if len(hits) != 1:
            raise ValueError(f"{p['description']}: pattern found {len(hits)} times (expected once): unsupported game version")
        v = value(p['value'], width, height)
        out[hits[0] + p.get('offset', 0):hits[0] + p.get('offset', 0) + len(v)] = v
    return bytes(out)


def patch(fix, game, width, height):
    exe = game / fix['exe']
    backup = exe.with_name(exe.name + BACKUP)
    data = exe.read_bytes()
    try:
        new = apply(data, fix['patches'], width, height)
        shutil.copy2(exe, backup)                       # fresh original (also after a game update)
    except ValueError:
        # Already patched (e.g. for another resolution): patch again from the original, if it is this version.
        if not backup.is_file() or backup.stat().st_size != len(data):
            raise
        new = apply(backup.read_bytes(), fix['patches'], width, height)
    exe.write_bytes(new)
    return exe, backup


def restore(fix, game):
    exe = game / fix['exe']
    backup = exe.with_name(exe.name + BACKUP)
    if not backup.is_file():
        raise SystemExit(f'No backup next to {exe}: nothing to restore (or use Steam\'s "Verify integrity of game files").')
    shutil.copy2(backup, exe)
    return exe


def main(argv=None):
    ap = argparse.ArgumentParser(prog='widefix', description='Ultrawide / any-aspect-ratio patcher for PC games.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list', help='supported games')
    for name in ('patch', 'restore'):
        s = sub.add_parser(name)
        s.add_argument('game', help='game id from "widefix list"')
        s.add_argument('--path', type=pathlib.Path, help='game install folder (default: found through Steam)')
        if name == 'patch':
            s.add_argument('--res', help='your resolution, e.g. 3440x1440 (default: the main screen, on Windows)')
    a = ap.parse_args(argv)
    all_fixes = fixes()
    if a.cmd == 'list':
        for gid, f in all_fixes.items():
            print(f"{gid:24} {f['name']}  (Steam {f['steam_appid']}) - {f['summary']}")
        return
    fix = all_fixes.get(a.game) or ap.error(f'unknown game {a.game!r}; see "widefix list"')
    game = a.path or find_game(fix) or ap.error(f"{fix['name']} not found in your Steam libraries; pass --path")
    if a.cmd == 'restore':
        print(f'Restored {restore(fix, game)}')
        return
    res = (tuple(int(n) for n in a.res.lower().split('x')) if a.res else screen_resolution()) or ap.error('pass your resolution, e.g. --res 3440x1440')
    try:
        exe, backup = patch(fix, game, *res)
    except (ValueError, OSError) as e:
        raise SystemExit(f'Not patched: {e}')
    print(f"Patched {exe} for {res[0]}x{res[1]} (aspect {res[0] / res[1]:.4f}).\nOriginal kept as {backup.name}; undo: widefix restore {a.game}")


if __name__ == '__main__':
    main()
