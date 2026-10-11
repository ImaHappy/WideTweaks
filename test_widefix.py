#!/usr/bin/env python3
"""python3 test_widefix.py: the patch logic on fake executables (no game needed)."""
import pathlib, struct, tempfile
import widefix

fix = widefix.fixes()['sinking-star']
original = b'\x00' * 100 + struct.pack('<ff', 13 / 6, 1.6) + b'\x00' * 100

# Patch writes width/height as a float where the pattern starts, and keeps the 1.6 next to it.
out = widefix.apply(original, fix['patches'], 3440, 1440)
assert struct.unpack_from('<ff', out, 100) == (struct.unpack('<f', struct.pack('<f', 3440 / 1440))[0], struct.unpack('<f', struct.pack('<f', 1.6))[0])

# A version where the pattern is missing or appears twice is refused.
for bad in (b'\x00' * 50, original + original):
    try:
        widefix.apply(bad, fix['patches'], 3440, 1440); raise AssertionError('should refuse')
    except ValueError:
        pass

# On disk: backup made, re-patching for another resolution works from the backup, restore puts the original back.
with tempfile.TemporaryDirectory() as d:
    game = pathlib.Path(d); exe = game / fix['exe']; exe.write_bytes(original)
    widefix.patch(fix, game, 3440, 1440)
    assert exe.read_bytes() != original and (game / (fix['exe'] + widefix.BACKUP)).read_bytes() == original
    widefix.patch(fix, game, 5120, 1440)
    assert struct.unpack_from('<f', exe.read_bytes(), 100)[0] == struct.unpack('<f', struct.pack('<f', 5120 / 1440))[0]
    widefix.restore(fix, game)
    assert exe.read_bytes() == original

# Every fix file has what the patcher needs.
for gid, f in widefix.fixes().items():
    assert {'name', 'steam_appid', 'exe', 'summary', 'patches'} <= f.keys(), gid
    for p in f['patches']:
        widefix.value(p['value'], 16, 9); bytes.fromhex(p['pattern'].replace('??', '00'))
print('ok')
