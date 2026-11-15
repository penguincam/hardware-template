-- ASA. Units per ssot/types/Material.dhall (MPa, GPa, degC, mm). UV/heat resistant, weak layers; print enclosed.
let T = ../types/package.dhall

in  { name = "ASA"
    , process = T.Process.Fdm
    , tensile_xy_mpa = 40.0
    , z_ratio = 0.29
    , modulus_gpa = 1.6
    , density_g_cm3 = 1.07
    , hdt_c = 93.0
    , clearance_per_side_mm = 0.25
    , kerf_mm = None Double
    , source = "Prusament ASA TDS https://prusament.com/wp-content/uploads/2022/10/ASA_Prusament_TDS_2022_16_EN.pdf (filament yield 40, modulus 1.6 XY, HDT 93 @0.45 MPa); z_ratio 0.29: https://www.cnckitchen.com/blog/comparing-pla-petg-amp-asa-feat-prusament ; clearance 0.20-0.30 (tripo3d.ai, secondary); density g/cm3: UNVERIFIED (from memory) Prusament ASA TDS 1.07"
    }
    : T.Material
