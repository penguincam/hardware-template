-- 3mm birch plywood. Units per ssot/types/Material.dhall (MPa, GPa, degC, mm). Measure sheet thickness (often 2.8-3.1) and kerf per machine.
let T = ../types/package.dhall

in  { name = "3mm birch plywood"
    , process = T.Process.Laser
    , tensile_xy_mpa = 40.0
    , z_ratio = 1.0
    , modulus_gpa = 7.0
    , density_g_cm3 = 0.68
    , hdt_c = 100.0
    , clearance_per_side_mm = 0.1
    , kerf_mm = Some 0.18
    , source = "kerf 0.15-0.25 CO2 (0.18 mid): https://box-studio.cc/blog/2026-05-en-kerf-reference-table-by-machine and https://engraverhq.com/guides/laser-cutter-kerf/ ; press fit +0.1-0.2 interference (clearance field is the magnitude) https://1cutfab.com/blogs/news/designing-notches-tabs-and-slots-for-laser-cut-assembly ; tensile/modulus/HDT UNVERIFIED placeholders (wood: no HDT; z_ratio n/a = 1.0); density g/cm3: UNVERIFIED birch plywood 0.65-0.70"
    }
    : T.Material
