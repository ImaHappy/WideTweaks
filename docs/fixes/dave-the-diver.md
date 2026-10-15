# DAVE THE DIVER: how the fix works

Tested: 3440x1440 (Steam, build of October 2026).

The game only offers 16:9 resolutions (IsTargetRatio) and defaults to the largest 16:9 size (GetBestResolution). Its view setup (CoUpdateResolution) divides the screen shape by 16:9 and, when wider, narrows the camera and shows side-art panels; making that ratio 1 keeps the full width and hides the panels, as the old BepInEx mod did at runtime.

## Patches

### Remove Black Bars

The game runs at your screen's own resolution and fills its full width, instead of a 16:9 picture with decorative side panels.

- resolution list: accept every aspect ratio (IsTargetRatio returns true) (`GameAssembly.dll`)
- default resolution: keep the screen's own, not the largest 16:9 (GetBestResolution) (`GameAssembly.dll`)
- view setup (CameraResolution.CoUpdateResolution): screen shape ÷ 16:9 becomes 1, so the side-art panels hide and the camera keeps the full width (divss xmm9,[16:9] -> divss xmm9,xmm9) (`GameAssembly.dll`)

### Ultrawide HUD

The HUD, menus, popups and cutscene bars reach your screen edges instead of sitting in a 16:9 box; dialogue stays together in the middle, and the intro animation is zoomed to fill the width.

- UI layout boxes (Unity AspectRatioFitter, Fit In Parent): on a screen wider than the box's shape, fill it instead of narrowing to a centred 16:9 box, so the HUD, dims and cinematic bars reach the edges (`GameAssembly.dll`)
- dialogue layout: LeftDialoguePanel as a centred 1920x1080 (16:9) box, so its portraits, box and text stay together (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/be2f279a7770773a0b40e2affc558ab0.bundle`)
- dialogue layout: CenterDialoguePanel as a centred 1920x1080 (16:9) box, so its portraits, box and text stay together (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/be2f279a7770773a0b40e2affc558ab0.bundle`)
- dialogue layout: RightDialoguePanel as a centred 1920x1080 (16:9) box, so its portraits, box and text stay together (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/be2f279a7770773a0b40e2affc558ab0.bundle`)
- cinematic bars: LetterBox_CutScene/Top three times as wide as the 16:9 cutscene frame, centred (covers up to 48:9) (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/baa63b89e2eb2021984c92801f550cdb.bundle`)
- cinematic bars: LetterBox_CutScene/Bottom three times as wide as the 16:9 cutscene frame, centred (covers up to 48:9) (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/baa63b89e2eb2021984c92801f550cdb.bundle`)
- pause / Return to Boat popup (PauseMenuPanel): full screen instead of a 1920-wide box pinned to the right (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/6d4ee9910f5656707fa7cddf2721138c.bundle`)
- sushi bar menu (ContentsGroup/ManagementPanel): full screen instead of a 1920x1080 box, so its bottom band reaches the edges (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/85d5c86f68c9034c2ddd026bd939af87.bundle`)
- intro animation: zoom CutAnimCtrl (x) so the 16:9 intro fills your width, at most 1.366x (what its 13.4% black bars hid, so no art is cropped on 32:9) (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/c6294796e2f4f82a4c3cc2d0768ebed8.bundle`)
- intro animation: zoom CutAnimCtrl (y) so the 16:9 intro fills your width, at most 1.366x (what its 13.4% black bars hid, so no art is cropped on 32:9) (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/c6294796e2f4f82a4c3cc2d0768ebed8.bundle`)
- intro animation: zoom LetterBox_CutScene (x) so the 16:9 intro fills your width, at most 1.366x (what its 13.4% black bars hid, so no art is cropped on 32:9) (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/c6294796e2f4f82a4c3cc2d0768ebed8.bundle`)
- intro animation: zoom LetterBox_CutScene (y) so the 16:9 intro fills your width, at most 1.366x (what its 13.4% black bars hid, so no art is cropped on 32:9) (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/c6294796e2f4f82a4c3cc2d0768ebed8.bundle`)
- intro animation: zoom LetterBox (x) so the 16:9 intro fills your width, at most 1.366x (what its 13.4% black bars hid, so no art is cropped on 32:9) (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/c6294796e2f4f82a4c3cc2d0768ebed8.bundle`)
- intro animation: zoom LetterBox (y) so the 16:9 intro fills your width, at most 1.366x (what its 13.4% black bars hid, so no art is cropped on 32:9) (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/c6294796e2f4f82a4c3cc2d0768ebed8.bundle`)
- area title card (AreaInfoPanel): full screen instead of a 1920x1080 box pinned bottom-left (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/47c837abba25b7f2c4754e323a92080c.bundle`)
- area title card (Area_Timeline): full screen instead of a 1920x1080 box pinned bottom-left (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/47c837abba25b7f2c4754e323a92080c.bundle`)
- area title card (Area): full screen instead of a 1920x1080 box pinned bottom-left (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/47c837abba25b7f2c4754e323a92080c.bundle`)
- global popup (Popups/Layer2/MiniGameSkipPopup): full width instead of a 1920-wide box (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/a764af4da3107fddf5725f76454af9e5.bundle`)
- global popup (Popups/Layer2/GameNormalPopup): full width instead of a 1920-wide box (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/a764af4da3107fddf5725f76454af9e5.bundle`)
- global popup (Popups/Layer2/GameHoldPopup): full width instead of a 1920-wide box (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/a764af4da3107fddf5725f76454af9e5.bundle`)
- global popup (Popups/Layer2/GameWarninglPopup): full width instead of a 1920-wide box (`DaveTheDiver_Data/StreamingAssets/aa/StandaloneWindows64/a764af4da3107fddf5725f76454af9e5.bundle`)

### Unlock FPS

Removes the 60 FPS cap, so the game runs at your monitor's refresh rate.

- frame limit 60 -> none, when VSync changes (CameraResolution.UpdateVSyncValue) (`GameAssembly.dll`)
- frame limit 60 -> none, at startup (TimeManager.Init) (`GameAssembly.dll`)
- VSync on every refresh, not every 2nd-4th (which held 120-240 Hz screens to 60) (`GameAssembly.dll`)
- VSync kept on above 60 Hz (the refresh / interval <= 60 test) (`GameAssembly.dll`)
- VSync watchdog: don't switch VSync off for running above 63 fps (UpdateVSyncWatchdog) (`GameAssembly.dll`)
- VSync watchdog: same check inlined in CameraResolution.Update (`GameAssembly.dll`)
