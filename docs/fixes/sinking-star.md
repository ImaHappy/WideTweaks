# Order of the Sinking Star: how the fix works

Tested: 3440x1440 (Steam, build of 9 October 2026). Should work at 32:9 too.

The game clamps its render shape between 1.6 and 13/6 (two floats stored side by side). Raising the upper limit to your aspect ratio renders the full screen. Found from the game log (Render target 3120x1440 on a 3440x1440 display). Tested at 3440x1440, build of 9 October 2026.

## Patches

### Remove Black Bars

The game fills your whole screen instead of leaving black bars at the sides.

- maximum aspect ratio (13/6, next to the 1.6 minimum) (`sinking_star.exe`)
