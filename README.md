# WideTweaks

**Happy's Ultrawide Fixes** • [ImaHappy.dev](https://imahappy.dev/widetweaks)

![WideTweaks](docs/app.png)

## Supported games

| Game | Fix |
|---|---|
| [Darksiders II Deathinitive Edition](https://store.steampowered.com/app/388410/) | Minimap icons line up with the minimap (needs the DX11 beta branch "closed", code `DeathIstheRealDeal`)<br><a href="docs/fixes/darksiders-2.md">How it works</a><details><summary>Before / after</summary><img src="docs/darksiders-2.jpg" width="560" alt="Darksiders II Deathinitive Edition at 3440x1440, original vs WideTweaks"></details> |
| [DAVE THE DIVER](https://store.steampowered.com/app/1868140/) | Full width, ultrawide HUD, unlocked FPS<br><a href="docs/fixes/dave-the-diver.md">How it works</a><details><summary>Before / after</summary><img src="docs/dave-the-diver.jpg" width="560" alt="DAVE THE DIVER at 3440x1440, original vs WideTweaks"></details> |
| [Order of the Sinking Star](https://store.steampowered.com/app/499170/) | Removes the black bars on 21:9 and 32:9<br><a href="docs/fixes/sinking-star.md">How it works</a><details><summary>Before / after</summary><img src="docs/sinking-star.jpg" width="560" alt="Order of the Sinking Star at 3440x1440, original vs WideTweaks"></details> |
| [Sleeping Dogs: Definitive Edition](https://store.steampowered.com/app/307690/) | Full-width cutscenes and menus, HUD at the screen edges (minimap intact)<br><a href="docs/fixes/sleeping-dogs.md">How it works</a><details><summary>Before / after</summary><img src="docs/sleeping-dogs.jpg" width="560" alt="Sleeping Dogs: Definitive Edition at 3440x1440, original vs WideTweaks"></details> |

## How to use

1. Download `WideTweaks.exe` from [Releases](../../releases).
2. Close the game and open WideTweaks.
3. Pick the game and flip its switches on. Flip them off to undo.

New games and fix updates show up in the app by themselves (it reads the fix files here on GitHub), and it tells you
when a new WideTweaks is out: one click downloads it (the .exe, or the Linux zip), checks its SHA-256 against the release and restarts; a git checkout does `git pull`.
Nothing is updated without you clicking.

Your original game file is kept as a backup, so you can always switch back (or use Steam's "Verify integrity of
game files").

**After a game update,** flip the switch on again. If the update changed too much, WideTweaks says
"unsupported game version" and leaves the game alone.

**Linux / Steam Deck:** download `WideTweaks_Linux.zip` and run `python3 widetweaks.py` (needs Python with Tk;
Pillow adds the game pictures, and `python-lz4` makes Unity games like Dave fast).

## Support

WideTweaks is free. If you want to support it: [Ko-fi](https://ko-fi.com/imahappy).

---

Want to add a game or use the command line? See [CONTRIBUTING.md](CONTRIBUTING.md).
MIT, see [LICENSE](LICENSE). Game names and trademarks belong to their owners; not affiliated with any developer or
publisher.
