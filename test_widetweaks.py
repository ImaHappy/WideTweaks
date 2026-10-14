#!/usr/bin/env python3
"""python3 test_widetweaks.py: the patch logic on fake executables (no game needed)."""
import pathlib, struct, tempfile, zlib
import widetweaks

fix = widetweaks.fixes()['sinking-star']
original = b'\x00' * 100 + struct.pack('<ff', 13 / 6, 1.6) + b'\x00' * 100

# Patch writes width/height as a float where the pattern starts, and keeps the 1.6 next to it.
out = widetweaks.apply(original, fix['patches'], 3440, 1440)
assert struct.unpack_from('<ff', out, 100) == (struct.unpack('<f', struct.pack('<f', 3440 / 1440))[0], struct.unpack('<f', struct.pack('<f', 1.6))[0])

# A version where the pattern is missing or appears twice is refused.
for bad in (b'\x00' * 50, original + original):
    try:
        widetweaks.apply(bad, fix['patches'], 3440, 1440); raise AssertionError('should refuse')
    except ValueError:
        pass

# On disk: backup made, re-patching for another resolution works from the backup, restore puts the original back.
with tempfile.TemporaryDirectory() as d:
    game = pathlib.Path(d); exe = game / fix['exe']; exe.write_bytes(original)
    assert widetweaks.status(fix, game) == 'off'
    widetweaks.patch(fix, game, 3440, 1440)
    assert widetweaks.status(fix, game) == 'on'
    assert exe.read_bytes() != original and (game / (fix['exe'] + widetweaks.BACKUP)).read_bytes() == original
    widetweaks.patch(fix, game, 5120, 1440)
    assert struct.unpack_from('<f', exe.read_bytes(), 100)[0] == struct.unpack('<f', struct.pack('<f', 5120 / 1440))[0]
    widetweaks.restore(fix, game)
    assert exe.read_bytes() == original
    assert widetweaks.status(fix, game) == 'off'
    exe.write_bytes(b'\x00' * 50); assert widetweaks.status(fix, game) == 'unsupported'
    assert widetweaks.status(fix, game / 'nowhere') == 'missing' and widetweaks.status(fix, None) == 'missing'

# A value that leaves the pattern matching is refused (the patched file would still look original, and the backup
# be lost); one that overwrites a ?? along with fixed bytes is fine.
try:
    widetweaks.apply(original, [{**fix['patches'][0], 'pattern': '?? ?? ?? ?? CD CC CC 3F'}], 3440, 1440); raise AssertionError('should refuse')
except ValueError:
    pass
assert widetweaks.apply(b'\x01\x02\x03\x04', [{'description': 'x', 'pattern': '01 ?? 03', 'value': 'bytes:09 09'}], 16, 9) == b'\x09\x09\x03\x04'

# A game update (same size, other bytes) is never mistaken for our patch: restore and status leave it alone.
with tempfile.TemporaryDirectory() as d:
    game = pathlib.Path(d); exe = game / fix['exe']; exe.write_bytes(original)
    widetweaks.patch(fix, game, 3440, 1440)
    updated = b'\x01' * 100 + original[100:108] + b'\x01' * 100      # new version, unpatched, same size
    exe.write_bytes(updated)
    widetweaks.restore(fix, game)                                       # already original: left alone,
    assert exe.read_bytes() == updated and widetweaks.status(fix, game) == 'off'   # never the old backup over it
    moved = b'\x01' * 208                                                  # same size, pattern gone
    exe.write_bytes(moved)
    assert widetweaks.status(fix, game) == 'unsupported'
    try:
        widetweaks.patch(fix, game, 3440, 1440); raise AssertionError('should refuse')
    except ValueError:
        pass
    assert exe.read_bytes() == moved

assert widetweaks.value('bytes:B0 01 C3', 16, 9) == b'\xb0\x01\xc3'
assert struct.unpack('<f', widetweaks.value('float:zoom', 5120, 1440))[0] == 2 and struct.unpack('<f', widetweaks.value('float:zoom', 1920, 1200))[0] == 1
assert abs(struct.unpack('<f', widetweaks.value('float:zoom:1.366', 5120, 1440))[0] - 1.366) < 1e-6
assert widetweaks.parse_resolution(' 3440 × 1440 ') == (3440, 1440) and widetweaks.parse_resolution('3440') is None

