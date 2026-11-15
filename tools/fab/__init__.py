"""Reusable fab library for build123d part modules.

Import with the repo root on sys.path (a mod test: ROOT = HERE.parents[3]):

    sys.path.insert(0, str(ROOT))
    from tools.fab import checks, coupon, features, keepout, rays

Under Bazel, list "//tools/fab:lib" in the target's data (cad_part or
pytest_test) so the files are in the runfiles tree. Modules:

  checks      check(params) convention: collect every broken rule, raise once
  coupon      fit coupons cut from the real part
  features    build123d features: self-tap/insert bosses, teardrop gland holes, rim gasket
              groove and bead, strain-relief saddle with TPU liners, TPU skin with dovetail keys,
              PCB bay from a board_outline.json (bosses, envelopes, plug clearances)
  keepout     rigid hardware keep-out clearance versus printed features
  rays        ray-measured thickness and heights through a B-rep
"""
