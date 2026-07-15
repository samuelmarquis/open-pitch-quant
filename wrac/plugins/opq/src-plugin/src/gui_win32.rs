//! The panel's Windows mount: a child HWND embedded in the host's editor
//! window, repainted by a 30 Hz WM_TIMER. Fittings are the dialogue: drags
//! and throws go to the host as begin/perform/end parameter gestures and to
//! the engine immediately.
//!
//! Fixed-pixel decree: the 1280x720 plate is expanded by an INTEGER factor
//! and blitted with SetDIBitsToDevice at that exact density. GDI never
//! interpolates. Windows child windows live in physical pixels, so the
//! factor comes from the desktop DPI (200% -> 2x), with the host's
//! set_scale as a floor for hosts that report it. Rounded to the nearest
//! integer and pinned for the life of the editor: a 150% desktop gets the
//! 2x plate (big, crunchy) rather than a smeared fractional one.

use std::cell::RefCell;
use std::ffi::c_void;
use std::sync::{Arc, Mutex, Once};

use windows_sys::Win32::Foundation::{HWND, LPARAM, LRESULT, WPARAM};
use windows_sys::Win32::Graphics::Gdi::{
    BI_RGB, BITMAPINFO, BITMAPINFOHEADER, BeginPaint, DIB_RGB_COLORS, EndPaint, InvalidateRect,
    PAINTSTRUCT, SetDIBitsToDevice,
};
use windows_sys::Win32::System::LibraryLoader::GetModuleHandleW;
use windows_sys::Win32::System::Threading::GetCurrentThreadId;
use windows_sys::Win32::UI::HiDpi::GetDpiForSystem;
use windows_sys::Win32::UI::Input::KeyboardAndMouse::{ReleaseCapture, SetCapture};
use windows_sys::Win32::UI::WindowsAndMessaging::{
    CREATESTRUCTW, CreateWindowExW, DefWindowProcW, DestroyWindow, GWLP_USERDATA,
    GetWindowLongPtrW, IDC_ARROW, KillTimer, LoadCursorW, RegisterClassW, SW_HIDE, SW_SHOW,
    SetTimer,
    SetWindowLongPtrW, ShowWindow, WM_ERASEBKGND, WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MOUSEMOVE,
    WM_NCCREATE, WM_NCDESTROY, WM_PAINT, WM_TIMER, WNDCLASSW, WS_CHILD, WS_VISIBLE,
};
use wrac_clap_adapter::{
    GuiApi, GuiConfig, GuiResizeHints, GuiSize, HostParamsEditNotifier, HostWindow, PluginError,
    PluginGuiExtension, PluginResult,
};

use crate::board::{BOARD_H, BOARD_W, Board, Edit, MouseEv, MouseKind};
use crate::state::SharedState;

const TICK_MS: u32 = 33; // ~30 Hz
const TIMER_ID: usize = 1;
const MAX_INTEGER_SCALE: u32 = 4;

/// Holds the GUI-thread-only HWND inside a `Send + Sync` controller. Access
/// and drop are guarded by a creation-thread-id check; `PanelGui` leaks the
/// window rather than destroying it cross-thread (a host misbehaving beats
/// a crash — DestroyWindow only works from the creating thread).
struct MainCell<T>(T);
unsafe impl<T> Send for MainCell<T> {}
unsafe impl<T> Sync for MainCell<T> {}

struct Runtime {
    hwnd: HWND,
    thread_id: u32,
}

pub(crate) struct PanelGui {
    shared: Arc<SharedState>,
    notifier: Arc<dyn HostParamsEditNotifier>,
    /// Host content scale, reported before set_parent. Density is fixed at
    /// attach time; later scale changes are logged and ignored (v1).
    scale: Mutex<f64>,
    /// Density pinned at the first get_size of an editor open, so the size
    /// the host laid out and the window we attach can never disagree.
    chosen_k: Mutex<Option<u32>>,
    runtime: Mutex<Option<MainCell<Runtime>>>,
}

/// GUI-thread state owned by the window (via GWLP_USERDATA): the wndproc is
/// the sole owner; the box is dropped in WM_NCDESTROY.
struct PanelShared {
    board: Board,
    shared: Arc<SharedState>,
    notifier: Arc<dyn HostParamsEditNotifier>,
    scratch: Vec<opq_engine::VizFrame>,
    /// The k-expanded plate in DIB order (BGRA, top-down), kw * kh * 4.
    plate: Vec<u8>,
    k: u32,
    dragging: bool,
    dirty: bool,
}

