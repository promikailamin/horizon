# Horizon for Android (arm64-v8a)

This APK contains the Horizon game engine, the small Android launcher and the
crash reporter. It contains **no Minecraft code, textures or sounds**: Horizon
prepares those from the player's own copy of Minecraft: Java Edition 26.3, as
the desktop build does.

## Install

1. Download `horizon-android-arm64-v8a.apk` (or the file attached to the latest
   `android-v*` release) and install it on an arm64 Android 9 (API 28) or newer
   phone.
2. On a computer, prepare the game files for Minecraft 26.3:

   ```sh
   cargo run -p horizon-prepare -- --prepare --server-jar /path/to/server.jar \
     --output horizon-resources
   ```

   Use the server jar of the same 26.3 version the engine pins
   (`research-lock.json`). The output folder contains `horizon-resources.json`.
3. Zip that folder (the ZIP may hold the folder itself or its files directly).
4. Open Horizon on the phone, press **Import prepared resources (.zip)** and
   choose the ZIP. The app unpacks it into its private storage; later starts go
   straight to the game. No computer or network is needed afterwards.

The import screen appears only when the files are missing. The crash screen has
the report on the clipboard and a **Restart** button.

## What works and what does not

- The arm64 native game, single player, LAN and multiplayer use the same code as
  the desktop client.
- The game expects a touch screen to be driven by Horizon's on-screen controls.
  That wiring is not complete in this build: use a Bluetooth/USB keyboard and
  mouse, or a controller the Android input runtime recognises.
- The importer deliberately does not download or bundle Mojang's files. A
  private test build may pass `--resources <prepared folder>` to
  `tools/android_build.py`, which packs it into the APK's assets; do not publish
  that APK.

## Build locally

Needs an Android SDK with NDK 27.3 or newer, build-tools 35, Gradle 8.14, a JDK
and the `aarch64-linux-android` Rust target.

```sh
rustup target add aarch64-linux-android
python3 tools/android_build.py --check                  # type-check only
python3 tools/android_build.py --abi arm64-v8a           # release APK
python3 tools/android_build.py --resources .local/horizon-client/26.3
```

The APK is written to `.local/android/apk/horizon-android-arm64-v8a.apk`.
`CARGO_TARGET_DIR` is honoured; the Gradle build uses
`packaging/android/build/`.

## Layout

| Path | What it is |
| --- | --- |
| `crates/horizon-client/src/android_main.rs` | `android_main`, the native entry point; unpacking a bundled resource ZIP; panic report file |
| `crates/horizon-client/src/android_platform.rs` | keeps the `AndroidApp` winit's event loop needs |
| `crates/horizon-client/src/launch_args.rs` | lets the Android host supply the command line the shared startup reads |
| `packaging/android/java/.../HorizonApplication.java` | uncaught-exception handler: report to clipboard and `DebugActivity` |
| `packaging/android/java/.../DebugActivity.java` | shows and copies the crash report, restarts the app |
| `packaging/android/java/.../LauncherActivity.java` | first-run resource import through Android's document picker |
| `packaging/android/java/.../GameActivity.java` | the `NativeActivity` that loads `libhorizon_android.so` |
| `.github/workflows/android.yml` | builds arm64-v8a and publishes `android-v*` releases |

The release job never adds Mojang files. Keep it that way: the repository and
its releases must not redistribute game jars, assets or prepared resources.
