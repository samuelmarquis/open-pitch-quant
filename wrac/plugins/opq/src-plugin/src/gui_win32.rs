//! The Win32 mount for the OpenPitchQuant board: a child HWND embedded in
//! the host's editor window, rendered by the same wgpu Board the Cocoa
//! mount runs, beaten by a 30 Hz WM_TIMER. open-eq's Win32 mount (itself
//! OpenCepstrum's), for this board.
//!
//! Rules it keeps (the Cocoa mount's):
//! - Host callbacks may reenter the editor: the view's state is never
//!   borrowed while edits are delivered (panelkit's `GestureDelivery`).
//! - A restore (preset/state load) cancels a gesture in progress.
//! - The window lives and dies on the thread that created it; the timer dies
//!   with it.
//! - Knobs drag relative (panelkit's `PointerLock`): the cursor hides,
//!   motion comes as deltas added to the editor's own pointer, and on
//!   release the cursor lands back on the knob.
//! - Focus is taken only by an editor click. Escape is the panel's; every
//!   other key goes back to the host window, so DAW shortcuts keep working.
//!   Ctrl maps to Command, Alt to Option.
//!
//! The initial size follows fractional desktop DPI. Rendering ceils to 1x/2x
//! and the present blit downsamples fractional sizes.
use crate::gui_shared::{Scene, ViewState, apply};
use crate::state::SharedState;
use opq_panel::{Edit, HEIGHT, Modifiers, WIDTH};
use panelkit::interaction::GestureDelivery;
use panelkit::mount::{self, MainCell, PointerLock, ViewWindowHandle, release_capture};
use std::cell::{Cell, RefCell};
use std::ffi::c_void;
use std::num::NonZeroIsize;
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::rc::Rc;
use std::sync::{Arc, LazyLock, Mutex, MutexGuard, Once};
use windows_sys::Win32::Foundation::{HWND, LPARAM, LRESULT, POINT, WPARAM};
use windows_sys::Win32::Graphics::Gdi::ScreenToClient;
use windows_sys::Win32::System::LibraryLoader::GetModuleHandleW;
use windows_sys::Win32::System::Threading::GetCurrentThreadId;
use windows_sys::Win32::UI::HiDpi::GetDpiForSystem;
use windows_sys::Win32::UI::Input::KeyboardAndMouse::{
    GetCapture, GetFocus, GetKeyState, SetFocus, TME_LEAVE, TRACKMOUSEEVENT, TrackMouseEvent, VK_CONTROL,
    VK_LWIN, VK_MENU, VK_RWIN, VK_SHIFT,
};
use windows_sys::Win32::UI::WindowsAndMessaging::{
    CREATESTRUCTW, CS_DBLCLKS, CreateWindowExW, DefWindowProcW, DestroyWindow, GWLP_USERDATA, GetCursorPos,
    GetParent, GetWindowLongPtrW, HTCLIENT, IDC_ARROW, IsWindowVisible, KillTimer, LoadCursorW, RegisterClassW,
    RegisterWindowMessageW, RemovePropW, SW_HIDE, SW_SHOW, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOZORDER, SendMessageW,
    SetCursor, SetPropW, SetTimer, SetWindowLongPtrW, SetWindowPos, ShowWindow, WM_CANCELMODE, WM_CAPTURECHANGED,
    WM_CHAR, WM_DESTROY, WM_ERASEBKGND, WM_KEYDOWN, WM_KEYUP, WM_KILLFOCUS, WM_LBUTTONDBLCLK, WM_LBUTTONDOWN,
    WM_LBUTTONUP, WM_MOUSEMOVE, WM_MOUSEWHEEL, WM_NCCREATE, WM_NCDESTROY, WM_SETCURSOR, WM_TIMER, WNDCLASSW,
    WS_CHILD, WS_VISIBLE, WindowFromPoint,
};
use wrac_clap_adapter::{
    GuiApi, GuiConfig, GuiResizeHints, GuiSize, HostParamsEditNotifier, HostWindow, PluginError,
    PluginGuiExtension, PluginResult,
};

