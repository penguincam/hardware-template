-- PLA. Units per ssot/types/Material.dhall (MPa, GPa, degC, mm). Avoid for stage/hot-car use: creeps.
let T = ../types/package.dhall

in  { name = "PLA"
    , process = T.Process.Fdm
    , tensile_xy_mpa = 57.0
    , z_ratio = 0.55
    , modulus_gpa = 2.2
    , density_g_cm3 = 1.24
    , hdt_c = 55.0
    , clearance_per_side_mm = 0.15
    , kerf_mm = None Double
    , source = "tensile/modulus/HDT: Prusament PLA TDS (UNVERIFIED, from memory: 57 MPa, 2.2 GPa, HDT 55); z_ratio 0.55: https://www.cnckitchen.com/blog/comparing-pla-petg-amp-asa-feat-prusament ; clearance: https://www.tripo3d.ai/blog/print-joints-keys-pins-alignment (secondary, 0.15-0.25); density g/cm3: UNVERIFIED (from memory) Prusament PLA TDS 1.24"
    }
    : T.Material
