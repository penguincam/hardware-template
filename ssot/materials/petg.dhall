-- PETG. Units per ssot/types/Material.dhall (MPa, GPa, degC, mm). Default body material for stage gear.
let T = ../types/package.dhall

in  { name = "PETG"
    , process = T.Process.Fdm
    , tensile_xy_mpa = 47.0
    , z_ratio = 0.46
    , modulus_gpa = 1.5
    , density_g_cm3 = 1.27
    , hdt_c = 68.0
    , clearance_per_side_mm = 0.3
    , kerf_mm = None Double
    , source = "Prusament PETG TDS v1.1 https://prusament.com/wp-content/uploads/2022/10/PETG_Prusament_TDS_2021_10_EN.pdf (yield 47 XY, modulus 1.5, HDT 68 @0.45 MPa); z_ratio 0.46: https://www.cnckitchen.com/blog/comparing-pla-petg-amp-asa-feat-prusament ; clearance 0.25-0.35 (tripo3d.ai, secondary); density g/cm3: UNVERIFIED (from memory) Prusament PETG TDS 1.27"
    }
    : T.Material
