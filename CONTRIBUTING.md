# Contributing to WideTweaks

## Command line

The app and the command line do the same thing:

```
python3 widetweaks.py list                                   # supported games
python3 widetweaks.py patch sinking-star [--res 3440x1440]   # default: your main screen
python3 widetweaks.py restore sinking-star                   # undo
```

Add `--path "D:\Games\Order of the Sinking Star"` for a game outside your Steam libraries.

## Adding a game

Add `fixes/<id>.json`:

```json
{
  "name": "Game Name",
  "steam_appid": 123456,
  "exe": "Game.exe",
  "summary": "One line on what the fix does.",
  "toggle": "Remove black bars",
  "tested": "3440x1440 (Steam, build of 9 October 2026)",
  "notes": "How the fix was found and what it was tested with.",
  "patches": [
    { "description": "what this changes", "pattern": "AB AA 0A 40 ?? CC CC 3F", "offset": 0, "value": "float:aspect" }
  ]
}
```

- `toggle`: the switch's label in the app, e.g. "Remove Black Bars" or "Unlock FPS". A patch can name its own
  `"toggle"` to put it on another switch (one switch per name).
- `"file"` on a patch: patch another file of the game than `exe` (relative to the game folder), e.g. a Unity asset
  bundle (`*.bundle`): WideTweaks decompresses it, patches the uncompressed bytes and stores only the changed blocks
  uncompressed.
- `pattern`: hex bytes, `??` for any byte. It must occur exactly once in the file, and the value must change at least
  one of its fixed bytes, or WideTweaks refuses.
- `offset`: where the value goes, counted from the start of the pattern.
- `value`: `float:aspect` writes your width ÷ height as a 32-bit float; `float:zoom` how much a 16:9 picture must grow
  to fill your width (1.34 at 21:9, 2 at 32:9), `float:zoom:1.366` the same capped at 1.366; `bytes:B0 01 C3` writes those bytes.
- `exe`: the file to patch, relative to the game folder (for Unity IL2CPP games usually `GameAssembly.dll`).
- Optional: `fixes/previews/<id>-<switch>-before.jpg` and `-after.jpg` (about 960 px wide, switch name lowercase with
  dashes, e.g. `dave-the-diver-unlock-fps-before.jpg`) add a Compare button to that switch; the first switch may use
  `<id>-before.jpg`.

Then run `python3 test_widetweaks.py`.

## Releases

Pushing a tag `v*` tests, builds `WideTweaks.exe` with PyInstaller on GitHub Actions, and attaches it to a release
with a build attestation (`gh attestation verify WideTweaks.exe --repo ImaHappy/WideTweaks`). GitHub shows each
file's SHA-256 next to it on the release page.
