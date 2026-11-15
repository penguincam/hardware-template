-- TPU90A. Units per ssot/types/Material.dhall (MPa, GPa, degC, mm). Polymaker PolyFlex
-- TPU90 (90A): gaskets, cable liners and feet.
--
-- Small-strain modulus about 21 MPa (0.021 GPa), from two independent routes that agree:
--   1. Polymaker TDS V5.6 gives stress at 100 % strain 7.1 MPa for TPU90 against 11.1 MPa
--      for TPU95, whose TDS also gives Young's modulus 33.6 MPa: 33.6 x 7.1 / 11.1 = 21.5.
--   2. Gent's Shore A relation (A. N. Gent, Rubber Chem. Technol. 31 (1958) 896; ASTM
--      D2240 / ISO 7619-1 durometer): E = 0.0981 (56 + 7.62336 S) / (0.137505 (254 -
--      2.54 S)) MPa gives 20.8 MPa at 90A and 43.8 MPa at 95A.
-- Both put 90A at about 0.48-0.64 of 95A. The value is an ESTIMATE (no Young's row in the
-- TPU90 TDS); it sizes the gasket and liner squeeze, it does not gate a FEA.
let T = ../types/package.dhall

in  { name = "TPU90A"
    , process = T.Process.Fdm
    , tensile_xy_mpa = 30.1
    , z_ratio = 0.8
    , modulus_gpa = 0.021
    , density_g_cm3 = 1.21
    , hdt_c = 55.0
    , clearance_per_side_mm = 0.3
    , kerf_mm = None Double
    , source = "Polymaker PolyFlex TPU90 TDS V5.6 2025-12-11 https://polymaker.com/wp-content/uploads/TDS_Polymaker_PolyFlex-TPU90_V5.6_2025-12-11_EN.pdf (density 1.21 g/cm3 ISO 1183, tensile 30.1 MPa X-Y ISO 37, stress at 100 % 7.1 MPa, Shore 90A ISO 7619-1); modulus 0.021 GPa ESTIMATED from the TPU95 TDS ratio (Young's 33.6, 100 % stress 11.1; https://wiki.polymaker.com/polymaker-products/more-about-our-products/documents/technical-data-sheets/tpu/polyflex-tm-tpu95) and Gent 1958 (20.8 MPa at 90A); HDT and z_ratio UNVERIFIED placeholders"
    }
    : T.Material
