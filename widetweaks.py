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
import argparse, json, math, os, pathlib, platform, re, shutil, struct, sys, zlib
try:
    import lz4.block as lz4
except ImportError:
    lz4 = None

VERSION = '0.5.4'                 # a release's tag must be v + this (the release workflow checks)
TITLE = f"WideTweaks {VERSION} · Happy's Ultrawide Fixes · imahappy.dev/widetweaks"
REPO = 'ImaHappy/WideTweaks'
HERE = pathlib.Path(getattr(sys, '_MEIPASS', pathlib.Path(__file__).resolve().parent))   # also inside the .exe build
FIXES = HERE / 'fixes'
BACKUP = '.widetweaks-backup'


def fixes():
    """{id: fix definition} from fixes/*.json (id = file name)."""
    return {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in sorted(FIXES.glob('*.json'))}


def version(text):
    """'0.4.0' -> (0, 4, 0), for comparing; 'v0.4.0' too."""
    return tuple(int(n) for n in re.findall(r'\d+', text)[:3])


def supported(fix):
    """True if this WideTweaks is new enough for the fix ("requires": the lowest version that has what it uses)."""
    return version(fix.get('requires', '0')) <= version(VERSION)


def switch_text(fix, name):
    """The plain-language line of a switch: what it changes on screen."""
    return fix.get('switches', {}).get(name, '')


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
    (e.g. what black bars hid, so nothing is cropped); 'float:left:255' / 'float:right:1665' an x on a centred 1920x1080
    UI moved to your screen's left / right edge as far as it was from the 16:9 one; 'bytes:B0 01 C3' is those bytes
    (e.g. new instructions); 'float:fov:45' a field of view of 45 degrees at 16:9 widened for your screen, the height
    kept (Hor+: 45 at 16:9, 58.2 at 3440x1440, 79.3 at 32:9). Parts joined by '+' are written one after another,
    e.g. 'bytes:C7 44 24 70+float:fov:45' (an instruction and its value)."""
    if '+' in kind:
        return b''.join(value(part, width, height) for part in kind.split('+'))
    if kind.startswith('float:fov:'):
        wider = max(1.0, width / height * 9 / 16)
        return struct.pack('<f', math.degrees(2 * math.atan(math.tan(math.radians(float(kind[10:])) / 2) * wider)))
    if kind == 'float:aspect':
        return struct.pack('<f', width / height)
    dx = max(0.0, (1080 * width / height - 1920) / 2)           # 16:9 edge to screen edge, in 1920x1080 units
    if kind.startswith(('float:left:', 'float:right:')):
        return struct.pack('<f', float(kind.split(':')[2]) + (dx if kind.startswith('float:right') else -dx))
    if kind.startswith('swfdouble:right:'):                     # an ActionScript 2 double: its 32-bit halves swapped
        b = struct.pack('<d', float(kind.split(':')[2]) + dx)
        return b[4:] + b[:4]
    if kind == 'int:stage:1920':                                # a 1920x1080 stage as wide as your screen
        return struct.pack('<i', round(1920 + 2 * dx))
    if kind.startswith('float:zoom'):
        cap = float(kind.split(':')[2]) if kind.count(':') == 2 else float('inf')
        return struct.pack('<f', min(cap, max(1.0, width / height * 9 / 16)))
    if kind.startswith('bytes:'):
        return bytes.fromhex(kind[6:])
    raise ValueError(f'unknown value kind {kind!r}')


def spots(data, patches):
    """[(position, patch)]: where each patch writes. Each pattern ("AB AA ?? 40", ?? = any byte) must occur exactly
    once, and the value must change at least one fixed byte of it (else the patched file would still match, and
    look original). A patch with "variants" (one per game build, each its own pattern / offset / value) uses the one
    whose pattern is in the file, so each build is detected by itself. Raises ValueError otherwise."""
    out = []
    for p in patches:
        found = []
        for alt in p.get('variants', [{}]):
            q = {**p, **alt}
            tokens, at = q['pattern'].split(), q.get('offset', 0)
            v = value(q['value'], 21, 9) if 'value' in q else b''       # checked at an ultrawide shape; a layout has no value
            if v and all(t == '??' or bytes.fromhex(t)[0] == b for t, b in zip(tokens[at:at + len(v)], v)):
                raise ValueError(f"{q['description']}: the value changes no fixed byte of the pattern")
            rx = re.compile(b''.join(b'.' if h == '??' else re.escape(bytes.fromhex(h)) for h in tokens), re.S)
            hits = [m.start() for m in rx.finditer(data)]
            if len(hits) > 1:
                raise ValueError(f"{q['description']}: pattern found {len(hits)} times (expected once)")
            found += [(hits[0] + at, q)] if hits else []
        if len(found) != 1:
            raise ValueError(f"{p['description']}: pattern not found: unsupported game version")
        out.append(found[0])
    return out


def apply(data, patches, width, height):
    """Patched copy of an executable's bytes (see spots). A patch with a "layout" instead of a value lays out the
    Scaleform movie its pattern is in (see swf_layout), after the values are written."""
    out = bytearray(data)
    layouts = []
    for at, p in spots(data, patches):
        if 'layout' in p:
            layouts.append((at, p['layout'])); continue
        v = value(p['value'], width, height)
        out[at:at + len(v)] = v
    for at, layout in sorted(layouts, reverse=True):     # from the end: a movie's new length moves only what follows
        start = out.rfind(MOVIE, 0, at + len(MOVIE)); start = out.index(b'\0', start + len(MOVIE)) + 1   # the pattern may start on the marker
        end = out.find(MOVIE, start); end = len(out) if end == -1 else end
        out[start:end] = swf_layout(bytes(out[start:end]), layout, width, height)
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
    for maps in pathlib.Path('/proc').glob('[0-9]*/maps'):    # also a game that keeps no file open: its exe is mapped
        try:
            if ' ' + folder in maps.read_text(errors='ignore'):
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
        return big_pack(raw, plain, new) if len(plain) > len(raw) and plain.startswith(raw) else new
    head, flags, info, blocks = bundle_parts(raw)
    at, out = len(plain) - sum(b[0] for b in blocks), []      # where the data starts in the uncompressed layout
    for size, packed, f, o in blocks:
        same = new[at:at + size] == plain[at:at + size]
        out.append((size, f, raw[o:o + packed]) if same else (size, f & ~0x3f, new[at:at + size]))
        at += size
    return build(head, flags, info, out)


MOVIE = b'\0WideTweaks movie '    # in big_view: marks a movie appended after the archive


def big_movies(data):
    """[(name, at)] for the zlib-compressed Scaleform movies (CFX) in a United Front .big archive (Sleeping Dogs):
    each sits in a chunk (type hash D9 39 2A 44, size at +4 and +8) after a resource header that names it."""
    out, at = [], data.find(b'CFX')
    while at != -1:
        if at >= 0x78 and data[at - 0x78:at - 0x74] == b'\xd9\x39\x2a\x44' and data[at + 8] == 0x78:   # 0x78: zlib
            out.append((data[at - 0x34:at - 0x14].split(b'\0')[0].decode('latin-1'), at))
        at = data.find(b'CFX', at + 1)
    return out


def big_view(data):
    """A .big archive with its Scaleform movies also appended uncompressed (each after MOVIE + name + NUL), so byte
    patterns and layouts can work on them. Other files come back as they are."""
    if not data.startswith(b'\0' * 16) or not (movies := big_movies(data)):
        return data
    out = bytearray(data)
    for name, at in movies:
        out += MOVIE + name.encode('latin-1') + b'\0' + b'GFX' + data[at + 3:at + 8] + zlib.decompressobj().decompress(data[at + 8:at + 8 + (1 << 24)])
    return bytes(out)


def big_pack(raw, plain, new):
    """`new` (a patched big_view of `raw`) as an archive: each changed movie recompressed into its chunk, which may
    grow into the zero padding after it (to the next 4 KB); raises ValueError if one doesn't fit."""
    out = bytearray(new[:len(raw)])
    movies = dict(big_movies(raw))
    def parts(view):
        cut = view.split(MOVIE)[1:]
        return {c[:c.index(b'\0')].decode('latin-1'): c[c.index(b'\0') + 1:] for c in cut}
    before, after = parts(plain), parts(new)
    for name, movie in after.items():
        if movie == before[name]:
            continue
        at = movies[name]; chunk = at - 0x78
        old_end = chunk + 0x10 + struct.unpack_from('<I', raw, chunk + 4)[0]
        room = (old_end + 0xfff) & ~0xfff
        if raw[old_end:room].strip(b'\0'):
            raise ValueError(f'{name}: no room after it in the archive')
        packed = b'CFX' + struct.pack('<B', movie[3]) + struct.pack('<I', len(movie)) + zlib.compress(movie[8:], 9)
        size = align(at - chunk - 0x10 + len(packed))
        if chunk + 0x10 + size > room:
            raise ValueError(f'{name}: the patched movie is {chunk + 0x10 + size - room} bytes too big for its place')
        out[at:room] = packed + bytes(room - at - len(packed))
        struct.pack_into('<I', out, at - 0x10, len(packed))
        struct.pack_into('<II', out, chunk + 4, size, size)
    return bytes(out)


