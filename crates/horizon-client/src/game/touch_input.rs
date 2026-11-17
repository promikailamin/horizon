//! Touch on Android: the on-screen controls while in play, and a finger
//! standing in for the mouse on every screen (there is no pointer otherwise).
use super::*;
use winit::event::TouchPhase;

impl Game<'_> {
    /// Whether the on-screen controls own touches this frame.
    fn touch_playing(&self) -> bool {
        self.screen == Screen::Playing
            && self.player.is_some()
            && !self.ui.hide_gui
            && !self.screen_over_playing()
            && !self.prompt_open()
            && !self.overlay_holds_view()
    }

    /// The controls' pad state for this tick, or nothing when they are not shown.
    pub(super) fn touch_pad_state(&mut self) -> horizon_client::gamepad::PadState {
        if self.touch_playing() {
            self.touch.poll_state()
        } else {
            self.touch.clear();
            horizon_client::gamepad::PadState::default()
        }
    }

    /// Buttons that open something rather than being a controller button.
    pub(super) fn handle_touch_requests(&mut self) {
        if std::mem::take(&mut self.touch.clicked) {
            self.audio.play_button_click();
        }
        if std::mem::take(&mut self.touch.chat_requested) && self.screen == Screen::Playing {
            self.open_chat_method("");
        }
        if std::mem::take(&mut self.touch.settings_requested) && self.screen == Screen::Playing {
            self.open_options(self.title.is_some());
        }
        if std::mem::take(&mut self.touch.debug_requested) && self.screen == Screen::Playing {
            self.debug = !self.debug;
        }
        if std::mem::take(&mut self.touch.perspective_requested) && self.screen == Screen::Playing {
            self.cycle_camera();
        }
        for (token, down) in self.touch.key_events() {
            let action = token.strip_prefix("action:").unwrap_or(&token);
            if let Err(error) = self.pad_action(action, down) {
                log::warn!("Horizon: touch action {action} failed: {error}");
            }
        }
    }

    /// One touch event from the window.
    pub(super) fn handle_touch(
        &mut self,
        event_loop: &dyn EventLoopCtl,
        touch: &winit::event::Touch,
    ) {
        let Some(renderer) = &self.renderer else {
            return;
        };
        let (width, height) = (renderer.config.width.max(1), renderer.config.height.max(1));
        let point = [
            (touch.location.x as f32 / width as f32).clamp(0.0, 1.0),
            (touch.location.y as f32 / height as f32).clamp(0.0, 1.0),
        ];
        let started = touch.phase == TouchPhase::Started;
        let ended = matches!(touch.phase, TouchPhase::Ended | TouchPhase::Cancelled);
        self.touch.viewport(width, height);
        // A screen touched in play is the controls', unless a menu finger is
        // already standing in for the pointer.
        if self.touch_playing() && self.screen_touch.is_none() {
            let delta = self.touch.update(touch.id, point, started, ended);
            if delta != [0.0; 2] {
                let turn =
                    horizon_client::touch::camera_delta(delta, width, height, &self.touch.settings);
                self.look_turn(f64::from(turn[0]) / 0.15, f64::from(turn[1]) / 0.15);
            }
            self.last_input = Instant::now();
            return;
        }
        // Every other screen has no pointer of its own: the first finger moves
        // the cursor, presses the left button and releases it.
        if started && self.screen_touch.is_none() {
            self.screen_touch = Some((touch.id, touch.device_id));
            self.touch_cursor(event_loop, touch);
            self.touch_button(event_loop, touch, ElementState::Pressed);
        } else if self.screen_touch.is_some_and(|(id, _)| id == touch.id) {
            self.touch_cursor(event_loop, touch);
            if ended {
                self.touch_button(event_loop, touch, ElementState::Released);
                self.screen_touch = None;
            }
        }
    }

    fn touch_cursor(&mut self, event_loop: &dyn EventLoopCtl, touch: &winit::event::Touch) {
        self.handle_window_event_inner(
            event_loop,
            WindowEvent::CursorMoved {
                device_id: touch.device_id,
                position: touch.location,
            },
        );
    }

    fn touch_button(
        &mut self,
        event_loop: &dyn EventLoopCtl,
        touch: &winit::event::Touch,
        state: ElementState,
    ) {
        self.handle_window_event_inner(
            event_loop,
            WindowEvent::MouseInput {
                device_id: touch.device_id,
                state,
                button: MouseButton::Left,
            },
        );
    }
}
