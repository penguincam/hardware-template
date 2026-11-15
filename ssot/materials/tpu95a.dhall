-- TPU95A. Units per ssot/types/Material.dhall (MPa, GPa, degC, mm). Feet, gaskets. modulus is ~29-34 MPa (0.03 GPa).
let T = ../types/package.dhall

in  { name = "TPU95A"
    , process = T.Process.Fdm
    , tensile_xy_mpa = 29.0
    , z_ratio = 0.8
    , modulus_gpa = 0.03
    , density_g_cm3 = 1.22
    , hdt_c = 60.0
    , clearance_per_side_mm = 0.3
    , kerf_mm = None Double
    , source = "Polymaker PolyFlex TPU95 TDS V5.1 https://polymaker.com/wp-content/uploads/lana-downloads/PolyFlex_TPU95_TDS_V5.1.pdf (tensile 29.0 XY; Young's ~29-34 MPa); HDT and z_ratio UNVERIFIED placeholders; density g/cm3: UNVERIFIED PolyFlex TPU95 ~1.22"
    }
    : T.Material
