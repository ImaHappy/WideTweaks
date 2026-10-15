# Sleeping Dogs: Definitive Edition: how the fix works

Tested: 3440x1440 (Steam, build 979344, October 2026).

Gameplay is already Hor+. Remove Black Bars: cutscenes and menus set a cinematic flag (byte 0xA of the render-mode block the game copies in every frame) that forces a centred 16:9 viewport and camera; clearing it after each copy keeps them at full width. That also widens the upgrades screen, whose skill tree then scrolls to the right edge of a 1920 stage while the visible area ends at 1920+dx, so its scroller gets the real edge. Ultrawide HUD: the HUD movie (UI.big) gets a stage as wide as your screen, its edge clips (minimap ring, health, money, weapon, objective popup) move to the screen edges, the low-health tint takes the stage width, and the engine's UI width factor becomes 1.0 so the minimap, blips and objective markers use the whole screen; the world map's objectives/legend move to the sides and its cursor reaches the edges. The Nexus 'Black Bars Fix' (older build, hard-coded 3440x1440) instead overwrote shared 16:9 constants, including a reciprocal lookup table entry, which breaks its minimap; WideTweaks leaves those alone.

## Patches

### Remove Black Bars

Cutscenes and menus fill your whole screen instead of being boxed to 16:9 (gameplay already does).

- render mode setter: after copying the block in, clear its cinematic flag (mov byte [flag],0), so cutscenes keep the full-width viewport, aspect and FOV (`sdhdship.exe`)
- upgrades skill tree scroller: visible right edge 1920+dx (the stage is centred), not Stage.width (r7 + Stage.width) (`UI.big`)
- upgrades skill tree scroller: its edge value (the double after the bytes above) (`UI.big`)
- upgrades skill tree scroller: visible right edge 1920+dx instead of Stage.width (Stage.width - r4) (`UI.big`)

### Ultrawide HUD

Minimap, health, money and weapon move to your screen edges, and the big map's lists move to the sides; the minimap keeps its shape. The mission-complete screen stays centred on purpose. Tested up to 32:9.

- UI width factor on screens wider than 16:9 (up to 32:9): 1.0 instead of 16:9 / aspect (movss [scaleX],xmm2 -> xmm0), for the full-width HUD: the minimap, its blips and the objective markers then use the whole screen (`sdhdship.exe`)
- world map cursor limits: horizontal margin m - dx instead of m, so the cursor reaches your screen edges (min x = m - dx, max x = 1920 - m + dx; vertical unchanged); rewritten in place, dx kept in the bytes it jumps over (`sdhdship.exe`)
- world map cursor limits: dx (16:9 edge to screen edge, 1920x1080 units) read by the code above (`sdhdship.exe`)
- HUD movie: stage as wide as your screen; edge clips to the screen edges, the rest stays centred (`UI.big`)
- HUD low-health tint: the stage width instead of 1920 (centred by the HUD's own script) (`UI.big`)
- world map: objectives and collectibles to the left edge, legend to the right (`UI.big`)
