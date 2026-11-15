#!/usr/bin/env python3
"""Build a sheet-part quote package for a mod from its sheet_order.dhall.

Usage:
  python3 sheet_quote.py mods/<creator>/<mod>                spec: <mod>/sheet_order.dhall, out: <mod>/order/
  python3 sheet_quote.py MOD --out out/order/<mod>            another output directory
  python3 sheet_quote.py MOD --spec-json spec.json            a pre-rendered spec (tests; no dhall needed)
  python3 sheet_quote.py MOD --check                          validate only, write nothing
  python3 sheet_quote.py MOD --verify                         rebuild in a temp dir and fail if the
                                                              committed package differs (stale)

Nothing here orders, uploads or logs in: the package is for a person to upload by hand. For
every part in the spec (ssot/types/SheetOrder.dhall) it

  1. lints the DXF with dxf_lint.py against the vendor and SKU (and the finish window, if any);
  2. checks the order-level rules the DXF alone cannot show (vendor profile values):
       tapped     thread is in tap_drills, sheet >= tap_min_t_mm, the part fits the tapping
                  window, and the DXF has >= count holes at the tap drill (+/- 0.06 mm)
       hardware   the part fits the hardware window, >= count holes of hole_mm, and every such
                  hole centre is >= k_mm from any other cut edge (catalogue K)
       countersink sheet >= countersink_min_t_mm and the part fits the countersink window
       bends      the SKU has bend data, a STEP is given and exists, the part fits the bending window
       finish     anodize only on aluminium; powder coat only on metal SKUs
  3. writes <out>/DXF/<part>.dxf (one part per file), parts.csv (material, thickness, finish, ops
     per part), bom.csv, lint/<part>.json, order.json, spec.json (the rendered spec, so Bazel can
     re-verify without dhall) and checklist.md (machine checks ticked with evidence, manual steps
     left open).

Exit 1 (and write nothing) when any part has an error; 0 otherwise. Output is deterministic (no
timestamps), so a committed package only changes when the part or the spec does.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).absolute().parent  # not resolve(): keep Bazel runfiles paths
ROOT = HERE.parents[1]
DEFAULT_CONSTANTS = ROOT / "ssot" / "generated" / "constants.json"
MATCH_MM = 0.06  # tap drill / hardware hole match tolerance (vendors round drawn sizes differently)

_spec = importlib.util.spec_from_file_location("dxf_lint", HERE / "dxf_lint.py")
L = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(L)

METALS = ("alumin", "steel", "stainless", "304", "316", "brass", "copper", "titanium", "chromoly")


def load_spec(mod: Path, spec_json: str | None) -> dict:
    if spec_json:
        return json.loads(Path(spec_json).read_text())
    f = mod / "sheet_order.dhall"
    if not f.is_file():
        raise SystemExit(f"sheet_quote: {f} not found (see ssot/types/SheetOrder.dhall)")
    r = subprocess.run(["dhall-to-json", "--file", str(f)], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"sheet_quote: dhall-to-json {f} failed:\n{r.stderr}")
    return json.loads(r.stdout)


def window(vendor: dict, process: str) -> dict | None:
    for w in vendor.get("finish_windows", []):
        if w["process"] == process:
            return w
    return None


def _fits_window(ext, w: dict | None) -> bool:
    if ext is None or w is None:
        return True
    a, b = ext[2] - ext[0], ext[3] - ext[1]
    return L._fits(a, b, w["max_mm"], bigger=True) and L._fits(a, b, w["min_mm"], bigger=False)


def circles(dxf: str) -> tuple[list[tuple[float, float, float, int]], list]:
    """(x, y, d, index) of every circular hole (a CUT circle one level inside an outline) and the
    points of every CUT contour (outlines and holes), indexed alike."""
    import ezdxf

    cs = L.contours(ezdxf.readfile(dxf).modelspace())
    holes = [((c["bbox"][0] + c["bbox"][2]) / 2, (c["bbox"][1] + c["bbox"][3]) / 2, c["circle_d"], i)
             for i, c in enumerate(cs) if c["depth"] == 1 and c["circle_d"] is not None]
    return holes, [c["pts"] for c in cs]


def _edge_dist(x: float, y: float, contours: list, skip: int = -1) -> float:
    """Distance from (x, y) to the nearest cut edge (any contour but `skip`, the hole itself):
    the catalogue K for PEM hardware is measured to any cut edge, holes included."""
    best = math.inf
    for k, o in enumerate(contours):
        if k == skip:
            continue
        n = len(o)
        for i in range(n):
            best = min(best, L._pt_seg((x, y), o[i], o[(i + 1) % n]))
    return best


def part_checks(part: dict, rep: dict, vendor: dict, sku: dict, mod: Path) -> tuple[list[str], list[str], list[str]]:
    """(errors, warnings, evidence) for the order-level rules of one part."""
    errors: list[str] = []
    warnings: list[str] = []
    evidence: list[str] = []
    name, t, ext = part["name"], sku["t_mm"], rep.get("extents")
    holes, cuts = circles(str(mod / part["dxf"]))
    material = sku["material"].lower()
    drills = {d["thread"]: d["drill_mm"] for d in vendor.get("tap_drills", [])}

    if part["qty"] < 1:
        errors.append(f"{name}: qty must be >= 1")

    for tap in part["tapped"]:
        th = tap["thread"]
        if th not in drills:
            errors.append(f"{name}: tapped thread {th!r} not in {vendor['slug']} tap_drills {sorted(drills)}")
            continue
        n = sum(1 for _, _, d, _ in holes if abs(d - drills[th]) <= MATCH_MM)
        if n < tap["count"]:
            errors.append(f"{name}: {tap['count']} x {th} tapped but only {n} holes at the {drills[th]} mm tap drill")
        else:
            evidence.append(f"{tap['count']} x {th}: {n} holes at the {drills[th]} mm tap drill")
        if t < vendor.get("tap_min_t_mm", 0.0) - 1e-6:
            errors.append(f"{name}: {sku['sku']} t {t} below the tapping minimum {vendor['tap_min_t_mm']} mm")
        if not _fits_window(ext, window(vendor, "tapping")):
            errors.append(f"{name}: part outside the {vendor['slug']} tapping window {window(vendor, 'tapping')}")

    for hw in part["hardware"]:
        pn, k = hw["part_number"], hw["k_mm"]
        mine = [(x, y, i) for x, y, d, i in holes if abs(d - hw["hole_mm"]) <= MATCH_MM]
        if len(mine) < hw["count"]:
            errors.append(f"{name}: {hw['count']} x {pn} but only {len(mine)} holes of {hw['hole_mm']} mm")
        dist = [(x, y, _edge_dist(x, y, cuts, i)) for x, y, i in mine]
        close = [(x, y, dd) for x, y, dd in dist if dd < k - 1e-6]
        for x, y, dd in close:
            errors.append(f"{name}: {pn} hole at ({x:.2f}, {y:.2f}) is {dd:.2f} mm from the nearest cut edge, "
                          f"under catalogue K {k} mm")
        if not close and len(mine) >= hw["count"]:
            evidence.append(f"{hw['count']} x {pn}: {len(mine)} holes of {hw['hole_mm']} mm, all >= K {k} mm from any cut edge")
        if not _fits_window(ext, window(vendor, "hardware_insertion")):
            errors.append(f"{name}: part outside the {vendor['slug']} hardware window")

    if part["countersinks"] > 0:
        if t < vendor.get("countersink_min_t_mm", 0.0) - 1e-6:
            errors.append(f"{name}: {sku['sku']} t {t} below the countersink minimum {vendor['countersink_min_t_mm']} mm")
        if not _fits_window(ext, window(vendor, "countersink")):
            errors.append(f"{name}: part outside the {vendor['slug']} countersink window")

    if part["bends"] > 0:
        if not sku.get("bend"):
            errors.append(f"{name}: {sku['sku']} has no bend data at {vendor['slug']} (choose a bendable SKU)")
        step = part.get("step")
        if not step:
            errors.append(f"{name}: {part['bends']} bend(s) but no STEP; order bent parts from the STEP")
        elif not (mod / step).is_file():
            errors.append(f"{name}: STEP {step} not found in the mod")
        else:
            evidence.append(f"bent part ordered from {step} ({part['bends']} bend(s), SKU K {sku['bend']['k'] if sku.get('bend') else '?'})")
        if not _fits_window(ext, window(vendor, "bending")):
            errors.append(f"{name}: flat part outside the {vendor['slug']} bending window")
        if not part["note"]:
            warnings.append(f"{name}: bent part with no order note; state the bend direction relative to the DXF")

    fin = part.get("finish")
    if fin:
        if fin.startswith("anodize") and "alumin" not in material:
            errors.append(f"{name}: anodize needs aluminium; {sku['sku']} is {sku['material']}")
        if fin.startswith("powder_coat") and not any(m in material for m in METALS):
            errors.append(f"{name}: powder coat needs a metal SKU; {sku['sku']} is {sku['material']}")
        if fin == "powder_coat_304" and "304" not in material:
            warnings.append(f"{name}: powder_coat_304 window chosen for {sku['material']}")
        if not part.get("finish_color"):
            warnings.append(f"{name}: finish {fin} with no finish_color")
        evidence.append(f"finish {fin}: window, hang hole and min hole checked by the lint")
    return errors, warnings, evidence


def _csv(rows: list[list]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


def _fmt_ops(items: list[dict], key: str) -> str:
    return "; ".join(f"{i['count']} x {i[key]}" for i in items)


def build(mod: Path, spec: dict, constants: Path) -> dict:
    vendors = json.loads(constants.read_text())["laser_vendors"]
    if spec["vendor"] not in vendors:
        raise SystemExit(f"sheet_quote: vendor {spec['vendor']!r} not in {constants}")
    vendor = vendors[spec["vendor"]]
    parts = []
    names = [p["name"] for p in spec["parts"]]
    dup = sorted({n for n in names if names.count(n) > 1})
    top_errors = [f"duplicate part names {dup}"] if dup else []
    if not spec["parts"]:
        top_errors.append("sheet_order has no parts")
    for part in spec["parts"]:
        dxf = mod / part["dxf"]
        if not dxf.is_file():
            parts.append({"part": part, "lint": None, "errors": [f"{part['name']}: DXF {part['dxf']} not found "
                                                                 "(run just export-laser first)"], "warnings": [], "evidence": []})
            continue
        sku = L.find_sku(vendor, part["sku"])
        rep = L.lint(str(dxf), {s.upper() for s in vendor["layers"]}, None, vendor, sku, part.get("finish"))
        rep["file"] = part["dxf"]  # mod-relative, so the committed report is stable
        errs, warns, ev = part_checks(part, rep, vendor, sku, mod)
        parts.append({"part": part, "sku": sku, "lint": rep, "errors": [f"{part['name']}: {e}" for e in rep["errors"]] + errs,
                      "warnings": [f"{part['name']}: {w}" for w in rep["warnings"]] + warns, "evidence": ev})
    ok = not top_errors and all(not p["errors"] for p in parts)
    return {"vendor": vendor, "spec": spec, "parts": parts, "errors": top_errors, "ok": ok}


def write(res: dict, mod: Path, out: Path) -> list[Path]:
    vendor, spec = res["vendor"], res["spec"]
    if out.exists():
        shutil.rmtree(out)
    (out / "DXF").mkdir(parents=True)
    (out / "lint").mkdir()
    written = []
    parts_rows = [["part", "file", "qty", "vendor", "sku", "material", "process", "thickness_in", "thickness_mm",
                   "finish", "finish_color", "tapping", "hardware", "countersinks", "bends", "step",
                   "extent_x_mm", "extent_y_mm", "holes", "min_hole_mm", "lint_ok", "note"]]
    bom = [["line", "item", "kind", "qty", "per_part", "source"]]
    line = 0
    for p in res["parts"]:
        part, sku, rep = p["part"], p["sku"], p["lint"]
        dst = out / "DXF" / f"{part['name']}.dxf"
        shutil.copyfile(mod / part["dxf"], dst)
        written.append(dst)
        lj = out / "lint" / f"{part['name']}.json"
        lj.write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
        written.append(lj)
        ext = rep["extents"]
        parts_rows.append([
            part["name"], f"DXF/{part['name']}.dxf", part["qty"], vendor["slug"], sku["sku"], sku["material"],
            sku["process"], sku["t_in"], f"{sku['t_mm']:.3f}", part.get("finish") or "none", part.get("finish_color") or "",
            _fmt_ops(part["tapped"], "thread"), _fmt_ops(part["hardware"], "part_number"), part["countersinks"],
            part["bends"], part.get("step") or "", f"{ext[2] - ext[0]:.3f}", f"{ext[3] - ext[1]:.3f}",
            rep["contours"]["holes"], rep.get("min_hole_mm") if rep.get("min_hole_mm") is not None else "",
            str(rep["ok"]).lower(), part["note"]])
        line += 1
        bom.append([line, part["name"], f"sheet {sku['sku']} ({sku['material']}, {sku['t_mm']:.3f} mm)", part["qty"], 1,
                    f"{vendor['slug']} DXF/{part['name']}.dxf"])
        for tap in part["tapped"]:
            line += 1
            bom.append([line, f"tap {tap['thread']}", "operation", tap["count"] * part["qty"], tap["count"], f"{vendor['slug']} tapping"])
        for hw in part["hardware"]:
            line += 1
            bom.append([line, hw["part_number"], "hardware (vendor installed)", hw["count"] * part["qty"], hw["count"],
                        f"{vendor['slug']} hardware catalog"])
        if part["countersinks"]:
            line += 1
            bom.append([line, "countersink", "operation", part["countersinks"] * part["qty"], part["countersinks"],
                        f"{vendor['slug']} countersinking"])
        if part["bends"]:
            line += 1
            bom.append([line, "bend", "operation", part["bends"] * part["qty"], part["bends"], f"{vendor['slug']} bending"])
    for name, rows in (("parts.csv", parts_rows), ("bom.csv", bom)):
        f = out / name
        f.write_text(_csv(rows))
        written.append(f)
    summary = {
        "vendor": vendor["slug"], "mod": spec["mod"], "issue": spec.get("issue"), "ok": res["ok"],
        "parts": [{"name": p["part"]["name"], "sku": p["sku"]["sku"], "qty": p["part"]["qty"], "ok": not p["errors"],
                   "warnings": p["warnings"], "evidence": p["evidence"]} for p in res["parts"]],
    }
    f = out / "order.json"
    f.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    written.append(f)
    f = out / "spec.json"
    f.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")
    written.append(f)
    f = out / "checklist.md"
    f.write_text(checklist(res, mod))
    written.append(f)
    return written


def _rel(mod: Path) -> str:
    """The mod path as a person types it (repo-relative), whatever path the script was given."""
    try:
        return mod.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return mod.as_posix()


def checklist(res: dict, mod: Path) -> str:
    v, spec = res["vendor"], res["spec"]
    issue = spec.get("issue") or "the mod's tracking issue"
    lines = [
        f"# {spec['mod']}: {v['name']} order checklist",
        "",
        f"Generated by `just sheet-quote {_rel(mod)}` from `sheet_order.dhall`",
        "(tools/laser/sheet_quote.py). Ticked items were checked by the",
        "script; open items are for the person placing the order. No script places it.",
        "",
        "## Parts",
        "",
        "| Part | SKU | Material | t (mm) | Qty | Finish | Ops |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in res["parts"]:
        part, sku = p["part"], p["sku"]
        ops = ", ".join(x for x in (_fmt_ops(part["tapped"], "thread"), _fmt_ops(part["hardware"], "part_number"),
                                    f"{part['countersinks']} countersink(s)" if part["countersinks"] else "",
                                    f"{part['bends']} bend(s)" if part["bends"] else "") if x) or "cut only"
        lines.append(f"| {part['name']} | {sku['sku']} | {sku['material']} | {sku['t_mm']:.3f} | {part['qty']} | "
                     f"{part.get('finish') or 'none'} | {ops} |")
    lines += ["", "## Machine checks", ""]
    for p in res["parts"]:
        rep, name = p["lint"], p["part"]["name"]
        c = rep["contours"]
        lines.append(f"- [x] {name}: dxf_lint {v['slug']} {p['sku']['sku']} ok: 1 outer contour, {c['holes']} holes, "
                     f"{c['islands']} islands, units mm, CUT only, no text")
        lines.append(f"- [x] {name}: min hole {rep.get('min_hole_mm')} mm, min bridge {rep.get('min_bridge_mm')} mm, "
                     f"min hole-to-edge {rep.get('min_hole_edge_mm')} mm, no neck under the SKU bridge")
        ext = rep["extents"]
        lines.append(f"- [x] {name}: extents {ext[2] - ext[0]:.2f} x {ext[3] - ext[1]:.2f} mm inside the vendor and SKU limits")
        for e in p["evidence"]:
            lines.append(f"- [x] {name}: {e}")
        for w in p["warnings"]:
            lines.append(f"- [ ] review warning: {w}")
    lines += [
        "",
        "## Manual steps",
        "",
        "- [ ] Upload each `DXF/<part>.dxf` as its own line; set the quote unit to **mm** (the files are mm, 1:1).",
        "- [ ] Set material, thickness, finish and quantity per line from `parts.csv`; never nest copies in one file.",
        "- [ ] Confirm the quote shows no kerf, hole or bridge warnings; if it flags one, fix the CAD, not the quote.",
        "- [ ] Bent parts: upload the STEP, not the DXF, and paste the note (bend direction) into the order note.",
        "- [ ] Hardware and tapping: confirm the vendor shows the operations listed in `bom.csv`.",
        "- [ ] Record the order (SKU, quantity, finish, price, order number) in the mod's docs/ and as a",
        f"      comment on {issue}.",
        "",
    ]
    return "\n".join(lines)


def verify(res: dict, mod: Path, out: Path) -> list[str]:
    """Differences between the committed package at out and a fresh build (empty: current)."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="sheet_quote.") as tmp:
        fresh = Path(tmp) / "order"
        write(res, mod, fresh)
        want = {p.relative_to(fresh).as_posix(): p.read_bytes() for p in fresh.rglob("*") if p.is_file()}
    have = {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()} if out.is_dir() else {}
    diffs = [f"missing {k}" for k in sorted(set(want) - set(have))]
    diffs += [f"extra {k}" for k in sorted(set(have) - set(want))]
    diffs += [f"stale {k}" for k in sorted(set(want) & set(have)) if want[k] != have[k]]
    return diffs


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mod", help="mod directory, e.g. mods/<creator>/<mod>")
    ap.add_argument("--out", default=None, help="package directory (default <mod>/order)")
    ap.add_argument("--spec-json", default=None, help="rendered sheet_order spec (skip dhall-to-json)")
    ap.add_argument("--constants", default=str(DEFAULT_CONSTANTS))
    ap.add_argument("--check", action="store_true", help="validate only; write nothing")
    ap.add_argument("--verify", action="store_true", help="fail when the committed package is stale")
    a = ap.parse_args(argv)
    mod = Path(a.mod)
    spec = load_spec(mod, a.spec_json)
    res = build(mod, spec, Path(a.constants))
    report = {"mod": mod.as_posix(), "ok": res["ok"], "errors": res["errors"] + [e for p in res["parts"] for e in p["errors"]],
              "warnings": [w for p in res["parts"] for w in p["warnings"]]}
    out = Path(a.out) if a.out else mod / "order"
    if res["ok"] and a.verify:
        report["stale"] = verify(res, mod, out)
        if report["stale"]:
            report["ok"] = False
            report["errors"].append(f"order package {out.as_posix()} is stale; run just sheet-quote {mod.as_posix()}")
    elif res["ok"] and not a.check:
        report["written"] = [f.as_posix() for f in write(res, mod, out)]
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
