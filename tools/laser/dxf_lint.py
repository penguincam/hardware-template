#!/usr/bin/env python3
"""Lint a laser DXF: ezdxf audit, units, layers, closed cut paths, extents, vendor rules.

Usage:
  python3 dxf_lint.py part.dxf [--bed 400x300] [--layers CUT,SCORE,ENGRAVE]
  python3 dxf_lint.py part.dxf --vendor example_service --sku AL-2.3 [--constants ssot/generated/constants.json]
  python3 dxf_lint.py part.dxf --vendor my_shop          (a repo's shop profile)
  python3 dxf_lint.py part.dxf --vendor example_service --sku AL-3.2 --finish anodize

Needs ezdxf (tools/python/requirements.in). Exit 1 on any error, 0 otherwise.

Checks (always)
  audit      doc.audit() reports no unfixed errors
  units      $INSUNITS == 4 (millimetres)
  layers     every geometry entity sits on an allowed layer (default CUT, SCORE, ENGRAVE)
  closed     every path on CUT is closed: closed LWPOLYLINE/POLYLINE, CIRCLE,
             closed SPLINE, full ELLIPSE, or LINE/ARC segments whose endpoints
             all meet exactly two others (closed chains; build123d ExportDXF
             writes faces this way). Dangling chain ends are errors.
  duplicate  the same LINE, ARC, CIRCLE or polyline twice (double cuts burn the edge)
  overlap    collinear LINE segments on CUT that share a stretch (partial double cut)
  selfcross  a closed CUT contour that crosses itself (the cutter cannot follow it)
  degenerate zero-length or zero-radius geometry
  extents    bounding box fits the bed (if --bed given), and lies in +X/+Y

Vendor checks (--vendor <slug>, a LaserVendor record from
ssot/generated/constants.json laser_vendors.<slug>; ssot/types/LaserVendor.dhall)
  layers     only the vendor's layers (a cut service: CUT only)
  text       no TEXT/MTEXT anywhere unless text_allowed (convert text to outlines)
  parts      one outer contour per file (one_part_per_file); no floating islands
             inside holes (islands_allowed)
  extents    part fits min_part_mm .. max_part_mm in either orientation (the bed
             for a shop laser); a SKU may override the vendor limits
  holes      every hole >= max(sku.min_hole_rec_mm, min_hole_factor_t * t),
             warning below warn_hole_factor_t * t
  webs       hole-to-hole web >= sku.min_bridge_mm; hole-to-edge web >=
             sku.min_hole_edge_mm, warning below warn_edge_factor_t * t
  necks      the outline pinches to less than sku.min_bridge_mm (a thin finger
             or neck between two notches), or a hole has a slot arm narrower
             than the hole floor (a thin slot the bbox rule cannot see)
  finish     with --finish <process>: the part fits that finish_windows entry,
             every hole >= finish_min_hole_mm, and at least one hole >=
             hang_hole_mm to hang the part (anodize, powder coat)
A vendor with SKU rows needs --sku (the thickness drives the hole and web rules).
Hole size is the circle diameter, or the smaller bounding-box side for other
shapes; webs are measured on contours flattened to 0.02 mm. The report lists
hole diameters (hole_d_mm: {diameter: count}) for tap and hardware counts
(sheet_quote.py).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

try:
    import ezdxf
    from ezdxf import bbox
    from ezdxf import path as dxfpath
except ImportError:  # pragma: no cover
    sys.stderr.write("dxf_lint: ezdxf not installed (uv run --with ezdxf ...)\n")
    raise SystemExit(2)

GEOM = {"LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE", "SPLINE", "ELLIPSE", "HATCH", "TEXT", "MTEXT", "POINT"}
FLAT_MM = 0.02  # flattening chord error for web measurements
EPS = 1e-6
DEFAULT_CONSTANTS = Path(__file__).resolve().parents[2] / "ssot" / "generated" / "constants.json"


def is_closed(e) -> bool:
    t = e.dxftype()
    if t == "CIRCLE":
        return e.dxf.radius > 0
    if t == "LWPOLYLINE":
        return bool(e.closed) or (len(e) > 2 and _same(e[0][:2], e[-1][:2]))
    if t == "POLYLINE":
        pts = [v.dxf.location for v in e.vertices]
        return bool(e.is_closed) or (len(pts) > 2 and _same(pts[0], pts[-1]))
    if t == "SPLINE":
        return bool(e.closed)
    if t == "ELLIPSE":
        return math.isclose(abs(e.dxf.end_param - e.dxf.start_param), math.tau, abs_tol=1e-6)
    return False


def _same(a, b, tol: float = 1e-4) -> bool:
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def _key(p) -> tuple[float, float]:
    return (round(p[0], 3), round(p[1], 3))


def _dup_key(e):
    """Hashable identity of an entity's geometry (None when not checked)."""
    t = e.dxftype()
    if t == "LINE":
        return (t, e.dxf.layer.upper(), frozenset((_key(e.dxf.start), _key(e.dxf.end))))
    if t == "CIRCLE":
        return (t, e.dxf.layer.upper(), _key(e.dxf.center), round(e.dxf.radius, 3))
    if t == "ARC":
        return (t, e.dxf.layer.upper(), _key(e.dxf.center), round(e.dxf.radius, 3),
                round(e.dxf.start_angle % 360, 3), round(e.dxf.end_angle % 360, 3))
    if t == "LWPOLYLINE":
        return (t, e.dxf.layer.upper(), tuple(_key(p[:2]) for p in e.get_points("xy")))
    return None