# Unity asset bundles: LZ4 (with an overlapping copy) decompresses, and a compressed bundle comes back uncompressed
# with the same data, so patterns can be found in it.
assert widetweaks.lz4_block(bytes.fromhex('2f6162020013f00130313233343536373839616263646566'), 56) == b'ab' * 20 + b'0123456789abcdef'   # real LZ4 (overlapping copy)
def lz4(b):                                     # literals-only LZ4, enough to build a test bundle
    n = len(b) - 15
    return bytes([0xF0]) + b'\xff' * (n // 255) + bytes([n % 255]) + b
payload = b'GameObject ' * 40
info = bytes(16) + struct.pack('>i', 1) + struct.pack('>IIH', len(payload), len(lz4(payload)), 2) + struct.pack('>i', 0)
head = b'UnityFS\0' + struct.pack('>I', 8) + b'5.x.x\0' + b'2022.3\0'
body = lz4(info)
bundle = head + struct.pack('>qIII', 0, len(body), len(info), 0x43 | 0x200)
bundle += bytes(-len(bundle) % 16) + body
bundle += bytes(-len(bundle) % 16) + lz4(payload)
plain = widetweaks.unity_bundle(bundle)
assert plain.endswith(payload) and widetweaks.unity_bundle(plain) == plain and widetweaks.unity_bundle(b'MZ') == b'MZ'

# A compressed bundle in a fix: patched (only the changed block stored uncompressed, the rest as it was), reported
# on, restored to the exact original file.
blocks = [b'A' * 300 + b'MARKER42' + b'A' * 300, b'B' * 600]
info = bytes(16) + struct.pack('>i', 2) + b''.join(struct.pack('>IIH', len(b), len(lz4(b)), 2) for b in blocks) + struct.pack('>i', 0)
raw = head + struct.pack('>qIII', 0, len(lz4(info)), len(info), 0x43 | 0x200)
raw += bytes(-len(raw) % 16) + lz4(info)
raw += bytes(-len(raw) % 16) + b''.join(lz4(b) for b in blocks)
uni = {'exe': 'data.bundle', 'toggle': 'T', 'patches': [{'description': 'm', 'pattern': '4D 41 52 4B 45 52 34 32', 'value': 'bytes:58'}]}
with tempfile.TemporaryDirectory() as d:
    game = pathlib.Path(d); (game / 'data.bundle').write_bytes(raw)
    widetweaks.patch(uni, game, 16, 9)
    out = (game / 'data.bundle').read_bytes()
    assert b'XARKER42' in widetweaks.read(game / 'data.bundle') and lz4(blocks[1]) in out and len(out) < len(raw) + 700
    assert widetweaks.states(uni, game) == {'T': 'on'}
    widetweaks.restore(uni, game)
    assert (game / 'data.bundle').read_bytes() == raw and widetweaks.status(uni, game) == 'off'

# Switches: each turns its own patches on and off, from the one original.
two = {'exe': 'g.exe', 'toggle': 'A', 'patches': [
    {'description': 'a', 'pattern': '11 22 33', 'value': 'bytes:AA'},
    {'description': 'b', 'pattern': '44 55 66', 'value': 'bytes:BB', 'toggle': 'B'}]}
with tempfile.TemporaryDirectory() as d:
    game = pathlib.Path(d); (game / 'g.exe').write_bytes(b'\x11\x22\x33\x00\x44\x55\x66' + bytes(100))
    start = (game / 'g.exe').read_bytes()
    widetweaks.setup(two, game, 16, 9, {'B'})
    assert widetweaks.states(two, game) == {'A': 'off', 'B': 'on'}
    widetweaks.setup(two, game, 16, 9, {'A'})
    assert widetweaks.states(two, game) == {'A': 'on', 'B': 'off'} and (game / 'g.exe').read_bytes()[:7] == b'\xaa\x22\x33\x00\x44\x55\x66'
    widetweaks.setup(two, game, 16, 9, set())
    assert (game / 'g.exe').read_bytes() == start and widetweaks.status(two, game) == 'off'

# Every fix file has what the patcher needs.
for gid, f in widetweaks.fixes().items():
    assert {'name', 'steam_appid', 'exe', 'summary', 'toggle', 'tested', 'patches'} <= f.keys(), gid
    for p in f['patches']:
        assert ('value' in p) != ('layout' in p), (gid, p['description'])
        if 'value' in p: widetweaks.value(p['value'], 16, 9)
        bytes.fromhex(p['pattern'].replace('??', '00'))

# Values for a centred 1920x1080 UI: at 3440x1440 the 16:9 edge is 330 units from the screen edge.
assert struct.unpack('<f', widetweaks.value('float:left:255', 3440, 1440))[0] == -75 and struct.unpack('<f', widetweaks.value('float:left:255', 1920, 1080))[0] == 255
assert struct.unpack('<i', widetweaks.value('int:stage:1920', 3440, 1440))[0] == 2580 and struct.unpack('<i', widetweaks.value('int:stage:1920', 1920, 1200))[0] == 1920
v = widetweaks.value('swfdouble:right:1920', 3440, 1440); assert struct.unpack('<d', v[4:] + v[:4])[0] == 2250

# SWF matrices survive a round trip, also when the translation needs more bits.
for m in ({'scale': None, 'rotate': None, 'translate': (5133, 17730)}, {'scale': (98304, 65536), 'rotate': None, 'translate': (-1467, 0)}):
    assert widetweaks.swf_matrix(widetweaks.swf_matrix_bytes(m), 0)[0] == m

# A Scaleform movie in a .big archive: laid out (stage widened, a left clip kept at the screen edge, a centre clip
# moved with the stage), packed back into its chunk (growing into the padding), and restored to the exact original.
def place(name, x, y, depth):
    b = widetweaks.swf_matrix_bytes({'scale': None, 'rotate': None, 'translate': (x * 20, y * 20)})
    body = bytes([0x26]) + struct.pack('<HH', depth, 1) + b + name + b'\0'          # move, character, matrix, name
    return struct.pack('<H', 26 << 6 | len(body)) + body
r = widetweaks.Bits(); r.write(16, 5); [r.write(v & 0xffff, 16) for v in (0, 1920 * 20, 0, 1080 * 20)]
swf = bytearray(b'GFX\x08\0\0\0\0' + r.bytes() + b'\0\x1e\x01\0' + place(b'mc_left', 100, 900, 1) + place(b'mc_mid', 960, 540, 2) + b'\0\0')
struct.pack_into('<I', swf, 4, len(swf))
packed = b'CFX\x08' + struct.pack('<I', len(swf)) + zlib.compress(bytes(swf[8:]), 9)
res = bytes(0x30) + b'\xd9\x39\x2a\x44' + b'Hud'.ljust(0x24, b'\0') + struct.pack('<IIII', len(packed), 0, 8, 0)   # 0x68 bytes
big = bytes(16) + b'\xd9\x39\x2a\x44' + struct.pack('<II', 0x68 + len(packed), 0x68 + len(packed)) + bytes(4) + res + packed
big += bytes(-len(big) % 0x1000) + b'\xd9next chunk'
assert len(widetweaks.big_movies(big)) == 1 and widetweaks.big_view(b'MZ') == b'MZ'
anchor = ' '.join(f'{x:02X}' for x in widetweaks.MOVIE + b'Hud\0') + ' 47 46 58 08 ?? ?? ?? ?? ' + ' '.join(f'{x:02X}' for x in r.bytes())   # the stage: changes when widened
sf = {'exe': 'UI.big', 'toggle': 'HUD', 'patches': [{'description': 'hud', 'pattern': anchor, 'layout': {'stage': 'wide', 'left': ['mc_left']}}]}
with tempfile.TemporaryDirectory() as d:
    game = pathlib.Path(d); (game / 'UI.big').write_bytes(big)
    widetweaks.patch(sf, game, 3440, 1440)
    out = (game / 'UI.big').read_bytes(); assert len(out) == len(big) and out.endswith(b'\xd9next chunk')
    movie = widetweaks.read(game / 'UI.big').split(widetweaks.MOVIE + b'Hud\0')[1]
    b = widetweaks.Bits(movie, 8); n = b.read(5); assert [b.read(n, True) for _ in range(4)][1] == 2580 * 20
    tags = {nm: movie[movie.rindex(b'\x26', 0, movie.index(nm)) + 5:movie.index(nm)] for nm in (b'mc_left', b'mc_mid')}
    assert widetweaks.swf_matrix(tags[b'mc_left'], 0)[0]['translate'] == (100 * 20, 900 * 20)       # left clip: stays at the screen edge
    assert widetweaks.swf_matrix(tags[b'mc_mid'], 0)[0]['translate'] == (1290 * 20, 540 * 20)       # centre clip: moves with the stage
    assert widetweaks.states(sf, game) == {'HUD': 'on'}
    widetweaks.restore(sf, game)
    assert (game / 'UI.big').read_bytes() == big and widetweaks.status(sf, game) == 'off'
print('ok')
