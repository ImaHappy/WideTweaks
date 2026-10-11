# WideFix

Ultrawide and any-aspect-ratio patcher for PC games. One tool, one small definition file per game.

WideFix finds the game in your Steam libraries, keeps a backup of its executable, and changes the few bytes that
limit the picture to 16:9 (or whatever the developer picked), using values worked out from your resolution.
It never ships game files: it only edits your own copy, and can always put the original back.

## Supported games

| Game | Fix | Tested |
|---|---|---|
| [Order of the Sinking Star](https://store.steampowered.com/app/499170/) | Removes the 19.5:9 pillarbox: full 21:9 / 32:9 rendering | 3440x1440, build of 9 Oct 2026 |

`widefix list` shows the same list.

## Install

- **Windows:** download `widefix.exe` from [Releases](../../releases).
- **Linux / Steam Deck:** download `widefix.py` and the `fixes` folder (or clone this repo). Needs only Python 3.

## Use

Close the game first.

```
widefix patch sinking-star                    # Windows: uses your main screen's resolution
python3 widefix.py patch sinking-star --res 3440x1440
python3 widefix.py restore sinking-star       # undo
```

- The game is found through Steam. For other locations, add `--path "D:\Games\Order of the Sinking Star"`.
- Changed resolution? Run `patch` again with the new one.
- A game update replaces the executable, so run `patch` again afterwards. If the update moved things, WideFix
  refuses instead of guessing ("unsupported game version"), and the game is left untouched.
- Undo without WideFix: Steam → the game → Properties → Installed Files → **Verify integrity of game files**.

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

- `pattern`: hex bytes, `??` for any byte. It must occur exactly once in the executable, or WideFix refuses.
- `offset`: where the value goes, counted from the start of the pattern.
- `value`: `float:aspect` writes your width ÷ height as a 32-bit float.

Then run `python3 test_widefix.py`.

## Building the Windows .exe

Pushing a tag `v*` builds `widefix.exe` with PyInstaller on GitHub Actions and attaches it to a release.

## License

MIT. Game names and trademarks belong to their owners. Not affiliated with any developer or publisher.
