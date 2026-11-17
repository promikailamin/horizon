package dev.horizon.android;

import android.app.Application;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.util.Log;

import java.io.File;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Turns an uncaught exception into a readable report: the clipboard gets a copy
 * and {@link DebugActivity} shows it instead of the launcher. The report is also
 * kept in private storage, so a crash before the activity could start is shown
 * on the next launch.
 */
public final class HorizonApplication extends Application {
    private static final String TAG = "Horizon";
    static final String CRASH_FILE = "horizon-crash.txt";
    private static final AtomicBoolean HANDLING = new AtomicBoolean();

    @Override
    public void onCreate() {
        super.onCreate();
        Thread.setDefaultUncaughtExceptionHandler(this::handleCrash);
    }

    private void handleCrash(Thread thread, Throwable error) {
        if (!HANDLING.compareAndSet(false, true)) {
            return;
        }
        String report = report(thread, error);
        Log.e(TAG, report, error);
        try {
            Files.write(new File(getFilesDir(), CRASH_FILE).toPath(),
                    report.getBytes(StandardCharsets.UTF_8));
        } catch (Exception writeError) {
            Log.e(TAG, "Cannot keep the crash report", writeError);
        }
        copy(this, report);
        try {
            Intent intent = new Intent(this, DebugActivity.class);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK
                    | Intent.FLAG_ACTIVITY_CLEAR_TASK
                    | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            intent.putExtra(DebugActivity.EXTRA_REPORT, report);
            startActivity(intent);
        } catch (Exception launchError) {
            Log.e(TAG, "Cannot open the crash screen", launchError);
        }
    }

    static String report(Thread thread, Throwable error) {
        StringWriter text = new StringWriter();
        PrintWriter out = new PrintWriter(text);
        out.println("Horizon crash report");
        out.println("Version: " + BuildConfig.VERSION_NAME + " (" + BuildConfig.VERSION_CODE + ")");
        out.println("Android: " + Build.VERSION.RELEASE + " (API " + Build.VERSION.SDK_INT + ")");
        out.println("Device: " + Build.MANUFACTURER + " " + Build.MODEL + " (" + Build.DEVICE + ")");
        out.println("ABI: " + (Build.SUPPORTED_ABIS.length > 0 ? Build.SUPPORTED_ABIS[0] : "unknown"));
        out.println("Thread: " + thread.getName());
        out.println();
        error.printStackTrace(out);
        out.flush();
        return text.toString();
    }

    static void copy(Context context, String report) {
        try {
            ClipboardManager clipboard =
                    (ClipboardManager) context.getSystemService(Context.CLIPBOARD_SERVICE);
            if (clipboard != null) {
                clipboard.setPrimaryClip(ClipData.newPlainText("Horizon crash", report));
            }
        } catch (Exception error) {
            Log.e(TAG, "Cannot copy the crash report", error);
        }
    }
}
