#!/usr/bin/env python3
"""Check print exports: Voron naming, binary STL, watertight mesh, bed fit.

    mesh_check.py mods/me/box/STLs/*.stl mods/me/box/3MF/*.3mf
    mesh_check.py --printer example_large --json part.stl
    mesh_check.py --bed 220x220x250 part.stl

Per file it reports and checks:
  name      Voron STL naming: snake_case, optional "[a]_"/"[o]_"/"[c]_" colour
            prefix, optional "_xN" quantity suffix, no spaces
            (https://github.com/VoronDesign/VoronUsers/wiki/Mod-Submission-Rules)
  binary    STL must be binary (ASCII STL is rejected)
  manifold  every undirected edge shared by exactly two triangles, and every
            directed edge used once (consistent winding); no degenerate faces
  volume    signed volume > 0 (outward normals), in mm^3
  bbox      size in mm; with --printer/--bed, must fit the build volume in
            the exported orientation (Voron: STLs ship in print orientation)

3MF files are read with zipfile + ElementTree (3D/3dmodel.model, core spec
mesh <vertices>/<triangles>, unit attribute honoured). Each <object> mesh is
checked on its own (a multi-object plate whose bodies touch, such as a
co-printed gasket in its groove, is not one manifold), and a mesh that
Metadata/Slic3r_PE_model.config splits into volumes (firstid/lastid, the
PrusaSlicer layout for a flush label inlay in its recess) is checked per
volume; the bbox and volume reported for the file are the whole plate's.
Stdlib only. Exit 1 on any failure. --printer reads the build volume from
ssot/generated/constants.json (printers.<slug>.x/y/z, from
ssot/constants/printers.dhall).
"""

import argparse
import json
import math
import os
import re
import struct
import sys
import zipfile
import xml.etree.ElementTree as ET

NAME_RE = re.compile(r"^(?!.*_x0[0-9]*$)(\[[aoc]\]_)?[a-z0-9]+(?:[_-][a-z0-9]+)*(_x[1-9][0-9]*)?$")
CONSTANTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "ssot", "generated", "constants.json")


def load_printers(path=CONSTANTS):
    """{slug: (x, y, z) mm} for every printer row in constants.json ({} when absent)."""
    try:
        with open(path, encoding="utf-8") as fh:
            rows = json.load(fh).get("printers", {})
    except FileNotFoundError:
        return {}
    return {k: (float(v["x"]), float(v["y"]), float(v["z"]))
            for k, v in rows.items() if isinstance(v, dict) and all(a in v for a in "xyz")}


PRINTERS = load_printers()
UNIT_MM = {"micron": 0.001, "millimeter": 1.0, "centimeter": 10.0, "inch": 25.4, "foot": 304.8, "meter": 1000.0}
NS3MF = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"


def check_name(path):
    stem, _ = os.path.splitext(os.path.basename(path))
    return bool(NAME_RE.match(stem))


def read_stl(path):
    """Return (is_binary, triangles as [(v0, v1, v2)])."""
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) >= 84:
        (n,) = struct.unpack_from("<I", data, 80)
        if 84 + 50 * n == len(data):
            tris = []
            for i in range(n):
                f = struct.unpack_from("<12f", data, 84 + 50 * i)
                tris.append((f[3:6], f[6:9], f[9:12]))
            return True, tris
    text = data.decode("ascii", errors="replace")
    if not text.lstrip().startswith("solid"):
        raise ValueError("not a binary STL (size mismatch) and not ASCII STL")
    verts = [
        tuple(float(x) for x in m.groups())
        for m in re.finditer(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", text)
    ]
    return False, [tuple(verts[i : i + 3]) for i in range(0, len(verts) - len(verts) % 3, 3)]


def read_3mf(path):
    """All triangles of every object mesh, flattened (see read_3mf_objects)."""
    return [t for _, tris in read_3mf_objects(path) for t in tris]


def _volume_ranges(z):
    """{object id: [(firstid, lastid), ...]} from a PrusaSlicer model config, if any."""
    name = next((n for n in z.namelist() if n.lower() == "metadata/slic3r_pe_model.config"), None)
    if name is None:
        return {}
    out = {}
    for obj in ET.fromstring(z.read(name)).iter("object"):
        vols = [(int(v.get("firstid")), int(v.get("lastid"))) for v in obj.iter("volume")]
        if vols:
            out[obj.get("id")] = vols
    return out


def read_3mf_objects(path):
    """[(name, triangles)] per <mesh> object in every .model part, or per volume
    ("name:k") when the root model's config splits the object's triangles."""
    out = []
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".model")]
        if not names:
            raise ValueError("3MF has no .model part")
        ranges = _volume_ranges(z)
        for name in names:
            root = ET.fromstring(z.read(name))
            scale = UNIT_MM.get(root.get("unit", "millimeter"), 1.0)
            for obj in root.iter(NS3MF + "object"):
                for mesh in obj.iter(NS3MF + "mesh"):
                    vs = [
                        (float(v.get("x")) * scale, float(v.get("y")) * scale, float(v.get("z")) * scale)
                        for v in mesh.iter(NS3MF + "vertex")
                    ]
                    tris = [
                        (vs[int(t.get("v1"))], vs[int(t.get("v2"))], vs[int(t.get("v3"))])
                        for t in mesh.iter(NS3MF + "triangle")
                    ]
                    label = obj.get("name") or obj.get("id")
                    vols = ranges.get(obj.get("id")) if name.lower() == "3d/3dmodel.model" else None
                    if vols and len(vols) > 1 and sum(b - a + 1 for a, b in vols) == len(tris):
                        out += [("%s:%d" % (label, k), tris[a : b + 1]) for k, (a, b) in enumerate(vols)]
                    else:
                        out.append((label, tris))
    return out


