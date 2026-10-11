# Happy WideTweaks

**Ultrawide Game Compatibility Toolkit**
Ultrawide fixes, FOV adjustments, HUD corrections, and more.
Open-source • [ImaHappy.dev](https://imahappy.dev/widetweaks)

WideTweaks (HWT) finds the game in your Steam libraries, keeps a backup of its executable, and changes the few
bytes that hold the picture back on wide screens (a capped aspect ratio, a narrow field of view, a stretched HUD),
using values worked out from your resolution. It never ships game files: it only edits your own copy, and can
always put the original back.

## Supported games

| Game | Fix | Tested |
|---|---|---|
| [Order of the Sinking Star](https://store.steampowered.com/app/499170/) | Removes the 19.5:9 pillarbox: full 21:9 / 32:9 rendering | 3440x1440, build of 9 Oct 2026 |

`widetweaks list` shows the same list.

## Install

- **Windows:** download `widetweaks.exe` from [Releases](../../releases).
- **Linux / Steam Deck:** download `widetweaks.py` and the `fixes` folder (or clone this repo). Needs only Python 3.

## Use

Close the game first.

```
widetweaks patch sinking-star                    # Windows: uses your main screen's resolution
python3 widetweaks.py patch sinking-star --res 3440x1440
python3 widetweaks.py restore sinking-star       # undo
```

- The game is found through Steam. For other locations, add `--path "D:\Games\Order of the Sinking Star"`.
- Changed resolution? Run `patch` again with the new one.
- A game update replaces the executable, so run `patch` again afterwards. If the update moved things, WideTweaks
  refuses instead of guessing ("unsupported game version"), and the game is left untouched.
- Undo without WideTweaks: Steam → the game → Properties → Installed Files → **Verify integrity of game files**.

## Known issues

### Order of the Sinking Star
- The developer limits the shape on purpose. At 21:9 and wider you may see past the edges of some levels.

## Adding a game

Add `fixes/<id>.json`:

```json
{
  "name": "Game Name",
  "steam_appid": 123456,
  "exe": "Game.exe",
  "summary": "One line on what the fix does.",
  "notes": "How the fix was found and what it was tested with.",
  "patches": [
    { "description": "what this changes", "pattern": "AB AA 0A 40 ?? CC CC 3F", "offset": 0, "value": "float:aspect" }
  ]
}
```

- `pattern`: hex bytes, `??` for any byte. It must occur exactly once in the executable, or WideTweaks refuses.
- `offset`: where the value goes, counted from the start of the pattern.
- `value`: `float:aspect` writes your width ÷ height as a 32-bit float.

Then run `python3 test_widetweaks.py`.

## Building the Windows .exe

Pushing a tag `v*` builds `widetweaks.exe` with PyInstaller on GitHub Actions and attaches it to a release.

## License

MIT. Game names and trademarks belong to their owners. Not affiliated with any developer or publisher.
