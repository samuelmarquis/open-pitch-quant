//! OpenPitchQuant — real-time polyphonic pitch mapping (WRAC edition).
//!
//! The DSP lives in the shared `opq-engine` crate (also used by the nih-plug
//! build and the offline CLI). This crate is the WRAC/CLAP shell: parameters,
//! state persistence, MIDI note-sidechain plumbing, and (soon) the WebView GUI.
//!
//! File layout follows the WRAC template:
//! - `plugin.rs`   : the plugin contract as seen by the host
//! - `state.rs`    : lock-free parameter state + the analysis feed queue
//! - `audio.rs`    : the audio-thread processor driving `opq_engine::Engine`
//! - `gui.rs`      : WebView GUI integration; runtime/notifier under `gui/`
//! - `commands.rs` : Rust commands callable from the WebView frontend
//!
//! NOTE: unlike the template, we do NOT install the assert_no_alloc global
//! allocator. The engine currently allocates small scratch vectors during
//! analysis (multi-F0 candidate claims); cleaning that up for strict
//! RT-allocation discipline is tracked work, not a blocker.

mod audio;
mod commands;
mod gui;
mod plugin;
mod state;

// Export the CLAP entry point. The adapter owns the C ABI and calls the safe Rust entry.
wrac_clap_adapter::export_clap_entry! {
    entry: &crate::plugin::PLUGIN_ENTRY,
}
