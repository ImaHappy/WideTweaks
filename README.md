# WideTweaks

**Happy's Ultrawide Fixes** • [ImaHappy.dev](https://imahappy.dev/widetweaks)

![WideTweaks](docs/app.png)

## Supported games

| Game | Fix |
|---|---|
| [Darksiders II Deathinitive Edition](https://store.steampowered.com/app/388410/) | Minimap icons line up with the minimap (needs the DX11 beta branch "closed", code `DeathIstheRealDeal`) |
| [DAVE THE DIVER](https://store.steampowered.com/app/1868140/) | Full width, ultrawide HUD, unlocked FPS |
| [Order of the Sinking Star](https://store.steampowered.com/app/499170/) | Removes the black bars on 21:9 and 32:9 |
| [Sleeping Dogs: Definitive Edition](https://store.steampowered.com/app/307690/) | Full-width cutscenes and menus, HUD at the screen edges (minimap intact) |

![Darksiders II Deathinitive Edition at 3440x1440, original vs WideTweaks](docs/darksiders-2.jpg)
![DAVE THE DIVER at 3440x1440, original vs WideTweaks](docs/dave-the-diver.jpg)
![Order of the Sinking Star at 3440x1440, original vs WideTweaks](docs/sinking-star.jpg)
![Sleeping Dogs: Definitive Edition at 3440x1440, original vs WideTweaks](docs/sleeping-dogs.jpg)

## What each switch does

**Darksiders II Deathinitive Edition** ([how it works](docs/fixes/darksiders-2.md))

Needs the DX11 beta: in Steam, Darksiders II > Properties > Betas, enter the code `DeathIstheRealDeal`, then pick the branch "closed" (not "publicbeta").

- **Fix Minimap:** The player arrow and map markers sit on the minimap again, instead of drifting off to the right of it. The minimap stays where the game puts it.

**DAVE THE DIVER** ([how it works](docs/fixes/dave-the-diver.md))

- **Remove Black Bars:** The game runs at your screen's own resolution and fills its full width, instead of a 16:9 picture with decorative side panels.
- **Ultrawide HUD:** The HUD, menus, popups and cutscene bars reach your screen edges instead of sitting in a 16:9 box; dialogue stays together in the middle, and the intro animation is zoomed to fill the width.
- **Unlock FPS:** Removes the 60 FPS cap, so the game runs at your monitor's refresh rate.

**Order of the Sinking Star** ([how it works](docs/fixes/sinking-star.md))

- **Remove Black Bars:** The game fills your whole screen instead of leaving black bars at the sides.

**Sleeping Dogs: Definitive Edition** ([how it works](docs/fixes/sleeping-dogs.md))

- **Remove Black Bars:** Cutscenes and menus fill your whole screen instead of being boxed to 16:9 (gameplay already does).
- **Ultrawide HUD:** Minimap, health, money and weapon move to your screen edges, and the big map's lists move to the sides; the minimap keeps its shape. The mission-complete screen stays centred on purpose. Tested up to 32:9.

## How to use

1. Download `WideTweaks.exe` from [Releases](../../releases).
2. Close the game and open WideTweaks.
3. Pick the game and flip its switches on. Flip them off to undo.

New games and fix updates show up in the app by themselves (it reads the fix files here on GitHub), and it tells you
when a new WideTweaks is out: on Windows one click downloads it, checks its SHA-256 against the release and restarts.
Nothing is updated without you clicking.

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
