#!/usr/bin/env bash
# Build the arm64 Android APK and the public build ZIP on a fresh runner.
#
# Usage: .agent-work/tools/build_android_arm64.sh [version-name] [version-code]
#
# The public outputs go to .local/android/apk/. To also make the private
# prepared bundle, run tools/android_build.py yourself with
# --resources <folder prepared from your own Minecraft>.
set -euo pipefail

root=$(cd "$(dirname "$0")/../.." && pwd)
version=${1:-0.1.6}
code=${2:-6}
gradle=${HORIZON_GRADLE:-/tmp/gradle/gradle-8.14/bin/gradle}

if [[ ! -x "$gradle" ]]; then
    mkdir -p /tmp/gradle
    curl -fsSL -o /tmp/gradle/gradle-8.14-bin.zip https://services.gradle.org/distributions/gradle-8.14-bin.zip
    unzip -q -o /tmp/gradle/gradle-8.14-bin.zip -d /tmp/gradle
fi

rustup target add aarch64-linux-android
cd "$root"
CARGO_TARGET_DIR="$root/.local/android-target" \
    python3 tools/android_build.py \
    --abi arm64-v8a \
    --profile release \
    --ndk-version "${HORIZON_NDK_VERSION:-27.3.13750724}" \
    --build-tools-version "${HORIZON_BUILD_TOOLS_VERSION:-35.0.0}" \
    --gradle "$gradle" \
    --java-home "${JAVA_HOME_21_X64:-/usr/lib/jvm/temurin-21-jdk-amd64}" \
    --version-name "$version" \
    --version-code "$code"
