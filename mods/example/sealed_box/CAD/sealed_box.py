"""Example sealed box: body, lid and gasket from tools/fab/features.py.

Three builders share one params.json (rendered from ../params.dhall):

  build(params)        the box body, printed opening up: rounded shell, four corner pillars
                       with M3 insert bores, a gasket groove in the rim and a teardrop hole
                       for a cable gland in the front wall (tip up, so it prints without
                       support)
  build_lid(params)    a flat lid that covers the rim and the pillars, with screw clearance
                       holes at the pillars
  build_gasket(params) the TPU bead, printed flat and pressed into the groove

The lid screws sit outside the gasket ring, so no screw hole crosses the seal. check(params)
raises once with every broken rule. Frame: Z up, mm, the box centred on X = 0, Y = 0, the
front wall at -Y.

This is a starting point, not a tested enclosure: nothing here has been printed, and nothing
is proven for outdoor, waterproof or solar use.
"""

from __future__ import annotations

import math

from build123d import Align, Cylinder, Pos

from tools.fab import features as F
from tools.fab.checks import Checks

GLAND = "pg9"  # the hole size comes from params (gland_hole_mm), so no catalogue read here
MIN_WALL = 1.6  # four lines of a 0.4 mm nozzle
KEYS = (
    "inner_w_mm", "inner_d_mm", "inner_h_mm", "inner_r_mm", "wall_mm", "floor_mm",
    "pillar_od_mm", "pillar_ear_mm", "insert_hole_mm", "insert_depth_mm",
    "gasket_inset_mm", "groove_w_mm", "groove_depth_mm", "bead_w_mm", "bead_proud_mm",
    "gland_hole_mm", "gland_clamp_min_mm", "gland_clamp_max_mm", "gland_z_mm", "gland_cap_mm",
    "cable_od_mm", "lid_t_mm", "lid_hole_mm",
)
_MN = (Align.CENTER, Align.CENTER, Align.MIN)


def dims(p: dict) -> dict:
    """Derived sizes: outer W x D with corner R, height H, and the four pillar centres.

    A pillar sits on the diagonal of each outer corner, pillar_ear_mm outside the wall, so it
    fuses with the wall and its insert bore stays clear of the cavity."""
    w = p["inner_w_mm"] + 2 * p["wall_mm"]
    d = p["inner_d_mm"] + 2 * p["wall_mm"]
    r = p["inner_r_mm"] + p["wall_mm"]
    h = p["floor_mm"] + p["inner_h_mm"]
    s = (r + p["pillar_ear_mm"]) / math.sqrt(2)
    cx, cy = w / 2 - r + s, d / 2 - r + s
    pillars = [(sx * cx, sy * cy) for sx in (-1, 1) for sy in (-1, 1)]
    return {"W": w, "D": d, "R": r, "H": h, "pillars": pillars}


