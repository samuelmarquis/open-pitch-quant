//! The Cocoa mount for the OpenPitchQuant board (macOS). open-eq's mount
//! (itself OpenCepstrum's, without context menus and text entry), for this
//! board.
//!
//! Rules it keeps:
//! - Host callbacks may reenter the editor: the view's state is never
//!   borrowed while edits are delivered (panelkit's `GestureDelivery`).
//! - A restore (preset/state load) cancels a gesture in progress.
//! - Native objects live and die on the main thread; the timer stops first.
//! - Knobs drag relative (panelkit's `PointerLock`): the cursor hides,
//!   motion comes as deltas added to the editor's own pointer, and on
//!   release the cursor lands back on the knob. The lock is released before
//!   edits reach the host and taken after.
//! - The view refuses keyboard focus except while the pointer edits it, so
//!   DAW shortcuts stay with the host.
use crate::gui_shared::{Scene, ViewState, apply};
use crate::state::SharedState;
use block2::RcBlock;
use objc2::rc::Retained;
use objc2::{DefinedClass, MainThreadMarker, MainThreadOnly, define_class, msg_send, sel};
use objc2_app_kit::{NSCursor, NSEvent, NSEventModifierFlags, NSView, NSWindowDidResignKeyNotification};
use objc2_core_foundation::{CGPoint, CGRect, CGSize};
use objc2_foundation::{
    NSNotification, NSNotificationCenter, NSObjectProtocol, NSRunLoop, NSRunLoopCommonModes, NSTimer,
};
use opq_panel::{Edit, HEIGHT, Modifiers, WIDTH};
use panelkit::interaction::GestureDelivery;
use panelkit::mount::{self, MainCell, PointerLock, ViewWindowHandle};
use std::cell::RefCell;
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::ptr::NonNull;
use std::rc::Rc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, MutexGuard};
use wrac_clap_adapter::{
    GuiApi, GuiConfig, GuiResizeHints, GuiSize, HostParamsEditNotifier, HostWindow, PluginError,
    PluginGuiExtension, PluginResult,
};

pub(crate) struct PanelGui {
    shared: Arc<SharedState>,
    notifier: Arc<dyn HostParamsEditNotifier>,
    runtime: Mutex<Option<MainCell<Runtime>>>,
    size: Mutex<GuiSize>,
}

struct Runtime {
    view: Retained<OpqView>,
    timer: Retained<NSTimer>,
    stopped: Arc<AtomicBool>,
}

struct Ivars {
    state: Rc<RefCell<ViewState>>,
    delivery: Rc<GestureDelivery>,
    pointer: PointerLock,
}

#[derive(Clone, Copy)]
enum Mouse {
    Down,
    Drag,
    Up,
}

define_class!(
    #[unsafe(super(NSView))]
    #[thread_kind = MainThreadOnly]
    #[name = "OpenPitchQuantPanelView"]
    #[ivars = Ivars]
    struct OpqView;
    unsafe impl NSObjectProtocol for OpqView {}
    impl OpqView {
        #[unsafe(method(isFlipped))]
        fn is_flipped(&self) -> bool { true }
        #[unsafe(method(acceptsFirstMouse:))]
        fn accepts_first_mouse(&self, _event: Option<&NSEvent>) -> bool { true }
        #[unsafe(method(acceptsFirstResponder))]
        fn accepts_first_responder(&self) -> bool { true }
        #[unsafe(method(resignFirstResponder))]
        fn resign_first_responder(&self) -> bool {
            self.cancel();
            unsafe { msg_send![super(self), resignFirstResponder] }
        }
        #[unsafe(method(keyDown:))]
        fn key_down(&self, event: &NSEvent) { self.key(event); }
        #[unsafe(method(mouseMoved:))]
        fn mouse_moved(&self, event: &NSEvent) { self.track(event); }
        #[unsafe(method(mouseEntered:))]
        fn mouse_entered(&self, event: &NSEvent) { self.track(event); }
        #[unsafe(method(mouseExited:))]
        fn mouse_exited(&self, _event: &NSEvent) { self.pointer_exited(); }
        #[unsafe(method(mouseDown:))]
        fn mouse_down(&self, event: &NSEvent) { self.mouse(event, Mouse::Down); }
        #[unsafe(method(mouseDragged:))]
        fn mouse_dragged(&self, event: &NSEvent) { self.mouse(event, Mouse::Drag); }
        #[unsafe(method(mouseUp:))]
        fn mouse_up(&self, event: &NSEvent) { self.mouse(event, Mouse::Up); }
        #[unsafe(method(scrollWheel:))]
        fn scroll_wheel(&self, event: &NSEvent) { self.scroll(event); }
        #[unsafe(method(windowDidResignKey:))]
        fn window_did_resign_key(&self, _notification: &NSNotification) { self.cancel(); }
        #[unsafe(method(resetCursorRects))]
        fn reset_cursor_rects(&self) {
            if !self.isHiddenOrHasHiddenAncestor() {
                self.addCursorRect_cursor(self.visibleRect(), &NSCursor::arrowCursor());
            }
        }
        #[unsafe(method(viewWillMoveToWindow:))]
        fn will_move_to_window(&self, window: Option<&objc2_app_kit::NSWindow>) {
            self.cancel();
            let center = NSNotificationCenter::defaultCenter();
            unsafe {
                center.removeObserver_name_object(self, Some(NSWindowDidResignKeyNotification), None);
                if let Some(window) = window {
                    center.addObserver_selector_name_object(
                        self,
                        sel!(windowDidResignKey:),
                        Some(NSWindowDidResignKeyNotification),
                        Some(window),
                    );
                }
                let _: () = msg_send![super(self), viewWillMoveToWindow: window];
            }
        }
    }
);