impl PanelShared {
    fn params(&self) -> [f32; 18] {
        std::array::from_fn(|i| self.shared.parameter_value(i as u32).unwrap_or(0.0))
    }

    fn apply_edits(&mut self, edits: Vec<Edit>) {
        for e in edits {
            match e {
                Edit::Begin(id) => self.notifier.begin_edit(id),
                Edit::Value(id, v) => {
                    if let Some(applied) = self.shared.set_parameter_value(id, v as f64) {
                        self.notifier.update_edit(id, applied as f64);
                    }
                    self.dirty = true;
                }
                Edit::End(id) => self.notifier.end_edit(id),
            }
        }
    }

    fn mouse(&mut self, lparam: LPARAM, kind: MouseKind) {
        // Client coordinates are physical pixels; the board speaks plate
        // pixels, so divide out the integer density.
        let x = (lparam & 0xffff) as u16 as i16 as i32;
        let y = ((lparam >> 16) & 0xffff) as u16 as i16 as i32;
        let ev = MouseEv {
            x: x / self.k as i32,
            y: y / self.k as i32,
            kind,
        };
        let params = self.params();
        let edits = self.board.on_mouse(ev, &params);
        self.apply_edits(edits);
    }
}

impl PanelGui {
    pub(crate) fn new(shared: Arc<SharedState>, notifier: Arc<dyn HostParamsEditNotifier>) -> Self {
        Self {
            shared,
            notifier,
            scale: Mutex::new(1.0),
            chosen_k: Mutex::new(None),
            runtime: Mutex::new(None),
        }
    }

    fn k(&self) -> u32 {
        let mut chosen = self.chosen_k.lock().unwrap();
        *chosen.get_or_insert_with(|| {
            // A DPI-unaware host sees a virtualized 96 here and DWM stretches
            // its whole window instead, so 1x is the right answer for it.
            let dpi_scale = unsafe { GetDpiForSystem() } as f64 / 96.0;
            let scale = self.scale.lock().unwrap().max(dpi_scale);
            (scale.round() as u32).clamp(1, MAX_INTEGER_SCALE)
        })
    }

