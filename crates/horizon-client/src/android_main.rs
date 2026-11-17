//! Android's native entry point: the same game the desktop builds run, started
//! from the `AndroidApp` the platform hands `android_main` instead of a command
//! line.
//!
//! The APK's `LauncherActivity` makes sure the prepared game files are under
//! `files/horizon-resources` before this starts. A development build may instead
//! pack them as `assets/horizon-resources.zip`; the first launch unpacks that
//! copy, so a private test APK can carry its own resources.

#![cfg(target_os = "android")]

use std::path::{Path, PathBuf};

use winit::platform::android::activity::AndroidApp;

/// Open the log in logcat before the game installs its own logger.
fn init_logging() {
    android_logger::init_once(
        android_logger::Config::default()
            .with_max_level(log::LevelFilter::Info)
            .with_tag("Horizon"),
    );
}

/// A panic cannot reach Java's uncaught exception handler, so leave the report
/// where `LauncherActivity` looks for it on the next start.
fn install_panic_hook(home: PathBuf) {
    let previous = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        previous(info);
        let report = format!(
            "Horizon crashed on Android\n\n{info}\n\nThread: {:?}\n",
            std::thread::current().name()
        );
        let _ = std::fs::write(home.join("horizon-crash.txt"), report);
    }));
}

/// The single top-level folder a ZIP wraps its entries in, if it has one.
fn common_prefix(archive: &mut zip::ZipArchive<std::fs::File>) -> Option<String> {
    let mut prefix = None;
    for i in 0..archive.len() {
        let name = archive.by_index(i).ok()?.name().ok()?.to_string();
        let first = name.split('/').next()?.to_string();
        if first.is_empty() {
            continue;
        }
        match &prefix {
            Some(current) if *current != first => return None,
            Some(_) => {}
            None => prefix = Some(first),
        }
    }
    prefix.filter(|first| {
        // A file at the root means the archive has no wrapping folder.
        !Path::new(first)
            .extension()
            .is_some_and(|ext| ext == "json")
    })
}

/// Unpack `assets/horizon-resources.zip` into `resources`, stripping a single
/// wrapping folder so the manifest lands where the game looks for it.
fn unpack_bundled_resources(app: &AndroidApp, resources: &Path) -> std::io::Result<()> {
    let Some(mut data) = app.asset_manager().open(c"horizon-resources.zip") else {
        return Ok(());
    };
    let partial = resources.with_extension("partial");
    let _ = std::fs::remove_dir_all(&partial);
    std::fs::create_dir_all(&partial)?;
    let file = partial.join("bundle.zip");
    let mut out = std::fs::File::create(&file)?;
    std::io::copy(&mut data, &mut out)?;
    drop(out);
    let mut archive = zip::ZipArchive::new(std::fs::File::open(&file)?)?;
    let prefix = common_prefix(&mut archive);
    for i in 0..archive.len() {
        let mut entry = archive.by_index(i)?;
        let Some(name) = entry.enclosed_name() else {
            continue;
        };
        let name = if let Some(prefix) = &prefix {
            name.strip_prefix(prefix).unwrap_or(&name)
        } else {
            &name
        };
        let target = partial.join(name);
        if entry.is_dir() {
            std::fs::create_dir_all(&target)?;
            continue;
        }
        if let Some(parent) = target.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let mut target = std::fs::File::create(&target)?;
        std::io::copy(&mut entry, &mut target)?;
    }
    let _ = std::fs::remove_file(partial.join("bundle.zip"));
    if resources.exists() {
        let _ = std::fs::remove_dir_all(resources);
    }
    std::fs::rename(&partial, resources)
}

fn prepare_resources(app: &AndroidApp, resources: &Path) {
    if resources.join("horizon-resources.json").is_file() {
        return;
    }
    if let Err(error) = unpack_bundled_resources(app, resources) {
        log::error!(
            "Cannot unpack the bundled game resources into {}: {error}",
            resources.display()
        );
    }
}

fn run(app: AndroidApp) {
    init_logging();
    let Some(home) = app.internal_data_path() else {
        log::error!("Android supplied no application data directory");
        return;
    };
    install_panic_hook(home.clone());
    let game_dir = home.join("game");
    let resources = home.join("horizon-resources");
    if let Err(error) = std::fs::create_dir_all(&game_dir) {
        log::error!("Cannot create {}: {error}", game_dir.display());
        return;
    }
    prepare_resources(&app, &resources);
    if let Err(error) = std::env::set_current_dir(&game_dir) {
        log::error!("Cannot open {}: {error}", game_dir.display());
        return;
    }
    horizon_client::launch_args::set(vec![
        "--resources".into(),
        resources.to_string_lossy().into_owned(),
        "--game-dir".into(),
        game_dir.to_string_lossy().into_owned(),
    ]);
    horizon_client::android_platform::set_app(app);
    horizon_client::entry::main();
}

#[unsafe(no_mangle)]
fn android_main(app: AndroidApp) {
    run(app);
    // Winit builds one event loop per process, and NativeActivity may keep the
    // process cached after the player quits; a fresh launch must start clean.
    std::process::exit(0);
}

#[cfg(test)]
mod tests {
    use super::*;

    fn archive(entries: &[(&str, &[u8])]) -> zip::ZipArchive<std::fs::File> {
        let path = std::env::temp_dir().join(format!(
            "horizon-android-archive-{}-{:?}.zip",
            std::process::id(),
            std::thread::current().id()
        ));
        let file = std::fs::File::create(&path).unwrap();
        let mut writer = zip::ZipWriter::new(file);
        for (name, contents) in entries {
            writer
                .start_file::<_, ()>(*name, zip::write::SimpleFileOptions::default())
                .unwrap();
            use std::io::Write;
            writer.write_all(contents).unwrap();
        }
        writer.finish().unwrap();
        let archive = zip::ZipArchive::new(std::fs::File::open(&path).unwrap()).unwrap();
        let _ = std::fs::remove_file(path);
        archive
    }

    #[test]
    fn a_single_wrapping_folder_is_stripped() {
        let mut zip = archive(&[
            ("horizon-resources/horizon-resources.json", b"{}"),
            ("horizon-resources/textures/a.png", b"x"),
        ]);
        assert_eq!(
            common_prefix(&mut zip).as_deref(),
            Some("horizon-resources")
        );
    }

    #[test]
    fn files_at_the_root_are_not_stripped() {
        let mut zip = archive(&[("horizon-resources.json", b"{}"), ("textures/a.png", b"x")]);
        assert_eq!(common_prefix(&mut zip), None);
    }
}