impl OpqView {
    fn new(mtm: MainThreadMarker, state: Rc<RefCell<ViewState>>) -> Retained<Self> {
        let this = Self::alloc(mtm).set_ivars(Ivars { state, delivery: Rc::new(GestureDelivery::default()), pointer: PointerLock::new() });
        let frame = CGRect {
            origin: CGPoint { x: 0.0, y: 0.0 },
            size: CGSize { width: WIDTH as f64, height: HEIGHT as f64 },
        };
        unsafe { msg_send![super(this), initWithFrame: frame] }
    }

    /// Runs an input handler and delivers its edits outside the state borrow.
    fn dispatch(&self, f: impl FnOnce(&mut ViewState) -> Vec<Edit>) {
        self.dispatch_pointer(false, f);
    }

    /// As `dispatch`, keeping the pointer lock in step with the gesture:
    /// released (warping to the drag's anchor when `warp_on_release`)
    /// before the edits reach the host, taken after.
    fn dispatch_pointer(&self, warp_on_release: bool, f: impl FnOnce(&mut ViewState) -> Vec<Edit>) {
        let delivery = self.ivars().delivery.clone();
        let panel_state = self.ivars().state.clone();
        let pointer = &self.ivars().pointer;
        if delivery.is_active() {
            return;
        }
        let result = catch_unwind(AssertUnwindSafe(|| {
            let (edits, shared, notifier, release, anchor) = {
                let Ok(mut state) = self.ivars().state.try_borrow_mut() else { return };
                if state.dead {
                    return;
                }
                let capture = state.fittings.capture();
                let canceled = delivery.take_cancel();
                let mut edits = match canceled {
                    Some(rollback) => state.clear_editing(rollback),
                    None => Vec::new(),
                };
                let revision = state.restore_revision;
                edits.extend(state.refresh());
                // A restore or cancellation invalidates the gesture's input.
                let restored = canceled.is_some() || revision != state.restore_revision;
                if !restored {
                    edits.extend(f(&mut state));
                }
                let release = pointer.releases(capture, state.fittings.capture(), restored);
                let anchor = if release && warp_on_release && !restored {
                    capture.and_then(|capture| capture.release_position(&state.panel))
                } else {
                    None
                };
                (edits, state.shared.clone(), state.notifier.clone(), release, anchor)
            };
            if release {
                pointer.release(self, anchor, (WIDTH, HEIGHT));
            }
            delivery.deliver(
                edits,
                |edits| apply(edits, &shared, &*notifier),
                |rollback| panel_state.borrow_mut().clear_editing(rollback),
            );
            // The host may have ended the drag from a callback: lock only
            // for what is still captured.
            let capture =
                panel_state.try_borrow().ok().and_then(|state| (!state.dead).then(|| state.fittings.capture()).flatten());
            pointer.hold(self, capture, (WIDTH, HEIGHT));
        }));
        if result.is_err() {
            log::error!("OpenPitchQuant input callback panicked");
            self.cancel();
        }
    }

