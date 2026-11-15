-- Local helpers. Remote and env imports are forbidden in ssot/ (import gate in
-- tools/ssot/lib.sh), so the few Prelude functions the renderers need live here.
let T = ../types/package.dhall

let map =
      \(a : Type) ->
      \(b : Type) ->
      \(f : a -> b) ->
      \(xs : List a) ->
        List/fold
          a
          xs
          (List b)
          (\(x : a) -> \(acc : List b) -> [ f x ] # acc)
          ([] : List b)

let showProcess =
      \(p : T.Process) -> merge { Fdm = "fdm", Laser = "laser", Cnc = "cnc" } p

in  { map, showProcess }
