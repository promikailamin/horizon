package dev.horizon.android;

import android.app.NativeActivity;

/**
 * The window and input surface. Android creates it as a NativeActivity and
 * loads {@code libhorizon_android.so}, whose {@code android_main} runs the game.
 */
public final class GameActivity extends NativeActivity {
    static {
        System.loadLibrary("horizon_android");
    }
}