    fn mouse(&self, event: &NSEvent, kind: Mouse) {
        if self.ivars().delivery.is_active() {
            if matches!(kind, Mouse::Up) {
                self.cancel();
            }
            return;
        }
        let mods = modifiers(event);
        let pointer = &self.ivars().pointer;
        if pointer.is_locked() && !matches!(kind, Mouse::Down) {
            // A relative drag: the step moves the editor's own pointer.
            let last = matches!(kind, Mouse::Up);
            let Some((dx, dy)) = pointer.step(self, event, last, (WIDTH, HEIGHT)) else { return };
            self.dispatch_pointer(last, |st| {
                let (x, y) = (st.pointer.0 + dx, st.pointer.1 + dy);
                st.pointer = (x, y);
                let mut edits = st.fittings.drag(&mut st.panel, x, y, mods);
                if last {
                    edits.extend(st.fittings.up(&mut st.panel));
                }
                edits
            });
            return;
        }
        let at = mount::logical_point(self, event.locationInWindow(), (WIDTH, HEIGHT));
        if matches!(kind, Mouse::Up) {
            // AppKit may coalesce the last drag: commit the release position.
            self.dispatch(|st| match at {
                Some((x, y)) => {
                    st.pointer = (x, y);
                    let mut edits = st.fittings.drag(&mut st.panel, x, y, mods);
                    edits.extend(st.fittings.up(&mut st.panel));
                    edits
                }
                None => st.fittings.cancel(&mut st.panel),
            });
            return;
        }
        let Some((x, y)) = at else { return };
        if matches!(kind, Mouse::Down) {
            if let Some(window) = self.window() {
                window.makeFirstResponder(Some(self));
            }
            // A lock the press takes measures its first step from here.
            pointer.set_press(Some((x, y)));
        }
        let clicks = event.clickCount().clamp(0, u32::MAX as isize) as u32;
        self.dispatch(|st| {
            st.pointer = (x, y);
            match kind {
                Mouse::Down => st.fittings.down(&mut st.panel, x, y, mods, clicks),
                _ => st.fittings.drag(&mut st.panel, x, y, mods),
            }
        });
        pointer.set_press(None);
    }

    fn scroll(&self, event: &NSEvent) {
        let Some((x, y)) = mount::logical_point(self, event.locationInWindow(), (WIDTH, HEIGHT)) else {
            return;
        };
        let mods = modifiers(event);
        // Knobs read the physical direction; the pitch view scrolls as
        // content, with the user's natural-scrolling setting.
        let delta = mount::scroll_notches(event);
        let content = mount::scroll_content_notches(event);
        self.dispatch(|st| {
            if st.fittings.capture().is_none() {
                st.pointer = (x, y);
            }
            st.fittings.scroll(&mut st.panel, x, y, delta, content, mods)
        });
    }

    fn key(&self, event: &NSEvent) {
        let text = event.characters().map(|c| c.to_string()).unwrap_or_default();
        let key = match text.as_str() {
            "\u{1b}" => "Escape",
            _ => "",
        };
        if key == "Escape" && self.ivars().delivery.is_active() {
            self.ivars().delivery.request_rollback();
            self.cancel();
            return;
        }
        if key.is_empty() || modifiers(event).command {
            // Not ours: the host's shortcuts keep working.
            unsafe {
                let _: () = msg_send![super(self), keyDown: event];
            }
            return;
        }
        let mods = modifiers(event);
        self.dispatch(|st| st.fittings.key(&mut st.panel, key, mods));
    }

    fn track(&self, event: &NSEvent) {
        let Some((x, y)) = mount::logical_point(self, event.locationInWindow(), (WIDTH, HEIGHT)) else {
            return;
        };
        if let Ok(mut state) = self.ivars().state.try_borrow_mut() {
            let st = &mut *state;
            if st.fittings.capture().is_none() {
                st.pointer = (x, y);
            }
            st.fittings.hover_with_modifiers(&mut st.panel, x, y, modifiers(event));
        }
    }

    fn pointer_exited(&self) {
        if let Ok(mut state) = self.ivars().state.try_borrow_mut() {
            let st = &mut *state;
            st.fittings.hover(&mut st.panel, -1.0, -1.0);
        }
    }

    fn release_focus(&self) {
        self.cancel();
        if let Some(window) = self.window() {
            let is_first = window.firstResponder().is_some_and(|responder| {
                std::ptr::eq(std::ptr::from_ref(&*responder).cast::<()>(), std::ptr::from_ref(self).cast::<()>())
            });
            if is_first {
                window.makeFirstResponder(None);
            }
        }
    }

