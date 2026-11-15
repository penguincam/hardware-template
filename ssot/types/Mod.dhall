-- A Voron-mods-style mod manifest; renders to mods/<creator>/<mod>/.metadata.yml.
-- issue: an optional tracker link for the mod (a URL or an issue reference).
{ title : Text
, creator : Text
, slug : Text
, description : Text
, mod_version : Natural
, process : List ./Process.dhall
, materials : List Text
, printers : List Text
, issue : Optional Text
, cad : List Text
, stls : List Text
, threemf : List Text
, dxf : List Text
, images : List Text
, docs : List Text
}
