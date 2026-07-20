//! The panel's mount: a custom layer-backed NSView (flipped, mouse-aware)
//! embedded in the host's editor window, repainted by a 30 Hz main-run-loop
//! timer. Fittings are the dialogue: drags and throws go to the host as
//! begin/perform/end parameter gestures and to the engine immediately.
//!
//! Fixed-pixel decree: the 1280x720 plate is expanded by an INTEGER factor
//! (the window's backing scale, rounded) and handed to the layer at that
//! exact density. Cocoa never interpolates.

use std::cell::RefCell;
use std::ptr::NonNull;
use std::rc::Rc;
use std::sync::Arc;
use std::sync::Mutex;

use block2::RcBlock;
use objc2::rc::Retained;
use objc2::runtime::AnyObject;
use objc2::{AllocAnyThread, DefinedClass, MainThreadMarker, MainThreadOnly, define_class, msg_send};
use objc2_app_kit::{
    NSAutoresizingMaskOptions, NSBitmapImageRep, NSDeviceRGBColorSpace, NSEvent, NSImage, NSView,
};
use objc2_core_foundation::{CGPoint, CGRect, CGSize};
use objc2_foundation::{NSRunLoop, NSRunLoopCommonModes, NSTimer, ns_string};
use wrac_clap_adapter::{
    GuiApi, GuiConfig, GuiResizeHints, GuiSize, HostParamsEditNotifier, HostWindow, PluginError,
    PluginGuiExtension, PluginResult,
};

use crate::board::{BOARD_H, BOARD_W, Board, Edit, MouseEv, MouseKind};
use crate::state::SharedState;

const TICK_SECONDS: f64 = 1.0 / 30.0;
const MAX_INTEGER_SCALE: u32 = 4;

/// Holds main-thread-only values inside a `Send + Sync` controller. Access
/// and drop require a [`MainThreadMarker`]; `PanelGui` leaks the contents
/// rather than dropping them off-main (a host misbehaving beats a crash).
struct MainCell<T>(T);
unsafe impl<T> Send for MainCell<T> {}
unsafe impl<T> Sync for MainCell<T> {}

struct Runtime {
    view: Retained<PanelView>,
    timer: Retained<NSTimer>,
}

pub(crate) struct PanelGui {
    shared: Arc<SharedState>,
    notifier: Arc<dyn HostParamsEditNotifier>,
    runtime: Mutex<Option<MainCell<Runtime>>>,
}

/// GUI-thread state shared by the view (mouse) and the timer (paint).
struct PanelShared {
    board: Board,
    shared: Arc<SharedState>,
    notifier: Arc<dyn HostParamsEditNotifier>,
    scratch: Vec<opq_engine::VizFrame>,
    row: Vec<u8>,
    last_k: u32,
    painted: bool,
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
}

struct PanelIvars {
    state: Rc<RefCell<PanelShared>>,
}

define_class!(
    #[unsafe(super(NSView))]
    #[thread_kind = MainThreadOnly]
    #[name = "OpqPanelView"]
    #[ivars = PanelIvars]
    struct PanelView;

    impl PanelView {
        #[unsafe(method(isFlipped))]
        fn is_flipped(&self) -> bool {
            true
        }

        #[unsafe(method(acceptsFirstMouse:))]
        fn accepts_first_mouse(&self, _event: Option<&NSEvent>) -> bool {
            true
        }

        #[unsafe(method(mouseDown:))]
        fn mouse_down(&self, event: &NSEvent) {
            self.mouse(event, MouseKind::Down);
        }

        #[unsafe(method(mouseDragged:))]
        fn mouse_dragged(&self, event: &NSEvent) {
            self.mouse(event, MouseKind::Drag);
        }

        #[unsafe(method(mouseUp:))]
        fn mouse_up(&self, event: &NSEvent) {
            self.mouse(event, MouseKind::Up);
        }
    }
);

impl PanelView {
    fn new(mtm: MainThreadMarker, state: Rc<RefCell<PanelShared>>, frame: CGRect) -> Retained<Self> {
        let this = Self::alloc(mtm).set_ivars(PanelIvars { state });
        unsafe { msg_send![super(this), initWithFrame: frame] }
    }

