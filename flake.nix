{
  description = "open-pitch-quant — an open exploration of real-time polyphonic pitch mapping (à la Zynaptiq PITCHMAP)";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "aarch64-darwin" "x86_64-darwin" "x86_64-linux" "aarch64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAll (pkgs: {
        # DSP prototyping shell: Python scientific stack + audio utilities.
        # A plugin-build shell (rust/nih-plug or C++/JUCE) will be added once
        # we commit to a real-time stack.
        default = pkgs.mkShell {
          packages = [
            (pkgs.python3.withPackages (ps: with ps; [
              numpy
              scipy
              matplotlib
              soundfile
              mido
            ]))
            pkgs.ffmpeg
            pkgs.sox
            # rust for the real-time port (rt/)
            pkgs.cargo
            pkgs.rustc
            pkgs.libiconv
          ];
        };
      });
    };
}
