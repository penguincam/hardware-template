-- A sheet-part order package spec: mods/<creator>/<mod>/sheet_order.dhall. Read by
-- tools/laser/sheet_quote.py, which lints
-- each DXF against the vendor SKU and writes the quote package (DXF per part, parts.csv, bom.csv,
-- checklist.md, lint/*.json). Nothing here orders anything: a person uploads the package by hand.
--   vendor: laser_vendors slug (example_service in this template). parts: one row per part, one part per DXF.
--   dxf: path relative to the mod directory (the laser_sheet output copied by just export-laser).
--   step: the bent-part STEP relative to the mod (Some only when bends > 0; order bent parts from it).
--   finish: a vendor finish_windows process (anodize, powder_coat_al_steel, ...) or None for raw.
--   tapped: tap-drill holes to tap, by vendor tap_drills thread name; the DXF must carry at least
--     `count` holes at that drill. hardware: PEM part numbers with the catalogue K (centre to cut edge),
--     checked against the vendor hardware window and K to any other cut edge for every hole of hole_mm.
--   countersinks: holes to countersink (sheet >= countersink_min_t_mm). bends: press-brake bends.
--   note: the order note (bend direction, deburr, anything the vendor must read).
let Tapped = { thread : Text, count : Natural }

let Hardware = { part_number : Text, count : Natural, hole_mm : Double, k_mm : Double }

let Part =
      { name : Text
      , dxf : Text
      , step : Optional Text
      , sku : Text
      , qty : Natural
      , finish : Optional Text
      , finish_color : Optional Text
      , tapped : List Tapped
      , hardware : List Hardware
      , countersinks : Natural
      , bends : Natural
      , note : Text
      }

in  { Type = { vendor : Text, mod : Text, issue : Optional Text, parts : List Part }
    , Part
    , Tapped
    , Hardware
    , raw =
        { step = None Text
        , finish = None Text
        , finish_color = None Text
        , tapped = [] : List Tapped
        , hardware = [] : List Hardware
        , countersinks = 0
        , bends = 0
        , note = ""
        }
    }
