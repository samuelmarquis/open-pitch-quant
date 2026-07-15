//! OpenPitchQuant — real-time polyphonic pitch mapping (WRAC edition).
//!
//! The DSP lives in the shared `opq-engine` crate (also used by the nih-plug
//! build and the offline CLI). This crate is the WRAC/CLAP shell: parameters,
//! state persistence, MIDI note-sidechain plumbing, and the drum.
//!
//! Controls stay in the host's generic parameter editor — the plugin's one
//! visual organ is the drum (`drum.rs`): a fixed, unclickable transect of the
//! tracker's belief. It observes; it cannot be operated.
//!
//! File layout follows the WRAC template:
//! - `plugin.rs`   : the plugin contract as seen by the host
//! - `state.rs`    : lock-free parameter state + the analysis feed
//! - `audio.rs`    : the audio-thread processor driving `opq_engine::Engine`
//! - `drum.rs`     : the transect renderer (pure pixels, platform-free)
//! - `gui.rs`      : the drum's Cocoa mount (macOS)
//! - `gui_win32.rs`: the drum's Win32 mount (Windows; elsewhere: headless)
//!
//! NOTE: unlike the template, we do NOT install the assert_no_alloc global
//! allocator. The engine currently allocates small scratch vectors during
//! analysis (multi-F0 candidate claims); cleaning that up for strict
//! RT-allocation discipline is tracked work, not a blocker.

mod audio;
#[cfg(any(target_os = "macos", target_os = "windows"))]
mod assets;
#[cfg(any(target_os = "macos", target_os = "windows"))]
mod board;
#[cfg(any(target_os = "macos", target_os = "windows"))]
mod canvas;
#[cfg(any(target_os = "macos", target_os = "windows"))]
mod drum;
#[cfg(any(target_os = "macos", target_os = "windows"))]
mod font;
#[cfg(target_os = "macos")]
mod gui;
#[cfg(target_os = "windows")]
mod gui_win32;
mod plugin;
mod state;

// Export the CLAP entry point. The adapter owns the C ABI and calls the safe Rust entry.
wrac_clap_adapter::export_clap_entry! {
    entry: &crate::plugin::PLUGIN_ENTRY,
}
