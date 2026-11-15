-- One sheet stock a laser vendor cuts (material + thickness). Units: mm unless the field says _in.
-- min_hole_mm is the vendor's absolute floor; min_hole_rec_mm its recommended minimum (the lint
-- uses max(min_hole_rec_mm, vendor.min_hole_factor_t * t_mm)). min_bridge_mm is the narrowest web
-- between two cuts, min_hole_edge_mm the narrowest web between a hole and the part edge.
-- kerf_mm: measured kerf for this stock on a shop laser (None: use the vendor kerf_mm).
-- min_part_mm / max_part_mm: None uses the vendor-level limits.
{ sku : Text
, material : Text
, process : Text
, t_in : Double
, t_mm : Double
, cut_tol_mm : Double
, min_hole_mm : Double
, min_hole_rec_mm : Double
, min_bridge_mm : Double
, min_hole_edge_mm : Double
, tab_slot_tol_mm : Double
, kerf_mm : Optional Double
, min_part_mm : Optional ./SizeMm.dhall
, max_part_mm : Optional ./SizeMm.dhall
, bend : Optional ./LaserBend.dhall
, source : Text
}
