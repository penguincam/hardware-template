{
  description = "hardware-template: parametric part design for 3D printing and sheet cutting";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    { nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        linuxOnly = pkgs.lib.optionals pkgs.stdenv.hostPlatform.isLinux;
        default = pkgs.mkShell {
          packages =
            with pkgs;
            [
              # entrypoints + SSOT
              just
              bazelisk
              buildifier
              dhall
              dhall-json
              jq
              yq-go
              # python CAD lane (build123d via uv)
              uv
              python312
              # repo hygiene
              git
              gh
              git-cliff
              gitleaks
              shellcheck
            ]
            ++ linuxOnly [ orca-slicer ];
          shellHook = ''
            if [[ $- == *i* ]]; then echo "hardware-template dev shell: run: just doctor" >&2; fi
          '';
        };
      in
      {
        devShells = {
          inherit default;
        };
      }
    );
}
