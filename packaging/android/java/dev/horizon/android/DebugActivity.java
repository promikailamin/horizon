package dev.horizon.android;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Process;
import android.text.method.ScrollingMovementMethod;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

/** The crash report, with the same text already on the clipboard. */
public final class DebugActivity extends Activity {
    public static final String EXTRA_REPORT = "dev.horizon.android.CRASH_REPORT";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        String report = getIntent().getStringExtra(EXTRA_REPORT);
        if (report == null) {
            report = readSaved();
        }
        HorizonApplication.copy(this, report);

        int pad = (int) TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_DIP, 16, getResources().getDisplayMetrics());
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);
        root.setBackgroundColor(Color.rgb(17, 16, 20));

        TextView body = new TextView(this);
        body.setText(report);
        body.setTextColor(Color.rgb(235, 232, 245));
        body.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        body.setTypeface(Typeface.MONOSPACE);
        body.setTextIsSelectable(true);
        body.setMovementMethod(new ScrollingMovementMethod());
        ScrollView scroll = new ScrollView(this);
        scroll.addView(body);
        root.addView(scroll, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        Button copy = new Button(this);
        copy.setText(R.string.crash_copy);
        copy.setOnClickListener(view -> {
            HorizonApplication.copy(this, report);
            Toast.makeText(this, R.string.crash_copied, Toast.LENGTH_SHORT).show();
        });
        root.addView(copy);

        Button restart = new Button(this);
        restart.setText(R.string.crash_restart);
        restart.setOnClickListener(view -> restart());
        root.addView(restart);

        Button close = new Button(this);
        close.setText(R.string.crash_close);
        close.setOnClickListener(view -> {
            finishAffinity();
            Process.killProcess(Process.myPid());
        });
        root.addView(close);

        setContentView(root);
    }

    private String readSaved() {
        try {
            File file = new File(getFilesDir(), HorizonApplication.CRASH_FILE);
            if (file.isFile()) {
                return new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8);
            }
        } catch (Exception ignored) {
            // The screen still says what happened.
        }
        return getString(R.string.debug_body);
    }

    private void restart() {
        //noinspection ResultOfMethodCallIgnored
        new File(getFilesDir(), HorizonApplication.CRASH_FILE).delete();
        Intent intent = new Intent(this, LauncherActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK
                | Intent.FLAG_ACTIVITY_CLEAR_TASK
                | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        startActivity(intent);
        finish();
    }
}
