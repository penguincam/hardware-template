-- ABS. Units per ssot/types/Material.dhall (MPa, GPa, degC, mm). The numbers are a
-- representative brand TDS, so they are reported, not measured on any spool.
--
-- Polymaker PolyLite ABS TDS V5.6 (2025-12-30), ISO 527 / ISO 75 / ISO 1183:
--   Young's modulus X-Y 2246.6 MPa, Z 2080.9 MPa; tensile strength X-Y 33.4 MPa (the
--   PDF prints "33.4 +/- 92.7", a typo carried from the modulus row), Z 29.7 MPa;
--   HDT 100 C @ 0.45 MPa (98 C @ 1.8 MPa); density 1.04 g/cm3. Printing: nozzle
--   245-265 C, bed 90-100 C, cooling fan OFF, "Closure chamber: Needed"; the TDS
--   specimens were printed at a 90 C environment temperature.
-- z_ratio 0.4 is a DESIGN knock-down, not the TDS ratio (29.7 / 33.4 = 0.89): the TDS
-- bars were printed in a 90 C chamber, and an open-frame printer bonds layers far below
-- the chamber value. A ratio of 28/33 = 0.85 seen elsewhere is likewise an enclosed figure.
-- UNVERIFIED until a warp coupon is broken across its layers.
let T = ../types/package.dhall

in  { name = "ABS"
    , process = T.Process.Fdm
    , tensile_xy_mpa = 33.4
    , z_ratio = 0.4
    , modulus_gpa = 2.25
    , density_g_cm3 = 1.04
    , hdt_c = 100.0
    , clearance_per_side_mm = 0.25
    , kerf_mm = None Double
    , source = "Polymaker PolyLite ABS TDS V5.6 2025-12-30 https://polymaker.com/wp-content/uploads/lana-downloads/TDS_Polymaker_PolyLite-ABS_V5.6_2025-12-30_EN.pdf (ISO 527: E X-Y 2246.6, Z 2080.9 MPa; tensile X-Y 33.4, Z 29.7 MPa; HDT 100 C @0.45 MPa ISO 75; density 1.04 ISO 1183; nozzle 245-265 C, bed 90-100 C, fan off, chamber needed); z_ratio 0.4 is a design knock-down for an open-frame printer (TDS ratio 0.89 is from a 90 C chamber), UNVERIFIED; clearance 0.20-0.30 (tripo3d.ai, secondary)"
    }
    : T.Material
