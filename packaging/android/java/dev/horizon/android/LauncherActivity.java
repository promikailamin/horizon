package dev.horizon.android;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.text.method.ScrollingMovementMethod;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * The small first-run screen: prepared game files are imported once, then the
 * native activity takes over. Nothing of the game itself lives here.
 */
public final class LauncherActivity extends Activity {
    private static final String TAG = "Horizon";
    private static final int REQUEST_ZIP = 4101;
    private static final String MANIFEST = "horizon-resources.json";

    private final File resources() {
        return new File(getFilesDir(), "horizon-resources");
    }

    private TextView message;
    private Button importButton;
    private volatile boolean importing;
    private boolean gameStarted;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        if (showSavedCrash()) {
            return;
        }
        buildUi();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (!importing && !gameStarted && ready()) {
            startGame();
        }
    }

    private boolean ready() {
        return new File(resources(), MANIFEST).isFile() || bundled();
    }

    /**
     * A private test APK may carry prepared files in its assets. The native
     * entry point unpacks them on the first launch, so there is nothing to
     * import from the phone.
     */
    private boolean bundled() {
        try (InputStream ignored = getAssets().open("horizon-resources.zip")) {
            return true;
        } catch (IOException missing) {
            return false;
        }
    }

    private boolean showSavedCrash() {
        File file = new File(getFilesDir(), HorizonApplication.CRASH_FILE);
        if (!file.isFile()) {
            return false;
        }
        String report;
        try {
            report = new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8);
        } catch (IOException error) {
            Log.e(TAG, "Cannot read the saved crash report", error);
            return false;
        }
        Intent intent = new Intent(this, DebugActivity.class);
        intent.putExtra(DebugActivity.EXTRA_REPORT, report);
        startActivity(intent);
        finish();
        return true;
    }

    private void buildUi() {
        int pad = (int) TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_DIP, 20, getResources().getDisplayMetrics());

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setPadding(pad, pad, pad, pad);
        root.setBackgroundColor(Color.rgb(17, 16, 20));

        TextView title = new TextView(this);
        title.setText(R.string.launcher_title);
        title.setTextColor(Color.WHITE);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 26);
        title.setGravity(Gravity.CENTER);
        root.addView(title, matchWrap());

        TextView body = new TextView(this);
        body.setText(R.string.launcher_body);
        body.setTextColor(Color.rgb(210, 206, 224));
        body.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        body.setPadding(0, pad, 0, pad);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(body);
        root.addView(scroll, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        message = new TextView(this);
        message.setTextColor(Color.rgb(154, 134, 255));
        message.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        message.setMovementMethod(new ScrollingMovementMethod());
        root.addView(message, matchWrap());

        importButton = new Button(this);
        importButton.setText(R.string.launcher_import);
        importButton.setOnClickListener(view -> chooseZip());
        root.addView(importButton, matchWrap());

        Button quit = new Button(this);
        quit.setText(R.string.launcher_quit);
        quit.setOnClickListener(view -> finishAffinity());
        root.addView(quit, matchWrap());

        setContentView(root);
    }

    private static LinearLayout.LayoutParams matchWrap() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.setMargins(0, 8, 0, 8);
        return params;
    }

    private void chooseZip() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{
                "application/zip", "application/x-zip-compressed", "application/octet-stream"});
        try {
            startActivityForResult(intent, REQUEST_ZIP);
        } catch (Exception error) {
            showError(getString(R.string.launcher_no_picker));
        }
    }

    @Override
    protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != REQUEST_ZIP || result != RESULT_OK || data == null) {
            return;
        }
        Uri uri = data.getData();
        if (uri == null) {
            return;
        }
        importing = true;
        importButton.setEnabled(false);
        message.setText(R.string.launcher_waiting);
        new Thread(() -> importZip(uri), "horizon-resource-import").start();
    }

    private void importZip(Uri uri) {
        File temporary = new File(getCacheDir(), "resources-import");
        try {
            delete(temporary);
            if (!temporary.mkdirs() && !temporary.isDirectory()) {
                throw new IOException("Cannot create " + temporary);
            }
            try (InputStream raw = getContentResolver().openInputStream(uri)) {
                if (raw == null) {
                    throw new IOException("The selected file cannot be read");
                }
                unzip(raw, temporary);
            }
            File root = findManifestRoot(temporary, 2);
            if (root == null) {
                throw new IOException(getString(R.string.launcher_bad_zip));
            }
            File destination = resources();
            delete(destination);
            if (!copyTree(root, destination)) {
                throw new IOException("Cannot write " + destination);
            }
            delete(temporary);
            runOnUiThread(() -> {
                importing = false;
                message.setText(R.string.launcher_done);
                startGame();
            });
        } catch (Exception error) {
            Log.e(TAG, "Resource import failed", error);
            runOnUiThread(() -> {
                importing = false;
                importButton.setEnabled(true);
                showError(getString(R.string.launcher_failed,
                        error.getMessage() == null ? error.toString() : error.getMessage()));
            });
        }
    }

    private void unzip(InputStream raw, File destination) throws IOException {
        String base = destination.getCanonicalPath() + File.separator;
        try (ZipInputStream zip = new ZipInputStream(new BufferedInputStream(raw))) {
            ZipEntry entry;
            byte[] buffer = new byte[64 * 1024];
            while ((entry = zip.getNextEntry()) != null) {
                String name = entry.getName().replace('\\', '/');
                if (name.startsWith("/") || name.contains("../") || name.contains("/..")) {
                    throw new IOException("Unsafe path in ZIP: " + name);
                }
                File target = new File(destination, name);
                if (!target.getCanonicalPath().startsWith(base)) {
                    throw new IOException("Unsafe path in ZIP: " + name);
                }
                if (entry.isDirectory()) {
                    if (!target.mkdirs() && !target.isDirectory()) {
                        throw new IOException("Cannot create " + target);
                    }
                    continue;
                }
                File parent = target.getParentFile();
                if (parent != null && !parent.mkdirs() && !parent.isDirectory()) {
                    throw new IOException("Cannot create " + parent);
                }
                try (OutputStream out = new FileOutputStream(target)) {
                    int count;
                    while ((count = zip.read(buffer)) > 0) {
                        out.write(buffer, 0, count);
                    }
                }
            }
        }
    }

    private static File findManifestRoot(File directory, int depth) {
        if (new File(directory, MANIFEST).isFile()) {
            return directory;
        }
        if (depth <= 0) {
            return null;
        }
        File[] children = directory.listFiles(File::isDirectory);
        if (children == null) {
            return null;
        }
        for (File child : children) {
            File found = findManifestRoot(child, depth - 1);
            if (found != null) {
                return found;
            }
        }
        return null;
    }

    private static boolean copyTree(File source, File destination) {
        if (source.isDirectory()) {
            if (!destination.mkdirs() && !destination.isDirectory()) {
                return false;
            }
            File[] children = source.listFiles();
            if (children == null) {
                return false;
            }
            for (File child : children) {
                if (!copyTree(child, new File(destination, child.getName()))) {
                    return false;
                }
            }
            return true;
        }
        if (destination.getParentFile() != null) {
            destination.getParentFile().mkdirs();
        }
        try (InputStream in = new FileInputStream(source);
             OutputStream out = new FileOutputStream(destination)) {
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = in.read(buffer)) > 0) {
                out.write(buffer, 0, count);
            }
            return true;
        } catch (IOException error) {
            Log.e(TAG, "Cannot copy " + source, error);
            return false;
        }
    }

    private static void delete(File file) {
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) {
                    delete(child);
                }
            }
        }
        //noinspection ResultOfMethodCallIgnored
        file.delete();
    }

    private void showError(String text) {
        new AlertDialog.Builder(this)
                .setTitle(R.string.launcher_import_failed_title)
                .setMessage(text)
                .setPositiveButton(android.R.string.ok, null)
                .show();
    }

    private void startGame() {
        File library = new File(getApplicationInfo().nativeLibraryDir, "libhorizon_android.so");
        if (!library.isFile()) {
            message.setText(R.string.launcher_native_missing);
            return;
        }
        gameStarted = true;
        try {
            startActivity(new Intent(this, GameActivity.class));
            finish();
        } catch (Exception error) {
            gameStarted = false;
            showError(getString(R.string.launcher_failed, error.toString()));
        }
    }
}
