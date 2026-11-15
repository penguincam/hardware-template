-- Parameters of the example sealed box. Units are in each name. Every value carries a tag:
--   DESIGN      a choice made for this example
--   CATALOGUE   read from ssot/constants (its own source and UNVERIFIED flags apply)
--   UNVERIFIED  needs a coupon before it is trusted
-- Nothing in this mod is VERIFIED: no part of it has been printed.
let inserts = ../../../ssot/constants/inserts.dhall

let glands = ../../../ssot/constants/pg_glands.dhall

let fasteners = ../../../ssot/constants/fasteners.dhall

in  { -- Cavity. DESIGN.
      inner_w_mm = 80.0
    , inner_d_mm = 60.0
    , inner_h_mm = 40.0
    , inner_r_mm = 3.0
    , -- Shell. DESIGN: a 5 mm wall leaves room for the gasket groove on the rim.
      wall_mm = 5.0
    , floor_mm = 3.0
    , -- Corner pillars that carry the lid screws outside the gasket ring. DESIGN.
      pillar_od_mm = 9.0
    , pillar_ear_mm = 2.0
    , -- M3 heat-set inserts in the pillars. CATALOGUE (inserts.m3).
      insert_hole_mm = inserts.m3.hole
    , insert_depth_mm = inserts.m3.depth
    , -- Rim gasket: groove in the box rim, TPU bead printed flat and pressed in.
      -- DESIGN, UNVERIFIED: print a groove and bead coupon first.
      gasket_inset_mm = 2.5
    , groove_w_mm = 2.0
    , groove_depth_mm = 1.5
    , bead_w_mm = 1.2
    , bead_proud_mm = 0.6
    , -- Cable gland in the front wall. Hole CATALOGUE (pg_glands.pg9), UNVERIFIED for any
      -- one gland: print a hole ladder. Height and cap DESIGN.
      gland_hole_mm = glands.pg9.hole
    , gland_clamp_min_mm = glands.pg9.clamp_min
    , gland_clamp_max_mm = glands.pg9.clamp_max
    , gland_z_mm = 18.0
    , gland_cap_mm = 0.6
    , cable_od_mm = 6.0
    , -- Lid. Thickness DESIGN, screw clearance CATALOGUE (fasteners.iso273.m3.normal).
      lid_t_mm = 4.0
    , lid_hole_mm = fasteners.iso273.m3.normal
    }