# ---------------------------------------------------------------- contours

def _flat(e) -> list[tuple[float, float]]:
    return [(v.x, v.y) for v in dxfpath.make_path(e).flattening(FLAT_MM)]


def _chain_loops(segs: list) -> list[list[tuple[float, float]]]:
    """Order LINE/ARC segments (each a flattened point list) into closed loops."""
    at: dict[tuple[float, float], list[int]] = {}
    for i, pts in enumerate(segs):
        for p in (pts[0], pts[-1]):
            at.setdefault(_key(p), []).append(i)
    used = [False] * len(segs)
    loops = []
    for start in range(len(segs)):
        if used[start]:
            continue
        used[start] = True
        loop = list(segs[start])
        head = _key(loop[0])
        while _key(loop[-1]) != head:
            nxt = [j for j in at.get(_key(loop[-1]), []) if not used[j]]
            if not nxt:
                break  # open chain: reported by the closed check
            j = nxt[0]
            used[j] = True
            pts = segs[j]
            if _key(pts[0]) != _key(loop[-1]):
                pts = pts[::-1]
            loop.extend(pts[1:])
        if len(loop) > 2 and _key(loop[-1]) == head:
            loops.append(loop)
    return loops


def _bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _inside(pt, poly) -> bool:
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def _pt_seg(p, a, b) -> float:
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def _poly_dist(a, b) -> float:
    def one(src, dst):
        best = math.inf
        m = len(dst)
        for p in src:
            for i in range(m):
                d = _pt_seg(p, dst[i], dst[(i + 1) % m])
                if d < best:
                    best = d
        return best
    return min(one(a, b), one(b, a))


def _bbox_gap(a, b) -> float:
    dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2]))
    dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
    return math.hypot(dx, dy)


def contours(msp) -> list[dict]:
    """Closed CUT contours: points, bbox, circle diameter (or None), nesting depth."""
    out, segs = [], []
    for e in msp:
        t = e.dxftype()
        if e.dxf.layer.upper() != "CUT" or t not in GEOM:
            continue
        if t in ("LINE", "ARC"):
            segs.append(_flat(e))
        elif t in ("CIRCLE", "LWPOLYLINE", "POLYLINE", "SPLINE", "ELLIPSE") and is_closed(e):
            out.append({"pts": _flat(e), "circle_d": 2.0 * e.dxf.radius if t == "CIRCLE" else None})
    out += [{"pts": loop, "circle_d": None} for loop in _chain_loops(segs)]
    for c in out:
        c["bbox"] = _bbox(c["pts"])
    for i, c in enumerate(out):
        probe = c["pts"][0]
        c["depth"] = sum(
            1 for j, o in enumerate(out)
            if j != i and o["bbox"][0] <= c["bbox"][0] and o["bbox"][1] <= c["bbox"][1]
            and o["bbox"][2] >= c["bbox"][2] and o["bbox"][3] >= c["bbox"][3] and _inside(probe, o["pts"]))
    return out


