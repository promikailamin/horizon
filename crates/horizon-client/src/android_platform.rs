//! The Android app handle winit's event loop needs.
//!
//! On Android winit cannot create an event loop from the environment alone: the
//! process must pass it the [`AndroidApp`] its `android_main` entry point got.
//! The handle arrives before the shared startup runs, on the same thread that
//! later builds the loop, so a thread-local slot is enough. Desktop builds use
//! [`EventLoop::new`] and never touch this module.

use std::cell::RefCell;
use winit::event_loop::EventLoop;
use winit::platform::android::{EventLoopBuilderExtAndroid, activity::AndroidApp};

thread_local! {
    static APP: RefCell<Option<AndroidApp>> = const { RefCell::new(None) };
}

/// Keep the app handle for the event loop this thread builds next.
pub fn set_app(app: AndroidApp) {
    APP.with(|slot| *slot.borrow_mut() = Some(app));
}

/// Build the event loop with the app handle `set_app` kept.
pub fn event_loop() -> Result<EventLoop<()>, winit::error::EventLoopError> {
    APP.with(|slot| {
        let app = slot
            .borrow()
            .as_ref()
            .expect("android_main sets the app before the game builds its event loop")
            .clone();
        EventLoop::builder().with_android_app(app).build()
    })
}
