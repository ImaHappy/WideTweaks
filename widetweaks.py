#!/usr/bin/env python3
"""WideTweaks: Happy's ultrawide fixes, by ImaHappy (imahappy.dev).
Ultrawide fixes, FOV adjustments, HUD corrections, and more.

Each supported game is one file in fixes/ that says where its executable is and which bytes to change. WideTweaks
finds the game in your Steam libraries, backs up the executable, and writes values computed from your resolution.

  widetweaks                                    the app window (also what double-clicking WideTweaks.exe opens)
  widetweaks list                                  supported games
  widetweaks patch <game> [--res 3440x1440] [--path DIR]
  widetweaks restore <game> [--path DIR]           put the original executable back

Never distributes game files: it only edits your own copy, and keeps the original next to it (*.widetweaks-backup).
"""
import argparse, json, os, pathlib, platform, re, shutil, struct, sys
try:
    import lz4.block as lz4
except ImportError:
    lz4 = None

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
    """The bytes a patch writes: 'float:aspect' is width/height as a 32-bit float; 'float:zoom' how much a 16:9
    picture must grow to fill your width (1.34 at 21:9, 2 at 32:9), 'float:zoom:1.366' the same but at most 1.366
    (e.g. what black bars hid, so nothing is cropped); 'bytes:B0 01 C3' is those bytes (e.g. new instructions)."""
    if kind == 'float:aspect':
        return struct.pack('<f', width / height)
    if kind.startswith('float:zoom'):
        cap = float(kind.split(':')[2]) if kind.count(':') == 2 else float('inf')
        return struct.pack('<f', min(cap, max(1.0, width / height * 9 / 16)))
    if kind.startswith('bytes:'):
        return bytes.fromhex(kind[6:])
    raise ValueError(f'unknown value kind {kind!r}')


def spots(data, patches):
    """[(position, patch)]: where each patch writes. Each pattern ("AB AA ?? 40", ?? = any byte) must occur exactly
    once, and the value must change at least one fixed byte of it (else the patched file would still match, and
    look original). Raises ValueError otherwise."""
    out = []
    for p in patches:
        tokens, at, v = p['pattern'].split(), p.get('offset', 0), value(p['value'], 21, 9)   # checked at an ultrawide shape
        if all(t == '??' or bytes.fromhex(t)[0] == b for t, b in zip(tokens[at:at + len(v)], v)):
            raise ValueError(f"{p['description']}: the value changes no fixed byte of the pattern")
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


