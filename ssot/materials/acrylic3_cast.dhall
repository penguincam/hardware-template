-- 3mm cast acrylic (PMMA). Units per ssot/types/Material.dhall (MPa, GPa, degC, mm). Never press-fit acrylic: it cracks. Clearance fits only.
let T = ../types/package.dhall

in  { name = "3mm cast acrylic (PMMA)"
    , process = T.Process.Laser
    , tensile_xy_mpa = 70.0
    , z_ratio = 1.0
    , modulus_gpa = 3.2
    , density_g_cm3 = 1.19
    , hdt_c = 95.0
    , clearance_per_side_mm = 0.2
    , kerf_mm = Some 0.15
    , source = "kerf 0.12-0.22 CO2 (0.15 mid): https://box-studio.cc/blog/2026-05-en-kerf-reference-table-by-machine ; clearance 0.15-0.3: https://1cutfab.com/blogs/news/designing-notches-tabs-and-slots-for-laser-cut-assembly ; PMMA tensile ~70, modulus ~3.2, HDT ~95 UNVERIFIED generic; density g/cm3: UNVERIFIED cast PMMA 1.18-1.19"
    }
    : T.Material
