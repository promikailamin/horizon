#!/usr/bin/env python3
"""Build the arm64 Horizon Android APK.

The APK carries Horizon's Rust game (``libhorizon_android.so``) and the small
Java crash/import shell in :mod:`packaging.android`. It never carries Minecraft
itself: point ``--resources`` at a folder prepared by ``horizon-prepare`` to put
that copy in the APK's assets for a private test build, or import a prepared ZIP
from the app's first screen. See ``docs/android.md``.

Examples::

    python3 tools/android_build.py --abi arm64-v8a
    python3 tools/android_build.py --check
    python3 tools/android_build.py --resources .local/horizon-client/26.3
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "packaging" / "android"
LOCAL = ROOT / ".local" / "android"
TARGETS = {"arm64-v8a": "aarch64-linux-android", "x86_64": "x86_64-linux-android"}
MIN_SDK = {"arm64-v8a": 28, "x86_64": 28}


def newest(directory: Path) -> Path:
    candidates = [p for p in directory.iterdir() if p.is_dir()]
    if not candidates:
        raise SystemExit(f"No version found in {directory}")
    return max(candidates, key=lambda p: tuple(int(v) for v in p.name.split(".") if v.isdigit()))


def run(command: list[object], **kwargs) -> None:
    text = [str(value) for value in command]
    print("$", " ".join(text), flush=True)
    subprocess.run(text, check=True, **kwargs)


def sdk(args: argparse.Namespace) -> Path:
    value = args.sdk or os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    path = Path(value) if value else Path.home() / "Android" / "Sdk"
    if not path.is_dir():
        raise SystemExit(f"Android SDK not found: {path} (set ANDROID_HOME or pass --sdk)")
    return path


def ndk(root: Path, version: str | None) -> Path:
    folder = root / "ndk" / version if version else newest(root / "ndk")
    if not (folder / "toolchains").is_dir():
        raise SystemExit(f"Android NDK not found: {folder}")
    return folder


def build_tools(root: Path, version: str | None) -> Path:
    folder = root / "build-tools" / version if version else newest(root / "build-tools")
    if not (folder / "apksigner").is_file():
        raise SystemExit(f"Android build-tools not found: {folder}")
    return folder


def cargo_target_dir() -> Path:
    """Where Cargo writes this build, honouring CARGO_TARGET_DIR."""
    value = os.environ.get("CARGO_TARGET_DIR")
    if not value:
        return ROOT / "target"
    directory = Path(value)
    return directory if directory.is_absolute() else ROOT / directory


def cargo_environment(ndk_root: Path, abi: str) -> dict[str, str]:
    target = TARGETS[abi]
    host = "windows-x86_64" if os.name == "nt" else "linux-x86_64"
    bin_dir = ndk_root / "toolchains" / "llvm" / "prebuilt" / host / "bin"
    clang = bin_dir / f"{target}{MIN_SDK[abi]}-clang"
    if os.name == "nt":
        clang = clang.with_suffix(".cmd")
    if not clang.is_file():
        raise SystemExit(f"NDK compiler not found: {clang}")
    suffix = ".exe" if os.name == "nt" else ""
    environment = dict(os.environ)
    environment["PATH"] = os.pathsep.join([str(bin_dir), environment.get("PATH", "")])
    triple = target.replace("-", "_")
    environment[f"CC_{triple}"] = str(clang)
    environment[f"CXX_{triple}"] = str(bin_dir / f"{target}{MIN_SDK[abi]}-clang++{suffix}")
    environment[f"AR_{triple}"] = str(bin_dir / f"llvm-ar{suffix}")
    environment[f"CARGO_TARGET_{triple.upper()}_LINKER"] = str(clang)
    environment.setdefault("CARGO_PROFILE_DEV_DEBUG", "0")
    return environment


def resource_zip(source: Path, output: Path) -> None:
    manifest = source / "horizon-resources.json"
    if not manifest.is_file():
        raise SystemExit(f"{source} is not a prepared resource folder (no horizon-resources.json)")
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(".partial")
    with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, (Path(source.name) / path.relative_to(source)).as_posix())
    partial.replace(output)


def make_keystore(path: Path) -> None:
    if path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    keytool = shutil.which("keytool")
    if keytool is None:
        raise SystemExit("keytool is not on PATH; install a JDK or pass --keystore")
    run([keytool, "-genkeypair", "-keystore", path, "-storepass", "android",
         "-keypass", "android", "-alias", "horizon", "-keyalg", "RSA",
         "-validity", "3650", "-dname", "CN=Horizon Android Development"])


def gradle_command(args: argparse.Namespace) -> str:
    if args.gradle:
        return str(args.gradle)
    found = shutil.which("gradle")
    if found:
        return found
    raise SystemExit("Gradle 8.14 is not on PATH; pass --gradle PATH")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--abi", choices=sorted(TARGETS), default="arm64-v8a")
    parser.add_argument("--profile", choices=["debug", "fast", "release"], default="release")
    parser.add_argument("--sdk", type=Path)
    parser.add_argument("--ndk-version")
    parser.add_argument("--build-tools-version")
    parser.add_argument("--java-home", type=Path)
    parser.add_argument("--gradle", type=Path)
    parser.add_argument("--resources", type=Path, help="A horizon-prepare output folder to pack in the APK")
    parser.add_argument("--keystore", type=Path, default=LOCAL / "debug.keystore")
    parser.add_argument("--version-name", default="0.1.0")
    parser.add_argument("--version-code", type=int, default=1)
    parser.add_argument("--out", type=Path, default=LOCAL / "apk")
    parser.add_argument("--check", action="store_true", help="Only type-check the Android target")
    parser.add_argument("--clippy", action="store_true", help="Run Android clippy with warnings denied")
    parser.add_argument("--skip-rust", action="store_true", help="Reuse the library already built")
    parser.add_argument("--rust-only", action="store_true", help="Build the shared library and stop")
    args = parser.parse_args()

    sdk_root = sdk(args)
    ndk_root = ndk(sdk_root, args.ndk_version)
    tools = build_tools(sdk_root, args.build_tools_version)
    target = TARGETS[args.abi]
    environment = cargo_environment(ndk_root, args.abi)
    environment["ANDROID_HOME"] = str(sdk_root)
    environment["ANDROID_NDK_HOME"] = str(ndk_root)
    if args.java_home:
        environment["JAVA_HOME"] = str(args.java_home)
        environment["PATH"] = os.pathsep.join([str(args.java_home / "bin"), environment["PATH"]])

    if args.check or args.clippy:
        command = ["cargo", "clippy" if args.clippy else "check", "-p", "horizon-android",
                   "--target", target]
        if args.clippy:
            command += ["--no-deps", "--", "-D", "warnings"]
        run(command, cwd=ROOT, env=environment)
        return

    if not args.skip_rust:
        run(["cargo", "build", "-p", "horizon-android", "--target", target,
             "--profile", args.profile], cwd=ROOT, env=environment)

    folder = "debug" if args.profile == "debug" else args.profile
    library = cargo_target_dir() / target / folder / "libhorizon_android.so"
    if not library.is_file():
        raise SystemExit(f"Native library not found: {library}")
    jni = ANDROID / "jniLibs" / args.abi
    jni.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(library, jni / "libhorizon_android.so")
    if args.rust_only:
        print(f"Native library: {jni / 'libhorizon_android.so'}")
        return

    assets = ANDROID / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    bundle = assets / "horizon-resources.zip"
    if args.resources:
        resource_zip(args.resources, bundle)
        print(f"Bundled private resources: {bundle}")
    else:
        bundle.unlink(missing_ok=True)

    make_keystore(args.keystore)
    variant = "Debug" if args.profile == "debug" else "Release"
    run([gradle_command(args), "--no-daemon", "-p", ANDROID,
         "-Pabi=" + args.abi,
         "-PminSdk=" + str(MIN_SDK[args.abi]),
         "-PversionName=" + args.version_name,
         "-PversionCode=" + str(args.version_code),
         "-Pkeystore=" + str(args.keystore.resolve()),
         "assemble" + variant], cwd=ROOT, env=environment)

    out_dir = ANDROID / "build" / "outputs" / "apk" / variant.lower()
    apks = sorted(out_dir.glob("*.apk"), key=lambda p: p.stat().st_mtime)
    if not apks:
        raise SystemExit(f"APK not found under {out_dir}")
    built = apks[-1]
    args.out.mkdir(parents=True, exist_ok=True)
    apk = args.out / f"horizon-android-{args.abi}.apk"
    shutil.copyfile(built, apk)
    signer = tools / "apksigner"
    if signer.is_file():
        run([signer, "verify", "--verbose", apk])
    print(f"APK: {apk}")


if __name__ == "__main__":
    main()
