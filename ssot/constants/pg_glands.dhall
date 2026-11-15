-- PG (Panzergewinde, DIN 40430) and metric cable glands. Units: mm.
-- thread_od: nominal major diameter. hole: clearance hole for a gland held by a locknut.
-- clamp: cable OD range the seal accepts (typical nylon glands; brands differ, check the bag).
-- Hole sizes vary between catalogues by ~0.5 mm: print a gauge (or check the maker's drawing) first.
let Gland =
      { name : Text
      , thread_od : Double
      , pitch : Double
      , hole : Double
      , clamp_min : Double
      , clamp_max : Double
      , source : Text
      }

let wiska = "Wiska cable gland catalogue https://www.wiska.com/en/30/cat/1917/cable-glands/ (thread OD, clamp)"

let mbt = "metric-bolt-torque.com https://www.metric-bolt-torque.com/metric-thread/cable-gland-sizes/ (hole)"

in  { schema = "Gland"
    , pg7 =
          { name = "PG7", thread_od = 12.5, pitch = 1.27, hole = 12.8
          , clamp_min = 3.0, clamp_max = 6.0, source = "${wiska}; ${mbt}" }
        : Gland
    , pg9 =
          { name = "PG9", thread_od = 15.2, pitch = 1.41, hole = 15.5
          , clamp_min = 4.0, clamp_max = 8.0
          , source = "${wiska}; ${mbt}; difvan size chart. Tapped alternative: 13.5 drill + M15x1.5 tap (vegetronix.com/Products/Boxes/CABLE-GLAND-PG9/). A fit coupon of one bought PG9 gland (reported) fitted at a 16.0 printed hole: print a ladder for your gland." }
        : Gland
    , pg11 =
          { name = "PG11", thread_od = 18.6, pitch = 1.41, hole = 18.9
          , clamp_min = 5.0, clamp_max = 10.0, source = "${wiska}; ${mbt}" }
        : Gland
    , pg13_5 =
          { name = "PG13.5", thread_od = 20.4, pitch = 1.41, hole = 20.7
          , clamp_min = 6.0, clamp_max = 12.0, source = "${wiska}; ${mbt}" }
        : Gland
    , pg16 =
          { name = "PG16", thread_od = 22.5, pitch = 1.41, hole = 22.8
          , clamp_min = 8.0, clamp_max = 14.0
          , source = "${wiska}; ${mbt}; some vendors quote 10-14 clamp (goswitchgear.com/pg-cable-gland-guide/)" }
        : Gland
    , m20 =
          { name = "M20x1.5", thread_od = 20.0, pitch = 1.5, hole = 20.5
          , clamp_min = 6.0, clamp_max = 12.0
          , source = "UNVERIFIED typical nylon M20x1.5 gland (hole 20.5, clamp 6-12 per common catalogues). PG and metric threads are not interchangeable: verchilconnect.com/cable-gland-size-chart/" }
        : Gland
    , locknut_note =
        "Hex AF, thread length and locknut thickness are not published for generic glands: measure before CAD (typical PG9 nylon ~19-20 AF, ~8 thread, ~5 locknut, unverified)."
    }
