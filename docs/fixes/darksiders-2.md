# Darksiders II Deathinitive Edition: how the fix works

Tested: 3440x1440 (Steam, default DX9 build 852291 and DX11 beta "closed" build 17701647, October 2026).

Works with the default DX9 build and the DX11 beta branch "closed" (code DeathIstheRealDeal); WideTweaks detects which one you have. Both builds have the same function, compiled differently, so the patch has one variant per build. Gameplay and HUD are already ultrawide. The minimap's icon layer (player arrow, markers) was scaled by screen width / 1280 and only centred vertically, while the minimap itself is scaled by height / 720 and centred, so on screens wider than 16:9 the icons drifted outward. The icon layout function now uses min(width / 1280, height / 720) and centres on both axes, like the rest of the HUD.

## Ultrawide FOV (DX9 only)

The DX9 build asks for a 16:9 projection for its gameplay camera whatever the screen or the Resolution setting, and the
picture is then stretched across a wider screen (characters too wide, view zoomed in). New code at the end of the code
section (in its unused bytes; the section size in the header is raised to cover them) checks the aspect every
projection builder gets: one within 4 ulp of 16:9 is replaced with your screen's width / height. The field of view is
vertical, so the picture keeps its 16:9 height and shows more at the sides (Hor+); zoom and camera moves work as
before. Views with other shapes (shadows, reflections) are left alone. Hooked: the projection builder at 0x14074F938,
its copy at 0x14075D814 and the D3DX-style builder at 0x140D38B9C.

## Patches

### Fix Minimap

The player arrow and map markers sit on the minimap again, instead of drifting off to the right of it. The minimap stays where the game puts it.

- minimap icon layer: same fit as the HUD (min of width/1280, height/720), centred (`Darksiders2.exe`)
