"""Reusable build123d features, each first used on a printed part.

Each builder returns plain build123d solids in a local frame (Z up = print up, mm) so a part
module positions them with Pos/Location and combines them itself. Features that both add and
remove material return a `Feature(add, cut)`; `apply(body, *features)` adds every `add`, then
subtracts every `cut`, so a bore is never filled by a neighbouring boss. Every builder has a
`*_errors(...)` partner that returns the broken design rules as strings (feed them to
tools/fab/checks.Checks.extend), and the numbers come from the SSOT where one exists:

  pilot_boss      round boss with a self-tap pilot (fasteners.self_tap) or heat-set insert bore
                  (inserts), optional countersink-dimple relief and screw-tip relief below
  teardrop_cutter horizontal hole printable without support (tip up, optional flat cap and
                  rounded cap corners); gland_hole() sizes it from pg_glands
  gasket_groove / gasket_bead   rounded-rectangle ring at an inset from an outline: the groove
                  cut into a rim and the TPU bead printed in (or loose) beside it
  strain_saddle   cable cradle (base with half groove and two insert bores), clamp bar with
                  clearance holes, and two TPU half-tube liners that squeeze the cable
  dovetail_cutter / skinned_bar  dovetail key grooves and a TPU skin over a rigid core as
                  separate solids that touch but never overlap
  board_outline / board_mount / board_envelope / plug_envelopes / keepout_boxes
                  the PCB bay from a board_outline.json: bosses at the board's holes,
                  the populated-board envelope, mating-plug clearances per connector and metal
                  keepouts; board_errors() checks the bay against the outline

build123d is imported lazily so `import tools.fab.features` works without it. A part module
imports it as `from tools.fab import features` (cad_part puts tools/fab on the package path
when the target lists "//tools/fab:lib" in data).

Proof: tools/fab/test_features.py (//tools/fab:features_test) measures every builder (bbox,
volume against closed-form values, ray-measured walls and openings, no overlaps), and
mods/example/sealed_box builds a small box from several of them.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import NamedTuple

EPS = 0.01  # boolean overlap so faces never coincide
HERE = Path(__file__).absolute().parent  # not resolve(): Bazel runfiles carry constants.json


class Feature(NamedTuple):
    add: object | None
    cut: object | None


def _b():
    import build123d

    return build123d


def constants(path: str | Path | None = None) -> dict:
    """ssot/generated/constants.json (pg_glands, fasteners, inserts, ...)."""
    p = Path(path) if path else HERE.parents[1] / "ssot" / "generated" / "constants.json"
    return json.loads(Path(p).read_text())


def _part(shape):
    b = _b()
    return shape if isinstance(shape, b.Part) else b.Part(shape.wrapped)


def apply(body, *features: Feature):
    """body + every add, then - every cut."""
    for f in features:
        if f.add is not None:
            body = body + f.add
    for f in features:
        if f.cut is not None:
            body = body - f.cut
    return _part(body)


def rrect_prism(w: float, d: float, r: float, z0: float, z1: float):
    """Rounded-rectangle prism centred on the Z axis from z0 to z1 (r <= 0: sharp)."""
    b = _b()
    body = b.Pos(0, 0, z0) * b.Box(w, d, z1 - z0, align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN))
    if r > 0:
        body = b.fillet(body.edges().filter_by(b.Axis.Z), radius=r)
    return _part(body)


# ---------------------------------------------------------------- screw bosses

def self_tap_pilot(thread_key: str = "n6_32", consts: dict | None = None) -> dict:
    """fasteners.self_tap.<key> row (pilot, ladder, depth_min, source)."""
    c = consts or constants()
    rows = c["fasteners"]["self_tap"]
    if thread_key not in rows:
        raise KeyError(f"no self-tap pilot {thread_key!r} in ssot/constants/fasteners.dhall (have {sorted(rows)})")
    return rows[thread_key]


def pilot_boss(od: float, height: float, bore_d: float, bore_depth: float, *, relief_d: float = 0.0,
               relief_depth: float = 0.0, tip_d: float = 0.0, tip_depth: float = 0.0,
               base_z: float = 0.0) -> Feature:
    """Round boss from base_z to base_z + height with a bore down from its top.

    bore_d / bore_depth: the self-tap pilot (fasteners.self_tap) or a heat-set insert hole
    (inserts.<size>.hole / depth). relief_*: a counterbore at the top for a dimpled countersink
    or a proud insert lip; the bore starts at its floor. tip_*: screw-tip relief below the bore.
    The add solid starts EPS below base_z so it fuses with the floor it stands on."""
    b = _b()
    mn = (b.Align.CENTER, b.Align.CENTER, b.Align.MIN)
    top = base_z + height
    add = b.Pos(0, 0, base_z - EPS) * b.Cylinder(od / 2, height + EPS, align=mn)
    z_bore = top - relief_depth
    cut = b.Pos(0, 0, z_bore - bore_depth) * b.Cylinder(bore_d / 2, bore_depth + 1.0 + relief_depth, align=mn)
    if relief_depth > 0:
        cut += b.Pos(0, 0, z_bore) * b.Cylinder(relief_d / 2, relief_depth + 1.0, align=mn)
    if tip_depth > 0:
        cut += b.Pos(0, 0, z_bore - bore_depth - tip_depth) * b.Cylinder(tip_d / 2, tip_depth + EPS, align=mn)
    return Feature(_part(add), _part(cut))


def pilot_boss_errors(od: float, height: float, bore_d: float, bore_depth: float, *, relief_d: float = 0.0,
                      relief_depth: float = 0.0, tip_d: float = 0.0, tip_depth: float = 0.0,
                      min_wall: float = 1.6, min_floor: float = 0.0) -> list[str]:
    """Boss rules: wall round the bore and the relief >= min_wall (4 lines of 0.4 by
    default), the bores fit inside the boss height with min_floor left under them."""
    e = []
    if (od - bore_d) / 2 < min_wall - 1e-9:
        e.append(f"boss wall {(od - bore_d) / 2:.2f} round the {bore_d} bore under {min_wall}")
    if relief_depth > 0:
        if relief_d <= bore_d:
            e.append(f"relief {relief_d} not wider than the bore {bore_d}")
        if (od - relief_d) / 2 < min_wall - 1e-9:
            e.append(f"boss wall {(od - relief_d) / 2:.2f} round the {relief_d} relief under {min_wall}")
    if tip_depth > 0 and tip_d > bore_d + 1e-9:
        e.append(f"tip relief {tip_d} wider than the bore {bore_d} (no shoulder for the screw)")
    used = relief_depth + bore_depth + tip_depth
    if used > height - min_floor + 1e-9:
        e.append(f"bores reach {used:.2f} below the boss top, past height {height} less floor {min_floor}")
    return e


def insert_boss(size: str, height: float, consts: dict | None = None, **kw) -> Feature:
    """pilot_boss sized from inserts.<size> (boss_od, hole, depth)."""
    c = (consts or constants())["inserts"][size]
    return pilot_boss(c["boss_od"], height, c["hole"], c["depth"], **kw)


# ---------------------------------------------------------------- horizontal holes and glands

def teardrop_profile(r: float, cap: float | None = None) -> tuple[float, float]:
    """(tip height above the axis, half width of the flat cap) of a tip-up teardrop."""
    tip = r * math.sqrt(2)
    top = tip if cap is None else min(r + cap, tip)
    return top, tip - top


def teardrop_cutter(r: float, length: float, *, cap: float | None = None, corner_r: float = 0.0,
                    y0: float = 0.0, z: float = 0.0):
    """Horizontal hole along +Y from y0, axis at height z, 45 deg teardrop tip up so it prints
    without support; cap truncates the tip at r + cap (flat bridge), corner_r rounds the two
    corners where the flat meets the 45 deg sides (an FEA hot spot on an earlier gland wall)."""
    b = _b()
    top, half = teardrop_profile(r, cap)
    t = r / math.sqrt(2)
    if half > 1e-9:
        pts = [(t, t), (half, top), (-half, top), (-t, t)]
    else:
        pts = [(t, t), (0.0, top), (-t, t)]
    plane = b.Plane(origin=(0, y0, z), x_dir=(-1, 0, 0), z_dir=(0, 1, 0))  # sketch +Y = world +Z
    poly = b.Polygon(*pts, align=None)
    if corner_r > 0 and half > 0:
        poly = b.fillet([v for v in poly.vertices() if abs(v.Y - top) < 1e-6], radius=corner_r)
    tool = b.extrude(plane * poly, amount=length)
    tool += b.Location((0, y0, z), (-90, 0, 0)) * b.Cylinder(r, length, align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN))
    return _part(tool)


def gland(key: str, consts: dict | None = None) -> dict:
    """pg_glands.<key> row (name, hole, thread_od, clamp_min, clamp_max, source)."""
    rows = (consts or constants())["pg_glands"]
    if key not in rows or not isinstance(rows[key], dict):
        raise KeyError(f"no gland {key!r} in ssot/constants/pg_glands.dhall (have {sorted(k for k, v in rows.items() if isinstance(v, dict) and 'hole' in v)})")
    return rows[key]


def gland_hole(key: str, wall_t: float, *, hole_d: float | None = None, cap: float | None = None,
               corner_r: float = 0.0, z: float = 0.0, horizontal: bool = True, consts: dict | None = None):
    """Through-hole for a cable gland in a wall wall_t thick lying in the XZ plane at y in
    [0, wall_t]: a teardrop along +Y when horizontal (the wall prints standing), else a plain
    cylinder (a floor or lid hole). hole_d overrides the catalogue hole (a coupon-measured
    value, for example 16.0 for one bought PG9 gland)."""
    b = _b()
    d = hole_d if hole_d is not None else gland(key, consts)["hole"]
    if horizontal:
        return teardrop_cutter(d / 2, wall_t + 2.0, cap=cap, corner_r=corner_r, y0=-1.0, z=z)
    return _part(b.Pos(0, 0, z - 1.0) * b.Cylinder(d / 2, wall_t + 2.0, align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN)))


def gland_errors(key: str, cable_od: float, *, squeeze_ok: float = 0.0, consts: dict | None = None) -> list[str]:
    """The cable must sit in the gland's clamp range (squeeze_ok mm over clamp_max allowed when
    a coupon shows the gland still seals, as one did for an 8.8 mm cable in a PG9)."""
    g = gland(key, consts)
    e = []
    if cable_od < g["clamp_min"] - 1e-9:
        e.append(f"cable {cable_od} under {g['name']} clamp_min {g['clamp_min']}: it will not seal")
    if cable_od > g["clamp_max"] + squeeze_ok + 1e-9:
        e.append(f"cable {cable_od} over {g['name']} clamp_max {g['clamp_max']} (+{squeeze_ok} squeeze allowed)")
    return e


# ---------------------------------------------------------------- rim gaskets

def _ring(w: float, d: float, r: float, inset: float, width: float, z0: float, z1: float):
    """Ring `width` wide centred `inset` in from a w x d (corner r) outline, z0..z1."""
    o_off, i_off = inset - width / 2, inset + width / 2
    outer = rrect_prism(w - 2 * o_off, d - 2 * o_off, max(r - o_off, 0.5), z0, z1)
    inner = rrect_prism(w - 2 * i_off, d - 2 * i_off, max(r - i_off, 0.3), z0 - 1, z1 + 1)
    return _part(outer - inner)


def gasket_groove(w: float, d: float, r: float, inset: float, groove_w: float, depth: float, top_z: float):
    """Groove cutter in a rim whose top is at top_z (outline w x d, corner r)."""
    return _ring(w, d, r, inset, groove_w, top_z - depth, top_z + 1.0)


def gasket_bead(w: float, d: float, r: float, inset: float, bead_w: float, depth: float, proud: float,
                top_z: float, *, flat: bool = False):
    """TPU bead centred in the groove, from the groove floor to proud above the rim. flat: moved
    down to Z = 0 to print loose and press in."""
    b = _b()
    bead = _ring(w, d, r, inset, bead_w, top_z - depth, top_z + proud)
    return _part(b.Pos(0, 0, -(top_z - depth)) * bead) if flat else bead


def gasket_errors(groove_w: float, bead_w: float, depth: float, proud: float, *, line_w: float = 0.4,
                  rim_w: float | None = None, inset: float | None = None, min_wall: float = 1.2) -> list[str]:
    """Bead >= 2 lines, a void each side of the bead for the TPU to spread into, the bead stands
    proud, and (given rim_w and inset) the groove leaves >= min_wall of rim each side."""
    e = []
    if bead_w < 2 * line_w - 1e-9:
        e.append(f"gasket bead {bead_w} under 2 lines of {line_w}")
    if groove_w <= bead_w + 1e-9:
        e.append(f"groove {groove_w} not wider than the bead {bead_w}: no room for the TPU to spread")
    if proud <= 0:
        e.append("gasket bead not proud of the rim: it will not compress")
    if depth <= 0:
        e.append("gasket groove depth must be positive")
    if rim_w is not None and inset is not None:
        out_wall, in_wall = inset - groove_w / 2, rim_w - inset - groove_w / 2
        if min(out_wall, in_wall) < min_wall - 1e-9:
            e.append(f"groove leaves {min(out_wall, in_wall):.2f} of rim (outer {out_wall:.2f}, inner {in_wall:.2f}) under {min_wall}")
    return e


# ---------------------------------------------------------------- strain relief saddle

class Saddle(NamedTuple):
    base: object       # cradle block, cable axis along Y at axis_z, half groove up, insert bores
    bar: object        # clamp bar in assembled position, half groove down, clearance holes
    liners: list       # two TPU half tubes (base, bar) in assembled position
    liner_print: object  # one liner in print orientation (standing on an end)
    dims: dict


def saddle_dims(cable_od: float, liner_t: float, squeeze: float, gap: float, *, wall: float = 3.0,
                pillar_d: float = 4.0) -> dict:
    """Derived saddle sizes. squeeze: radial interference of the liner on the cable (the liners'
    bore is cable_od / 2 - squeeze); gap: clamp take-up between base and bar at the axis."""
    r_in = cable_od / 2 - squeeze
    r_groove = r_in + liner_t
    pillar_x = r_groove + wall + pillar_d / 2
    return {"r_liner_in": r_in, "r_groove": r_groove, "gap": gap, "pillar_x": pillar_x,
            "half_x": pillar_x + pillar_d / 2 + wall}


def strain_saddle(cable_od: float, width: float, axis_z: float, *, liner_t: float = 1.2, squeeze: float = 0.4,
                  gap: float = 2.0, bar_h: float = 6.0, insert_d: float = 4.0, insert_depth: float = 6.7,
                  clear_d: float = 3.4, wall: float = 3.0, liner_trim: float = 0.4, corner_r: float = 2.0) -> Saddle:
    """Two-screw cable clamp: base from Z = 0 to axis_z - gap/2 (stand it on a floor), bar from
    axis_z + gap/2 up bar_h, both centred on X = 0 and Y = 0, cable along Y. Defaults: M3
    heat-set inserts (inserts.m3: hole 4.0, depth 6.7) and M3 normal clearance (fasteners)."""
    b = _b()
    g = saddle_dims(cable_od, liner_t, squeeze, gap, wall=wall, pillar_d=clear_d)
    hx, rg = g["half_x"], g["r_groove"]
    z_base, z_bar = axis_z - gap / 2, axis_z + gap / 2
    mn = (b.Align.CENTER, b.Align.CENTER, b.Align.MIN)
    groove = b.Location((0, -width / 2 - 1, axis_z), (-90, 0, 0)) * b.Cylinder(rg, width + 2, align=mn)
    base = rrect_prism(2 * hx, width, corner_r, 0.0, z_base) - groove
    for sx in (-1, 1):
        base -= b.Pos(sx * g["pillar_x"], 0, z_base - insert_depth) * b.Cylinder(insert_d / 2, insert_depth + 1, align=mn)
    bar = rrect_prism(2 * hx, width, corner_r, z_bar, z_bar + bar_h) - groove
    for sx in (-1, 1):
        bar -= b.Pos(sx * g["pillar_x"], 0, z_bar - 1) * b.Cylinder(clear_d / 2, bar_h + 2, align=mn)
    # Liner: half tube along +Z, open side +Y, edges trimmed liner_trim short of the parting plane.
    sec = b.Circle(rg) - b.Circle(g["r_liner_in"])
    sec = sec & b.Pos(0, -(rg + liner_trim) / 2) * b.Rectangle(2 * rg + 1, rg - liner_trim)
    shell = _part(b.extrude(sec, amount=width))
    lower = b.Pos(0, -width / 2, axis_z) * b.Rot(-90, 0, 0) * b.Rot(0, 0, 180) * shell  # opens up
    upper = b.Pos(0, -width / 2, axis_z) * b.Rot(-90, 0, 0) * shell  # opens down
    g.update({"z_base_top": z_base, "z_bar_bottom": z_bar, "z_bar_top": z_bar + bar_h, "axis_z": axis_z})
    return Saddle(_part(base), _part(bar), [_part(lower), _part(upper)], shell, g)


def saddle_errors(cable_od: float, *, liner_t: float = 1.2, squeeze: float = 0.4, gap: float = 2.0,
                  line_w: float = 0.4, insert_depth: float = 6.7, axis_z: float | None = None) -> list[str]:
    """Liner >= 2 lines, a real squeeze under a third of the liner, a positive take-up gap, and
    (given axis_z) enough base under the groove for the insert bores."""
    e = []
    if liner_t < 2 * line_w - 1e-9:
        e.append(f"liner {liner_t} under 2 lines of {line_w}")
    if squeeze <= 0:
        e.append("liner squeeze must be positive or the cable slips")
    elif squeeze > liner_t / 3 + 1e-9:
        e.append(f"liner squeeze {squeeze} over a third of the liner {liner_t} (TPU tears)")
    if gap <= 0:
        e.append("saddle gap must be positive (clamp take-up)")
    if axis_z is not None:
        z_base = axis_z - gap / 2
        if z_base < insert_depth + 1.0 - 1e-9:
            e.append(f"saddle base top {z_base:.2f} leaves under 1 mm below the {insert_depth} insert bores")
        r_groove = cable_od / 2 - squeeze + liner_t
        if axis_z - r_groove < 1.2 - 1e-9:
            e.append(f"groove floor {axis_z - r_groove:.2f} above Z = 0 is under 1.2 mm")
    return e


# ---------------------------------------------------------------- TPU skins with dovetail keys

def dovetail_cutter(depth: float, mouth: float, base: float, length: float, *, overrun: float = 0.2):
    """Dovetail groove cutter running along Y, centred on X = 0: mouth `mouth` wide at Z = 0,
    floor `base` wide at Z = -depth (base > mouth: the undercut holds the skin), extended
    `overrun` above Z = 0 along the flank slope so it cuts cleanly through the surface."""
    b = _b()
    slope = (base - mouth) / 2 / depth
    pts = [(-base / 2, -depth), (base / 2, -depth), (mouth / 2 - slope * overrun, overrun),
           (-(mouth / 2 - slope * overrun), overrun)]
    face = b.Plane.XZ * b.Polygon(*pts, align=None)
    return _part(b.extrude(face, amount=length / 2, both=True))


def dovetail_errors(depth: float, mouth: float, base: float, *, line_w: float = 0.4) -> list[str]:
    """Key rules: mouth >= 2 lines, base > mouth, undercut 15-30 deg per side."""
    e = []
    if mouth < 2 * line_w - 1e-9:
        e.append(f"key mouth {mouth} under 2 lines of {line_w}")
    if base <= mouth:
        e.append(f"key base {base} must exceed the mouth {mouth} (no undercut)")
        return e
    undercut = math.degrees(math.atan((base - mouth) / 2 / depth))
    if not 15.0 - 1e-6 <= undercut <= 30.0 + 1e-6:
        e.append(f"key undercut {undercut:.1f} deg outside 15-30")
    return e


class Skinned(NamedTuple):
    core: object
    skin: object
    dims: dict


def skinned_bar(length: float, core_w: float, core_h: float, skin_t: float, *, foot_h: float = 0.6,
                key_depth: float = 1.2, key_mouth: float = 1.6, key_base: float = 2.6,
                key_pitch: float = 8.0) -> Skinned:
    """A rigid core bar (X along length, Y width, Z up) with transverse dovetail keys along its
    top, and a TPU skin wrapping its top and both sides as a separate solid. The core owns the
    first foot_h of layers across the full skinned width (a flange), so no TPU prints on the
    bed; core and skin touch, never overlap, and fill the envelope exactly."""
    b = _b()
    mn = (b.Align.CENTER, b.Align.CENTER, b.Align.MIN)
    W = core_w + 2 * skin_t
    top = core_h + skin_t
    core = b.Box(length, core_w, core_h, align=mn) + b.Box(length, W, foot_h, align=mn)
    n = max(int(math.floor(length / key_pitch)) - 1, 0)
    xs = [(i - (n - 1) / 2) * key_pitch for i in range(n)]
    for x in xs:
        core = core - b.Pos(x, 0, core_h) * dovetail_cutter(key_depth, key_mouth, key_base, core_w + 4 * EPS)
    envelope = b.Pos(0, 0, foot_h) * b.Box(length, W, top - foot_h, align=mn)
    skin = envelope - core
    dims = {"outer_w": W, "top": top, "keys_x": xs, "swap_band": (foot_h, top),
            "envelope_volume": length * W * top}
    return Skinned(_part(core), _part(skin), dims)


def skin_errors(skin_t: float, foot_h: float, *, skin_min: float = 1.2, layer_h: float = 0.2,
                core_h: float | None = None, key_depth: float | None = None, line_w: float = 0.4) -> list[str]:
    """Skin >= skin_min, the core owns at least one layer, keys leave a core floor."""
    e = []
    if skin_t < skin_min - 1e-9:
        e.append(f"skin {skin_t} under skin_min {skin_min}")
    if foot_h < layer_h - 1e-9:
        e.append(f"core foot {foot_h} under one layer {layer_h}: TPU would print on layer 1")
    if core_h is not None and key_depth is not None and key_depth > core_h - foot_h - 2 * line_w + 1e-9:
        e.append(f"keys {key_depth} deep cut through the core floor (core {core_h}, foot {foot_h})")
    return e


# ---------------------------------------------------------------- PCB bay (board_outline.json)
# A board_outline.json describes one or more board variants: outline_mm polygon, thickness_mm,
# holes (x_mm, y_mm, d_mm, pad_d_mm), connectors (ref, x_mm, y_mm, w_mm, h_mm, mate_dir),
# keepouts (name, x_mm, y_mm, w_mm, d_mm) and the top and bottom component heights. See
# tools/fab/testdata/board_outline.json for the shape. Board frame: lower-left corner of the outline at the
# origin, top view, Z up out of the component side; the part module places the returned
# solids with a Location (for example a board standing on a wall: Rot then Pos).

MATE_DIRS = {"+X": (1, 0), "-X": (-1, 0), "+Y": (0, 1), "-Y": (0, -1)}


def board_outline(path: str | Path, variant: str | None = None) -> dict:
    """One variant of a board_outline.json (the only one when variant is None)."""
    doc = json.loads(Path(path).read_text())
    variants = {k: v for k, v in doc.items() if isinstance(v, dict) and "outline_mm" in v}
    if variant is None:
        if len(variants) != 1:
            raise KeyError(f"{path}: pick a variant from {sorted(variants)}")
        return next(iter(variants.values()))
    if variant not in variants:
        raise KeyError(f"{path}: no variant {variant!r} (have {sorted(variants)})")
    return variants[variant]


def board_bbox(o: dict) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) of the outline polygon."""
    xs = [p["x_mm"] for p in o["outline_mm"]]
    ys = [p["y_mm"] for p in o["outline_mm"]]
    return min(xs), min(ys), max(xs), max(ys)


