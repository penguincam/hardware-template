-- Press-brake data for one sheet SKU. Units: mm (k is unitless). bend_deduction_90_mm is for a 90 deg bend;
-- keep every cut feature at least die_width_mm / 2 from the bend centreline.
{ r_mm : Double
, k : Double
, bend_deduction_90_mm : Double
, die_width_mm : Double
, relief_depth_mm : Double
, min_flange_before_mm : Double
, min_flange_after_mm : Double
, max_bend_length_mm : Double
}
