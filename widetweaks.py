#!/usr/bin/env python3
"""WideTweaks: Happy's ultrawide fixes, by ImaHappy (imahappy.dev).
Ultrawide fixes, FOV adjustments, HUD corrections, and more.

Each supported game is one file in fixes/ that says where its executable is and which bytes to change. WideTweaks
finds the game in your Steam libraries, backs up the executable, and writes values computed from your resolution.

  widetweaks                                    the app window (also what double-clicking widetweaks.exe opens)
  widetweaks list                                  supported games
  widetweaks patch <game> [--res 3440x1440] [--path DIR]
  widetweaks restore <game> [--path DIR]           put the original executable back

Never distributes game files: it only edits your own copy, and keeps the original next to it (*.widetweaks-backup).
"""
import argparse, json, os, pathlib, platform, re, shutil, struct, sys

TITLE = "WideTweaks · Happy's Ultrawide Fixes · imahappy.dev/widetweaks"
HERE = pathlib.Path(getattr(sys, '_MEIPASS', pathlib.Path(__file__).resolve().parent))   # also inside the .exe build
FIXES = HERE / 'fixes'
BACKUP = '.widetweaks-backup'


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
    """The main screen's resolution: Windows' primary screen; on Linux / Steam Deck xrandr's primary screen, else the
    largest one. None if unknown (pass --res)."""
    if platform.system() != 'Windows':
        import subprocess
        try:
            out = subprocess.run(['xrandr', '--current'], capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        screens = [(bool(p), int(w), int(h)) for p, w, h in re.findall(r' connected( primary)? (\d+)x(\d+)\+', out)]
        return max(screens, key=lambda s: (s[0], s[1] * s[2]))[1:] if screens else None
    import ctypes
    ctypes.windll.user32.SetProcessDPIAware()
    return ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)


def value(kind, width, height):
    """The bytes a patch writes: kind 'float:aspect' is width/height as a 32-bit float."""
    if kind == 'float:aspect':
        return struct.pack('<f', width / height)
    raise ValueError(f'unknown value kind {kind!r}')


def spots(data, patches):
    """[(position, patch)]: where each patch writes. Each pattern ("AB AA ?? 40", ?? = any byte) must occur exactly
    once, and may not use ?? where the value goes (the patched file would still match, and look original).
    Raises ValueError otherwise."""
    out = []
    for p in patches:
        tokens, at, size = p['pattern'].split(), p.get('offset', 0), len(value(p['value'], 16, 9))
        if '??' in tokens[at:at + size]:
            raise ValueError(f"{p['description']}: the pattern has ?? where the value is written")
        rx = re.compile(b''.join(b'.' if h == '??' else re.escape(bytes.fromhex(h)) for h in tokens), re.S)
        hits = [m.start() for m in rx.finditer(data)]
        if len(hits) != 1:
            raise ValueError(f"{p['description']}: pattern found {len(hits)} times (expected once): unsupported game version")
        out.append((hits[0] + at, p))
    return out


def apply(data, patches, width, height):
    """Patched copy of an executable's bytes (see spots)."""
    out = bytearray(data)
    for at, p in spots(data, patches):
        v = value(p['value'], width, height)
        out[at:at + len(v)] = v
    return bytes(out)


def ours(fix, data, backup):
    """True if data is the backup patched by WideTweaks (same bytes everywhere except where the fix writes), so not
    a newer game version that happens to have the same size."""
    if len(data) != len(backup):
        return False
    try:
        theirs = bytearray(data)
        for at, p in spots(backup, fix['patches']):
            n = len(value(p['value'], 16, 9))
            theirs[at:at + n] = backup[at:at + n]
    except ValueError:
        return False
    return theirs == backup


def write(exe, data):
    """Replace the executable in one step, so a crash or full disk never leaves half a file."""
    tmp = exe.with_name(exe.name + '.widetweaks-tmp')
    try:
        tmp.write_bytes(data)
        shutil.copymode(exe, tmp)
        os.replace(tmp, exe)
    finally:
        tmp.unlink(missing_ok=True)