def board_mount(o: dict, standoff_h: float, boss_od: float, bore_d: float, bore_depth: float, *,
                base_z: float = 0.0, **kw) -> Feature:
    """A pilot_boss under every mounting hole: bosses stand from base_z, the board's bottom
    face seats on their tops at base_z + standoff_h. bore_d is the screw pilot (fasteners.
    self_tap) or an insert hole, never the board's clearance hole."""
    adds, cuts = [], []
    b = _b()
    for h in o["holes"]:
        f = pilot_boss(boss_od, standoff_h, bore_d, bore_depth, base_z=base_z, **kw)
        adds.append(b.Pos(h["x_mm"], h["y_mm"], 0) * f.add)
        cuts.append(b.Pos(h["x_mm"], h["y_mm"], 0) * f.cut)
    return Feature(_part(b.Compound(adds).fuse() if len(adds) > 1 else adds[0]),
                   _part(b.Compound(cuts).fuse() if len(cuts) > 1 else cuts[0]))


def board_seat_z(o: dict, standoff_h: float, base_z: float = 0.0) -> dict:
    """Z levels of the board stack above base_z: seat (board bottom), top copper, component
    tops, and the lowest bottom-side component (must stay above base_z)."""
    seat = base_z + standoff_h
    top = seat + o["thickness_mm"]
    return {"seat": seat, "top": top, "top_env": top + o["max_component_height_top_mm"],
            "bottom_env": seat - o["max_component_height_bottom_mm"]}


