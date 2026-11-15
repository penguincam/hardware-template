"""Export a build123d 2D sheet part to a layered, mm-unit DXF (laser_sheet macro).

    laser_export.py --module CAD/part.py --fn build_sheet --params params.json \
        --out out/part.dxf [--report out/part.dxf.json] \
        [--materials ssot/generated/materials.json --material acrylic3_cast --kerf-comp]
        [--constants ssot/generated/constants.json --vendor example_service --sku ACRYLIC-3.0]

The module's builder (default `build_sheet(params)`) returns either one 2D
shape (Face or Sketch; everything goes on CUT) or a dict of layer name to
shape, using the layers CUT (red), SCORE (blue), ENGRAVE (green).
Everything is translated so the CUT extents start at (margin, margin), in +X/+Y.
--kerf-comp offsets the CUT shape by kerf_mm/2 of the material (outline out,
holes in); kerf is applied once, so leave it off when the laser software
compensates. The report lists extents, CUT area and path lengths per layer.

--vendor picks a LaserVendor record (constants.json laser_vendors.<slug>) and
lets it decide kerf: a vendor that compensates kerf itself (kerf_in_cad false,
most cut services) gets nominal geometry and refuses --kerf-comp; a shop laser
(kerf_in_cad true) gets CUT offset by the SKU kerf_mm or the vendor kerf_mm.
Layers the vendor does not take (a cut service: everything but CUT) are dropped
and listed in the report as dropped_layers.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

LAYERS = {"CUT": "RED", "SCORE": "BLUE", "ENGRAVE": "GREEN"}


def load_module(path: str):
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(path).absolute().parent))  # sibling helpers (declare them in data)
    spec.loader.exec_module(mod)
    return mod


def vendor_profile(constants: str | None, slug: str, sku: str | None) -> tuple[dict, dict | None]:
    """Return (vendor, sku row or None) from constants.json laser_vendors."""
    if not constants:
        raise SystemExit("--vendor needs --constants ssot/generated/constants.json")
    vendors = json.loads(Path(constants).read_text()).get("laser_vendors", {})
    if slug not in vendors:
        raise SystemExit(f"vendor {slug!r} not in laser_vendors (have {sorted(vendors)})")
    v = vendors[slug]
    if sku is None:
        return v, None
    rows = [r for r in v.get("skus", []) if r["sku"] == sku]
    if not rows:
        raise SystemExit(f"sku {sku!r} not in vendor {slug} (have {[r['sku'] for r in v.get('skus', [])]})")
    return v, rows[0]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--module", required=True)
    ap.add_argument("--fn", default="build_sheet")
    ap.add_argument("--params", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report")
    ap.add_argument("--materials")
    ap.add_argument("--material")
    ap.add_argument("--kerf-comp", action="store_true")
    ap.add_argument("--constants", help="ssot/generated/constants.json (laser_vendors)")
    ap.add_argument("--vendor", help="laser_vendors slug; decides kerf and layers")
    ap.add_argument("--sku", help="vendor SKU (recorded; its kerf_mm overrides the vendor kerf)")
    ap.add_argument("--margin", type=float, default=0.0, help="mm from origin to CUT extents")
    a = ap.parse_args(argv)

    from build123d import ExportDXF, Kind, Pos, Unit, offset
    from build123d.exporters import ColorIndex

    params = json.loads(Path(a.params).read_text())
    shapes = getattr(load_module(a.module), a.fn)(params)
    if not isinstance(shapes, dict):
        shapes = {"CUT": shapes}
    unknown = sorted(set(shapes) - set(LAYERS))
    if unknown or "CUT" not in shapes:
        raise SystemExit(f"layers must include CUT and be within {sorted(LAYERS)}; got {sorted(shapes)}")

    kerf = None
    if a.material:
        table = json.loads(Path(a.materials).read_text())
        kerf = table[a.material].get("kerf_mm")
    vendor, sku, dropped = None, None, []
    if a.vendor:
        vendor, sku = vendor_profile(a.constants, a.vendor, a.sku)
        if vendor["kerf_in_cad"]:
            kerf = (sku or {}).get("kerf_mm") or vendor["kerf_mm"]
            if not kerf or kerf <= 0:
                raise SystemExit(f"vendor {a.vendor!r} compensates kerf in CAD but has no kerf_mm; "
                                 "cut a kerf coupon and record it in the profile")
            a.kerf_comp = True
        else:
            if a.kerf_comp:
                raise SystemExit(f"vendor {a.vendor!r} compensates kerf itself; draw nominal geometry (drop kerf_comp)")
            kerf = 0.0
        allowed = {s.upper() for s in vendor["layers"]}
        dropped = sorted(k for k in shapes if k not in allowed)
        for k in dropped:
            del shapes[k]
            sys.stderr.write(f"laser_export: dropped layer {k}: vendor {a.vendor} takes only {sorted(allowed)}\n")
    if a.kerf_comp:
        if kerf is None:
            raise SystemExit(f"--kerf-comp: material {a.material!r} has no kerf_mm")
        shapes["CUT"] = offset(shapes["CUT"], amount=kerf / 2.0, kind=Kind.INTERSECTION)

    bb = shapes["CUT"].bounding_box()
    shift = Pos(a.margin - bb.min.X, a.margin - bb.min.Y, -bb.min.Z)
    shapes = {k: shift * v for k, v in shapes.items()}

    exp = ExportDXF(unit=Unit.MM)
    for name in shapes:
        exp.add_layer(name, color=getattr(ColorIndex, LAYERS[name]))
    for name, shape in shapes.items():
        exp.add_shape(shape, layer=name)
    exp.write(a.out)

    cbb = shapes["CUT"].bounding_box()
    rep = {
        "file": Path(a.out).name,
        "extents_mm": [round(cbb.size.X, 3), round(cbb.size.Y, 3)],
        "cut_area_mm2": round(sum(f.area for f in shapes["CUT"].faces()), 3),
        "path_length_mm": {k: round(sum(e.length for e in v.edges()), 3) for k, v in shapes.items()},
        "material": a.material,
        "kerf_mm": kerf,
        "kerf_comp_in_cad": bool(a.kerf_comp),
        "vendor": a.vendor,
        "sku": a.sku,
        "t_mm": sku["t_mm"] if sku else None,
        "dropped_layers": dropped,
    }
    text = json.dumps(rep, indent=2, sort_keys=True) + "\n"
    if a.report:
        Path(a.report).write_text(text)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
