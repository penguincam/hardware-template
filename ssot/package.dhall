-- ssot/package.dhall: the single entry point to the Dhall source of truth.
-- Local imports only (tools/ssot/lib.sh refuses remote and env imports).
{ types = ./types/package.dhall
, constants = ./constants/package.dhall
, materials = ./materials/package.dhall
, render =
  { lib = ./render/lib.dhall
  , metadata_yml = ./render/metadata_yml.dhall
  , params = ./render/params.dhall
  }
}
