-- Heat-set threaded inserts, one product line: CNC Kitchen "standard" brass.
-- Units: mm. Read by tools/fab/features.py (insert_boss) through
-- ssot/generated/constants.json.
-- length L, od D1 (insert OD), hole D3 (catalog hole), min_wall W: catalog.
-- depth: blind hole depth = L + 1. boss_od: minimum boss OD = D3 + 2 W.
-- CAD hole = hole + printed_hole_bias. Printed holes shrink: print the insert
-- gauge on the coupon.
let Insert =
      { thread : Text
      , length : Double
      , od : Double
      , hole : Double
      , min_wall : Double
      , depth : Double
      , boss_od : Double
      , source : Text
      }

let catalog = "CNC Kitchen catalog table (L, D1, D3, W) via https://www.3djake.uk/cnc-kitchen/threaded-inserts-m3-standard (re-verify against the current listing)"

let cnck = "CNC Kitchen tips https://www.cnckitchen.com/blog/tips-and-tricks-for-heat-set-inserts (blind hole ~1 mm deeper than insert, straight hole)"

let ruthex = "cross-check: Ruthex lid table https://www.printables.com/model/707184-ruthex-practice-and-measurement-tools"

in  { schema = "Insert"
    , brand = "CNC Kitchen standard"
    , m2 =
          { thread = "M2", length = 3.0, od = 3.6, hole = 3.2, min_wall = 1.3, depth = 4.0, boss_od = 5.8
          , source = "${catalog}; ${cnck}; Ruthex M2 is a different part (L 4.0, hole 3.2)" }
        : Insert
    , m2_5 =
          { thread = "M2.5", length = 4.0, od = 4.6, hole = 4.0, min_wall = 1.6, depth = 5.0, boss_od = 7.2
          , source = "${catalog}; ${cnck}" }
        : Insert
    , m3 =
          { thread = "M3", length = 5.7, od = 4.6, hole = 4.0, min_wall = 1.6, depth = 6.7, boss_od = 7.2
          , source = "${catalog}; ${cnck}; ${ruthex} (same L and hole); CNC Kitchen datasheet check (4.2 CAD looked best printed) https://www.cnckitchen.com/blog/are-our-heat-set-insert-datasheets-wrong" }
        : Insert
    , m3_short =
          { thread = "M3-short", length = 3.0, od = 4.6, hole = 4.0, min_wall = 1.6, depth = 4.0, boss_od = 7.2
          , source = "${catalog}; ${cnck}" }
        : Insert
    , m3_voron =
          { thread = "M3-voron", length = 4.0, od = 5.0, hole = 4.4, min_wall = 1.3, depth = 5.0, boss_od = 7.0
          , source = "${catalog}; ${cnck}" }
        : Insert
    , m4 =
          { thread = "M4", length = 8.1, od = 6.3, hole = 5.6, min_wall = 2.1, depth = 9.1, boss_od = 9.8
          , source = "${catalog}; ${ruthex} (same L and hole); length per Prusa CNC Kitchen set https://www.prusa3d.com/product/threaded-inserts-set-standard-200-pcs/" }
        : Insert
    , m4_short =
          { thread = "M4-short", length = 4.0, od = 6.3, hole = 5.6, min_wall = 2.1, depth = 5.0, boss_od = 9.8
          , source = "${catalog}; ${cnck}" }
        : Insert
    , m5 =
          { thread = "M5", length = 9.5, od = 7.1, hole = 6.4, min_wall = 2.6, depth = 10.5, boss_od = 11.6
          , source = "${catalog}; ${ruthex} (same L and hole); length per Prusa CNC Kitchen set" }
        : Insert
    , m5_short =
          { thread = "M5-short", length = 5.8, od = 7.1, hole = 6.4, min_wall = 2.6, depth = 6.8, boss_od = 11.6
          , source = "${catalog}; ${cnck}" }
        : Insert
    , m6 =
          { thread = "M6", length = 12.7, od = 8.7, hole = 8.0, min_wall = 3.3, depth = 13.7, boss_od = 14.6
          , source = "${catalog}; ${cnck}" }
        : Insert
    , printed_hole_bias = 0.2
    , printed_hole_bias_note = "CNC Kitchen found 4.2 mm CAD best for M3 on printed samples; add +0.2 to hole if inserts sink too tight (verify per printer/material)"
    , install_temp_c = { pla = 225, petg = 245, abs = 265, pctg = 245, asa = 265, rule = "10-20 C above print temp (CNC Kitchen); pctg and asa by analogy to petg and abs (UNVERIFIED)" }
    }
