"""Tests for mesh_check.py. Run: pytest tools/print"""

import os
import struct
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mesh_check as mc  # noqa: E402


def cube_tris(s=10.0):
    v = [(x, y, z) for x in (0, s) for y in (0, s) for z in (0, s)]
    # index = x*4 + y*2 + z ; faces wound counter-clockwise seen from outside
    quads = [
        (0, 1, 3, 2),  # x=0
        (4, 6, 7, 5),  # x=s
        (0, 4, 5, 1),  # y=0
        (2, 3, 7, 6),  # y=s
        (0, 2, 6, 4),  # z=0
        (1, 5, 7, 3),  # z=s
    ]
    tris = []
    for a, b, c, d in quads:
        tris += [(v[a], v[b], v[c]), (v[a], v[c], v[d])]
    return tris


def write_binary_stl(path, tris):
    with open(path, "wb") as fh:
        fh.write(b"\0" * 80 + struct.pack("<I", len(tris)))
        for t in tris:
            fh.write(struct.pack("<3f", 0, 0, 0))
            for p in t:
                fh.write(struct.pack("<3f", *p))
            fh.write(b"\0\0")


def write_3mf(path, tris, unit="millimeter", config=None):
    verts, idx = [], {}
    faces = []
    for t in tris:
        f = []
        for p in t:
            if p not in idx:
                idx[p] = len(verts)
                verts.append(p)
            f.append(idx[p])
        faces.append(f)
    vx = "".join('<vertex x="%g" y="%g" z="%g"/>' % p for p in verts)
    tx = "".join('<triangle v1="%d" v2="%d" v3="%d"/>' % tuple(f) for f in faces)
    model = (
        '<?xml version="1.0"?><model unit="%s" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        '<resources><object id="1" type="model"><mesh><vertices>%s</vertices>'
        "<triangles>%s</triangles></mesh></object></resources>"
        '<build><item objectid="1"/></build></model>' % (unit, vx, tx)
    )
    # explicit timestamp: nix sets SOURCE_DATE_EPOCH=1980-01-01 UTC, which is
    # 1979 in US time zones and breaks zipfile's default on Python 3.14
    info = zipfile.ZipInfo("3D/3dmodel.model", date_time=(2026, 1, 1, 0, 0, 0))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(info, model)
        if config is not None:
            z.writestr(zipfile.ZipInfo("Metadata/Slic3r_PE_model.config", date_time=(2026, 1, 1, 0, 0, 0)), config)


@pytest.mark.parametrize(
    "name,ok",
    [
        ("lid.stl", True),
        ("[a]_label_plate_x4.stl", True),
        ("[c]_window.stl", True),
        ("gland-saddle_x2.stl", True),
        ("Lid.stl", False),
        ("lid clip.stl", False),
        ("[b]_lid.stl", False),
        ("lid_x0.stl", False),
    ],
)
def test_names(name, ok):
    assert mc.check_name(name) is ok


def test_binary_cube_passes(tmp_path):
    p = tmp_path / "cube_x2.stl"
    write_binary_stl(p, cube_tris())
    r = mc.check_file(str(p), mc.PRINTERS["example_small"])
    assert r["ok"], r["errors"]
    assert r["binary"] and r["manifold"]
    assert r["volume_mm3"] == pytest.approx(1000.0)
    assert r["bbox_size"] == [10.0, 10.0, 10.0]


def test_open_mesh_fails(tmp_path):
    p = tmp_path / "open.stl"
    write_binary_stl(p, cube_tris()[:-1])
    r = mc.check_file(str(p))
    assert not r["ok"] and r["open_edges"] > 0


def test_inverted_normals_fail(tmp_path):
    p = tmp_path / "inside_out.stl"
    write_binary_stl(p, [(a, c, b) for a, b, c in cube_tris()])
    r = mc.check_file(str(p))
    assert r["manifold"] and r["volume_mm3"] < 0 and not r["ok"]


def test_ascii_rejected(tmp_path):
    p = tmp_path / "ascii.stl"
    lines = ["solid x"]
    for t in cube_tris():
        lines += ["facet normal 0 0 0", "outer loop"]
        lines += ["vertex %g %g %g" % q for q in t]
        lines += ["endloop", "endfacet"]
    p.write_text("\n".join(lines + ["endsolid x"]))
    r = mc.check_file(str(p))
    assert r["binary"] is False and r["manifold"] and not r["ok"]


