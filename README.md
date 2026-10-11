# WideTweaks

**Happy's Ultrawide Fixes** • [ImaHappy.dev](https://imahappy.dev/widetweaks)

![WideTweaks](docs/app.png)

## Supported games

| Game | Fix |
|---|---|
| [DAVE THE DIVER](https://store.steampowered.com/app/1868140/) | Full width, ultrawide HUD, unlocked FPS |
| [Order of the Sinking Star](https://store.steampowered.com/app/499170/) | Removes the black bars on 21:9 and 32:9 |

![Order of the Sinking Star at 3440x1440, original vs WideTweaks](docs/sinking-star.jpg)

## How to use

1. Download `WideTweaks.exe` from [Releases](../../releases).
2. Close the game and open WideTweaks.
3. Pick the game and flip its switches on. Flip them off to undo.

Your original game file is kept as a backup, so you can always switch back (or use Steam's "Verify integrity of
game files").

**After a game update,** flip the switch on again. If the update changed too much, WideTweaks says
"unsupported game version" and leaves the game alone.

**Linux / Steam Deck:** download `WideTweaks_Linux.zip` and run `python3 widetweaks.py` (needs Python with Tk;
Pillow adds the game pictures, and `python-lz4` makes Unity games like Dave fast).

## Support

If a fix saved your ultrawide, [a coffee on Ko-fi](https://ko-fi.com/imahappy) keeps them coming.

---

Want to add a game or use the command line? See [CONTRIBUTING.md](CONTRIBUTING.md).
MIT, see [LICENSE](LICENSE). Game names and trademarks belong to their owners; not affiliated with any developer or
publisher.
