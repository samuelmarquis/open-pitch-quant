# OpenPitchQuant: the plugin workspace

The plugin crate (`plugins/opq/src-plugin`, `opq_plugin_wrac`) and its
`xtask`. The product's manual and changelog are the repo's
[README](../README.md); this file only says how the workspace builds.

The WRAC framework and the clap-wrapper build come from the sibling
checkout `../open-wrac`, the family's one copy (lineage in
`PROVENANCE.txt`; the shell's docs and patches live there). Build from
inside `nix develop`, which carries cmake:

```sh
cargo xtask install  -p opq_plugin_wrac --release   # CLAP, VST3, AU
cargo xtask validate -p opq_plugin_wrac --release   # clap-validator, VST3 validator, auval
```

Release builds only: a debug engine underruns in a host.

`README_JA.md` and `docs/` are the upstream WRAC template's own docs. They
describe its WebView demo plugin, not this one, and are kept only until
they're removed; for setup and readiness checks read `../open-wrac`.