def test_bed_overflow(tmp_path):
    p = tmp_path / "panel.stl"
    write_binary_stl(p, cube_tris(230.0))
    assert not mc.check_file(str(p), mc.PRINTERS["example_small"])["ok"]
    assert mc.check_file(str(p), mc.PRINTERS["example_large"])["ok"]


def test_3mf_units(tmp_path):
    p = tmp_path / "cube.3mf"
    write_3mf(p, cube_tris(1.0), unit="centimeter")
    r = mc.check_file(str(p))
    assert r["ok"], r["errors"]
    assert r["volume_mm3"] == pytest.approx(1000.0)


def test_printers_come_from_constants():
    assert set(mc.PRINTERS) >= {"example_large", "example_small"}
    assert mc.PRINTERS["example_small"] == (220.0, 220.0, 250.0)
    assert mc.load_printers("/nonexistent/constants.json") == {}


def test_cli_exit_code(tmp_path):
    good = tmp_path / "good.stl"
    write_binary_stl(good, cube_tris())
    assert mc.main([str(good), "--printer", "example_large"]) == 0
    bad = tmp_path / "Bad Name.stl"
    write_binary_stl(bad, cube_tris())
    assert mc.main([str(bad)]) == 1


def write_3mf_objects(path, objects):
    """One <object> per triangle list (a multi-body plate)."""
    parts = []
    for oid, tris in enumerate(objects, start=1):
        verts, idx, faces = [], {}, []
        for t in tris:
            f = []
            for p in t:
                if p not in idx:
                    idx[p] = len(verts)
                    verts.append(p)
                f.append(idx[p])
            faces.append(f)
        vx = "".join('<vertex x="%g" y="%g" z="%g"/>' % p for p in verts)
        tx = "".join('<triangle v1="%d" v2="%d" v3="%d"/>' % tuple(f) for f in faces)
        parts.append('<object id="%d" name="body_%d" type="model"><mesh><vertices>%s</vertices>'
                     "<triangles>%s</triangles></mesh></object>" % (oid, oid, vx, tx))
    items = "".join('<item objectid="%d"/>' % i for i in range(1, len(objects) + 1))
    model = ('<?xml version="1.0"?><model unit="millimeter" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             "<resources>%s</resources><build>%s</build></model>" % ("".join(parts), items))
    info = zipfile.ZipInfo("3D/3dmodel.model", date_time=(2026, 1, 1, 0, 0, 0))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(info, model)


def test_3mf_objects_checked_separately(tmp_path):
    # Two cubes sharing the x=10 face: merged they are non-manifold, each alone is closed.
    a = cube_tris(10.0)
    b = [tuple((x + 10.0, y, z) for x, y, z in t) for t in a]
    p = tmp_path / "plate.3mf"
    write_3mf_objects(p, [a, b])
    rep = mc.check_file(str(p))
    assert rep["ok"], rep["errors"]
    assert [o["manifold"] for o in rep["objects"]] == [True, True]
    assert rep["bbox_size"] == [20.0, 10.0, 10.0]
    # A broken object is still caught and named.
    write_3mf_objects(p, [a, b[:-1]])
    rep = mc.check_file(str(p))
    assert not rep["ok"] and any("object body_2" in e for e in rep["errors"])


def test_3mf_volumes_checked_separately(tmp_path):
    """A body and an inlay that share a face (two volumes of one object) are each watertight."""
    a = cube_tris(1.0)
    b = [tuple((x + 1.0, y, z) for x, y, z in t) for t in cube_tris(1.0)]
    merged = tmp_path / "plate.3mf"
    write_3mf(merged, a + b)
    assert not mc.check_file(str(merged))["manifold"]  # shared face, read as one mesh
    split = tmp_path / "plate_split.3mf"
    cfg = (
        '<?xml version="1.0"?><config><object id="1" instances_count="1">'
        '<volume firstid="0" lastid="11"/><volume firstid="12" lastid="23"/></object></config>'
    )
    write_3mf(split, a + b, config=cfg)
    r = mc.check_file(str(split))
    assert r["ok"], r["errors"]
    assert r["parts"] == 2 and r["volume_mm3"] == pytest.approx(2.0)
    assert r["bbox_size"] == [2.0, 1.0, 1.0]
