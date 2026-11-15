-- 1.5mm aluminium 5052-H32. Units per ssot/types/Material.dhall (MPa, GPa, degC, mm). Needs a FIBER laser (or send out); a CO2 hobby laser will not cut it.
let T = ../types/package.dhall

in  { name = "1.5mm aluminium 5052-H32"
    , process = T.Process.Laser
    , tensile_xy_mpa = 228.0
    , z_ratio = 1.0
    , modulus_gpa = 70.3
    , density_g_cm3 = 2.68
    , hdt_c = 150.0
    , clearance_per_side_mm = 0.1
    , kerf_mm = Some 0.15
    , source = "5052-H32 UTS 228 MPa, E 70.3 GPa (UNVERIFIED, from memory of MatWeb 5052-H32 https://www.matweb.com ); kerf ~0.1-0.2 fiber UNVERIFIED; hdt field is a service-temperature placeholder; density g/cm3: UNVERIFIED 5052 2.68"
    }
    : T.Material