/// TrackMouseEvent's answer. windows-sys files this constant under a
/// common-controls feature the mount otherwise never touches.
const WM_MOUSELEAVE: u32 = 0x02A3;

const TICK_MS: u32 = 33; // ~30 Hz, the Cocoa timer's beat
const TIMER_ID: usize = 1;
/// The editor's size follows the content scale fractionally (a 150% desktop
/// gets a 150% window), while the Board keeps its own 1x/2x densities.
const MAX_SCALE: f64 = 2.0;

pub(crate) struct PanelGui {
    shared: Arc<SharedState>,
    notifier: Arc<dyn HostParamsEditNotifier>,
    /// Host content scale, reported before set_parent. Density is fixed at
    /// attach time; later scale changes are logged and ignored.
    scale: Mutex<f64>,
    /// Scale pinned at the first get_size of an editor open, so the size
    /// the host laid out and the window we attach can never disagree.
    chosen_scale: Mutex<Option<f64>>,
    runtime: Mutex<Option<MainCell<Runtime>>>,
    view_size: Mutex<Option<(u32, u32)>>,
}

struct Runtime {
    hwnd: HWND,
    thread_id: u32,
}

/// Native ownership is outside the panel borrow, so reentrant focus/capture
/// loss can always unhide the cursor and defer the logical cancellation.
struct WindowState {
    state: Rc<RefCell<ViewState>>,
    pointer: PointerLock,
    delivery: Rc<GestureDelivery>,
    /// A key is on its way to the host window: don't take it back.
    forwarding_host_key: Cell<bool>,
}

fn window_of(hwnd: HWND) -> Option<&'static WindowState> {
    let ptr = unsafe { GetWindowLongPtrW(hwnd, GWLP_USERDATA) } as *const WindowState;
    unsafe { ptr.as_ref() }
}

fn state_of(hwnd: HWND) -> Option<&'static RefCell<ViewState>> {
    window_of(hwnd).map(|window| window.state.as_ref())
}

/// Runs an input handler and delivers its edits outside the state borrow.
fn dispatch(hwnd: HWND, f: impl FnOnce(&mut ViewState) -> Vec<Edit>) {
    dispatch_pointer(hwnd, false, f);
}

/// As `dispatch`, keeping the pointer lock in step with the gesture:
/// released (warping to the drag's anchor when `warp_on_release`) before the
/// edits reach the host, taken after.
fn dispatch_pointer(hwnd: HWND, warp_on_release: bool, f: impl FnOnce(&mut ViewState) -> Vec<Edit>) {
    let Some(window) = window_of(hwnd) else { return };
    let delivery = window.delivery.clone();
    let panel_state = window.state.clone();
    if delivery.is_active() {
        return;
    }
    let result = catch_unwind(AssertUnwindSafe(|| {
        let (edits, shared, notifier, release, anchor) = {
            let Ok(mut state) = window.state.try_borrow_mut() else { return };
            if state.dead {
                return;
            }
            let capture = state.fittings.capture();
            let canceled = delivery.take_cancel();
            let mut edits = canceled.map_or_else(Vec::new, |rollback| state.clear_editing(rollback));
            let revision = state.restore_revision;
            edits.extend(state.refresh());
            // A restore or cancellation invalidates the gesture's input.
            let restored = canceled.is_some() || revision != state.restore_revision;
            if !restored {
                edits.extend(f(&mut state));
            }
            let release = window.pointer.releases(capture, state.fittings.capture(), restored);
            let anchor = if release && warp_on_release && !restored {
                capture.and_then(|capture| capture.release_position(&state.panel))
            } else {
                None
            };
            (edits, state.shared.clone(), state.notifier.clone(), release, anchor)
        };
        if release {
            window.pointer.release(hwnd, anchor, (WIDTH, HEIGHT));
        }
        delivery.deliver(
            edits,
            |edits| apply(edits, &shared, &*notifier),
            |rollback| panel_state.borrow_mut().clear_editing(rollback),
        );
        // The host may have ended the drag, or destroyed the editor, from a
        // callback: look the window up again and lock only for what is
        // still captured.
        let capture = state_of(hwnd)
            .and_then(|cell| cell.try_borrow().ok())
            .and_then(|state| (!state.dead).then(|| state.fittings.capture()).flatten());
        if let Some(window) = window_of(hwnd) {
            window.pointer.hold(hwnd, capture);
        }
    }));
    if result.is_err() {
        log::error!("OpenPitchQuant input callback panicked");
        cancel(hwnd);
    }
}

