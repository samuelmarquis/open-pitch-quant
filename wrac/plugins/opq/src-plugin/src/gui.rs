//! The drum's mount: a plain layer-backed NSView embedded in the host's
//! editor window, repainted by a 30 Hz main-run-loop timer. No widgets, no
//! mouse handling, no resize — the view is an instrument of observation,
//! not a control surface; the controls stay in the host's generic editor.
//!
//! Fixed-pixel decree: the framebuffer is rendered at an INTEGER multiple of
//! the logical 576x336 plate (the window's backing scale, rounded), then
//! handed to the layer at that exact density. Cocoa never interpolates.

use std::cell::RefCell;
use std::ptr::NonNull;
use std::rc::Rc;
use std::sync::Arc;
use std::sync::Mutex;

use block2::RcBlock;
use objc2::rc::Retained;
use objc2::runtime::AnyObject;
use objc2::{AllocAnyThread, MainThreadMarker, MainThreadOnly, msg_send};
use objc2_app_kit::{
    NSAutoresizingMaskOptions, NSBitmapImageRep, NSDeviceRGBColorSpace, NSImage, NSView,
};
use objc2_core_foundation::{CGPoint, CGRect, CGSize};
use objc2_foundation::{NSRunLoop, NSRunLoopCommonModes, NSTimer, ns_string};
use wrac_clap_adapter::{
    GuiApi, GuiConfig, GuiResizeHints, GuiSize, HostWindow, PluginError, PluginGuiExtension,
    PluginResult,
};

use crate::drum::{DRUM_H, DRUM_W, Drum};
use crate::plugin::PARAM_FMAX_ID;
use crate::state::SharedState;

const TICK_SECONDS: f64 = 1.0 / 30.0;
const MAX_INTEGER_SCALE: u32 = 4;

/// Holds main-thread-only values inside a `Send + Sync` controller. Access
/// and drop require a [`MainThreadMarker`]; `DrumGui` leaks the contents
/// rather than dropping them off-main (a host misbehaving beats a crash).
struct MainCell<T>(T);
unsafe impl<T> Send for MainCell<T> {}
unsafe impl<T> Sync for MainCell<T> {}

struct Runtime {
    view: Retained<NSView>,
    timer: Retained<NSTimer>,
}

pub(crate) struct DrumGui {
    shared: Arc<SharedState>,
    runtime: Mutex<Option<MainCell<Runtime>>>,
}

impl DrumGui {
    pub(crate) fn new(shared: Arc<SharedState>) -> Self {
        Self {
            shared,
            runtime: Mutex::new(None),
        }
    }

    fn teardown(&self, _mtm: MainThreadMarker) {
        if let Some(MainCell(rt)) = self.runtime.lock().unwrap().take() {
            rt.timer.invalidate();
            rt.view.removeFromSuperview();
        }
    }
}

impl Drop for DrumGui {
    fn drop(&mut self) {
        match MainThreadMarker::new() {
            Some(mtm) => self.teardown(mtm),
            None => {
                if let Some(cell) = self.runtime.lock().unwrap().take() {
                    log::warn!("drum: dropped off the main thread; leaking the view");
                    std::mem::forget(cell);
                }
            }
        }
    }
}

/// GUI-thread state owned by the timer callback.
struct TickState {
    drum: Drum,
    scratch: Vec<opq_engine::VizFrame>,
    row: Vec<u8>,
    last_k: u32,
    painted: bool,
}

impl PluginGuiExtension for DrumGui {
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
        match MainThreadMarker::new() {
            Some(mtm) => self.teardown(mtm),
            None => {
                if let Some(cell) = self.runtime.lock().unwrap().take() {
                    log::warn!("drum: destroy off the main thread; leaking the view");
                    std::mem::forget(cell);
                }
            }
        }
    }

    fn set_scale(&self, _scale: f64) -> PluginResult<()> {
        // Density comes from the window's backing scale at paint time,
        // rounded to an integer. Host scale suggestions carry no extra truth.
        Ok(())
    }

    fn get_size(&self) -> PluginResult<GuiSize> {
        Ok(GuiSize {
            width: DRUM_W as u32,
            height: DRUM_H as u32,
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
        if size.width != DRUM_W as u32 || size.height != DRUM_H as u32 {
            log::debug!(
                "drum: host set_size {}x{} ignored (fixed {DRUM_W}x{DRUM_H})",
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

        let frame = CGRect {
            origin: CGPoint { x: 0.0, y: 0.0 },
            size: CGSize {
                width: DRUM_W as f64,
                height: DRUM_H as f64,
            },
        };
        let view = NSView::initWithFrame(NSView::alloc(mtm), frame);
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

        let shared = self.shared.clone();
        let tick_view = view.clone();
        let state = Rc::new(RefCell::new(TickState {
            drum: Drum::new(),
            scratch: Vec::with_capacity(64),
            row: vec![0u8; DRUM_W * MAX_INTEGER_SCALE as usize * 4],
            last_k: 0,
            painted: false,
        }));
        let block = RcBlock::new(move |_timer: NonNull<NSTimer>| {
            tick(&shared, &state, &tick_view);
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

/// One 30 Hz beat: drain the analysis queue, turn the drum a column per
/// frame, and hand the layer a fresh plate at integer density.
fn tick(shared: &Arc<SharedState>, state: &Rc<RefCell<TickState>>, view: &Retained<NSView>) {
    let mut st = state.borrow_mut();

    st.scratch.clear();
    shared.drain_viz(&mut st.scratch);
    let ceiling = shared.parameter_value(PARAM_FMAX_ID).unwrap_or(5000.0);
    let fresh = !st.scratch.is_empty();
    if fresh {
        let mut frames = std::mem::take(&mut st.scratch);
        for fr in &frames {
            st.drum.push_frame(fr, ceiling);
        }
        frames.clear();
        st.scratch = frames;
    }

    let k = view
        .window()
        .map(|w| w.backingScaleFactor())
        .unwrap_or(1.0)
        .round()
        .clamp(1.0, MAX_INTEGER_SCALE as f64) as u32;

    if !fresh && st.painted && k == st.last_k {
        return;
    }
    st.last_k = k;
    st.painted = true;
    let st = &mut *st;
    blit(&st.drum, &mut st.row, k, view);
}

/// Expand the logical plate k x and hand it to the view's layer.
fn blit(drum: &Drum, row_scratch: &mut [u8], k: u32, view: &Retained<NSView>) {
    let (kw, kh) = (DRUM_W * k as usize, DRUM_H * k as usize);
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

    let src = drum.pixels();
    let ku = k as usize;
    let row = &mut row_scratch[..DRUM_W * ku * 4];
    for y in 0..DRUM_H {
        let s = &src[y * DRUM_W * 4..(y + 1) * DRUM_W * 4];
        for x in 0..DRUM_W {
            for r in 0..ku {
                row[(x * ku + r) * 4..(x * ku + r) * 4 + 4].copy_from_slice(&s[x * 4..x * 4 + 4]);
            }
        }
        for ky in 0..ku {
            let d = (y * ku + ky) * stride;
            dst[d..d + DRUM_W * ku * 4].copy_from_slice(row);
        }
    }

    let img = NSImage::initWithSize(
        NSImage::alloc(),
        CGSize {
            width: DRUM_W as f64,
            height: DRUM_H as f64,
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
