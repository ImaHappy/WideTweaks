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

- `toggle`: the switch's label in the app, e.g. "Remove black bars" or "Fix FOV".
- `pattern`: hex bytes, `??` for any byte (not where the value goes). It must occur exactly once in the executable,
  or WideTweaks refuses.
- `offset`: where the value goes, counted from the start of the pattern.
- `value`: `float:aspect` writes your width ÷ height as a 32-bit float.
- Optional: `fixes/previews/<id>-before.jpg` and `<id>-after.jpg` (about 960 px wide) add the Compare button.

Then run `python3 test_widetweaks.py`.

## Releases

Pushing a tag `v*` tests, builds `WideTweaks.exe` with PyInstaller on GitHub Actions, and attaches it to a release
with a build attestation (`gh attestation verify WideTweaks.exe --repo ImaHappy/WideTweaks`). GitHub shows each
file's SHA-256 next to it on the release page.