def analyse(tris, quantum=1e-4):
    """Weld vertices on a grid, then measure topology, volume and bbox."""
    index = {}

    def vid(p):
        key = tuple(round(c / quantum) for c in p)
        return index.setdefault(key, len(index))

    directed = {}
    undirected = {}
    degenerate = 0
    vol6 = 0.0
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for a, b, c in tris:
        for p in (a, b, c):
            for k in range(3):
                lo[k] = min(lo[k], p[k])
                hi[k] = max(hi[k], p[k])
        ia, ib, ic = vid(a), vid(b), vid(c)
        if len({ia, ib, ic}) < 3:
            degenerate += 1
            continue
        vol6 += (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        )
        for u, v in ((ia, ib), (ib, ic), (ic, ia)):
            directed[(u, v)] = directed.get((u, v), 0) + 1
            e = (u, v) if u < v else (v, u)
            undirected[e] = undirected.get(e, 0) + 1
    open_edges = sum(1 for n in undirected.values() if n == 1)
    nonmanifold = sum(1 for n in undirected.values() if n > 2)
    flipped = sum(1 for n in directed.values() if n > 1)
    size = [hi[k] - lo[k] for k in range(3)] if tris else [0.0, 0.0, 0.0]
    return {
        "triangles": len(tris),
        "vertices": len(index),
        "degenerate": degenerate,
        "open_edges": open_edges,
        "nonmanifold_edges": nonmanifold,
        "inconsistent_winding": flipped,
        "manifold": bool(tris) and open_edges == 0 and nonmanifold == 0 and flipped == 0,
        "volume_mm3": round(vol6 / 6.0, 3),
        "bbox_min": [round(x, 4) for x in lo] if tris else None,
        "bbox_size": [round(x, 4) for x in size],
    }


def fits(size, bed):
    return all(s <= b + 1e-6 for s, b in zip(size, bed))


def _mesh_errors(m, errors, prefix):
    if not m["manifold"]:
        errors.append(
            prefix + "not manifold: %d open, %d non-manifold, %d mis-wound edges"
            % (m["open_edges"], m["nonmanifold_edges"], m["inconsistent_winding"])
        )
    if m["degenerate"]:
        errors.append(prefix + "%d degenerate triangles" % m["degenerate"])
    if m["volume_mm3"] <= 0:
        errors.append(prefix + "volume <= 0: normals inverted or mesh empty")


def check_file(path, bed=None):
    ext = os.path.splitext(path)[1].lower()
    rep = {"file": path, "name_ok": check_name(path), "errors": []}
    if ext == ".stl":
        binary, tris = read_stl(path)
        rep["binary"] = binary
        if not binary:
            rep["errors"].append("ASCII STL: export binary")
    elif ext == ".3mf":
        objects = read_3mf_objects(path)
        tris = [t for _, ts in objects for t in ts]
    else:
        raise ValueError("unsupported file type: " + path)
    rep.update(analyse(tris))
    if not rep["name_ok"]:
        rep["errors"].append("name breaks Voron rules ([a]_ prefix, snake_case, _xN suffix)")
    if ext == ".3mf" and len(objects) > 1:
        # Per object: bodies of one plate may share faces with each other.
        rep["objects"] = []
        for name, ts in objects:
            o = analyse(ts)
            rep["objects"].append({"name": name, **{k: o[k] for k in ("triangles", "manifold", "volume_mm3")}})
            _mesh_errors(o, rep["errors"], "object %s: " % name)
        rep["manifold"] = all(o["manifold"] for o in rep["objects"])
        rep["parts"] = len(objects)
    else:
        _mesh_errors(rep, rep["errors"], "")
    if bed is not None:
        rep["bed"] = list(bed)
        rep["fits_bed"] = fits(rep["bbox_size"], bed)
        if not rep["fits_bed"]:
            rep["errors"].append("bbox %s exceeds bed %s in print orientation" % (rep["bbox_size"], list(bed)))
    rep["ok"] = not rep["errors"]
    return rep


def parse_bed(text):
    parts = [float(x) for x in text.lower().split("x")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("bed must be XxYxZ in mm, e.g. 220x220x250")
    return tuple(parts)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check STL/3MF print exports.")
    ap.add_argument("files", nargs="+")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--printer", choices=sorted(PRINTERS))
    g.add_argument("--bed", type=parse_bed)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    bed = PRINTERS[args.printer] if args.printer else args.bed
    reports = [check_file(f, bed) for f in args.files]
    if args.json:
        print(json.dumps(reports, indent=1))
    else:
        for r in reports:
            flag = "ok  " if r["ok"] else "FAIL"
            print(
                "%s %s  tris=%d vol=%.1fmm3 bbox=%s"
                % (flag, r["file"], r["triangles"], r["volume_mm3"], r["bbox_size"])
            )
            for e in r["errors"]:
                print("     - " + e)
    return 0 if all(r["ok"] for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
