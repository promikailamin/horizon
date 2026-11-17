//! The command line the game starts with.
//!
//! Desktop builds read the process arguments directly. The Android build starts
//! from `android_main`, where the platform hands us an [`AndroidApp`] instead of
//! a command line, so the host supplies the same arguments here before the
//! shared startup runs. One process launches one game, hence the `OnceLock`.
//!
//! [`AndroidApp`]: https://docs.rs/android-activity/latest/android_activity/struct.AndroidApp.html

use std::sync::OnceLock;

static ARGS: OnceLock<Vec<String>> = OnceLock::new();

/// Set the arguments for this process. The second call is ignored: the first
/// launch owns the command line for the life of the process.
pub fn set(args: Vec<String>) {
    let _ = ARGS.set(args);
}

/// Whether a host supplied the arguments rather than the process itself.
pub fn provided() -> bool {
    ARGS.get().is_some()
}

/// The arguments after the program name: the host's, else the process's own.
pub fn args() -> Vec<String> {
    ARGS.get()
        .cloned()
        .unwrap_or_else(|| std::env::args().skip(1).collect())
}
