-- params.json / params.csv from a mod's params.dhall (a flat record of Double).
-- Call with `toMap`, which needs no type annotation for a non-empty record:
--   (./ssot/render/params.dhall).rows (toMap ./mods/c/m/params.dhall)
-- `json` is the record itself (dhall-to-json renders it as an object).
-- CSV rows use Fusion's layout `Name,Unit,Expression,Value,Comments,Favorite`;
-- Dhall cannot inspect Text, so the unit is derived from the name suffix by
-- ssot_params_csv in tools/ssot/lib.sh (jq): _mm mm, _cm cm, _in in, _deg deg,
-- _mpa MPa, _n N, _g g, _count and _flag unitless; any other name is an error.
let Entry = { mapKey : Text, mapValue : Double }

in  { Entry
    , rows =
        \(params : List Entry) ->
          List/fold
            Entry
            params
            (List { name : Text, value : Double })
            ( \(e : Entry) ->
              \(acc : List { name : Text, value : Double }) ->
                [ { name = e.mapKey, value = e.mapValue } ] # acc
            )
            ([] : List { name : Text, value : Double })
    }
