# Horizon for Android (arm64-v8a)

This release carries the arm64 build twice: the installable
`horizon-android-arm64-v8a.apk`, and the prepared build archive
`horizon-android-arm64-v8a.zip` (the same APK plus a short README).

Both contain the Horizon engine and its small Android launcher. They contain no
Minecraft code, textures or sounds: Horizon prepares those from the player's own
copy of Minecraft: Java Edition 26.3, like the desktop build. A prepared build
ZIP with Mojang's files is deliberately not published; build one for yourself
with `tools/android_build.py --resources <prepared folder>`.

## Install and play

1. Install the arm64-v8a APK (Android 9 / API 28 or newer). The rolling
   `android-latest` prerelease always carries the newest main build.
2. On a computer, prepare the 26.3 game files with `horizon-prepare` from this
   repository, then zip the resulting `horizon-resources` folder.
3. Open Horizon, choose **Import prepared resources (.zip)** and select the ZIP.
   The app keeps its own copy; later starts open the game directly.

The on-screen touch controls move, look, jump, sneak, sprint, attack and use;
buttons open chat, pause, inventory, settings, F3 and F5, and menus follow a
finger as the mouse pointer.

Read [docs/android.md](https://github.com/promikailamin/horizon/blob/main/docs/android.md)
for the exact commands, the supported input devices and the build steps.

The crash screen copies the report to the clipboard and offers a restart. Do
not publish an APK built with `--resources`: it would contain Mojang's files.
