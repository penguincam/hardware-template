# hardware-template

The starting point for a penguincam hardware repository: Dhall parameters, build123d parts and Bazel exports, with print and sheet metal checks. Status: the print flow is proven on real printed parts. The sheet metal flow passes its checks, but no part from it has been cut. Nothing is proven for outdoor, waterproof or solar use.

## Start

```sh
gh repo fork penguincam/hardware-template --fork-name hardware-template-contrib --clone
cd hardware-template-contrib
just fork-setup <your-login> && just hooks-install
nix develop                  # or: direnv allow
just ssot-render && just test-tools
```

## Tasks

| Task | Command |
|---|---|
| List recipes | `just` |
| Render the Dhall outputs | `just ssot-render` |
| Check freshness, manifests and order packages | `just check` |
| Test the tools without Bazel or a CAD kernel | `just test-tools` |
| Build and test everything | `just test` |
| Export the example box for printing | `just export-print mods/example/sealed_box` |
| Build a sheet order package | `just sheet-quote mods/<creator>/<mod>` |
| Stamp a new repository | `just stamp <name> --visibility private` |

## Related

- [.github](https://github.com/penguincam/.github): contributing guide, security policy and git hooks.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): the SSOT flow, the checks and the private overlay.

## Contributing

Read the [contributing guide](https://github.com/penguincam/.github/blob/main/CONTRIBUTING.md). Pull requests go from a branch on your fork into `dev`. Agent files stay on your fork.

## License

Designs and documentation are CERN-OHL-W-2.0, in `LICENSE-CERN-OHL-W-2.0.txt`. Tool code is GPL-3.0-or-later, in `LICENSE`. `docs/LICENSING.md` lists which paths are which.
