# Darksiders II Deathinitive Edition: how the fix works

Tested: 3440x1440 (Steam, DX11 beta branch, build 17701647, October 2026).

Needs the DX11 beta branch "closed" (not "publicbeta"): Steam > Darksiders II > Properties > Betas, enter the code DeathIstheRealDeal, then pick "closed". Gameplay and HUD are already ultrawide. The minimap's icon layer (player arrow, markers) was scaled by screen width / 1280 and only centred vertically, while the minimap itself is scaled by height / 720 and centred, so on screens wider than 16:9 the icons drifted outward. The icon layout function now uses min(width / 1280, height / 720) and centres on both axes, like the rest of the HUD.

## Patches

### Fix Minimap

The player arrow and map markers sit on the minimap again, instead of drifting off to the right of it. The minimap stays where the game puts it.

- minimap icon layer: same fit as the HUD (min of width/1280, height/720), centred (`Darksiders2.exe`)
