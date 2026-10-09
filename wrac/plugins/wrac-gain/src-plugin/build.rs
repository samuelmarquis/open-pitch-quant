//! Build script that generates the plugin descriptor table from
//! `[package.metadata.wrac]`, and bundles `src-gui/dist` into a single zip written to
//! `OUT_DIR` for release builds.
//!
//! The resulting zip is embedded into the plugin binary via `include_bytes!` in `gui.rs`
//! and served at runtime by the WebView under the `wxp-plugin://` scheme.
//! In debug builds Vite's dev server is used instead, so the bundle step does nothing.

use std::env;
use std::path::PathBuf;

use wrac_build::{FrontendBundleConfig, build_frontend_bundle};

fn main() {
    wrac_build::identity::generate();

    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR"));
    let gui_dist_dir = manifest_dir
        .parent()
        .expect("src-plugin must have a parent directory")
        .join("src-gui")
        .join("dist");
    build_frontend_bundle(FrontendBundleConfig {
        dist_dir: gui_dist_dir,
        output_file_name: "wrac_gain_plugin_gui.zip",
        rerun_if_changed: &[
            "../src-gui/index.html",
            "../src-gui/src",
            "../src-gui/package.json",
            "../src-gui/vite.config.ts",
        ],
        missing_dist_build_command:
            "Run `npm install && npm run build` in src-gui before release builds.",
    })
    .expect("failed to create frontend zip");
}