def check(p: dict) -> None:
    """Raise ValueError listing every broken rule (tools/fab/checks.py)."""
    c = Checks()
    if not c.need(p, *KEYS):
        c.raise_if_any()
    d = dims(p)
    for k in ("inner_w_mm", "inner_d_mm", "inner_h_mm", "wall_mm", "floor_mm", "lid_t_mm"):
        c.require(p[k] > 0, "%s must be positive", k)
    c.require(p["floor_mm"] >= MIN_WALL, "floor %.2f under %.1f", p["floor_mm"], MIN_WALL)
    c.require(p["lid_t_mm"] >= 2 * MIN_WALL, "lid %.2f under %.1f", p["lid_t_mm"], 2 * MIN_WALL)
    # Gasket groove on the rim (the rim is the wall top).
    c.extend(F.gasket_errors(p["groove_w_mm"], p["bead_w_mm"], p["groove_depth_mm"], p["bead_proud_mm"],
                             rim_w=p["wall_mm"], inset=p["gasket_inset_mm"]), prefix="gasket: ")
    # Pillars: insert boss rules, fused with the wall, bore clear of the cavity.
    c.extend(F.pilot_boss_errors(p["pillar_od_mm"], d["H"], p["insert_hole_mm"], p["insert_depth_mm"],
                                 min_wall=MIN_WALL, min_floor=1.0), prefix="pillar: ")
    c.require(0 <= p["pillar_ear_mm"] < p["pillar_od_mm"] / 2 - 0.5,
              "pillar ear %.2f leaves the pillar loose from the wall (keep it under od / 2 - 0.5)",
              p["pillar_ear_mm"])
    web = p["wall_mm"] + p["pillar_ear_mm"] - p["insert_hole_mm"] / 2
    c.require(web >= MIN_WALL, "insert bore %.2f from the cavity, under %.1f", web, MIN_WALL)
    c.require(p["lid_hole_mm"] < p["pillar_od_mm"] - 2 * MIN_WALL,
              "lid hole %.2f leaves under %.1f of lid round it", p["lid_hole_mm"], MIN_WALL)
    c.require(p["lid_hole_mm"] > p["insert_hole_mm"] - 1.0, "lid hole %.2f too small for the screw",
              p["lid_hole_mm"])
    # Gland: inside the clamp range, the hole between the floor and the rim, inside the wall.
    r = p["gland_hole_mm"] / 2
    top, _half = F.teardrop_profile(r, p["gland_cap_mm"])
    c.require(p["gland_clamp_min_mm"] <= p["cable_od_mm"] <= p["gland_clamp_max_mm"],
              "cable %.1f outside the gland clamp range %.1f-%.1f", p["cable_od_mm"],
              p["gland_clamp_min_mm"], p["gland_clamp_max_mm"])
    c.require(p["gland_z_mm"] - r >= p["floor_mm"] + 1.0,
              "gland hole bottom %.2f within 1 mm of the floor %.2f", p["gland_z_mm"] - r, p["floor_mm"])
    c.require(p["gland_z_mm"] + top <= d["H"] - p["groove_depth_mm"] - 2.0,
              "gland hole top %.2f within 2 mm of the groove floor", p["gland_z_mm"] + top)
    c.require(p["gland_hole_mm"] + 2 * MIN_WALL <= p["inner_w_mm"] - 2 * p["inner_r_mm"],
              "gland hole %.2f does not fit the flat of the front wall", p["gland_hole_mm"])
    c.raise_if_any()


def build(p: dict):
    """The box body, opening up, base on Z = 0."""
    check(p)
    d = dims(p)
    shell = F.rrect_prism(d["W"], d["D"], d["R"], 0.0, d["H"])
    feats = []
    for x, y in d["pillars"]:
        # base_z = EPS: the boss solid starts EPS lower, so the pillar foot lands on Z = 0.
        f = F.pilot_boss(p["pillar_od_mm"], d["H"] - F.EPS, p["insert_hole_mm"], p["insert_depth_mm"],
                         base_z=F.EPS)
        feats.append(F.Feature(Pos(x, y, 0) * f.add, Pos(x, y, 0) * f.cut))
    body = F.apply(shell, *feats)
    cavity = F.rrect_prism(p["inner_w_mm"], p["inner_d_mm"], p["inner_r_mm"], p["floor_mm"], d["H"] + 1.0)
    groove = F.gasket_groove(d["W"], d["D"], d["R"], p["gasket_inset_mm"], p["groove_w_mm"],
                             p["groove_depth_mm"], d["H"])
    # gland_hole cuts a wall that lies in XZ at y in [0, wall]; the front wall starts at -D / 2.
    gland = F.gland_hole(GLAND, p["wall_mm"], hole_d=p["gland_hole_mm"], cap=p["gland_cap_mm"],
                         z=p["gland_z_mm"])
    body = body - cavity - groove - Pos(0, -d["D"] / 2, 0) * gland
    return F._part(body)


def build_lid(p: dict):
    """The lid, printed flat, underside on Z = 0."""
    check(p)
    d = dims(p)
    t = p["lid_t_mm"]
    lid = F.rrect_prism(d["W"], d["D"], d["R"], 0.0, t)
    for x, y in d["pillars"]:
        lid = lid + Pos(x, y, 0) * Cylinder(p["pillar_od_mm"] / 2, t, align=_MN)
    for x, y in d["pillars"]:
        lid = lid - Pos(x, y, -1.0) * Cylinder(p["lid_hole_mm"] / 2, t + 2.0, align=_MN)
    return F._part(lid)


def build_gasket(p: dict):
    """The TPU bead, printed flat (groove floor at Z = 0)."""
    check(p)
    d = dims(p)
    return F.gasket_bead(d["W"], d["D"], d["R"], p["gasket_inset_mm"], p["bead_w_mm"], p["groove_depth_mm"],
                         p["bead_proud_mm"], d["H"], flat=True)