def _overlaps(lines: list) -> list[str]:
    """Collinear LINE pairs sharing more than a point (partial double cuts)."""
    out = []
    for i, (h1, a, b) in enumerate(lines):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        if L < EPS:
            continue
        ux, uy = dx / L, dy / L
        for h2, c, d in lines[i + 1:]:
            if {_key(a), _key(b)} == {_key(c), _key(d)}:
                continue  # exact duplicate: reported by the duplicate check
            # both ends of the other segment on this line?
            if abs((c[0] - a[0]) * uy - (c[1] - a[1]) * ux) > 1e-4 or abs((d[0] - a[0]) * uy - (d[1] - a[1]) * ux) > 1e-4:
                continue
            t0, t1 = sorted(((c[0] - a[0]) * ux + (c[1] - a[1]) * uy, (d[0] - a[0]) * ux + (d[1] - a[1]) * uy))
            shared = min(L, t1) - max(0.0, t0)
            if shared > 1e-3:
                out.append(f"LINE #{h1} and #{h2} overlap for {shared:.3f} mm on CUT; a shared stretch is cut twice")
    return out


def _seg_cross(p1, p2, p3, p4) -> bool:
    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    d1, d2 = orient(p3, p4, p1), orient(p3, p4, p2)
    d3, d4 = orient(p1, p2, p3), orient(p1, p2, p4)
    return ((d1 > 1e-9 and d2 < -1e-9) or (d1 < -1e-9 and d2 > 1e-9)) and \
        ((d3 > 1e-9 and d4 < -1e-9) or (d3 < -1e-9 and d4 > 1e-9))


def self_crosses(pts) -> bool:
    """True when a closed polygon crosses itself (proper crossings of non-adjacent edges)."""
    n = len(pts)
    if n < 4:
        return False
    boxes = [(min(pts[i][0], pts[(i + 1) % n][0]), min(pts[i][1], pts[(i + 1) % n][1]),
              max(pts[i][0], pts[(i + 1) % n][0]), max(pts[i][1], pts[(i + 1) % n][1])) for i in range(n)]
    for i in range(n):
        bi = boxes[i]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            bj = boxes[j]
            if bi[2] < bj[0] or bj[2] < bi[0] or bi[3] < bj[1] or bj[3] < bi[1]:
                continue
            if _seg_cross(pts[i], pts[(i + 1) % n], pts[j], pts[(j + 1) % n]):
                return True
    return False


def min_neck(pts, limit: float) -> tuple[float, tuple[float, float]] | None:
    """Narrowest pinch of a closed contour below `limit`: the smallest distance between two
    points of the outline that are more than 4 x limit apart along it (so corners never
    count, while a neck between two notches or a thin slot arm does). None when no pinch."""
    n = len(pts)
    if n < 4 or limit <= 0:
        return None
    cum = [0.0]
    for i in range(1, n + 1):
        a, b = pts[i - 1], pts[i % n]
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    per = cum[-1]
    skip = 4.0 * limit
    best = None
    for i in range(n):
        p = pts[i]
        for j in range(n):
            a, b = pts[j], pts[(j + 1) % n]
            if min(abs(a[0] - p[0]), abs(b[0] - p[0])) > limit and (a[0] - p[0]) * (b[0] - p[0]) > 0:
                continue
            if min(abs(a[1] - p[1]), abs(b[1] - p[1])) > limit and (a[1] - p[1]) * (b[1] - p[1]) > 0:
                continue
            sep = abs(cum[j] - cum[i])
            sep2 = abs(cum[j + 1] - cum[i])
            if min(sep, per - sep, sep2, per - sep2) <= skip:
                continue
            d = _pt_seg(p, a, b)
            if d < limit - EPS and (best is None or d < best[0]):
                best = (d, p)
    return best


# ---------------------------------------------------------------- vendors

def load_vendor(constants: str | Path, slug: str) -> dict:
    vendors = json.loads(Path(constants).read_text()).get("laser_vendors", {})
    if slug not in vendors:
        raise SystemExit(f"dxf_lint: vendor {slug!r} not in {constants} laser_vendors (have {sorted(vendors)})")
    return vendors[slug]


def find_sku(vendor: dict, sku: str | None) -> dict | None:
    if sku is None:
        return None
    for row in vendor.get("skus", []):
        if row["sku"] == sku:
            return row
    raise SystemExit(f"dxf_lint: sku {sku!r} not in vendor {vendor['slug']} (have {[r['sku'] for r in vendor['skus']]})")


def _fits(w: float, h: float, lim: dict, bigger: bool) -> bool:
    a, b = sorted((w, h))
    c, d = sorted((lim["x"], lim["y"]))
    return (a <= c + EPS and b <= d + EPS) if bigger else (a >= c - EPS and b >= d - EPS)


