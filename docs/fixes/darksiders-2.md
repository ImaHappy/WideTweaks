# Darksiders II Deathinitive Edition: how the fix works

Tested: 3440x1440 (Steam, default DX9 build 852291 and DX11 beta "closed" build 17701647, October 2026).

Works with the default DX9 build and the DX11 beta branch "closed" (code DeathIstheRealDeal); WideTweaks detects which one you have. Both builds have the same function, compiled differently, so the patch has one variant per build. Gameplay and HUD are already ultrawide. The minimap's icon layer (player arrow, markers) was scaled by screen width / 1280 and only centred vertically, while the minimap itself is scaled by height / 720 and centred, so on screens wider than 16:9 the icons drifted outward. The icon layout function now uses min(width / 1280, height / 720) and centres on both axes, like the rest of the HUD.

## Ultrawide FOV (DX9 only)

The DX9 build is Vert-: at 21:9 it keeps the 16:9 width of view and cuts the top and bottom, so the picture looks
zoomed in (DX11 is Hor+). Like the Cheat Engine "Darksiders II Deathinitive Edition FOV v1.4" table, the switch writes a
fixed field of view where the game stores the camera's (camera + 0x6C, 45 degrees by default) after blending it: 45 at
16:9, widened for your screen with the height kept (58.2 at 3440x1440, 79.3 at 32:9). The blend call is replaced by
the store, so the game's own field-of-view changes (zoom) don't apply while it's on.

## Patches

### Fix Minimap

The player arrow and map markers sit on the minimap again, instead of drifting off to the right of it. The minimap stays where the game puts it.

- minimap icon layer: same fit as the HUD (min of width/1280, height/720), centred (`Darksiders2.exe`)
