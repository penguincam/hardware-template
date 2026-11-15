-- Engineering record. Units: MPa, GPa, degC, mm, g/cm3 (density, used for part mass reports). z_ratio = Z (inter-layer) / XY tensile strength.
{ name : Text
, process : ./Process.dhall
, tensile_xy_mpa : Double
, z_ratio : Double
, modulus_gpa : Double
, density_g_cm3 : Double
, hdt_c : Double
, clearance_per_side_mm : Double
, kerf_mm : Optional Double
, source : Text
}
