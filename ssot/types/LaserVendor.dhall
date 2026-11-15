-- A laser or sheet-cutting vendor profile: a cut service (kind "service") or a
-- shop laser (kind "shop", added by a child repo in ssot/constants/laser_vendors_local.dhall).
-- Read by tools/bazel/laser_export.py (kerf) and tools/laser/dxf_lint.py
-- (rules) through ssot/generated/constants.json (laser_vendors.<slug>). Units: mm.
--   kerf_in_cad: true when CAD must offset CUT by kerf/2 (shop lasers); false when the vendor
--     compensates kerf itself (draw nominal geometry; most cut services).
--   kerf_mm: default kerf when kerf_in_cad (a LaserSku kerf_mm overrides it); measure it with the
--     kerf coupon cut on that laser. 0.0 with kerf_in_cad is an error at export.
--   layers: layers that may carry geometry; text_allowed: TEXT/MTEXT entities allowed off CUT.
--   one_part_per_file: exactly one outer contour; islands_allowed: contours nested inside holes.
--   min_part_mm / max_part_mm: part extents (either orientation); max is the bed for a shop laser.
--   min_hole_factor_t: hole floor as a fraction of thickness (error); warn_hole_factor_t and
--     warn_edge_factor_t: warnings for hole size and hole-to-edge web as multiples of thickness.
{ slug : Text
, name : Text
, kind : Text
, processes : List Text
, formats : List Text
, units : List Text
, kerf_in_cad : Bool
, kerf_mm : Double
, layers : List Text
, text_allowed : Bool
, one_part_per_file : Bool
, islands_allowed : Bool
, min_part_mm : ./SizeMm.dhall
, max_part_mm : ./SizeMm.dhall
, min_hole_factor_t : Double
, warn_hole_factor_t : Double
, warn_edge_factor_t : Double
, inside_corner_r_mm : Double
, finish_windows :
    List { process : Text, min_mm : ./SizeMm.dhall, max_mm : ./SizeMm.dhall }
, tap_drills : List { thread : Text, drill_mm : Double }
, finish_min_hole_mm : Double
, hang_hole_mm : Double
, tap_min_t_mm : Double
, countersink_min_t_mm : Double
, skus : List ./LaserSku.dhall
, source : Text
}
