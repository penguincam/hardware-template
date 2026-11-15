-- mods/<creator>/<mod>/.metadata.yml from a Mod record (dhall-to-yaml).
let T = ../types/package.dhall

let L = ./lib.dhall

in  \(m : T.Mod) ->
      { title = m.title
      , creator = m.creator
      , slug = m.slug
      , description = m.description
      , mod_version = m.mod_version
      , process = L.map T.Process Text L.showProcess m.process
      , materials = m.materials
      , printers = m.printers
      , issue = m.issue
      , cad = m.cad
      , stls = m.stls
      , threemf = m.threemf
      , dxf = m.dxf
      , images = m.images
      , docs = m.docs
      }
