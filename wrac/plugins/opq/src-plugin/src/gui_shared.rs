//! What the Cocoa and Win32 mounts share: committing editor operations to
//! the host, the view's state over the shared truth, and the GPU scene.
//! Each mount keeps its own native shell (view, timer, input translation).
//! open-eq's gui_shared, for this board.
use crate::state::SharedState;
use opq_engine::params::ParameterBatch;
use opq_engine::VizFrame;
use opq_panel::{pack, Board, Edit, Fittings, Modifiers, PanelState, HEIGHT, WIDTH};
use panelkit::gpu::Present;
use panelkit::mount::ViewWindowHandle;
use std::sync::Arc;
use std::time::Instant;
use wrac_clap_adapter::{GuiSize, HostParamsEditNotifier};

/// The editor's largest scale, both mounts.
pub(crate) const MAX_SCALE: f64 = 2.0;

/// The board's aspect at the scale `size` allows (0.7 to `MAX_SCALE`), at a
/// fixed point (panelkit's `size::fitted`): what `adjust_size` proposes,
/// `set_size` accepts.
pub(crate) fn fitted_size(size: GuiSize) -> GuiSize {
    let (width, height) = panelkit::size::fitted((WIDTH, HEIGHT), (size.width, size.height), (0.7, MAX_SCALE));
    GuiSize { width, height }
}

/// Commit a whole editor operation, then tell the host, so a reentrant host
/// callback reads the new values.
pub(crate) fn apply(edits: Vec<Edit>, shared: &SharedState, notifier: &dyn HostParamsEditNotifier) {
    let mut batch = ParameterBatch::new();
    for edit in &edits {
        if let Edit::Value(id, value) = *edit {
            batch.insert(id, value);
        }
    }
    if !batch.is_empty() {
        shared.set_batch(&batch);
    }
    for edit in edits {
        match edit {
            Edit::Begin(id) => notifier.begin_edit(id as u32),
            Edit::Value(id, _) => {
                if let Some(value) = batch.value(id) {
                    notifier.update_edit(id as u32, value as f64);
                }
            }
            Edit::End(id) => notifier.end_edit(id as u32),
            // Product state, not a parameter: stored, and the host told
            // its saved state changed.
            Edit::Keys(keys) => shared.set_keys(keys, true),
        }
    }
}

pub(crate) struct ViewState {
    pub(crate) shared: Arc<SharedState>,
    pub(crate) notifier: Arc<dyn HostParamsEditNotifier>,
    pub(crate) panel: PanelState,
    pub(crate) fittings: Fittings,
    pub(crate) restore_revision: u64,
    pub(crate) scene: Option<Scene>,
    pub(crate) dead: bool,
    /// The editor's pointer, logical px: the cursor's, except during a
    /// relative drag, where it accumulates the drag's steps.
    pub(crate) pointer: (f32, f32),
    /// Analysis frames drained this beat (kept to reuse its allocation).
    frames: Vec<VizFrame>,
}

impl ViewState {
    /// A fresh view over the shared truth, as the editor attaches.
    pub(crate) fn new(shared: Arc<SharedState>, notifier: Arc<dyn HostParamsEditNotifier>) -> Self {
        let (params, restore_revision) = shared.snapshot();
        let mut panel = PanelState::new(Instant::now());
        panel.params = params;
        panel.keys = shared.keys();
        panel.version = env!("CARGO_PKG_VERSION");
        Self {
            shared,
            notifier,
            panel,
            fittings: Fittings::default(),
            restore_revision,
            scene: None,
            dead: false,
            pointer: (-1.0, -1.0),
            frames: Vec::with_capacity(opq_engine::VIZ_RING * 4),
        }
    }

    pub(crate) fn clear_editing(&mut self, rollback: bool) -> Vec<Edit> {
        if rollback {
            self.fittings.key(&mut self.panel, "Escape", Modifiers::default())
        } else {
            self.fittings.focus_lost(&mut self.panel)
        }
    }

    /// Reads the shared truth (values, analysis). A restore ends any
    /// gesture in progress.
    pub(crate) fn refresh(&mut self) -> Vec<Edit> {
        let (params, revision) = self.shared.snapshot();
        let restored = revision != self.restore_revision;
        let edits = if restored { self.clear_editing(false) } else { Vec::new() };
        self.restore_revision = revision;
        self.panel.params = params;
        self.panel.keys = self.shared.keys();
        self.frames.clear();
        self.shared.drain_viz(&mut self.frames);
        self.panel.push_frames(self.frames.drain(..));
        self.panel.engine_info = self.shared.engine_info();
        self.panel.update(Instant::now());
        edits
    }
}

pub(crate) struct Scene {
    present: Present,
    board: Board,
    pub(crate) size: (u32, u32),
}

impl Scene {
    pub(crate) fn new(target: ViewWindowHandle, size: (u32, u32)) -> Result<Self, String> {
        let (gpu, mut present) = Present::new(target, size)?;
        // Ceil: a fractional surface takes the 2x board and the present blit
        // downsamples it.
        let scale = (size.0 as f32 / WIDTH as f32).min(size.1 as f32 / HEIGHT as f32).ceil().clamp(1.0, 2.0) as u32;
        let board = Board::new(gpu, &pack::embedded(), scale)?;
        present.set_source(board.gpu(), board.out_view());
        Ok(Self { present, board, size })
    }

    pub(crate) fn render(&mut self, state: &PanelState) -> Result<(), String> {
        self.board.render(state)?;
        // A compositor timeout is a dropped frame, not a failed scene.
        if let Err(error) = self.present.blit(self.board.gpu()) {
            log::debug!("OpenPitchQuant frame dropped: {error}");
        }
        Ok(())
    }
}
