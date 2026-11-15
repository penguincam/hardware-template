-- ASA-GF (glass-fibre ASA). Units per ssot/types/Material.dhall (MPa, GPa, degC, mm).
-- Picked for an earlier box after an ABS warp coupon warped at layer 9 on an open-frame
-- printer (reported).
--
-- RaccoonWorks ASA-GF, retailer product page (3dimensionally.com, read 2026-10-20; no TDS
-- PDF is published, so these are reported, not measured on any spool):
--   density 1.08 g/cm3 (ISO 1183); Young's modulus 2826 +/- 56 MPa; tensile strength at
--   break 46 MPa; elongation at break 2.43 %; bending strength 69 MPa; flexural modulus
--   2860 MPa; HDT 88 C @0.45 MPa, 84 C @1.8 MPa; Vicat 98 C; Tg 101 C. Test orientation
--   (XY or Z) and standard for the tensile figures are not stated: taken as XY.
-- Cross-check, Spectrum ASA-X GF10 TDS (2023-10-01, injection-moulded bars): 55 MPa,
--   2550 MPa, HDT 100 C @0.45 MPa, density 1.11, bed 80-100 C, fan 0-20 %, "closed
--   chamber not necessary". The RaccoonWorks figures are the lower and are used.
-- z_ratio 0.30 is a DESIGN knock-down, UNVERIFIED: no ASA-GF vendor publishes a Z value;
--   unfilled ASA measures 0.29 (CNC Kitchen, below), and glass fibres lie in the XY roads
--   and do not cross the layer line, so the filled ratio is not expected to be higher.
--   Confirm by breaking an ASA-GF warp coupon across its layers.
-- Shrinkage (no Material field; recorded here): not published for ASA-GF; unfilled ASA
--   moulds at about 0.4-0.7 % and glass fill lowers it (UNVERIFIED, generic). The
--   warp coupon is the check.
-- clearance 0.20-0.30 as ASA (tripo3d.ai, secondary), UNVERIFIED for the filled grade.
let T = ../types/package.dhall

in  { name = "ASA-GF"
    , process = T.Process.Fdm
    , tensile_xy_mpa = 46.0
    , z_ratio = 0.3
    , modulus_gpa = 2.83
    , density_g_cm3 = 1.08
    , hdt_c = 88.0
    , clearance_per_side_mm = 0.25
    , kerf_mm = None Double
    , source = "RaccoonWorks ASA-GF product page https://3dimensionally.com/shop/raccoonworks-asa-gf-filament-1-75mm-1kg (read 2026-10-20, no TDS PDF: E 2826 +/- 56 MPa, tensile at break 46 MPa, elongation 2.43, flexural 69 MPa / 2860 MPa, HDT 88 C @0.45 MPa and 84 C @1.8 MPa, Vicat 98 C, Tg 101 C, density 1.08 ISO 1183; orientation not stated, taken as XY); cross-check Spectrum ASA-X GF10 TDS https://spectrumfilaments.com/wp-content/uploads/2023/11/en_tds_spectrum_asax_x_gf10.pdf (55 MPa, 2550 MPa, HDT 100 C, 1.11); z_ratio 0.30 design knock-down UNVERIFIED (unfilled ASA 0.29: https://www.cnckitchen.com/blog/comparing-pla-petg-amp-asa-feat-prusament ); shrinkage unpublished, generic ASA 0.4-0.7 % lowered by glass fill UNVERIFIED; clearance 0.20-0.30 (tripo3d.ai, secondary)"
    }
    : T.Material