    /// Ends any gesture, committing what it did (Escape rolls back).
    fn cancel(&self) {
        let delivery = self.ivars().delivery.clone();
        let panel_state = self.ivars().state.clone();
        delivery.request_cancel();
        // The cursor comes back where it is; a cancelled drag has no anchor.
        self.ivars().pointer.release(self, None, (WIDTH, HEIGHT));
        if delivery.is_active() {
            return;
        }
        let _ = catch_unwind(AssertUnwindSafe(|| {
            let payload = self.ivars().state.try_borrow_mut().ok().map(|mut st| {
                let rollback = delivery.take_cancel().unwrap_or(false);
                (st.clear_editing(rollback), st.shared.clone(), st.notifier.clone())
            });
            if let Some((edits, shared, notifier)) = payload {
                delivery.deliver(
                    edits,
                    |edits| apply(edits, &shared, &*notifier),
                    |rollback| panel_state.borrow_mut().clear_editing(rollback),
                );
            }
        }));
    }
}

fn modifiers(event: &NSEvent) -> Modifiers {
    let flags = event.modifierFlags();
    Modifiers {
        shift: flags.contains(NSEventModifierFlags::Shift),
        command: flags.contains(NSEventModifierFlags::Command),
        alt: flags.contains(NSEventModifierFlags::Option),
    }
}

fn tick(view: &OpqView) {
    if view.isHiddenOrHasHiddenAncestor() {
        view.cancel();
        return;
    }
    // Refreshing can close gestures (a restore): deliver outside the render borrow.
    view.dispatch(|_| Vec::new());
    let result = catch_unwind(AssertUnwindSafe(|| -> Result<(), String> {
        let Ok(mut state) = view.ivars().state.try_borrow_mut() else { return Ok(()) };
        if state.dead {
            return Ok(());
        }
        let Some(size) = mount::drawable_size(view, 2.0, 8192.0) else { return Ok(()) };
        // A density change replaces the board and surface together, while the
        // owning view is alive.
        if state.scene.as_ref().is_some_and(|scene| scene.size != size) {
            state.scene = None;
        }
        if state.scene.is_none() {
            let target = ViewWindowHandle::from_ns_view(NonNull::from(view).cast());
            state.scene = Some(Scene::new(target, size)?);
        }
        let st = &mut *state;
        if let Some(scene) = st.scene.as_mut() {
            scene.render(&st.panel)?;
        }
        Ok(())
    }));
    let error = match result {
        Ok(Ok(())) => return,
        Ok(Err(error)) => error,
        Err(_) => "renderer panicked".to_owned(),
    };
    log::error!("OpenPitchQuant panel stopped: {error}");
    view.cancel();
    if let Ok(mut state) = view.ivars().state.try_borrow_mut() {
        state.dead = true;
        state.scene = None;
    }
}

impl PanelGui {
    pub(crate) fn new(shared: Arc<SharedState>, notifier: Arc<dyn HostParamsEditNotifier>) -> Self {
        Self {
            shared,
            notifier,
            runtime: Mutex::new(None),
            size: Mutex::new(GuiSize { width: WIDTH, height: HEIGHT }),
        }
    }

    pub(crate) fn cancel_gestures(&self) {
        if let Ok(view) = self.view() {
            view.cancel();
        }
    }

    fn runtime(&self) -> MutexGuard<'_, Option<MainCell<Runtime>>> {
        self.runtime.lock().unwrap_or_else(|e| e.into_inner())
    }

    fn teardown(&self) {
        let runtime = self.runtime().take();
        if let Some(MainCell(runtime)) = runtime {
            runtime.stopped.store(true, Ordering::Release);
            if MainThreadMarker::new().is_none() {
                // AppKit cannot be destroyed off the main thread: stop the
                // timer's work and keep the native objects.
                log::warn!("OpenPitchQuant GUI destroyed off-main; retaining native view and timer");
                std::mem::forget(runtime);
                return;
            }
            runtime.timer.invalidate();
            runtime.view.release_focus();
            if let Ok(mut state) = runtime.view.ivars().state.try_borrow_mut() {
                state.scene = None;
            }
            runtime.view.removeFromSuperview();
        }
    }

    fn view(&self) -> PluginResult<Retained<OpqView>> {
        let _mtm = MainThreadMarker::new().ok_or(PluginError::InvalidState)?;
        self.runtime().as_ref().map(|MainCell(rt)| rt.view.clone()).ok_or(PluginError::InvalidState)
    }
}