    fn mouse(&self, event: &NSEvent, kind: MouseKind) {
        let p = event.locationInWindow();
        let local = self.convertPoint_fromView(p, None);
        // Flipped view: local y already runs top-down in view points; the
        // view is BOARD_W x BOARD_H points, matching board pixels 1:1.
        let ev = MouseEv {
            x: local.x as i32,
            y: local.y as i32,
            kind,
        };
        let st = self.ivars().state.clone();
        let mut st = st.borrow_mut();
        let params = st.params();
        let edits = st.board.on_mouse(ev, &params);
        st.apply_edits(edits);
    }
}

impl PanelGui {
    pub(crate) fn new(shared: Arc<SharedState>, notifier: Arc<dyn HostParamsEditNotifier>) -> Self {
        Self {
            shared,
            notifier,
            runtime: Mutex::new(None),
        }
    }

    fn teardown(&self, _mtm: MainThreadMarker) {
        if let Some(MainCell(rt)) = self.runtime.lock().unwrap().take() {
            rt.timer.invalidate();
            rt.view.removeFromSuperview();
        }
    }

    fn drop_or_leak(&self) {
        match MainThreadMarker::new() {
            Some(mtm) => self.teardown(mtm),
            None => {
                if let Some(cell) = self.runtime.lock().unwrap().take() {
                    log::warn!("panel: released off the main thread; leaking the view");
                    std::mem::forget(cell);
                }
            }
        }
    }
}

impl Drop for PanelGui {
    fn drop(&mut self) {
        self.drop_or_leak();
    }
}

impl PluginGuiExtension for PanelGui {
    fn is_api_supported(&self, api: GuiApi, is_floating: bool) -> bool {
        api == GuiApi::Cocoa && !is_floating
    }

    fn preferred_api(&self) -> Option<GuiConfig> {
        Some(GuiConfig {
            api: GuiApi::Cocoa,
            is_floating: false,
        })
    }

    fn create(&self, configuration: GuiConfig) -> PluginResult<()> {
        if configuration.api != GuiApi::Cocoa || configuration.is_floating {
            return Err(PluginError::Message("unsupported GUI configuration"));
        }
        Ok(())
    }

    fn destroy(&self) {
        self.drop_or_leak();
    }

    fn set_scale(&self, _scale: f64) -> PluginResult<()> {
        // Density comes from the window's backing scale at paint time,
        // rounded to an integer. Host scale suggestions carry no extra truth.
        Ok(())
    }