class Bits:
    """Big-endian bit reader/writer for SWF records (RECT, MATRIX)."""
    def __init__(self, data=b'', at=0):
        self.data, self.pos, self.bits = data, at * 8, []
    def read(self, n, signed=False):
        v = 0
        for _ in range(n):
            v = v << 1 | (self.data[self.pos >> 3] >> (7 - (self.pos & 7))) & 1; self.pos += 1
        return v - (1 << n) if signed and n and v >> (n - 1) else v
    def end(self):
        return (self.pos + 7) >> 3
    def write(self, v, n):
        self.bits += [(v >> (n - 1 - i)) & 1 for i in range(n)]
    def bytes(self):
        b = self.bits + [0] * (-len(self.bits) % 8)
        return bytes(int(''.join(map(str, b[i:i + 8])), 2) for i in range(0, len(b), 8))


def nbits(*vals):
    return max(1, max(abs(v) for v in vals).bit_length() + 1)


def swf_matrix(data, at):
    """({'scale', 'rotate', 'translate'}, end) of the SWF MATRIX at `at` (twips; scale and rotate None if absent)."""
    b, m = Bits(data, at), {}
    for k in ('scale', 'rotate'):
        m[k] = (b.read(n := b.read(5), True), b.read(n, True)) if b.read(1) else None
    n = b.read(5); m['translate'] = (b.read(n, True), b.read(n, True))
    return m, b.end()