impl Drop for PanelGui {
    fn drop(&mut self) {
        self.teardown();
    }
}

impl PluginGuiExtension for PanelGui {
    fn is_api_supported(&self, api: GuiApi, is_floating: bool) -> bool {
        api == GuiApi::Cocoa && !is_floating
    }
    fn preferred_api(&self) -> Option<GuiConfig> {
        Some(GuiConfig { api: GuiApi::Cocoa, is_floating: false })
    }
    fn create(&self, config: GuiConfig) -> PluginResult<()> {
        if !self.is_api_supported(config.api, config.is_floating) || MainThreadMarker::new().is_none() {
            return Err(PluginError::InvalidState);
        }
        Ok(())
    }
    fn destroy(&self) {
        self.teardown();
    }
    fn set_scale(&self, scale: f64) -> PluginResult<()> {
        // Cocoa's backing scale sets the density, not a host suggestion.
        if scale.is_finite() && scale > 0.0 { Ok(()) } else { Err(PluginError::InvalidState) }
    }
    fn get_size(&self) -> PluginResult<GuiSize> {
        let size = self.size.lock().unwrap_or_else(|e| e.into_inner());
        Ok(GuiSize { width: size.width, height: size.height })
    }
    fn can_resize(&self) -> bool {
        true
    }
    fn resize_hints(&self) -> Option<GuiResizeHints> {
        Some(GuiResizeHints {
            can_resize_horizontally: true,
            can_resize_vertically: true,
            preserve_aspect_ratio: true,
            aspect_ratio_width: WIDTH,
            aspect_ratio_height: HEIGHT,
        })
    }
    fn adjust_size(&self, size: GuiSize) -> PluginResult<GuiSize> {
        let scale = (size.width as f64 / WIDTH as f64).min(size.height as f64 / HEIGHT as f64).clamp(0.7, 2.0);
        Ok(GuiSize { width: (WIDTH as f64 * scale).round() as u32, height: (HEIGHT as f64 * scale).round() as u32 })
    }
    fn set_size(&self, size: GuiSize) -> PluginResult<()> {
        let _mtm = MainThreadMarker::new().ok_or(PluginError::InvalidState)?;
        let adjusted = self.adjust_size(GuiSize { width: size.width, height: size.height })?;
        if adjusted.width != size.width || adjusted.height != size.height {
            return Err(PluginError::InvalidState);
        }
        if let Ok(view) = self.view() {
            view.cancel();
            view.setFrameSize(CGSize { width: size.width as f64, height: size.height as f64 });
        }
        *self.size.lock().unwrap_or_else(|e| e.into_inner()) = size;
        Ok(())
    }
    fn set_parent(&self, window: HostWindow) -> PluginResult<()> {
        let mtm = MainThreadMarker::new().ok_or(PluginError::InvalidState)?;
        let HostWindow::Cocoa { ns_view } = window else {
            return Err(PluginError::InvalidState);
        };
        self.teardown();
        // The host guarantees the parent outlives this attachment.
        let parent = unsafe { &*(ns_view.get() as *const NSView) };
        let state = Rc::new(RefCell::new(ViewState::new(self.shared.clone(), self.notifier.clone())));
        let view = OpqView::new(mtm, state);
        let size = self.get_size()?;
        view.setFrameSize(CGSize { width: size.width as f64, height: size.height as f64 });
        view.setWantsLayer(true);
        mount::track_pointer(&view);
        parent.addSubview(&view);
        let stopped = Arc::new(AtomicBool::new(false));
        let tick_stopped = stopped.clone();
        let tick_view = view.clone();
        let block = RcBlock::new(move |timer: NonNull<NSTimer>| {
            if !tick_stopped.load(Ordering::Acquire) {
                tick(&tick_view);
            } else {
                tick_view.cancel();
                unsafe { timer.as_ref().invalidate() };
            }
        });
        let timer = unsafe { NSTimer::timerWithTimeInterval_repeats_block(1.0 / 30.0, true, &block) };
        unsafe { NSRunLoop::mainRunLoop().addTimer_forMode(&timer, NSRunLoopCommonModes) };
        *self.runtime() = Some(MainCell(Runtime { view, timer, stopped }));
        Ok(())
    }
    fn show(&self) -> PluginResult<()> {
        self.view()?.setHidden(false);
        Ok(())
    }
    fn hide(&self) -> PluginResult<()> {
        let view = self.view()?;
        view.release_focus();
        view.setHidden(true);
        Ok(())
    }
}