def board_envelope(o: dict, standoff_h: float, *, base_z: float = 0.0, clear: float = 0.0):
    """The space the populated board needs (outline bbox, bottom components to top components)
    grown by clear on every side: subtract it from ribs and walls inside the bay."""
    x0, y0, x1, y1 = board_bbox(o)
    z = board_seat_z(o, standoff_h, base_z)
    b = _b()
    mn = (b.Align.MIN, b.Align.MIN, b.Align.MIN)
    return _part(b.Pos(x0 - clear, y0 - clear, z["bottom_env"] - clear) * b.Box(
        x1 - x0 + 2 * clear, y1 - y0 + 2 * clear, z["top_env"] - z["bottom_env"] + 2 * clear, align=mn))


def plug_envelopes(o: dict, standoff_h: float, plug_len: float, *, base_z: float = 0.0, clear: float = 0.5,
                   skip: tuple[str, ...] = ()) -> list[tuple[str, object]]:
    """(ref, solid) per connector: the mating plug's box from the board edge on the connector's
    mate_dir side out to plug_len, w_mm wide across that direction (centred on the connector),
    from the board top to h_mm above it, grown by clear. Cut them from the shell so a plug
    always fits. skip: refs to leave out (a bench-only programming port)."""
    x0, y0, x1, y1 = board_bbox(o)
    top = board_seat_z(o, standoff_h, base_z)["top"]
    b = _b()
    mn = (b.Align.MIN, b.Align.MIN, b.Align.MIN)
    out = []
    for c in o["connectors"]:
        if c["ref"] in skip:
            continue
        if c["mate_dir"] not in MATE_DIRS:
            raise ValueError(f"connector {c['ref']}: mate_dir {c['mate_dir']!r} not in {sorted(MATE_DIRS)}")
        dx, dy = MATE_DIRS[c["mate_dir"]]
        half = c["w_mm"] / 2 + clear
        if dx:
            xe = x1 if dx > 0 else x0
            lo = (min(xe, xe + dx * plug_len), c["y_mm"] - half)
            size = (plug_len, 2 * half)
        else:
            ye = y1 if dy > 0 else y0
            lo = (c["x_mm"] - half, min(ye, ye + dy * plug_len))
            size = (2 * half, plug_len)
        out.append((c["ref"], _part(b.Pos(lo[0], lo[1], top - clear) * b.Box(
            size[0], size[1], c["h_mm"] + 2 * clear, align=mn))))
    return out


