-- example_service: an EXAMPLE cut service profile that shows the shape of a real profile and
-- exercises the sheet checks. The part limits and finish windows are rounded from one cut
-- service's published limits as read in October 2026. The SKU rows are placeholders in the same
-- range. None of it is current vendor data. Before an order, a repo copies this file, renames the
-- slug, and replaces every row from its vendor's own published design guide, citing the page in
-- each `source` field.
-- Units: mm. kerf_in_cad = False: the service compensates kerf, so draw nominal geometry. One part
-- per file, cut path on one layer only, text converted to outlines, closed contours.
-- Minimum hole rule: the lint fails below max(min_hole_rec_mm, min_hole_factor_t x t) and warns
-- below warn_hole_factor_t x t and below a warn_edge_factor_t x t hole-to-edge web.
let T = ../../types/package.dhall

let SizeMm = T.SizeMm

let example = "EXAMPLE value, not current vendor data: replace from your vendor's design guide"

in    { slug = "example_service"
      , name = "Example cut service"
      , kind = "service"
      , processes = [ "laser_fiber", "laser_co2", "waterjet" ]
      , formats = [ "DXF", "STEP" ]
      , units = [ "mm", "in" ]
      , kerf_in_cad = False
      , kerf_mm = 0.0
      , layers = [ "CUT" ]
      , text_allowed = False
      , one_part_per_file = True
      , islands_allowed = False
      , min_part_mm = { x = 6.0, y = 10.0 }
      , max_part_mm = { x = 1100.0, y = 750.0 }
      , min_hole_factor_t = 0.5
      , warn_hole_factor_t = 1.0
      , warn_edge_factor_t = 2.0
      , inside_corner_r_mm = 0.8
      , finish_windows =
        [ { process = "anodize"
          , min_mm = { x = 25.0, y = 75.0 }
          , max_mm = { x = 580.0, y = 580.0 }
          }
        , { process = "powder_coat"
          , min_mm = { x = 25.0, y = 75.0 }
          , max_mm = { x = 760.0, y = 910.0 }
          }
        , { process = "tapping"
          , min_mm = { x = 25.0, y = 38.0 }
          , max_mm = { x = 910.0, y = 1160.0 }
          }
        , { process = "hardware_insertion"
          , min_mm = { x = 25.0, y = 38.0 }
          , max_mm = { x = 910.0, y = 1160.0 }
          }
        , { process = "countersink"
          , min_mm = { x = 25.0, y = 100.0 }
          , max_mm = { x = 350.0, y = 1160.0 }
          }
        , { process = "bending"
          , min_mm = { x = 10.0, y = 38.0 }
          , max_mm = { x = 760.0, y = 1100.0 }
          }
        ]
        -- Tap drills: common ISO and UNC tap drill sizes, as an example. A service may want a
        -- different drawn size for its own taps: use the size its tapping page lists.
      , tap_drills =
        [ { thread = "M2.5x0.45", drill_mm = 2.05 }
        , { thread = "M3x0.5", drill_mm = 2.5 }
        , { thread = "M4x0.7", drill_mm = 3.3 }
        , { thread = "M5x0.8", drill_mm = 4.2 }
        , { thread = "M6x1.0", drill_mm = 5.0 }
        , { thread = "6-32", drill_mm = 2.85 }
        ]
      , finish_min_hole_mm = 1.0
      , hang_hole_mm = 1.6
      , tap_min_t_mm = 1.5
      , countersink_min_t_mm = 3.2
      , skus =
        [ { sku = "AL-2.3"
          , material = "5052 aluminium"
          , process = "laser_fiber"
          , t_in = 0.090
          , t_mm = 2.3
          , cut_tol_mm = 0.13
          , min_hole_mm = 0.4
          , min_hole_rec_mm = 0.8
          , min_bridge_mm = 0.9
          , min_hole_edge_mm = 0.7
          , tab_slot_tol_mm = 0.25
          , kerf_mm = None Double
          , min_part_mm = None SizeMm
          , max_part_mm = None SizeMm
          , bend = Some
              { r_mm = 1.5
              , k = 0.4
              , bend_deduction_90_mm = 4.0
              , die_width_mm = 16.0
              , relief_depth_mm = 3.0
              , min_flange_before_mm = 8.0
              , min_flange_after_mm = 9.0
              , max_bend_length_mm = 1100.0
              }
          , source = example
          }
        , { sku = "AL-3.2"
          , material = "5052 aluminium"
          , process = "laser_fiber"
          , t_in = 0.125
          , t_mm = 3.2
          , cut_tol_mm = 0.13
          , min_hole_mm = 0.5
          , min_hole_rec_mm = 1.0
          , min_bridge_mm = 1.2
          , min_hole_edge_mm = 1.0
          , tab_slot_tol_mm = 0.25
          , kerf_mm = None Double
          , min_part_mm = None SizeMm
          , max_part_mm = None SizeMm
          , bend = Some
              { r_mm = 2.0
              , k = 0.4
              , bend_deduction_90_mm = 5.5
              , die_width_mm = 20.0
              , relief_depth_mm = 4.0
              , min_flange_before_mm = 10.0
              , min_flange_after_mm = 11.0
              , max_bend_length_mm = 1100.0
              }
          , source = example
          }
        , { sku = "STEEL-1.9"
          , material = "mild steel"
          , process = "laser_fiber"
          , t_in = 0.075
          , t_mm = 1.9
          , cut_tol_mm = 0.13
          , min_hole_mm = 0.4
          , min_hole_rec_mm = 0.8
          , min_bridge_mm = 0.9
          , min_hole_edge_mm = 0.7
          , tab_slot_tol_mm = 0.25
          , kerf_mm = None Double
          , min_part_mm = None SizeMm
          , max_part_mm = None SizeMm
          , bend = Some
              { r_mm = 1.5
              , k = 0.4
              , bend_deduction_90_mm = 3.5
              , die_width_mm = 14.0
              , relief_depth_mm = 2.5
              , min_flange_before_mm = 7.0
              , min_flange_after_mm = 8.0
              , max_bend_length_mm = 1100.0
              }
          , source = example
          }
        , { sku = "ACRYLIC-3.0"
          , material = "cast acrylic"
          , process = "laser_co2"
          , t_in = 0.118
          , t_mm = 3.0
          , cut_tol_mm = 0.25
          , min_hole_mm = 1.0
          , min_hole_rec_mm = 1.5
          , min_bridge_mm = 1.5
          , min_hole_edge_mm = 1.5
          , tab_slot_tol_mm = 0.25
          , kerf_mm = None Double
          , min_part_mm = Some { x = 25.0, y = 50.0 }
          , max_part_mm = None SizeMm
          , bend = None T.LaserBend
          , source = example
          }
        ]
      , source = example
      }
    : T.LaserVendor