    fn get_size(&self) -> PluginResult<GuiSize> {
        Ok(GuiSize {
            width: BOARD_W as u32,
            height: BOARD_H as u32,
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
        if size.width != BOARD_W as u32 || size.height != BOARD_H as u32 {
            log::debug!(
                "panel: host set_size {}x{} ignored (fixed {BOARD_W}x{BOARD_H})",
                size.width,
                size.height
            );
        }
        Ok(())
    }

    fn set_parent(&self, window: HostWindow) -> PluginResult<()> {
        let mtm = MainThreadMarker::new().ok_or(PluginError::InvalidState)?;
        let HostWindow::Cocoa { ns_view } = window else {
            return Err(PluginError::Message("expected a Cocoa parent"));
        };
        self.teardown(mtm);

        // The host guarantees the parent NSView outlives this attachment
        // (CLAP gui.set_parent contract; clap-wrapper upholds it for VST3/AU).
        let parent: &NSView = unsafe { &*(ns_view.get() as *const NSView) };

        let state = Rc::new(RefCell::new(PanelShared {
            board: Board::new(),
            shared: self.shared.clone(),
            notifier: self.notifier.clone(),
            scratch: Vec::with_capacity(64),
            row: vec![0u8; BOARD_W * MAX_INTEGER_SCALE as usize * 4],
            last_k: 0,
            painted: false,
            dirty: true,
        }));

        let frame = CGRect {
            origin: CGPoint { x: 0.0, y: 0.0 },
            size: CGSize {
                width: BOARD_W as f64,
                height: BOARD_H as f64,
            },
        };
        let view = PanelView::new(mtm, state.clone(), frame);
        view.setWantsLayer(true);
        view.setAutoresizingMask(
            NSAutoresizingMaskOptions::ViewWidthSizable
                | NSAutoresizingMaskOptions::ViewHeightSizable,
        );
        parent.addSubview(&view);
        if let Some(layer) = layer_of(&view) {
            // Insurance for a mis-sized parent; at matched density it's inert.
            let _: () = unsafe { msg_send![&*layer, setMagnificationFilter: ns_string!("nearest")] };
        }

        let tick_view = view.clone();
        let block = RcBlock::new(move |_timer: NonNull<NSTimer>| {
            tick(&tick_view);
        });
        let timer =
            unsafe { NSTimer::timerWithTimeInterval_repeats_block(TICK_SECONDS, true, &block) };
        unsafe { NSRunLoop::mainRunLoop().addTimer_forMode(&timer, NSRunLoopCommonModes) };

        *self.runtime.lock().unwrap() = Some(MainCell(Runtime { view, timer }));
        Ok(())
    }

    fn show(&self) -> PluginResult<()> {
        let _mtm = MainThreadMarker::new().ok_or(PluginError::InvalidState)?;
        if let Some(MainCell(rt)) = self.runtime.lock().unwrap().as_ref() {
            rt.view.setHidden(false);
        }
        Ok(())
    }

    fn hide(&self) -> PluginResult<()> {
        let _mtm = MainThreadMarker::new().ok_or(PluginError::InvalidState)?;
        if let Some(MainCell(rt)) = self.runtime.lock().unwrap().as_ref() {
            rt.view.setHidden(true);
        }
        Ok(())
    }
}

fn layer_of(view: &NSView) -> Option<Retained<AnyObject>> {
    unsafe { msg_send![view, layer] }
}

/// One 30 Hz beat: drain the analysis queue, run the board, blit at integer
/// density. The board repaints every beat (its furniture animates); the
/// expensive part is the blit, which is skipped only when nothing changed
/// and nothing is animating — i.e. never, by design: the panel is alive.
fn tick(view: &Retained<PanelView>) {
    let state = view.ivars().state.clone();
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

    let k = view
        .window()
        .map(|w| w.backingScaleFactor())
        .unwrap_or(1.0)
        .round()
        .clamp(1.0, MAX_INTEGER_SCALE as f64) as u32;
    st.last_k = k;
    st.painted = true;
    blit(&st.board.fb, &mut st.row, k, view);
}

/// Expand the logical plate k x and hand it to the view's layer.
fn blit(src: &[u8], row_scratch: &mut [u8], k: u32, view: &Retained<PanelView>) {
    let (kw, kh) = (BOARD_W * k as usize, BOARD_H * k as usize);
    let Some(rep) = (unsafe {
        NSBitmapImageRep::initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel(
            NSBitmapImageRep::alloc(),
            std::ptr::null_mut(),
            kw as isize,
            kh as isize,
            8,
            4,
            true,
            false,
            NSDeviceRGBColorSpace,
            (kw * 4) as isize,
            32,
        )
    }) else {
        return;
    };
    let stride = rep.bytesPerRow() as usize;
    let data = rep.bitmapData();
    if data.is_null() {
        return;
    }
    let dst = unsafe { std::slice::from_raw_parts_mut(data, stride * kh) };

    let ku = k as usize;
    let row = &mut row_scratch[..BOARD_W * ku * 4];
    for y in 0..BOARD_H {
        let s = &src[y * BOARD_W * 4..(y + 1) * BOARD_W * 4];
        if ku == 1 {
            let d = y * stride;
            dst[d..d + BOARD_W * 4].copy_from_slice(s);
            continue;
        }
        for x in 0..BOARD_W {
            for r in 0..ku {
                row[(x * ku + r) * 4..(x * ku + r) * 4 + 4].copy_from_slice(&s[x * 4..x * 4 + 4]);
            }
        }
        for ky in 0..ku {
            let d = (y * ku + ky) * stride;
            dst[d..d + BOARD_W * ku * 4].copy_from_slice(row);
        }
    }

    let img = NSImage::initWithSize(
        NSImage::alloc(),
        CGSize {
            width: BOARD_W as f64,
            height: BOARD_H as f64,
        },
    );
    img.addRepresentation(&rep);

    if let Some(layer) = layer_of(view) {
        let scale = k as f64;
        // The blessed path for layer contents from an NSImage: let the image
        // pick the representation for this scale.
        let contents: Retained<AnyObject> =
            unsafe { msg_send![&*img, layerContentsForContentsScale: scale] };
        unsafe {
            let _: () = msg_send![&*layer, setContentsScale: scale];
            let _: () = msg_send![&*layer, setContents: &*contents];
        }
    }
}
