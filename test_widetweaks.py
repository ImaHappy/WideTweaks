#!/usr/bin/env python3
"""python3 test_widetweaks.py: the patch logic on fake executables (no game needed)."""
import pathlib, struct, tempfile
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

# A ?? where the value is written is refused (the patched file would still look original, and the backup be lost).
try:
    widetweaks.apply(original, [{**fix['patches'][0], 'pattern': '?? ?? ?? ?? CD CC CC 3F'}], 3440, 1440); raise AssertionError('should refuse')
except ValueError:
    pass

# A game update (same size, other bytes) is never mistaken for our patch: restore and status leave it alone.
with tempfile.TemporaryDirectory() as d:
    game = pathlib.Path(d); exe = game / fix['exe']; exe.write_bytes(original)
    widetweaks.patch(fix, game, 3440, 1440)
    updated = b'\x01' * 100 + original[100:108] + b'\x01' * 100      # new version, unpatched, same size
    exe.write_bytes(updated)
    try:
        widetweaks.restore(fix, game); raise AssertionError('should refuse')
    except ValueError:
        pass
    assert exe.read_bytes() == updated
    moved = b'\x01' * 208                                                  # same size, pattern gone
    exe.write_bytes(moved)
    assert widetweaks.status(fix, game) == 'unsupported'
    try:
        widetweaks.patch(fix, game, 3440, 1440); raise AssertionError('should refuse')
    except ValueError:
        pass
    assert exe.read_bytes() == moved

assert widetweaks.parse_resolution(' 3440 × 1440 ') == (3440, 1440) and widetweaks.parse_resolution('3440') is None

# Every fix file has what the patcher needs.
for gid, f in widetweaks.fixes().items():
    assert {'name', 'steam_appid', 'exe', 'summary', 'patches'} <= f.keys(), gid
    for p in f['patches']:
        widetweaks.value(p['value'], 16, 9); bytes.fromhex(p['pattern'].replace('??', '00'))
print('ok')