def keepout_boxes(o: dict, z0: float, z1: float, *, grow: float = 0.0) -> list[tuple[str, object]]:
    """(name, solid) per board keepout (antenna, isothermal island...) from z0 to z1, grown by
    grow in XY: no metal (inserts, pins, magnets) may intersect them."""
    b = _b()
    mn = (b.Align.MIN, b.Align.MIN, b.Align.MIN)
    return [(k["name"], _part(b.Pos(k["x_mm"] - grow, k["y_mm"] - grow, z0) * b.Box(
        k["w_mm"] + 2 * grow, k["d_mm"] + 2 * grow, z1 - z0, align=mn))) for k in o["keepouts"]]


def board_errors(o: dict, *, standoff_h: float, boss_od: float, bore_d: float,
                 bay: tuple[float, float, float] | None = None, base_z: float = 0.0,
                 clear: float = 0.5) -> list[str]:
    """Rules between the outline and the bay that holds it:
    the boss seats on the hole's pad (boss_od <= pad_d_mm), the screw pilot is narrower than
    the board's clearance hole, bottom-side components clear the bay floor (standoff_h >
    max_component_height_bottom_mm), every connector has a known mate_dir, and the populated
    board plus clear fits the bay (W, D, H above base_z) when one is given. Feed the result to
    checks.Checks.extend."""
    e = []
    for h in o["holes"]:
        if boss_od > h["pad_d_mm"] + 1e-9:
            e.append(f"boss od {boss_od} wider than hole {h['name']} pad {h['pad_d_mm']} (boss presses on copper)")
        if bore_d >= h["d_mm"] - 1e-9:
            e.append(f"pilot {bore_d} not narrower than hole {h['name']} clearance {h['d_mm']}")
    if standoff_h <= o["max_component_height_bottom_mm"] + 1e-9:
        e.append(f"standoff {standoff_h} does not clear bottom components {o['max_component_height_bottom_mm']}")
    for c in o["connectors"]:
        if c.get("mate_dir") not in MATE_DIRS:
            e.append(f"connector {c['ref']} mate_dir {c.get('mate_dir')!r} not in {sorted(MATE_DIRS)}")
    if bay is not None:
        x0, y0, x1, y1 = board_bbox(o)
        z = board_seat_z(o, standoff_h, base_z)
        need = (x1 - x0 + 2 * clear, y1 - y0 + 2 * clear, z["top_env"] - base_z + clear)
        for axis, n, have in zip("WDH", need, bay):
            if n > have + 1e-9:
                e.append(f"board bay {axis} {have} under the populated board {n:.2f} (clear {clear})")
    return e
