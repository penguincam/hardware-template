-- PCTG. Units per ssot/types/Material.dhall (MPa, GPa, degC, mm). Best impact pick; numbers are generic ranges.
let T = ../types/package.dhall

in  { name = "PCTG"
    , process = T.Process.Fdm
    , tensile_xy_mpa = 45.0
    , z_ratio = 0.5
    , modulus_gpa = 1.9
    , density_g_cm3 = 1.23
    , hdt_c = 70.0
    , clearance_per_side_mm = 0.3
    , kerf_mm = None Double
    , source = "UNVERIFIED generic ranges: modulus 1.8-2.3 GPa, HDT 65-80 @0.45 MPa per https://craftcloud3d.com/en/material-guide/pctg ; tensile and z_ratio UNVERIFIED (assumed ~PETG); impact ~24 kJ/m2 per CNC Kitchen; density g/cm3: UNVERIFIED (from memory) Prusament PCTG TDS 1.23"
    }
    : T.Material