def ours(data, backup):
    """True if data is the backup with a few bytes patched by WideTweaks (by this or an older version of the fix),
    not a newer game version that happens to have the same size."""
    if len(data) != len(backup):
        return False
    changed, limit = 0, min(4096, len(data) // 16)   # a game update changes far more; fixes write a few bytes per spot
    for i in range(0, len(data), 1 << 20):              # compare big blocks, then 4 KB slices, then bytes (C speed first)
        if data[i:i + (1 << 20)] == backup[i:i + (1 << 20)]:
            continue
        for j in range(i, min(i + (1 << 20), len(data)), 4096):
            a, b = data[j:j + 4096], backup[j:j + 4096]
            if a != b:
                changed += sum(x != y for x, y in zip(a, b))
                if changed > limit:
                    return False
    return True


def running(game):
    """True if a program has a file in the game folder open, i.e. the game is running (Linux: /proc; on Windows
    replacing an open file fails anyway). Swapping files under a running Unity game crashes it."""
    folder = str(game.resolve()) + os.sep
    for fd in pathlib.Path('/proc').glob('[0-9]*/fd/*'):
        try:
            if os.readlink(fd).startswith(folder):
                return True
        except OSError:
            pass
    return False


def stamp(exe):
    """Size and modification time of a file WideTweaks wrote, kept next to it: while they match, the file is still
    ours and needn't be read and compared with its backup (166 MB for some Unity bundles)."""
    return exe.with_name(exe.name + '.widetweaks-stamp')


def unchanged(exe):
    try:
        st = exe.stat()
        return stamp(exe).read_text() == f'{st.st_size} {st.st_mtime_ns}'
    except OSError:
        return False


def write(exe, data):
    """Replace the executable in one step, so a crash or full disk never leaves half a file."""
    tmp = exe.with_name(exe.name + '.widetweaks-tmp')
    try:
        tmp.write_bytes(data)
        shutil.copymode(exe, tmp)
        os.replace(tmp, exe)
        st = exe.stat()
        stamp(exe).write_text(f'{st.st_size} {st.st_mtime_ns}')
    finally:
        tmp.unlink(missing_ok=True)


def lz4_block(src, size):
    """One LZ4 block, decompressed (the format Unity compresses asset bundles with). Uses the lz4 package when it is
    installed (the .exe has it; about 50x faster), else plain Python."""
    if lz4:
        try:
            return lz4.decompress(src, uncompressed_size=size)
        except Exception as e:                      # lz4.block.LZ4BlockError
            raise ValueError('damaged LZ4 data') from e
    out, i = bytearray(), 0
    while i < len(src):
        token = src[i]; i += 1
        n = token >> 4
        if n == 15:
            while src[i] == 255: n += 255; i += 1
            n += src[i]; i += 1
        out += src[i:i + n]; i += n
        if i >= len(src):
            break
        back = src[i] | src[i + 1] << 8; i += 2
        n = token & 15
        if n == 15:
            while src[i] == 255: n += 255; i += 1
            n += src[i]; i += 1
        n += 4
        while n > 0:                                # the copy may overlap what it is writing
            chunk = out[len(out) - back:len(out) - back + n]; out += chunk; n -= len(chunk)
    if len(out) != size:
        raise ValueError('damaged LZ4 data')
    return bytes(out)


def bundle_parts(data):
    """A UnityFS file's header, flags, directory (decompressed) and [(size, packed size, flags, offset)] per block."""
    o = data.index(b'\0', data.index(b'\0', 12) + 1) + 1      # after the signature, format, two version strings
    head = data[:o]
    _, csize, usize, flags = struct.unpack_from('>qIII', data, o)
    if flags & 0x80:
        raise ValueError('Unity bundle with its directory at the end: not supported')   # shortcut: Unity writes it first by default; add if a game needs it
    o = align(o + 20)
    info = unpack(flags, data[o:o + csize], usize)
    o += csize
    o = align(o) if flags & 0x200 else o
    count, blocks = struct.unpack_from('>i', info, 16)[0], []
    for b in range(count):
        size, packed, bflags = struct.unpack_from('>IIH', info, 20 + 10 * b)
        blocks.append((size, packed, bflags, o)); o += packed
    return head, flags, info, blocks


def align(n):
    return (n + 15) & ~15


def unpack(flags, src, size):
    if flags & 0x3f in (2, 3):
        return lz4_block(src, size)
    if flags & 0x3f:
        raise ValueError('Unity bundle compressed with LZMA: not supported')   # shortcut: no LZMA (1); add if a game uses it
    return src


def build(head, flags, info, blocks):
    """A UnityFS file from its parts; blocks are (size, flags, bytes) and are stored as given (compressed or not)."""
    count = struct.unpack_from('>i', info, 16)[0]
    info = info[:20] + b''.join(struct.pack('>IIH', size, len(b), f) for size, f, b in blocks) + info[20 + 10 * count:]
    start = align(len(head) + 20)
    body = align(start + len(info)) if flags & 0x200 else start + len(info)
    out = bytearray(head + struct.pack('>qIII', body + sum(len(b) for *_, b in blocks), len(info), len(info), flags & ~0x3f))
    out += bytes(start - len(out)) + info
    out += bytes(body - len(out))
    for *_, b in blocks:
        out += b
    return bytes(out)


def unity_bundle(data):
    """A Unity asset bundle (UnityFS) with its LZ4 blocks decompressed, so byte patterns can be found in it; Unity
    loads uncompressed bundles too. Other files come back as they are."""
    if not data.startswith(b'UnityFS\0'):
        return data
    head, flags, info, blocks = bundle_parts(data)
    return build(head, flags, info, [(size, f & ~0x3f, unpack(f, data[o:o + packed], size)) for size, packed, f, o in blocks])


def repack(raw, plain, new):
    """The patched bundle `new` (uncompressed, laid out like `plain` = unity_bundle(raw)) stored small: every block
    that didn't change keeps its compressed bytes from `raw`, only changed blocks are stored uncompressed (Unity allows
    a mix). Other files: `new` itself."""
    if not raw.startswith(b'UnityFS\0'):
        return new
    head, flags, info, blocks = bundle_parts(raw)
    at, out = len(plain) - sum(b[0] for b in blocks), []      # where the data starts in the uncompressed layout
    for size, packed, f, o in blocks:
        same = new[at:at + size] == plain[at:at + size]
        out.append((size, f, raw[o:o + packed]) if same else (size, f & ~0x3f, new[at:at + size]))
        at += size
    return build(head, flags, info, out)


def files(fix):
    """{file in the game folder: its patches}; a patch names its file with "file", else it is the fix's exe."""
    out = {}
    for p in fix['patches']:
        out.setdefault(p.get('file', fix['exe']), []).append(p)
    return out


def read(path):
    return unity_bundle(path.read_bytes())


def toggle(fix, p):
    """The switch a patch belongs to: its "toggle", else the fix's."""
    return p.get('toggle', fix['toggle'])


def toggles(fix):
    return list(dict.fromkeys(toggle(fix, p) for p in fix['patches']))


def setup(fix, game, width, height, on):
    """Make the game's files match the switches in `on` (toggle names): each file is the original with the patches of
    those switches, or the original itself. Originals are kept next to the files; nothing is written unless every file
    can be done. Returns the files changed."""
    if running(game):
        raise ValueError('The game is running: close it first')
    plan = []
    for name, patches in files(fix).items():
        exe = game / name
        backup = exe.with_name(exe.name + BACKUP)
        raw = exe.read_bytes()
        data = unity_bundle(raw)
        try:
            spots(data, patches)                        # every pattern there: this is the original
            raw_original, original, fresh = raw, data, True
        except ValueError:
            # Patched before (other switches, another resolution): start from the original, if it is this version.
            if not backup.is_file():
                raise
            raw_original = backup.read_bytes(); original = unity_bundle(raw_original)
            if not (unchanged(exe) or ours(data, original)):
                raise
            fresh = False
        wanted = [p for p in patches if toggle(fix, p) in on]
        if wanted:
            plan.append((exe, backup, repack(raw_original, original, apply(original, wanted, width, height)), fresh))
        elif not fresh:
            plan.append((exe, backup, raw_original, False))     # all its switches off: the original back
    for exe, backup, new, fresh in plan:
        if fresh:
            shutil.copy2(exe, backup)                   # fresh original (also after a game update)
        write(exe, new)
    return [exe for exe, *_ in plan]


def patch(fix, game, width, height):
    return setup(fix, game, width, height, set(toggles(fix)))


def restore(fix, game):
    """Every file back to the original; refuses (and changes nothing) if one isn't the patched backup."""
    return setup(fix, game, 16, 9, set())


def states(fix, game):
    """{switch: 'missing' (a file isn't there), 'off', 'on' or 'unsupported' (unknown game version)}."""
    found = {t: set() for t in toggles(fix)}
    for name, patches in files(fix).items():
        exe = game / name if game else None
        if not exe or not exe.is_file():
            for p in patches: found[toggle(fix, p)].add('missing')
            continue
        data = read(exe)
        present = {}                                    # each pattern searched once: there (off) or not (patched?)
        for p in patches:
            try: spots(data, [p]); present[id(p)] = True
            except ValueError: present[id(p)] = False
        if all(present.values()):
            for p in patches: found[toggle(fix, p)].add('off')
            continue
        backup = exe.with_name(exe.name + BACKUP)
        known = backup.is_file() and (unchanged(exe) or ours(data, read(backup)))
        for p in patches:
            found[toggle(fix, p)].add('unsupported' if not known else 'off' if present[id(p)] else 'on')
    # only on/off mixed (a change stopped halfway, e.g. a locked file): 'off', so flipping it on finishes the job
    return {t: s.pop() if len(s) == 1 else 'off' if s == {'on', 'off'} else 'unsupported' for t, s in found.items()}


def overall(states):
    """The game as a whole from its switches: 'missing', 'unsupported', 'on' (any switch on) or 'off'."""
    s = set(states.values())
    return next((k for k in ('missing', 'unsupported', 'on') if k in s), 'off')


def status(fix, game):
    return overall(states(fix, game))


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
            print('\n'.join(f'Restored {exe}' for exe in restore(fix, game)))
        except ValueError as e:
            raise SystemExit(str(e))
        return
    res = (parse_resolution(a.res) if a.res else screen_resolution()) or ap.error('pass your resolution, e.g. --res 3440x1440')
    try:
        done = patch(fix, game, *res)
    except (ValueError, OSError) as e:
        raise SystemExit(f'Not patched: {e}')
    for exe in done:
        print(f"Patched {exe} for {res[0]}x{res[1]} (aspect {res[0] / res[1]:.4f}), original kept as {exe.name + BACKUP}")
    print(f'Undo: widetweaks restore {a.game}')


if __name__ == '__main__':
    main()
