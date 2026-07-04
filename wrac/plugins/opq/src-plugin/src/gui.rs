//! Product-specific WebView GUI runtime for OpenPitchQuant.
//!
//! The GUI itself is the HTML/CSS/TypeScript in `src-gui/`. This module
//! attaches a WebView containing that content to the host window and talks to
//! the frontend via [`wxp`] commands and channels — including the analysis
//! feed driving the live pitch-object display.

use std::sync::Arc;

mod notifier;
mod runtime;

pub(crate) use notifier::{GuiStateNotifier, GuiSubscriptionId, parameter_payload};

use novonotes_run_loop::RunLoopLocal;
use runtime::{
    DEFAULT_GUI_SIZE, GuiRuntimeDependencies, MAX_GUI_SIZE, MIN_GUI_SIZE, OpqGuiRuntime,
};
use wrac_clap_adapter::{
    GuiConfig, GuiSize, HostContext, HostGuiResizeRequester, HostParamsEditNotifier, PluginResult,
};
use wrac_wxp_gui::{
    GuiSizeLimits, ParentWindowHandle, WxpGuiController, WxpGuiFactory, WxpGuiResizeHandle,
    WxpGuiRuntime,
};

use crate::state::SharedState;

pub(crate) struct GuiIntegration {
    pub(crate) controller: Arc<WxpGuiController>,
    pub(crate) notifier: Arc<GuiStateNotifier>,
}

struct OpqGuiFactory {
    dependencies: GuiRuntimeDependencies,
}

impl WxpGuiFactory for OpqGuiFactory {
    fn create_gui_runtime(
        &self,
        run_loop: &RunLoopLocal,
        configuration: GuiConfig,
        initial_size: GuiSize,
        parent: ParentWindowHandle,
    ) -> PluginResult<Box<dyn WxpGuiRuntime>> {
        OpqGuiRuntime::create(
            run_loop,
            self.dependencies.clone(),
            configuration,
            initial_size,
            parent,
        )
        .map(|runtime| Box::new(runtime) as Box<dyn WxpGuiRuntime>)
    }
}

/// Assembles the complete GUI extension set used by the plugin core.
pub(crate) fn create_gui_integration(
    descriptor: wrac_clap_adapter::PluginDescriptor,
    shared: Arc<SharedState>,
    host_parameter_edit_notifier: Arc<dyn HostParamsEditNotifier>,
    host_gui_resize_requester: Arc<dyn HostGuiResizeRequester>,
    host_context: HostContext,
) -> GuiIntegration {
    let notifier = Arc::new(GuiStateNotifier::new());
    let resize_handle = WxpGuiResizeHandle::new(
        DEFAULT_GUI_SIZE,
        GuiSizeLimits {
            min: MIN_GUI_SIZE,
            max: MAX_GUI_SIZE,
        },
    );
    let runtime_dependencies = GuiRuntimeDependencies {
        descriptor,
        shared,
        gui_notifier: notifier.clone(),
        host_parameter_edit_notifier,
        host_gui_resize_requester,
        resize_handle: resize_handle.clone(),
        host_context: host_context.clone(),
    };
    let controller = Arc::new(WxpGuiController::new_with_resize_handle(
        OpqGuiFactory {
            dependencies: runtime_dependencies,
        },
        resize_handle,
        host_context,
    ));

    GuiIntegration {
        controller,
        notifier,
    }
}