    fn teardown(&self) {
        if let Some(MainCell(rt)) = self.runtime.lock().unwrap().take() {
            if unsafe { GetCurrentThreadId() } == rt.thread_id {
                // WM_NCDESTROY kills the timer and frees the panel state.
                unsafe { DestroyWindow(rt.hwnd) };
            } else {
                log::warn!("panel: released off the GUI thread; leaking the window");
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
        Some(GuiConfig {
            api: GuiApi::Win32,
            is_floating: false,
        })
    }

    fn create(&self, configuration: GuiConfig) -> PluginResult<()> {
        if configuration.api != GuiApi::Win32 || configuration.is_floating {
            return Err(PluginError::Message("unsupported GUI configuration"));
        }
        // Each editor open re-derives density (the window may land on a
        // different monitor this time).
        *self.chosen_k.lock().unwrap() = None;
        Ok(())
    }

    fn destroy(&self) {
        self.teardown();
    }

    fn set_scale(&self, scale: f64) -> PluginResult<()> {
        *self.scale.lock().unwrap() = scale;
        if self.runtime.lock().unwrap().is_some() {
            log::debug!("panel: set_scale {scale} after attach ignored (density fixed at attach)");
        }
        Ok(())
    }

    fn get_size(&self) -> PluginResult<GuiSize> {
        let k = self.k();
        Ok(GuiSize {
            width: BOARD_W as u32 * k,
            height: BOARD_H as u32 * k,
        })
    }

    fn can_resize(&self) -> bool {
        false
    }

    fn resize_hints(&self) -> Option<GuiResizeHints> {
        None
    }

    fn adjust_size(&self, _size: GuiSize) -> PluginResult<GuiSize> {
        self.get_size()
    }

    fn set_size(&self, size: GuiSize) -> PluginResult<()> {
        let want = self.get_size()?;
        if size.width != want.width || size.height != want.height {
            log::debug!(
                "panel: host set_size {}x{} ignored (fixed {}x{})",
                size.width,
                size.height,
                want.width,
                want.height
            );
        }
        Ok(())
    }

    fn set_parent(&self, window: HostWindow) -> PluginResult<()> {
        let HostWindow::Win32 { hwnd } = window else {
            return Err(PluginError::Message("expected a Win32 parent"));
        };
        self.teardown();

        let k = self.k();
        let (kw, kh) = (BOARD_W as u32 * k, BOARD_H as u32 * k);
        let state = Box::new(RefCell::new(PanelShared {
            board: Board::new(),
            shared: self.shared.clone(),
            notifier: self.notifier.clone(),
            scratch: Vec::with_capacity(64),
            plate: vec![0u8; kw as usize * kh as usize * 4],
            k,
            dragging: false,
            dirty: true,
        }));

        let class = panel_class();
        // The host guarantees the parent HWND outlives this attachment
        // (CLAP gui.set_parent contract; clap-wrapper upholds it for VST3).
        let child = unsafe {
            CreateWindowExW(
                0,
                class,
                std::ptr::null(),
                WS_CHILD | WS_VISIBLE,
                0,
                0,
                kw as i32,
                kh as i32,
                hwnd.get() as HWND,
                std::ptr::null_mut(),
                GetModuleHandleW(std::ptr::null()),
                Box::into_raw(state) as *const c_void,
            )
        };
        if child.is_null() {
            return Err(PluginError::Message("CreateWindowExW failed"));
        }

        unsafe {
            SetTimer(child, TIMER_ID, TICK_MS, None);
        }
        // Paint the first frame now rather than a black flash at t+33ms.
        tick(child);

        *self.runtime.lock().unwrap() = Some(MainCell(Runtime {
            hwnd: child,
            thread_id: unsafe { GetCurrentThreadId() },
        }));
        Ok(())
    }

    fn show(&self) -> PluginResult<()> {
        if let Some(MainCell(rt)) = self.runtime.lock().unwrap().as_ref() {
            unsafe { ShowWindow(rt.hwnd, SW_SHOW) };
        }
        Ok(())
    }

    fn hide(&self) -> PluginResult<()> {
        if let Some(MainCell(rt)) = self.runtime.lock().unwrap().as_ref() {
            unsafe { ShowWindow(rt.hwnd, SW_HIDE) };
        }
        Ok(())
    }
}

/// Register the panel's window class once per process and return its name.
fn panel_class() -> *const u16 {
    // NUL-terminated UTF-16 "OpqPanelWindow".
    static CLASS_NAME: [u16; 15] = [
        b'O' as u16,
        b'p' as u16,
        b'q' as u16,
        b'P' as u16,
        b'a' as u16,
        b'n' as u16,
        b'e' as u16,
        b'l' as u16,
        b'W' as u16,
        b'i' as u16,
        b'n' as u16,
        b'd' as u16,
        b'o' as u16,
        b'w' as u16,
        0,
    ];
    static REGISTER: Once = Once::new();
    REGISTER.call_once(|| unsafe {
        let wc = WNDCLASSW {
            style: 0,
            lpfnWndProc: Some(wndproc),
            cbClsExtra: 0,
            cbWndExtra: 0,
            hInstance: GetModuleHandleW(std::ptr::null()),
            hIcon: std::ptr::null_mut(),
            hCursor: LoadCursorW(std::ptr::null_mut(), IDC_ARROW),
            hbrBackground: std::ptr::null_mut(),
            lpszMenuName: std::ptr::null(),
            lpszClassName: CLASS_NAME.as_ptr(),
        };
        if RegisterClassW(&wc) == 0 {
            log::error!("panel: RegisterClassW failed");
        }
    });
    CLASS_NAME.as_ptr()
}

fn state_of(hwnd: HWND) -> Option<&'static RefCell<PanelShared>> {
    let ptr = unsafe { GetWindowLongPtrW(hwnd, GWLP_USERDATA) } as *const RefCell<PanelShared>;
    unsafe { ptr.as_ref() }
}

unsafe extern "system" fn wndproc(
    hwnd: HWND,
    msg: u32,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    match msg {
        WM_NCCREATE => {
            let cs = lparam as *const CREATESTRUCTW;
            let state = unsafe { (*cs).lpCreateParams };
            unsafe { SetWindowLongPtrW(hwnd, GWLP_USERDATA, state as isize) };
            unsafe { DefWindowProcW(hwnd, msg, wparam, lparam) }
        }
        WM_NCDESTROY => {
            unsafe { KillTimer(hwnd, TIMER_ID) };
            let ptr =
                unsafe { SetWindowLongPtrW(hwnd, GWLP_USERDATA, 0) } as *mut RefCell<PanelShared>;
            if !ptr.is_null() {
                drop(unsafe { Box::from_raw(ptr) });
            }
            unsafe { DefWindowProcW(hwnd, msg, wparam, lparam) }
        }
        WM_TIMER if wparam == TIMER_ID => {
            tick(hwnd);
            0
        }
        WM_PAINT => {
            paint(hwnd);
            0
        }
        // The plate covers the whole client area every paint; skipping the
        // background erase avoids a per-frame flicker.
        WM_ERASEBKGND => 1,
        WM_LBUTTONDOWN => {
            if let Some(state) = state_of(hwnd) {
                unsafe { SetCapture(hwnd) };
                let mut st = state.borrow_mut();
                st.dragging = true;
                st.mouse(lparam, MouseKind::Down);
            }
            0
        }
        WM_MOUSEMOVE => {
            if let Some(state) = state_of(hwnd) {
                let mut st = state.borrow_mut();
                if st.dragging {
                    st.mouse(lparam, MouseKind::Drag);
                }
            }
            0
        }
        WM_LBUTTONUP => {
            if let Some(state) = state_of(hwnd) {
                let mut st = state.borrow_mut();
                if st.dragging {
                    st.dragging = false;
                    drop(st);
                    unsafe { ReleaseCapture() };
                    if let Some(state) = state_of(hwnd) {
                        state.borrow_mut().mouse(lparam, MouseKind::Up);
                    }
                }
            }
            0
        }
        _ => unsafe { DefWindowProcW(hwnd, msg, wparam, lparam) },
    }
}

/// One 30 Hz beat: drain the analysis queue, run the board, expand the plate
/// at integer density into DIB order, and invalidate. The board repaints
/// every beat (its furniture animates) — the panel is alive.
fn tick(hwnd: HWND) {
    let Some(state) = state_of(hwnd) else { return };
    let mut st = state.borrow_mut();
    let st = &mut *st;

    st.scratch.clear();
    st.shared.drain_viz(&mut st.scratch);
    let params = st.params();
    let (sr, hop) = st.shared.engine_info();
    let frames = std::mem::take(&mut st.scratch);
    st.board.tick(&frames, &params, sr, hop);
    st.scratch = frames;
    st.scratch.clear();
    st.dirty = false;

    expand(&st.board.fb, &mut st.plate, st.k as usize);
    unsafe { InvalidateRect(hwnd, std::ptr::null(), 0) };
}

/// Expand the logical RGBA plate k x into the top-down BGRA DIB buffer.
fn expand(src: &[u8], plate: &mut [u8], k: usize) {
    let stride = BOARD_W * k * 4;
    for y in 0..BOARD_H {
        let s = &src[y * BOARD_W * 4..(y + 1) * BOARD_W * 4];
        let d0 = y * k * stride;
        {
            let row = &mut plate[d0..d0 + stride];
            for x in 0..BOARD_W {
                let px = [s[x * 4 + 2], s[x * 4 + 1], s[x * 4], 255];
                for r in 0..k {
                    row[(x * k + r) * 4..(x * k + r) * 4 + 4].copy_from_slice(&px);
                }
            }
        }
        for ky in 1..k {
            plate.copy_within(d0..d0 + stride, d0 + ky * stride);
        }
    }
}

fn paint(hwnd: HWND) {
    let Some(state) = state_of(hwnd) else { return };
    let st = state.borrow();
    let (kw, kh) = (BOARD_W as u32 * st.k, BOARD_H as u32 * st.k);

    let mut ps: PAINTSTRUCT = unsafe { std::mem::zeroed() };
    let hdc = unsafe { BeginPaint(hwnd, &mut ps) };
    if hdc.is_null() {
        return;
    }

    let mut bmi: BITMAPINFO = unsafe { std::mem::zeroed() };
    bmi.bmiHeader = BITMAPINFOHEADER {
        biSize: std::mem::size_of::<BITMAPINFOHEADER>() as u32,
        biWidth: kw as i32,
        // Negative height: rows run top-down, matching the plate buffer.
        biHeight: -(kh as i32),
        biPlanes: 1,
        biBitCount: 32,
        biCompression: BI_RGB as u32,
        biSizeImage: 0,
        biXPelsPerMeter: 0,
        biYPelsPerMeter: 0,
        biClrUsed: 0,
        biClrImportant: 0,
    };
    unsafe {
        SetDIBitsToDevice(
            hdc,
            0,
            0,
            kw,
            kh,
            0,
            0,
            0,
            kh,
            st.plate.as_ptr() as *const c_void,
            &bmi,
            DIB_RGB_COLORS,
        );
        EndPaint(hwnd, &ps);
    }
}