def swf_matrix_bytes(m):
    b = Bits()
    for k in ('scale', 'rotate'):
        b.write(bool(m[k]), 1)
        if m[k]:
            n = nbits(*m[k]); b.write(n, 5); b.write(m[k][0] & (1 << n) - 1, n); b.write(m[k][1] & (1 << n) - 1, n)
    n = nbits(*m['translate']) if any(m['translate']) else 0
    b.write(n, 5)
    if n:
        b.write(m['translate'][0] & (1 << n) - 1, n); b.write(m['translate'][1] & (1 << n) - 1, n)
    return b.bytes()


def swf_layout(movie, layout, width, height):
    """A Scaleform movie (uncompressed GFX/SWF, 1920x1080 stage) laid out for your screen: the clips named in
    layout["left"] / ["right"] move to the screen's left / right edge as far as they were from the 16:9 one,
    ["widen"] grow sideways around the centre to your width; with layout["stage"] == "wide" the stage itself becomes
    your width (the game then fills the screen with it, no side bars) and everything else stays centred. Only the
    main timeline's placements move (scripts that place clips themselves need their own patches)."""
    dx = max(0.0, (1080 * width / height - 1920) / 2)
    wide = layout.get('stage') == 'wide'
    b = Bits(movie, 8); n = b.read(5); rect = [b.read(n, True) for _ in range(4)]; o = b.end() + 4
    head = bytearray(movie[:8])
    if wide:
        rect[1] = round((1920 + 2 * dx) * 20); w = Bits(); n = nbits(*rect); w.write(n, 5)
        for v in rect: w.write(v & (1 << n) - 1, n)
        head += w.bytes() + movie[b.end():o]
    else:
        head += movie[8:o]
    out, role, depth_of = head, {}, {}
    names = {**{k: 'left' for k in layout.get('left', [])}, **{k: 'right' for k in layout.get('right', [])},
             **{k: 'widen' for k in layout.get('widen', [])}}
    while o < len(movie):
        code, size = movie[o + 1] << 2 | movie[o] >> 6, movie[o] & 63
        hl = 2
        if size == 63:
            size = struct.unpack_from('<I', movie, o + 2)[0]; hl = 6
        body = movie[o + hl:o + hl + size]; o += hl + size
        if code in (26, 70) and body and body[0] & 4:            # PlaceObject2/3 with a matrix
            flags, q = body[0], 1 + (code == 70)
            depth = struct.unpack_from('<H', body, q)[0]; q += 2
            if code == 70 and body[1] & 8:
                q = body.index(b'\0', q) + 1                     # class name
            q += 2 if flags & 2 else 0                           # character id
            m, end = swf_matrix(body, q)
            if flags & 32:                                       # name (after colour transform and ratio)
                r = end
                if flags & 8:
                    c = Bits(body, r); a, mul = c.read(1), c.read(1); k = c.read(4)
                    for _ in range(4 * (a + mul)): c.read(k)
                    r = c.end()
                r += 2 if flags & 16 else 0
                role[depth] = names.get(body[r:body.index(b'\0', r)].decode('latin-1'), 'centre')
            what = role.get(depth, 'centre')
            if wide or what != 'centre':
                tx, ty = m['translate']; shift = round(dx * 20)
                base = shift if wide else 0
                if what == 'left': tx += base - shift
                elif what == 'right': tx += base + shift
                elif what == 'widen':
                    k = (1920 + 2 * dx) / 1920; sx, sy = m['scale'] or (65536, 65536)
                    tx = round(19200 + (tx - 19200) * k) + base; m['scale'] = (round(sx * k), sy)
                else: tx += base
                m['translate'] = (tx, ty)
                body = body[:q] + swf_matrix_bytes(m) + body[end:]
        out += (struct.pack('<HI', code << 6 | 63, len(body)) if len(body) >= 63 or hl == 6 else struct.pack('<H', code << 6 | len(body))) + body
        if code == 0:
            break
    struct.pack_into('<I', out, 4, len(out))
    return bytes(out)


