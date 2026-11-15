"""Export a build123d part module to STEP, binary STL, 3MF and a JSON report.

Used by the cad_part macro (defs.bzl); also runnable by hand:

    cad_export.py --module CAD/part.py --params params.json \
        --materials ssot/generated/materials.json --material petg \
        --step out/part.step --stl out/part.stl --3mf out/part.3mf \
        --report out/part.report.json

The module must define `build(params: dict) -> Part` (pure, mm, print
orientation). It is loaded by file path, so the module's own CLI is not used.
The report holds validity, solid count, bbox (min, max, size), B-rep volume
and solid mass at the material density (100 % infill upper bound; the slicer
gives the real grams). Exit 1 when the part is invalid or has no solid.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

STL_TOL = 0.01  # mm linear deflection; matches the committed-STL convention
STL_ANG = 0.1  # rad angular deflection


def expose_repo_tools(module_path: str) -> None:
    """Make `from tools.fab import coupon` work in a part module.

    Under Bazel the exporter's runfiles hold a regular `tools` package (rules_python
    writes tools/__init__.py and tools/bazel/__init__.py) with no fab in it, so the
    import resolved `tools` there and failed. The mod lists //tools/fab:lib as data,
    which stages tools/fab in the execroot (the genrule's working directory): add that
    tools/ directory to the package path. Run by hand from the repo root, the root is
    put on sys.path instead.
    """
    roots = [Path.cwd(), *Path(module_path).absolute().parents]
    root = next((r for r in roots if (r / "tools" / "fab" / "__init__.py").is_file()), None)
    if root is None:
        return
    if str(root) not in sys.path:
        sys.path.append(str(root))
    try:
        import tools  # noqa: PLC0415
    except ImportError:
        return
    pkg_path = getattr(tools, "__path__", None)
    tools_dir = str(root / "tools")
    if pkg_path is not None and tools_dir not in list(pkg_path):
        pkg_path.append(tools_dir)


def load_module(path: str):
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(path).absolute().parent))  # sibling helpers (declare them in data)
    expose_repo_tools(path)
    spec.loader.exec_module(mod)
    return mod


def report(part, material: dict | None, material_key: str | None) -> dict:
    bb = part.bounding_box()
    vol = float(part.volume)
    rep = {
        "valid": bool(part.is_valid),
        "solids": len(part.solids()),
        "volume_mm3": round(vol, 3),
        "bbox_mm": {
            "min": [round(v, 3) for v in (bb.min.X, bb.min.Y, bb.min.Z)],
            "max": [round(v, 3) for v in (bb.max.X, bb.max.Y, bb.max.Z)],
            "size": [round(v, 3) for v in (bb.size.X, bb.size.Y, bb.size.Z)],
        },
    }
    if material is not None:
        rho = float(material["density_g_cm3"])
        rep["material"] = {"key": material_key, "name": material["name"], "density_g_cm3": rho}
        # mm^3 -> cm^3 is 1e-3; solid mass, not sliced mass.
        rep["mass_solid_g"] = round(vol * 1e-3 * rho, 3)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--module", required=True, help="build123d part module with build(params)")
    ap.add_argument("--fn", default="build", help="builder function name (default build)")
    ap.add_argument("--params", required=True, help="params.json rendered from params.dhall")
    ap.add_argument("--materials", help="ssot/generated/materials.json")
    ap.add_argument("--material", help="key in materials.json (petg, pla, ...)")
    ap.add_argument("--step")
    ap.add_argument("--stl")
    ap.add_argument("--3mf", dest="threemf")
    ap.add_argument("--report")
    a = ap.parse_args(argv)

    from build123d import Mesher, export_step, export_stl

    params = json.loads(Path(a.params).read_text())
    part = getattr(load_module(a.module), a.fn)(params)
    material = None
    if a.material:
        if not a.materials:
            raise SystemExit("--material needs --materials")
        table = json.loads(Path(a.materials).read_text())
        if a.material not in table:
            raise SystemExit(f"unknown material {a.material!r}; have {sorted(table)}")
        material = table[a.material]
    rep = report(part, material, a.material)

    if a.step:
        export_step(part, a.step)
    if a.stl:
        export_stl(part, a.stl, tolerance=STL_TOL, angular_tolerance=STL_ANG)
    if a.threemf:
        mesher = Mesher()
        mesher.add_shape(part, linear_deflection=STL_TOL, angular_deflection=STL_ANG)
        mesher.write(a.threemf)
    text = json.dumps(rep, indent=2, sort_keys=True) + "\n"
    if a.report:
        Path(a.report).write_text(text)
    sys.stdout.write(text)
    return 0 if rep["valid"] and rep["solids"] >= 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
