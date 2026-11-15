"""Assert a part's bounding box fits named printers' build volumes (bed_fit_test).

Usage:
  bed_fit.py --report part.report.json --constants ssot/generated/constants.json \
      --printer example_large --printer example_small [--margin 5] [--orientation as_built|any|xzy]

The bbox comes from the cad_part JSON report (bbox_mm.size, mm). Printer
volumes come from ssot/constants/printers.dhall rendered to
ssot/generated/constants.json (printers.<slug>.x/y/z).

--margin M     mm kept free on each side in X and Y (2*M total) and M on top.
--orientation  as_built: the exported orientation only (Voron rule: STLs ship
               in print orientation); any: any of the 6 axis-aligned
               orientations (axis permutations); or a permutation such as
               "xzy" naming which part axis lies along printer X, Y, Z.
Prints JSON; exit 1 when any printer does not fit. Stdlib only.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

AXES = "xyz"


def orientations(spec: str) -> list[str]:
    if spec == "as_built":
        return ["xyz"]
    if spec == "any":
        return ["".join(p) for p in itertools.permutations(AXES)]
    if sorted(spec) != sorted(AXES):
        raise SystemExit(f"bad --orientation {spec!r}: as_built, any, or a permutation of xyz")
    return [spec]


def fit(size: list[float], bed: tuple[float, float, float], margin: float, spec: str) -> dict:
    limit = (bed[0] - 2 * margin, bed[1] - 2 * margin, bed[2] - margin)
    # First fitting orientation wins (as-built "xyz" is tried first); if none
    # fits, report the closest miss.
    best = None
    for o in orientations(spec):
        dims = [size[AXES.index(c)] for c in o]
        slack = [round(limit[k] - dims[k], 3) for k in range(3)]
        cand = {"orientation": o, "dims_mm": [round(d, 3) for d in dims], "slack_mm": slack,
                "fits": min(slack) >= 0}
        if cand["fits"]:
            return cand
        if best is None or min(slack) > min(best["slack_mm"]):
            best = cand
    return best


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", required=True)
    ap.add_argument("--constants", required=True)
    ap.add_argument("--printer", action="append", required=True)
    ap.add_argument("--margin", type=float, default=5.0)
    ap.add_argument("--orientation", default="as_built")
    a = ap.parse_args(argv)

    rep = json.loads(Path(a.report).read_text())
    size = rep["bbox_mm"]["size"]
    printers = json.loads(Path(a.constants).read_text())["printers"]
    out = {"bbox_size_mm": size, "margin_mm": a.margin, "orientation": a.orientation, "printers": {}}
    ok = True
    for slug in a.printer:
        pr = printers.get(slug)
        if not pr or not all(k in pr for k in AXES):
            raise SystemExit(f"printer {slug!r} has no x/y/z build volume in constants.json")
        bed = (float(pr["x"]), float(pr["y"]), float(pr["z"]))
        res = fit(size, bed, a.margin, a.orientation)
        res["bed_mm"] = list(bed)
        out["printers"][slug] = res
        ok = ok and res["fits"]
    out["ok"] = ok
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")
    if not ok:
        bad = [s for s, r in out["printers"].items() if not r["fits"]]
        print(f"FAIL: does not fit {bad} with {a.margin} mm margin ({a.orientation})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
