-- PA-CF. Units per ssot/types/Material.dhall (MPa, GPa, degC, mm). Stiff brackets/rack ears, not drop-prone shells (CF lowers impact).
let T = ../types/package.dhall

in  { name = "PA-CF"
    , process = T.Process.Fdm
    , tensile_xy_mpa = 42.0
    , z_ratio = 0.6
    , modulus_gpa = 2.5
    , density_g_cm3 = 1.15
    , hdt_c = 120.0
    , clearance_per_side_mm = 0.2
    , kerf_mm = None Double
    , source = "Prusament PA11 CF TDS (Scribd copy, horizontal yield 42, modulus 2.5; HDT 192 @0.45 conflicts, conservative 120 used: Prusa page quotes up to 122.5 C after annealing) https://prusament.com/materials/prusament-pa11/ ; z_ratio UNVERIFIED; dry before printing; density g/cm3: UNVERIFIED PA11-CF ~1.15"
    }
    : T.Material