def patch(fix, game, width, height):
    exe = game / fix['exe']
    backup = exe.with_name(exe.name + BACKUP)
    data = exe.read_bytes()
    try:
        new = apply(data, fix['patches'], width, height)
        shutil.copy2(exe, backup)                       # fresh original (also after a game update)
    except ValueError:
        # Already patched (e.g. for another resolution): patch again from the original, if it is this version.
        if not backup.is_file() or not ours(fix, data, original := backup.read_bytes()):
            raise
        new = apply(original, fix['patches'], width, height)
    write(exe, new)
    return exe, backup


def restore(fix, game):
    exe = game / fix['exe']
    backup = exe.with_name(exe.name + BACKUP)
    if not backup.is_file():
        raise ValueError(f'No backup next to {exe}: nothing to restore (or use Steam\'s "Verify integrity of game files").')
    original = backup.read_bytes()
    if not ours(fix, exe.read_bytes(), original):
        raise ValueError(f'{exe.name} is not the WideTweaks-patched backup (game updated?): left as it is.')
    write(exe, original)
    return exe


def status(fix, game):
    """'missing' (no executable), 'off' (original), 'on' (patched by WideTweaks) or 'unsupported' (unknown version)."""
    exe = game / fix['exe'] if game else None
    if not exe or not exe.is_file():
        return 'missing'
    data = exe.read_bytes()
    try:
        spots(data, fix['patches'])
        return 'off'
    except ValueError:
        backup = exe.with_name(exe.name + BACKUP)
        return 'on' if backup.is_file() and ours(fix, data, backup.read_bytes()) else 'unsupported'


def parse_resolution(text):
    """(width, height) from "3440x1440", "3440 × 1440", "3440:1440"..., or None."""
    m = re.fullmatch(r'\s*(\d{3,5})\s*[x×*: ]\s*(\d{3,5})\s*', text or '')
    return (int(m.group(1)), int(m.group(2))) if m else None


def main(argv=None):
    ap = argparse.ArgumentParser(prog='widetweaks', description=TITLE)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list', help='supported games')
    for name in ('patch', 'restore'):
        s = sub.add_parser(name)
        s.add_argument('game', help='game id from "widetweaks list"')
        s.add_argument('--path', type=pathlib.Path, help='game install folder (default: found through Steam)')
        if name == 'patch':
            s.add_argument('--res', help='your resolution, e.g. 3440x1440 (default: the main screen)')
    if not (sys.argv[1:] if argv is None else argv):       # double-clicked: open the window
        import widetweaks_app
        return widetweaks_app.run()
    a = ap.parse_args(argv)
    print(TITLE)
    all_fixes = fixes()
    if a.cmd == 'list':
        for gid, f in all_fixes.items():
            print(f"{gid:24} {f['name']}  (Steam {f['steam_appid']}) - {f['summary']}")
        return
    fix = all_fixes.get(a.game) or ap.error(f'unknown game {a.game!r}; see "widetweaks list"')
    game = a.path or find_game(fix) or ap.error(f"{fix['name']} not found in your Steam libraries; pass --path")
    if a.cmd == 'restore':
        try:
            print(f'Restored {restore(fix, game)}')
        except ValueError as e:
            raise SystemExit(str(e))
        return
    res = (parse_resolution(a.res) if a.res else screen_resolution()) or ap.error('pass your resolution, e.g. --res 3440x1440')
    try:
        exe, backup = patch(fix, game, *res)
    except (ValueError, OSError) as e:
        raise SystemExit(f'Not patched: {e}')
    print(f"Patched {exe} for {res[0]}x{res[1]} (aspect {res[0] / res[1]:.4f}).\nOriginal kept as {backup.name}; undo: widetweaks restore {a.game}")


if __name__ == '__main__':
    main()
