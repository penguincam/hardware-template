-- Clearance holes and nut traps. Units: mm.
-- ISO 273 series: fine (H12), medium/normal (H13), coarse (H14). Values from secondary charts
-- (ISO text is paywalled): https://www.engreference.com/fasteners/iso-273 ,
-- https://mechcodex.com/reference/metric-clearance-hole-sizes
-- FDM: printed vertical holes shrink ~0.1-0.2; prefer `normal` and print a gauge.
let Clearance = { thread : Text, fine : Double, normal : Double, coarse : Double }

let Nut = { thread : Text, af : Double, height : Double }

let iso273 =
      { m2 = { thread = "M2", fine = 2.2, normal = 2.4, coarse = 2.6 } : Clearance
      , m2_5 = { thread = "M2.5", fine = 2.7, normal = 2.9, coarse = 3.1 } : Clearance
      , m3 = { thread = "M3", fine = 3.2, normal = 3.4, coarse = 3.6 } : Clearance
      , m4 = { thread = "M4", fine = 4.3, normal = 4.5, coarse = 4.8 } : Clearance
      , m5 = { thread = "M5", fine = 5.3, normal = 5.5, coarse = 5.8 } : Clearance
      , m6 = { thread = "M6", fine = 6.4, normal = 6.6, coarse = 7.0 } : Clearance
      , source = "ISO 273 via https://www.engreference.com/fasteners/iso-273 (secondary)"
      }

let unc =
      { n6_32 =
          { thread = "6-32 UNC", fine = 3.66, normal = 3.80, coarse = 3.97 } : Clearance
      , n6_32_source = "close #27 (0.1440 in), free #25 (0.1495 in): https://www.mform.com/tap-drill-chart/ ; coarse 5/32 in UNVERIFIED"
      , n6_32_nut = { thread = "6-32 UNC", af = 7.94, height = 2.78 } : Nut
      , n6_32_nut_source = "UNVERIFIED (ASME B18.2.2 from memory: 5/16 in AF, 7/64 in thick)"
      }

let iso4032 =
      { m2 = { thread = "M2", af = 4.0, height = 1.6 } : Nut
      , m2_5 = { thread = "M2.5", af = 5.0, height = 2.0 } : Nut
      , m3 = { thread = "M3", af = 5.5, height = 2.4 } : Nut
      , m4 = { thread = "M4", af = 7.0, height = 3.2 } : Nut
      , m5 = { thread = "M5", af = 8.0, height = 4.7 } : Nut
      , source = "ISO 4032 max dims via https://www.fasteners.eu/standards/iso/4032/"
      }

let nut_trap =
      { af_clearance = 0.2
      , depth_extra = 0.3
      , note = "Trap AF = nut AF + 0.2 (FDM, per side ~0.1); depth = nut height + 0.3; orient flats parallel to the bed. Design rule, verify on the coupon."
      }

-- Self-tapping (thread-forming) pilots for machine screws driven straight into printed bosses
-- (tools/fab/features.py pilot_boss). CAD diameter of a vertical hole, no bias. Only coupon-proven
-- rows live here; add one per screw after a pilot ladder coupon.
let SelfTap = { thread : Text, pilot : Double, ladder : List Double, depth_min : Double, source : Text }

let self_tap =
      { n6_32 =
            { thread = "6-32 UNC"
            , pilot = 2.6
            , ladder = [ 2.5, 2.6, 2.7, 2.8 ]
            , depth_min = 6.0
            , source = "Coupon-proven (reported): one printed fit coupon in PLA, vertical holes, best pilot 2.6 on the 2.5-2.8 ladder. Other materials (ASA-GF, PETG) UNVERIFIED: drive a screw into a coupon first. depth_min is a design floor (about 2 x the 3.5 mm major diameter), UNVERIFIED."
            }
          : SelfTap
      }

in  { iso273, unc, iso4032, nut_trap, self_tap }