def finish_window(vendor: dict, process: str) -> dict:
    for w in vendor.get("finish_windows", []):
        if w["process"] == process:
            return w
    raise SystemExit(f"dxf_lint: finish {process!r} not in vendor {vendor['slug']} finish_windows "
                     f"(have {[w['process'] for w in vendor.get('finish_windows', [])]})")


def vendor_checks(msp, ext, vendor: dict, sku: dict | None, errors: list, warnings: list,
                  finish: str | None = None) -> dict:
    name = vendor["slug"]
    if vendor.get("skus") and sku is None:
        errors.append(f"vendor {name} needs --sku (thickness drives the hole and web rules); "
                      f"one of {[r['sku'] for r in vendor['skus']]}")
    if not vendor.get("text_allowed", True):
        for e in msp:
            if e.dxftype() in ("TEXT", "MTEXT"):
                errors.append(f"{e.dxftype()} #{e.dxf.handle}: vendor {name} needs text converted to outlines")
    out: dict = {"vendor": name, "sku": sku["sku"] if sku else None, "t_mm": sku["t_mm"] if sku else None}
    win = finish_window(vendor, finish) if finish else None
    if ext is not None:
        w, h = ext[2] - ext[0], ext[3] - ext[1]
        if win is not None:
            if not _fits(w, h, win["max_mm"], bigger=True):
                errors.append(f"extents {w:.1f} x {h:.1f} exceed {name} {finish} max {win['max_mm']['x']} x {win['max_mm']['y']} mm")
            if not _fits(w, h, win["min_mm"], bigger=False):
                errors.append(f"extents {w:.1f} x {h:.1f} below {name} {finish} min {win['min_mm']['x']} x {win['min_mm']['y']} mm")
        mx = (sku or {}).get("max_part_mm") or vendor["max_part_mm"]
        mn = (sku or {}).get("min_part_mm") or vendor["min_part_mm"]
        if not _fits(w, h, mx, bigger=True):
            errors.append(f"extents {w:.1f} x {h:.1f} exceed vendor {name} max part {mx['x']} x {mx['y']} mm")
        if not _fits(w, h, mn, bigger=False):
            errors.append(f"extents {w:.1f} x {h:.1f} below vendor {name} min part {mn['x']} x {mn['y']} mm")
    cs = contours(msp)
    outers = [c for c in cs if c["depth"] == 0]
    holes = [c for c in cs if c["depth"] == 1]
    islands = [c for c in cs if c["depth"] >= 2]
    out["contours"] = {"outer": len(outers), "holes": len(holes), "islands": len(islands)}
    if vendor.get("one_part_per_file") and len(outers) > 1:
        errors.append(f"{len(outers)} separate parts; vendor {name} wants one part per file (set quantity at checkout)")
    if islands and not vendor.get("islands_allowed", True):
        errors.append(f"{len(islands)} floating island(s) inside holes; add bridges or use a stencil font ({name})")
    for c in cs:
        if c["circle_d"] is None and self_crosses(c["pts"]):
            x0, y0, x1, y1 = c["bbox"]
            errors.append(f"contour near ({(x0 + x1) / 2:.2f}, {(y0 + y1) / 2:.2f}) crosses itself; redraw it as a simple loop")
    hole_d = {}
    for c in holes:
        x0, y0, x1, y1 = c["bbox"]
        d = c["circle_d"] if c["circle_d"] is not None else min(x1 - x0, y1 - y0)
        c["size"] = d
        if c["circle_d"] is not None:
            k = f"{d:.3f}"
            hole_d[k] = hole_d.get(k, 0) + 1
    out["hole_d_mm"] = dict(sorted(hole_d.items(), key=lambda kv: float(kv[0])))
    if win is not None:
        fmin, hang = vendor.get("finish_min_hole_mm", 0.0), vendor.get("hang_hole_mm", 0.0)
        for c in holes:
            if c["size"] < fmin - EPS:
                x0, y0, x1, y1 = c["bbox"]
                errors.append(f"hole {c['size']:.3f} mm at ({(x0 + x1) / 2:.2f}, {(y0 + y1) / 2:.2f}) below the "
                              f"{name} {finish} minimum {fmin} mm (it may fill)")
        if hang > 0 and not any(c["size"] >= hang - EPS for c in holes):
            errors.append(f"{finish} needs a hanging hole >= {hang} mm ({name}); the part has none")
    if sku is None:
        return out
    t = sku["t_mm"]
    hole_floor = max(sku["min_hole_rec_mm"], vendor["min_hole_factor_t"] * t)
    hole_warn = vendor["warn_hole_factor_t"] * t
    sizes = []
    for c in holes:
        x0, y0, x1, y1 = c["bbox"]
        d = c["size"]
        sizes.append(d)
        at = f"({(x0 + x1) / 2:.2f}, {(y0 + y1) / 2:.2f})"
        if d < hole_floor - EPS:
            errors.append(f"hole {d:.3f} mm at {at} below {name} {sku['sku']} minimum {hole_floor:.3f} mm "
                          f"(max of {sku['min_hole_rec_mm']} rec, {vendor['min_hole_factor_t']} t)")
        elif d < hole_warn - EPS:
            warnings.append(f"hole {d:.3f} mm at {at} below {vendor['warn_hole_factor_t']} t = {hole_warn:.3f} mm "
                            f"({name} material-page rule)")
    out["min_hole_mm"] = round(min(sizes), 3) if sizes else None
    necks = []
    for o in outers:
        hit = min_neck(o["pts"], sku["min_bridge_mm"])
        if hit:
            necks.append(hit[0])
            errors.append(f"outline pinches to {hit[0]:.3f} mm near ({hit[1][0]:.2f}, {hit[1][1]:.2f}), below "
                          f"{name} {sku['sku']} min bridge {sku['min_bridge_mm']} mm (thin finger or neck)")
    for c in holes:
        if c["circle_d"] is not None:
            continue
        hit = min_neck(c["pts"], hole_floor)
        if hit:
            necks.append(hit[0])
            errors.append(f"slot in a cutout narrows to {hit[0]:.3f} mm near ({hit[1][0]:.2f}, {hit[1][1]:.2f}), "
                          f"below the {name} {sku['sku']} hole floor {hole_floor:.3f} mm")
    out["min_neck_mm"] = round(min(necks), 3) if necks else None
    edge_warn = vendor["warn_edge_factor_t"] * t
    reach = max(sku["min_bridge_mm"], sku["min_hole_edge_mm"], edge_warn) + 1.0
    min_bridge = min_edge = math.inf
    for i, a in enumerate(holes):
        for b in holes[i + 1:]:
            if _bbox_gap(a["bbox"], b["bbox"]) > reach:
                continue
            d = _poly_dist(a["pts"], b["pts"])
            min_bridge = min(min_bridge, d)
            if d < sku["min_bridge_mm"] - EPS:
                errors.append(f"web {d:.3f} mm between holes near ({a['bbox'][0]:.2f}, {a['bbox'][1]:.2f}) "
                              f"below {name} {sku['sku']} min bridge {sku['min_bridge_mm']} mm")
        for o in outers:
            if not _inside(a["pts"][0], o["pts"]):
                continue
            d = _poly_dist(a["pts"], o["pts"])
            min_edge = min(min_edge, d)
            if d < sku["min_hole_edge_mm"] - EPS:
                errors.append(f"hole-to-edge web {d:.3f} mm near ({a['bbox'][0]:.2f}, {a['bbox'][1]:.2f}) "
                              f"below {name} {sku['sku']} minimum {sku['min_hole_edge_mm']} mm")
            elif d < edge_warn - EPS:
                warnings.append(f"hole-to-edge web {d:.3f} mm near ({a['bbox'][0]:.2f}, {a['bbox'][1]:.2f}) "
                                f"below {vendor['warn_edge_factor_t']} t = {edge_warn:.3f} mm")
    out["min_bridge_mm"] = None if math.isinf(min_bridge) else round(min_bridge, 3)
    out["min_hole_edge_mm"] = None if math.isinf(min_edge) else round(min_edge, 3)
    return out