/// Ends any gesture, committing what it did (Escape rolls back).
fn cancel(hwnd: HWND) {
    let Some(window) = window_of(hwnd) else { return };
    let delivery = window.delivery.clone();
    let panel_state = window.state.clone();
    delivery.request_cancel();
    // The cursor comes back where it is; a cancelled drag has no anchor.
    window.pointer.unlock(hwnd, None, (WIDTH, HEIGHT));
    if delivery.is_active() {
        release_capture(hwnd);
        return;
    }
    let _ = catch_unwind(AssertUnwindSafe(|| {
        let payload = window.state.try_borrow_mut().ok().map(|mut st| {
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
    // Also release if the cancellation panicked or its borrow was unavailable.
    release_capture(hwnd);
}

/// Signed client coordinates from a mouse message's lParam: signed because
/// a captured drag runs past the client edge.
fn client_xy(lparam: LPARAM) -> (i32, i32) {
    ((lparam & 0xffff) as u16 as i16 as i32, ((lparam >> 16) & 0xffff) as u16 as i16 as i32)
}

fn modifiers() -> Modifiers {
    Modifiers {
        shift: unsafe { GetKeyState(VK_SHIFT as i32) } < 0,
        command: unsafe { GetKeyState(VK_CONTROL as i32) } < 0,
        alt: unsafe { GetKeyState(VK_MENU as i32) } < 0,
    }
}

fn system_key_down() -> bool {
    (unsafe { GetKeyState(VK_LWIN as i32) } < 0) || (unsafe { GetKeyState(VK_RWIN as i32) } < 0)
}

/// The panel's one key, as the Cocoa mount maps it: Escape, never with
/// Command.
fn panel_key(vk: u16, character: u16, mods: Modifiers) -> Option<&'static str> {
    if mods.command {
        return None;
    }
    match (vk, character) {
        (0x1b, _) | (_, 0x1b) => Some("Escape"),
        _ => None,
    }
}

/// SDK KeyModifier bits from the VST3 key bridge: shift 1, alternate 2,
/// command 4. Control (8) on Windows is a host combination: decline it.
fn callback_modifiers(bits: u16) -> Option<Modifiers> {
    (bits & !7 == 0).then_some(Modifiers { shift: bits & 1 != 0, alt: bits & 2 != 0, command: bits & 4 != 0 })
}

// This HWND opts into the shared VST3 wrapper's focused-editor key protocol
// (open-wrac's clap-wrapper detail/vst3/win32-keyboard.h), whose names are
// the plugin id (CLAP_WRAPPER_KEY_PROTOCOL) plus a suffix.
const KEY_TARGET: *const u16 = windows_sys::w!("org.open-pitch-quant.opq.vst3-key-target.v1");
fn key_message() -> u32 {
    static MESSAGE: LazyLock<u32> =
        LazyLock::new(|| unsafe { RegisterWindowMessageW(windows_sys::w!("org.open-pitch-quant.opq.vst3-key.v1")) });
    *MESSAGE
}

/// Delivers a panel key; false when the key is not the panel's.
fn dispatch_key(hwnd: HWND, vk: u16, character: u16, mods: Modifiers) -> bool {
    let Some(key) = panel_key(vk, character, mods) else { return false };
    if key == "Escape" && window_of(hwnd).is_some_and(|window| window.delivery.is_active()) {
        if let Some(window) = window_of(hwnd) {
            window.delivery.request_rollback();
        }
        cancel(hwnd);
        return true;
    }
    dispatch(hwnd, |st| st.fittings.key(&mut st.panel, key, mods));
    true
}

/// Hands a key the panel does not use back to the host's window.
fn forward_host_key(hwnd: HWND, msg: u32, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
    let Some(window) = window_of(hwnd) else {
        return unsafe { DefWindowProcW(hwnd, msg, wparam, lparam) };
    };
    if window.forwarding_host_key.replace(true) {
        return unsafe { DefWindowProcW(hwnd, msg, wparam, lparam) };
    }
    let result = unsafe { SendMessageW(GetParent(hwnd), msg, wparam, lparam) };
    // Sending to a host can reenter its callbacks or destroy the editor.
    if let Some(window) = window_of(hwnd) {
        window.forwarding_host_key.set(false);
    }
    result
}

fn hover(hwnd: HWND, at: Option<(f32, f32)>, mods: Modifiers) {
    if let Some(cell) = state_of(hwnd) {
        if let Ok(mut state) = cell.try_borrow_mut() {
            let st = &mut *state;
            let (x, y) = match at {
                Some(at) => at,
                None => st.pointer,
            };
            if st.fittings.capture().is_none() {
                st.pointer = (x, y);
            }
            st.fittings.hover_with_modifiers(&mut st.panel, x, y, mods);
        }
    }
}

fn tick(hwnd: HWND) {
    if unsafe { IsWindowVisible(hwnd) } == 0 {
        cancel(hwnd);
        return;
    }
    // Refreshing can close gestures (a restore): deliver outside the render borrow.
    dispatch(hwnd, |_| Vec::new());
    let Some(cell) = state_of(hwnd) else { return };
    let result = catch_unwind(AssertUnwindSafe(|| -> Result<(), String> {
        let Ok(mut state) = cell.try_borrow_mut() else { return Ok(()) };
        if state.dead {
            return Ok(());
        }
        let Some(size) = mount::drawable_size(hwnd, 8192) else { return Ok(()) };
        // A size change replaces the board and surface together.
        if state.scene.as_ref().is_some_and(|scene| scene.size != size) {
            state.scene = None;
        }
        if state.scene.is_none() {
            let raw = NonZeroIsize::new(hwnd as isize).ok_or("window handle is null")?;
            state.scene = Some(Scene::new(ViewWindowHandle::from_hwnd(raw), size)?);
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
    cancel(hwnd);
    if let Some(cell) = state_of(hwnd) {
        if let Ok(mut state) = cell.try_borrow_mut() {
            state.dead = true;
            state.scene = None;
        }
    }
}

unsafe extern "system" fn wndproc(hwnd: HWND, msg: u32, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
    if msg != 0 && msg == key_message() {
        let ready = unsafe { GetFocus() } == hwnd
            && window_of(hwnd).is_some_and(|window| {
                !window.forwarding_host_key.get() && window.state.try_borrow().is_ok_and(|st| !st.dead)
            });
        // The panel has no release actions: decline key-up rather than claim
        // a host release it did not handle.
        if !ready || lparam & (1 << 16) != 0 {
            return 0;
        }
        let Some(mods) = callback_modifiers(lparam as u16) else { return 0 };
        return dispatch_key(hwnd, wparam as u16, (wparam >> 16) as u16, mods) as LRESULT;
    }
    match msg {
        WM_NCCREATE => {
            let cs = lparam as *const CREATESTRUCTW;
            let state = unsafe { (*cs).lpCreateParams };
            unsafe { SetWindowLongPtrW(hwnd, GWLP_USERDATA, state as isize) };
            unsafe { SetPropW(hwnd, KEY_TARGET, 1usize as *mut c_void) };
            unsafe { DefWindowProcW(hwnd, msg, wparam, lparam) }
        }
        WM_DESTROY => {
            cancel(hwnd);
            unsafe { DefWindowProcW(hwnd, msg, wparam, lparam) }
        }
        WM_NCDESTROY => {
            unsafe { RemovePropW(hwnd, KEY_TARGET) };
            unsafe { KillTimer(hwnd, TIMER_ID) };
            let ptr = unsafe { SetWindowLongPtrW(hwnd, GWLP_USERDATA, 0) } as *mut WindowState;
            if !ptr.is_null() {
                // The surface inside dies here, while its window still lives.
                drop(unsafe { Box::from_raw(ptr) });
            }
            unsafe { DefWindowProcW(hwnd, msg, wparam, lparam) }
        }
        WM_TIMER if wparam == TIMER_ID => {
            tick(hwnd);
            0
        }
        // wgpu covers the whole client area every beat; skipping the erase
        // avoids a per-frame background flash.
        WM_ERASEBKGND => 1,
        WM_SETCURSOR if wparam as HWND == hwnd && lparam as u16 == HTCLIENT as u16 => {
            let mut point = POINT { x: 0, y: 0 };
            if unsafe { IsWindowVisible(hwnd) } != 0
                && unsafe { GetCursorPos(&mut point) } != 0
                && unsafe { WindowFromPoint(point) } == hwnd
            {
                // DefWindowProc asks the parent first, which can leave a
                // host's resize or text cursor over the editor.
                unsafe { SetCursor(LoadCursorW(std::ptr::null_mut(), IDC_ARROW)) };
                1
            } else {
                unsafe { DefWindowProcW(hwnd, msg, wparam, lparam) }
            }
        }
        WM_LBUTTONDOWN | WM_LBUTTONDBLCLK => {
            unsafe { SetFocus(hwnd) };
            let (cx, cy) = client_xy(lparam);
            let at = mount::logical_point(hwnd, cx, cy, (WIDTH, HEIGHT));
            let mods = modifiers();
            let clicks = if msg == WM_LBUTTONDBLCLK { 2 } else { 1 };
            dispatch(hwnd, |st| {
                let Some((x, y)) = at else { return Vec::new() };
                st.pointer = (x, y);
                st.fittings.down(&mut st.panel, x, y, mods, clicks)
            });
            0
        }
        WM_MOUSEMOVE => {
            let (cx, cy) = client_xy(lparam);
            let at = mount::logical_point(hwnd, cx, cy, (WIDTH, HEIGHT));
            if unsafe { GetCapture() } == hwnd {
                let mods = modifiers();
                let locked = window_of(hwnd).is_some_and(|window| window.pointer.is_locked());
                let delta = window_of(hwnd).and_then(|window| window.pointer.delta(hwnd, (WIDTH, HEIGHT)));
                dispatch(hwnd, |st| {
                    match (locked, delta, at) {
                        // A relative drag: the step moves the editor's own pointer.
                        (true, Some((dx, dy)), _) => {
                            st.pointer.0 += dx;
                            st.pointer.1 += dy;
                        }
                        (false, _, Some((x, y))) => st.pointer = (x, y),
                        _ => return Vec::new(),
                    }
                    let (x, y) = st.pointer;
                    st.fittings.drag(&mut st.panel, x, y, mods)
                });
                // Native reanchoring never runs under the panel borrow.
                if let Some(window) = window_of(hwnd) {
                    window.pointer.recentre();
                }
            } else {
                // Hover is free on Win32 but leaving is not: ask for the one
                // WM_MOUSELEAVE that tells a raised hover the pointer is gone.
                let mut track = TRACKMOUSEEVENT {
                    cbSize: std::mem::size_of::<TRACKMOUSEEVENT>() as u32,
                    dwFlags: TME_LEAVE,
                    hwndTrack: hwnd,
                    dwHoverTime: 0,
                };
                unsafe { TrackMouseEvent(&mut track) };
                if at.is_some() {
                    hover(hwnd, at, modifiers());
                }
            }
            0
        }
        WM_MOUSELEAVE => {
            // Off every fitting, as Cocoa's mouseExited.
            if let Some(cell) = state_of(hwnd) {
                if let Ok(mut state) = cell.try_borrow_mut() {
                    let st = &mut *state;
                    if st.fittings.capture().is_none() {
                        st.pointer = (-1.0, -1.0);
                    }
                    st.fittings.hover(&mut st.panel, -1.0, -1.0);
                }
            }
            0
        }
        WM_LBUTTONUP => {
            if window_of(hwnd).is_some_and(|window| window.delivery.is_active()) {
                cancel(hwnd);
                return 0;
            }
            if unsafe { GetCapture() } == hwnd {
                let mods = modifiers();
                if window_of(hwnd).is_some_and(|window| window.pointer.is_locked()) {
                    let delta = window_of(hwnd).and_then(|window| window.pointer.delta(hwnd, (WIDTH, HEIGHT)));
                    dispatch_pointer(hwnd, true, |st| {
                        let mut edits = Vec::new();
                        if let Some((dx, dy)) = delta {
                            st.pointer.0 += dx;
                            st.pointer.1 += dy;
                            edits.extend(st.fittings.drag(&mut st.panel, st.pointer.0, st.pointer.1, mods));
                        }
                        edits.extend(st.fittings.up(&mut st.panel));
                        edits
                    });
                } else {
                    // Commit the release position, as the Cocoa mount does.
                    let (cx, cy) = client_xy(lparam);
                    let at = mount::logical_point(hwnd, cx, cy, (WIDTH, HEIGHT));
                    dispatch(hwnd, |st| match at {
                        Some((x, y)) => {
                            st.pointer = (x, y);
                            let mut edits = st.fittings.drag(&mut st.panel, x, y, mods);
                            edits.extend(st.fittings.up(&mut st.panel));
                            edits
                        }
                        None => st.fittings.cancel(&mut st.panel),
                    });
                }
                release_capture(hwnd);
            }
            0
        }
        // Capture torn away mid-gesture (a host menu, a window drag): the
        // Cocoa mount's windowDidResignKey.
        WM_CAPTURECHANGED => {
            if lparam != hwnd as isize
                && window_of(hwnd).is_some_and(|window| {
                    window.pointer.is_locked()
                        || window.state.try_borrow().map_or(true, |state| state.fittings.capture().is_some())
                })
            {
                cancel(hwnd);
            }
            0
        }
        WM_MOUSEWHEEL => {
            // The wheel's lParam is in screen coordinates, alone among the
            // mouse messages.
            let (sx, sy) = client_xy(lparam);
            let mut point = POINT { x: sx, y: sy };
            unsafe { ScreenToClient(hwnd, &mut point) };
            let at = mount::logical_point(hwnd, point.x, point.y, (WIDTH, HEIGHT));
            // Wheel up raises the value, as on the Mac.
            let delta = mount::scroll_notches(((wparam >> 16) & 0xffff) as u16 as i16);
            let mods = modifiers();
            dispatch(hwnd, |st| {
                let Some((x, y)) = at else { return Vec::new() };
                if st.fittings.capture().is_none() {
                    st.pointer = (x, y);
                }
                st.fittings.scroll(&mut st.panel, x, y, delta, mods)
            });
            0
        }
        WM_KILLFOCUS | WM_CANCELMODE => {
            cancel(hwnd);
            0
        }
        WM_KEYUP => {
            hover(hwnd, None, modifiers());
            forward_host_key(hwnd, msg, wparam, lparam)
        }
        WM_KEYDOWN => {
            let mods = modifiers();
            hover(hwnd, None, mods);
            if !system_key_down() && dispatch_key(hwnd, wparam as u16, 0, mods) {
                return 0;
            }
            forward_host_key(hwnd, msg, wparam, lparam)
        }
        WM_CHAR => {
            // Control characters follow key-downs handled above (Escape):
            // never dispatch them twice. Text goes to the host.
            if wparam >= 0x20 && wparam != 0x7f {
                return forward_host_key(hwnd, msg, wparam, lparam);
            }
            0
        }
        _ => unsafe { DefWindowProcW(hwnd, msg, wparam, lparam) },
    }
}

/// Registers the panel's window class once per process and returns its name.
fn panel_class() -> *const u16 {
    const CLASS_NAME: *const u16 = windows_sys::w!("OpenPitchQuantPanelWindow");
    static REGISTER: Once = Once::new();
    REGISTER.call_once(|| unsafe {
        let wc = WNDCLASSW {
            style: CS_DBLCLKS,
            lpfnWndProc: Some(wndproc),
            cbClsExtra: 0,
            cbWndExtra: 0,
            hInstance: GetModuleHandleW(std::ptr::null()),
            hIcon: std::ptr::null_mut(),
            hCursor: LoadCursorW(std::ptr::null_mut(), IDC_ARROW),
            hbrBackground: std::ptr::null_mut(),
            lpszMenuName: std::ptr::null(),
            lpszClassName: CLASS_NAME,
        };
        if RegisterClassW(&wc) == 0 {
            log::error!("OpenPitchQuant panel: RegisterClassW failed");
        }
    });
    CLASS_NAME
}

impl PanelGui {
    pub(crate) fn new(shared: Arc<SharedState>, notifier: Arc<dyn HostParamsEditNotifier>) -> Self {
        Self {
            shared,
            notifier,
            scale: Mutex::new(1.0),
            chosen_scale: Mutex::new(None),
            runtime: Mutex::new(None),
            view_size: Mutex::new(None),
        }
    }

    pub(crate) fn cancel_gestures(&self) {
        if let Some(hwnd) = self.window_here() {
            cancel(hwnd);
        }
    }

    /// The editor window, when this is its thread. The lock is released
    /// before the caller acts: a host callback during a cancellation may
    /// call back into the GUI extension.
    fn window_here(&self) -> Option<HWND> {
        let runtime = self.runtime();
        let MainCell(rt) = runtime.as_ref()?;
        (unsafe { GetCurrentThreadId() } == rt.thread_id).then_some(rt.hwnd)
    }

    fn runtime(&self) -> MutexGuard<'_, Option<MainCell<Runtime>>> {
        self.runtime.lock().unwrap_or_else(|e| e.into_inner())
    }

    fn chosen_scale(&self) -> f64 {
        let mut chosen = self.chosen_scale.lock().unwrap_or_else(|e| e.into_inner());
        *chosen.get_or_insert_with(|| {
            // A DPI-unaware host sees a virtualized 96 here and DWM stretches
            // its whole window instead, so 1x is right for it.
            let dpi_scale = unsafe { GetDpiForSystem() } as f64 / 96.0;
            self.scale.lock().unwrap_or_else(|e| e.into_inner()).max(dpi_scale).clamp(1.0, MAX_SCALE)
        })
    }

    /// The editor's physical size at the pinned scale: logical panel pixels
    /// scaled fractionally, so the window sits in the host's layout at the
    /// host's own idea of 100%.
    fn scaled_size(&self) -> (u32, u32) {
        if let Some(size) = *self.view_size.lock().unwrap_or_else(|e| e.into_inner()) {
            return size;
        }
        let s = self.chosen_scale();
        ((WIDTH as f64 * s).round() as u32, (HEIGHT as f64 * s).round() as u32)
    }

    fn teardown(&self) {
        let runtime = self.runtime().take();
        if let Some(MainCell(rt)) = runtime {
            if unsafe { GetCurrentThreadId() } == rt.thread_id {
                // Close any open gesture with the host first; WM_NCDESTROY
                // then kills the timer, the surface and the state together.
                cancel(rt.hwnd);
                unsafe { DestroyWindow(rt.hwnd) };
            } else {
                // A window is affine to its creating thread: leak rather than
                // destroy it from another one.
                log::warn!("OpenPitchQuant GUI destroyed off the GUI thread; leaking the window");
            }
        }
    }
}

impl Drop for PanelGui {
    fn drop(&mut self) {
        self.teardown();
    }
}

impl PluginGuiExtension for PanelGui {
    fn is_api_supported(&self, api: GuiApi, is_floating: bool) -> bool {
        api == GuiApi::Win32 && !is_floating
    }
    fn preferred_api(&self) -> Option<GuiConfig> {
        Some(GuiConfig { api: GuiApi::Win32, is_floating: false })
    }
    fn create(&self, config: GuiConfig) -> PluginResult<()> {
        if !self.is_api_supported(config.api, config.is_floating) {
            return Err(PluginError::InvalidState);
        }
        // Each editor open re-derives its scale: the window may land on a
        // different monitor this time.
        *self.chosen_scale.lock().unwrap_or_else(|e| e.into_inner()) = None;
        Ok(())
    }
    fn destroy(&self) {
        self.teardown();
    }
    fn set_scale(&self, scale: f64) -> PluginResult<()> {
        if !(scale.is_finite() && scale > 0.0) {
            return Err(PluginError::InvalidState);
        }
        *self.scale.lock().unwrap_or_else(|e| e.into_inner()) = scale;
        if self.runtime().is_some() {
            log::debug!("OpenPitchQuant set_scale {scale} after attach ignored (density fixed)");
        }
        Ok(())
    }
    fn get_size(&self) -> PluginResult<GuiSize> {
        let (width, height) = self.scaled_size();
        Ok(GuiSize { width, height })
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
        let scale = (size.width as f64 / WIDTH as f64).min(size.height as f64 / HEIGHT as f64).clamp(0.7, MAX_SCALE);
        Ok(GuiSize { width: (WIDTH as f64 * scale).round() as u32, height: (HEIGHT as f64 * scale).round() as u32 })
    }
    fn set_size(&self, size: GuiSize) -> PluginResult<()> {
        let want = self.adjust_size(size)?;
        if size.width != want.width || size.height != want.height {
            return Err(PluginError::InvalidState);
        }
        let attached = self.runtime().as_ref().map(|MainCell(rt)| rt.thread_id);
        if let Some(thread_id) = attached {
            if unsafe { GetCurrentThreadId() } != thread_id {
                return Err(PluginError::InvalidState);
            }
            let hwnd = self.window_here().ok_or(PluginError::InvalidState)?;
            cancel(hwnd);
            let moved = unsafe {
                SetWindowPos(
                    hwnd,
                    std::ptr::null_mut(),
                    0,
                    0,
                    size.width as i32,
                    size.height as i32,
                    SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE,
                )
            };
            if moved == 0 {
                return Err(PluginError::InvalidState);
            }
        }
        *self.view_size.lock().unwrap_or_else(|e| e.into_inner()) = Some((size.width, size.height));
        Ok(())
    }
    fn set_parent(&self, window: HostWindow) -> PluginResult<()> {
        let HostWindow::Win32 { hwnd } = window else {
            return Err(PluginError::InvalidState);
        };
        self.teardown();
        let (width, height) = self.scaled_size();
        let state = Box::new(WindowState {
            state: Rc::new(RefCell::new(ViewState::new(self.shared.clone(), self.notifier.clone()))),
            pointer: PointerLock::new(),
            delivery: Rc::new(GestureDelivery::default()),
            forwarding_host_key: Cell::new(false),
        });
        // The host guarantees the parent outlives this attachment.
        let child = unsafe {
            CreateWindowExW(
                0,
                panel_class(),
                std::ptr::null(),
                WS_CHILD | WS_VISIBLE,
                0,
                0,
                width as i32,
                height as i32,
                hwnd.get() as HWND,
                std::ptr::null_mut(),
                GetModuleHandleW(std::ptr::null()),
                Box::into_raw(state) as *const c_void,
            )
        };
        if child.is_null() {
            return Err(PluginError::InvalidState);
        }
        unsafe { SetTimer(child, TIMER_ID, TICK_MS, None) };
        // Build the scene and put up the first frame now rather than a black
        // flash at t+33 ms.
        tick(child);
        *self.runtime() = Some(MainCell(Runtime { hwnd: child, thread_id: unsafe { GetCurrentThreadId() } }));
        Ok(())
    }
    fn show(&self) -> PluginResult<()> {
        let hwnd = self.window_here().ok_or(PluginError::InvalidState)?;
        unsafe { ShowWindow(hwnd, SW_SHOW) };
        Ok(())
    }
    fn hide(&self) -> PluginResult<()> {
        let hwnd = self.window_here().ok_or(PluginError::InvalidState)?;
        cancel(hwnd);
        unsafe { ShowWindow(hwnd, SW_HIDE) };
        Ok(())
    }
}
