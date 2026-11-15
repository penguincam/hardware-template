-- Printers a repo prints on. Units: mm. Build volume is the printable volume.
-- The two rows below are EXAMPLES that show the shape and drive the template's own tests. A new
-- repo replaces them with its own machines: measure the printable volume or read it from the
-- machine's slicer profile, and cite that in `source`.
-- Laser and sheet cutting is not here: see ./laser_vendors.dhall.
let Printer =
      { slug : Text
      , model : Text
      , x : Double
      , y : Double
      , z : Double
      , toolheads : Natural
      , nozzle : Double
      , profiles : Text
      , source : Text
      }

in  { schema = "Printer"
    , example_large =
          { slug = "example_large"
          , model = "Example large-bed printer, 4 toolheads"
          , x = 270.0
          , y = 270.0
          , z = 270.0
          , toolheads = 4
          , nozzle = 0.4
          , profiles = "third_party/slicer_profiles/example_large"
          , source = "EXAMPLE values: replace with your printer's printable volume"
          }
        : Printer
    , example_small =
          { slug = "example_small"
          , model = "Example small-bed printer, 1 toolhead"
          , x = 220.0
          , y = 220.0
          , z = 250.0
          , toolheads = 1
          , nozzle = 0.4
          , profiles = "third_party/slicer_profiles/example_small"
          , source = "EXAMPLE values: replace with your printer's printable volume"
          }
        : Printer
    }
