//! Runtime for one GUI window: WebView creation, command registration, and
//! the periodic state-sync timer (parameters + analysis feed).

use std::rc::Rc;
use std::sync::Arc;
use std::time::Duration;

use novonotes_run_loop::RunLoopLocal;
use run_loop_timer::Timer;
use wrac_clap_adapter::{
    GuiConfig, GuiSize, HostContext, HostGuiResizeRequester, HostParamsEditNotifier,
    PluginDescriptor, PluginError, PluginResult,
};
use wrac_wxp_gui::{
    GuiSizeLimits, ParentWindowHandle, WxpFrontendSource, WxpGuiResizeHandle, WxpGuiRuntime,
    WxpWebViewConfig, WxpWebViewSession,
};
use wxp::WxpCommandHandler;

use crate::commands::{CommandRegistrationDependencies, register_commands};
use crate::gui::GuiStateNotifier;
use crate::plugin::notify_gui_parameters;
use crate::state::SharedState;

// GUI window size bounds (pixels). The host opens at the default; resize is
// clamped to min..=max. The display needs room — this is a maximalist UI.
pub(super) const DEFAULT_GUI_SIZE: GuiSize = GuiSize {
    width: 1080,
    height: 720,
};
pub(super) const MIN_GUI_SIZE: GuiSize = GuiSize {
    width: 880,
    height: 560,
};
pub(super) const MAX_GUI_SIZE: GuiSize = GuiSize {
    width: 1920,
    height: 1200,
};

// Embed the frontend zip only for release builds; debug builds use the Vite
// dev server (hot reload inside the DAW).
#[cfg(not(debug_assertions))]
const FRONTEND_ZIP: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/opq_plugin_gui.zip"));

#[derive(Clone)]
pub(super) struct GuiRuntimeDependencies {
    pub(super) descriptor: PluginDescriptor,
    pub(super) shared: Arc<SharedState>,
    pub(super) gui_notifier: Arc<GuiStateNotifier>,
    pub(super) host_parameter_edit_notifier: Arc<dyn HostParamsEditNotifier>,
    pub(super) host_gui_resize_requester: Arc<dyn HostGuiResizeRequester>,
    pub(super) resize_handle: WxpGuiResizeHandle,
    pub(super) host_context: HostContext,
}

/// Runtime for one GUI window. Created when the host opens the GUI; dropped
/// when closed.
pub(crate) struct OpqGuiRuntime {
    gui_notifier: Arc<GuiStateNotifier>,
    webview: WxpWebViewSession,
    gui_update_timer: Timer,
}

impl OpqGuiRuntime {
    pub(super) fn create(
        run_loop: &RunLoopLocal,
        dependencies: GuiRuntimeDependencies,
        configuration: GuiConfig,
        initial_size: GuiSize,
        parent: ParentWindowHandle,
    ) -> PluginResult<Self> {
        if configuration.is_floating {
            log::warn!("rejecting floating GUI configuration");
            return Err(PluginError::Message("unsupported GUI configuration"));
        }
        log::debug!(
            "creating GUI runtime: width={}, height={}, configuration={configuration:?}",
            initial_size.width,
            initial_size.height
        );

        let command_handler = Rc::new(WxpCommandHandler::new());
        let host_size_unit = dependencies.resize_handle.host_size_unit();
        register_commands(
            command_handler.clone(),
            CommandRegistrationDependencies {
                shared: dependencies.shared.clone(),
                gui_notifier: dependencies.gui_notifier.clone(),
                descriptor: dependencies.descriptor,
                host_parameter_edit_notifier: dependencies.host_parameter_edit_notifier,
                host_gui_resize_requester: dependencies.host_gui_resize_requester,
                gui_resize_handle: dependencies.resize_handle,
                host_context: dependencies.host_context,
            },
        );

        let webview = WxpWebViewSession::create(
            WxpWebViewConfig {
                plugin_id: dependencies.descriptor.id,
                initial_size,
                limits: GuiSizeLimits {
                    min: MIN_GUI_SIZE,
                    max: MAX_GUI_SIZE,
                },
                host_size_unit,
                parent,
                frontend: frontend_source(),
                devtools: cfg!(debug_assertions),
            },
            command_handler,
        )?;

        // ~30 Hz sync: parameter values (cheap; automation reaches the GUI
        // this way) plus a drain of the analysis-frame queue. Frames arrive
        // at hop rate (~43 Hz @ 44.1k), so each tick ships 1–2 frames.
        let gui_update_timer = Timer::new(Duration::from_millis(33), {
            let shared = dependencies.shared.clone();
            let gui_notifier = dependencies.gui_notifier.clone();
            // Timer takes Fn; the scratch buffer is GUI-thread-only state.
            let viz_scratch: std::cell::RefCell<Vec<opq_engine::VizFrame>> =
                std::cell::RefCell::new(Vec::with_capacity(64));
            move || {
                notify_gui_parameters(&shared, |parameter_id, value| {
                    gui_notifier.notify_parameter(parameter_id, value);
                });
                if gui_notifier.has_viz_subscribers() {
                    let mut viz_scratch = viz_scratch.borrow_mut();
                    viz_scratch.clear();
                    shared.drain_viz(&mut viz_scratch);
                    let (sample_rate, hop) = shared.engine_info();
                    gui_notifier.notify_viz(&viz_scratch, sample_rate, hop);
                }
            }
        });
        gui_update_timer.start(run_loop);

        log::debug!("creating GUI runtime: completed");
        Ok(Self {
            gui_notifier: dependencies.gui_notifier,
            webview,
            gui_update_timer,
        })
    }
}

impl WxpGuiRuntime for OpqGuiRuntime {
    fn set_scale(&mut self, scale: f64) -> PluginResult<()> {
        self.webview.set_scale(scale)
    }

    fn set_size(&mut self, size: GuiSize) -> PluginResult<()> {
        self.webview.set_size(size)
    }

    fn show(&mut self, run_loop: &RunLoopLocal) -> PluginResult<()> {
        log::debug!("showing GUI runtime");
        self.webview.show()?;
        self.gui_update_timer.start(run_loop);
        Ok(())
    }

    fn hide(&mut self) -> PluginResult<()> {
        log::debug!("hiding GUI runtime");
        self.gui_update_timer.stop();
        self.webview.hide()?;
        Ok(())
    }
}

fn frontend_source() -> WxpFrontendSource {
    #[cfg(debug_assertions)]
    {
        WxpFrontendSource::Url {
            url: "http://127.0.0.1:5173/",
        }
    }

    #[cfg(not(debug_assertions))]
    {
        WxpFrontendSource::Zip {
            scheme: "wxp-plugin",
            url: "wxp-plugin://localhost/",
            bytes: FRONTEND_ZIP,
        }
    }
}

impl Drop for OpqGuiRuntime {
    fn drop(&mut self) {
        log::debug!("dropping GUI runtime");
        self.gui_update_timer.stop();
        self.gui_notifier.clear_subscriptions();
        let _ = self.gui_update_timer.is_running();
    }
}
