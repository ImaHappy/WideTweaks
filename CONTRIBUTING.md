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
  "toggle": "Remove Black Bars",
  "switches": { "Remove Black Bars": "What this switch changes on screen, in plain words." },
  "tested": "3440x1440 (Steam, build of 9 October 2026)",
  "requires": "0.1.0",
  "patches": [
    { "description": "what this changes", "pattern": "AB AA 0A 40 ?? CC CC 3F", "offset": 0, "value": "float:aspect" }
  ]
}
```

- `switches`: one plain-language line per switch (what the player sees change, and any known limits), shown under
  the switch in the app and in the README. Leave the technical side for `docs/fixes/<id>.md`.
- `requires`: the lowest WideTweaks version that has everything the fix uses (e.g. `0.3.0` for `.big` archives). The
  app loads fix files from GitHub, so an older WideTweaks may see a new fix: it then shows "Update WideTweaks" instead
  of switches.
- Optional `setup`: a step to do in Steam first, `{"text": "...", "copy": "code"}`; the app shows the text with a
  button that copies the code (e.g. a beta branch's password).
- `docs/fixes/<id>.md`: how the fix was found and what each patch does (linked from the app's Details).
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
- More values for a centred 1920x1080 UI: `float:left:255` / `float:right:1665` move an x to your screen's left /
  right edge (as far as it was from the 16:9 edge), `int:stage:1920` is the stage width that fills your screen,
  `swfdouble:right:1920` the same as `float:right` stored as an ActionScript 2 double.
- United Front `.big` archives (Sleeping Dogs): their Scaleform movies are decompressed, so patterns can be found in
  them. A patch with `"layout"` instead of a value lays out the movie its pattern is in:
  `{"stage": "wide", "left": [clip names], "right": [...], "widen": [...]}` (`stage: wide` makes the stage as wide as
  your screen and keeps the rest centred). Changed movies are stored zlib-compressed in their place.
- `exe`: the file to patch, relative to the game folder (for Unity IL2CPP games usually `GameAssembly.dll`).
- Optional: `fixes/previews/<id>-<switch>-before.jpg` and `-after.jpg` (about 960 px wide, switch name lowercase with
  dashes, e.g. `dave-the-diver-unlock-fps-before.jpg`) add a Compare button to that switch; the first switch may use
  `<id>-before.jpg`. They aren't built into WideTweaks: the app downloads them from GitHub when Compare is clicked.

Once a fix file is on `main`, every WideTweaks (0.5.0 and newer) shows it, no release needed. Running from a git
checkout, the app uses only the checkout's own `fixes/`, so you can try a fix before pushing it.

Then run `python3 test_widetweaks.py`.

## Releases

Set `VERSION` in `widetweaks.py`, then push the tag `v` + that version (the workflow refuses a tag that doesn't
match). Pushing a tag `v*` tests, builds `WideTweaks.exe` with PyInstaller on GitHub Actions, and attaches it to a release
with a build attestation (`gh attestation verify WideTweaks.exe --repo ImaHappy/WideTweaks`). GitHub shows each
file's SHA-256 next to it on the release page; the app's one-click update checks the download against it. Only code
and `fixes/*.json` are built in (pictures are downloaded when shown), so the exe stays small.
