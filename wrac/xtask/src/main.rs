use std::path::Path;

use wrac_xtask::{XtaskConfig, run};

fn main() -> wrac_xtask::Result<()> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("xtask must be a direct child of the repository root")
        .to_path_buf();
    // The family's one clap-wrapper build, in the sibling open-wrac checkout.
    let wrapper_dir = root
        .join("../../open-wrac/clap_wrapper_builder")
        .canonicalize()
        .expect("../open-wrac must be checked out beside this repository");
    run(XtaskConfig {
        wrapper_dir,
        target_namespace: "wrac-plugins".to_string(),
        root,
    })
}