# ---------------------------------------------------------------- lint

def lint(path: str, layers: set[str], bed: tuple[float, float] | None,
         vendor: dict | None = None, sku: dict | None = None, finish: str | None = None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if vendor is not None:
        layers = {s.upper() for s in vendor["layers"]}
    doc = ezdxf.readfile(path)
    auditor = doc.audit()
    if auditor.has_errors:
        errors.append(f"audit: {len(auditor.errors)} unfixed errors")
    if auditor.has_fixes:
        warnings.append(f"audit: {len(auditor.fixes)} issues auto-fixed in memory; re-export clean")
    units = doc.header.get("$INSUNITS", 0)
    if units != 4:
        errors.append(f"$INSUNITS={units}; set doc.units = ezdxf.units.MM (4)")
    msp = doc.modelspace()
    counts: dict[str, int] = {}
    nodes: dict[tuple[float, float], int] = {}
    seen: dict = {}
    chain_segments = 0
    cut_lines: list = []
    for e in msp:
        t = e.dxftype()
        if t not in GEOM:
            continue
        layer = e.dxf.layer.upper()
        counts[layer] = counts.get(layer, 0) + 1
        if layer not in layers:
            errors.append(f"{t} #{e.dxf.handle} on layer '{e.dxf.layer}' (allowed: {sorted(layers)})")
        dk = _dup_key(e)
        if dk is not None:
            if dk in seen:
                errors.append(f"duplicate {t} #{e.dxf.handle} (same as #{seen[dk]}); double cuts burn the edge")
            else:
                seen[dk] = e.dxf.handle
        if t == "LINE" and _same(e.dxf.start, e.dxf.end):
            errors.append(f"zero-length LINE #{e.dxf.handle}")
        if t in ("CIRCLE", "ARC") and e.dxf.radius <= 0:
            errors.append(f"zero-radius {t} #{e.dxf.handle}")
        if layer == "CUT" and t in ("TEXT", "MTEXT", "HATCH", "POINT"):
            errors.append(f"{t} #{e.dxf.handle} on CUT; text and fills belong on ENGRAVE")
        elif layer == "CUT" and t in ("LINE", "ARC"):
            chain_segments += 1
            if t == "LINE":
                ends = (e.dxf.start, e.dxf.end)
                cut_lines.append((e.dxf.handle, (e.dxf.start[0], e.dxf.start[1]), (e.dxf.end[0], e.dxf.end[1])))
            else:
                ends = (e.start_point, e.end_point)
            for p in ends:
                key = _key(p)
                nodes[key] = nodes.get(key, 0) + 1
        elif layer == "CUT" and not is_closed(e):
            errors.append(f"open {t} #{e.dxf.handle} on CUT; close it")
    errors.extend(_overlaps(cut_lines))
    dangling = [k for k, v in nodes.items() if v != 2]
    if dangling:
        errors.append(f"CUT has {len(dangling)} open or branching chain ends, e.g. {dangling[:3]}")
    elif chain_segments:
        warnings.append(
            f"CUT uses {chain_segments} LINE/ARC segments in closed chains; fine for most CAM,"
            " join to polylines if your laser software cuts them out of order")
    ext = bbox.extents(msp)
    out_ext = None
    if ext.has_data:
        (x0, y0, _), (x1, y1, _) = ext.extmin, ext.extmax
        out_ext = [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)]
        if x0 < -1e-6 or y0 < -1e-6:
            warnings.append("geometry extends into negative X/Y; laser origin is usually bottom-left")
        if bed and ((x1 - x0) > bed[0] or (y1 - y0) > bed[1]):
            errors.append(f"extents {x1 - x0:.1f} x {y1 - y0:.1f} exceed bed {bed[0]} x {bed[1]}")
    else:
        errors.append("no geometry")
    if "CUT" not in counts:
        warnings.append("no entities on CUT")
    rep = {"file": path, "units": units, "layers": counts, "extents": out_ext}
    if vendor is not None:
        rep.update(vendor_checks(msp, out_ext, vendor, sku, errors, warnings, finish))
    rep.update({"errors": errors, "warnings": warnings, "ok": not errors})
    return rep


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dxf")
    p.add_argument("--layers", default="CUT,SCORE,ENGRAVE")
    p.add_argument("--bed", default=None, help="WxH in mm, e.g. 400x300")
    p.add_argument("--vendor", default=None, help="laser_vendors slug, e.g. example_service")
    p.add_argument("--sku", default=None, help="vendor SKU, e.g. AL-2.3")
    p.add_argument("--constants", default=str(DEFAULT_CONSTANTS), help="ssot/generated/constants.json")
    p.add_argument("--finish", default=None, help="vendor finish_windows process, e.g. anodize, powder_coat")
    a = p.parse_args(argv)
    bed = tuple(float(v) for v in a.bed.lower().split("x")) if a.bed else None
    vendor = load_vendor(a.constants, a.vendor) if a.vendor else None
    sku = find_sku(vendor, a.sku) if vendor else None
    if a.finish and vendor is None:
        p.error("--finish needs --vendor")
    rep = lint(a.dxf, {s.strip().upper() for s in a.layers.split(",")}, bed, vendor, sku, a.finish)
    json.dump(rep, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