def files(fix):
    """{file in the game folder: its patches}; a patch names its file with "file", else it is the fix's exe."""
    out = {}
    for p in fix['patches']:
        out.setdefault(p.get('file', fix['exe']), []).append(p)
    return out


def view(data):
    """A file's bytes as patches see them: Unity bundles decompressed, .big archives with their movies appended."""
    return big_view(unity_bundle(data))


def read(path):
    return view(path.read_bytes())


def game_build(fix, game):
    """Which of the fix's "builds" (e.g. DX9 / DX11) the installed game is, found by its variant patterns (in the file,
    or in the original kept next to it once patched); None if the fix has no builds or the game isn't found."""
    if 'builds' not in fix or not game:
        return None
    exe = game / fix['exe']
    for path in (exe, exe.with_name(exe.name + BACKUP)):
        if path.is_file():
            data = read(path)
            for p in fix['patches']:
                for v in p.get('variants', []):
                    try:
                        spots(data, [{**p, 'variants': [v]}]); return v.get('build')
                    except ValueError:
                        pass
    return None


def for_build(fix, name):
    """The fix as it applies to one of its builds: only the patches (and variants) for that build. None: all of them."""
    if name is None:
        return fix
    keep = lambda p: name in p.get('builds', [name])
    patches = [{**p, 'variants': [v for v in p['variants'] if v.get('build', name) == name]} if 'variants' in p else p
               for p in fix['patches'] if keep(p)]
    return {**fix, 'patches': [p for p in patches if p.get('variants', [None])]}


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
    fix = for_build(fix, game_build(fix, game))              # e.g. a DX9-only switch: only on the DX9 build
    plan = []
    for name, patches in files(fix).items():
        exe = game / name
        backup = exe.with_name(exe.name + BACKUP)
        raw = exe.read_bytes()
        data = view(raw)
        try:
            spots(data, patches)                        # every pattern there: this is the original
            raw_original, original, fresh = raw, data, True
        except ValueError:
            # Patched before (other switches, another resolution): start from the original, if it is this version.
            if not backup.is_file():
                raise
            raw_original = backup.read_bytes(); original = view(raw_original)
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
    """{switch: 'missing' (a file isn't there), 'off', 'on' or 'unsupported' (unknown game version)}; for a fix with
    builds, the switches of the installed build."""
    fix = for_build(fix, game_build(fix, game))
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
    ap.add_argument('--version', action='version', version=VERSION)
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
            for name in toggles(f):
                print(f"{'':24}   {name}: {switch_text(f, name)}")
        return
    fix = all_fixes.get(a.game) or ap.error(f'unknown game {a.game!r}; see "widetweaks list"')
    if not supported(fix):
        raise SystemExit(f"This fix needs WideTweaks {fix['requires']} or newer (this is {VERSION}): https://github.com/{REPO}/releases/latest")
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
