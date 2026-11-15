"""Repo macros for mods (load from //tools/bazel:defs.bzl).

cad_part(name, src, params, material): build123d module -> <name>.step,
    <name>.stl (binary), <name>.3mf and <name>.report.json (valid, solids,
    bbox, volume, solid mass at the material density from
    ssot/generated/materials.json). The module defines build(params) -> Part;
    tools/bazel/cad_export.py loads it by path. committed_stl adds
    <name>_test (built vs committed STL: volume and bbox).
bed_fit_test(name, report, printers): the report bbox fits each named
    printer (ssot/constants/printers.dhall) with a margin, as built or in any
    of the 6 axis-aligned orientations.
laser_sheet(name, src, params, vendor, sku): build123d 2D builder (default
    build_sheet) -> <name>.dxf (mm, CUT/SCORE/ENGRAVE layers) and
    <name>.dxf.json, plus <name>_test: ezdxf audit and DXF lint
    (tools/laser/dxf_lint.py) against the vendor profile
    (ssot/constants/laser_vendors.dhall; default example_service: nominal
    geometry, CUT only, SKU hole and web rules).
sheet_order_test(name): the mod's committed order/ package matches a fresh
    build from order/spec.json (tools/laser/sheet_quote.py --verify).
slice_check(name, model, profile): py_test slicing the model with the
    OrcaSlicer CLI (profiles under third_party/slicer_profiles/<printer>/,
    flattened through their inherits chain first) and asserting
    grams/hours/tool-change budgets from
    Metadata/slice_info.config; skips with a reason when no slicer is found
    or the vendor presets cannot be fetched.
metadata_test(name, metadata): checks a rendered .metadata.yml against the
    mod layout (required keys, slug == directory, every listed file exists).
pytest_test(name, paths, data, deps): runs pytest over workspace-relative
    paths inside the test's runfiles (tools/bazel/pytest_main.py).
"""

load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_test.bzl", "py_test")

_MOD_FILES = ["CAD/**", "STLs/**", "3MF/**", "DXF/**", "images/**", "docs/**"]
_MATERIALS = "//:ssot/generated/materials.json"
_CONSTANTS = "//:ssot/generated/constants.json"
_CAD_EXPORT = "//tools/bazel:cad_export"
_LASER_EXPORT = "//tools/bazel:laser_export"
_DXF_LINT = "//tools/laser:dxf_lint.py"
_SHEET_QUOTE = "//tools/laser:sheet_quote.py"
_SLICE_REPORT = "//tools/print:slice_report.py"

def cad_part(
        name,
        src,
        params,
        material = None,
        fn = "build",
        data = [],
        deps = [],
        committed_stl = None,
        **kwargs):
    """Build STEP, binary STL, 3MF and a JSON report from a build123d module.

    Args:
      name: target name; output basename (use a Voron-valid name: snake_case,
        optional [a]_ prefix, optional _xN suffix).
      src: the build123d module (defines `fn(params) -> Part`).
      params: the mod's rendered params.json.
      material: key in ssot/generated/materials.json (petg, pla, ...) for
        the report's solid mass; None leaves mass out.
      fn: builder function name in src.
      data: extra files the module reads (sibling helper modules, fonts).
        List "//tools/fab:lib" to `from tools.fab import coupon` (or any
        tools.fab module): cad_export.py adds the staged tools/fab to the
        `tools` package path.
      deps: extra py deps; when set, a private exporter binary is built.
      committed_stl: if set, also define <name>_test comparing the built STL
        with this committed file (volume and bounding box).
      **kwargs: passed to the genrule (tags, visibility, ...).
    """
    tool = _CAD_EXPORT
    if deps:
        tool = ":" + name + "_export"
        py_binary(
            name = name + "_export",
            srcs = ["//tools/bazel:cad_export.py"],
            main = "//tools/bazel:cad_export.py",
            deps = ["@pypi//build123d"] + deps,
        )
    mat = ""
    if material:
        mat = "--materials $(location {m}) --material {k} ".format(m = _MATERIALS, k = material)
    native.genrule(
        name = name,
        srcs = [src, params, _MATERIALS] + data,
        outs = [
            name + ".step",
            name + ".stl",
            name + ".3mf",
            name + ".report.json",
        ],
        cmd = ("$(execpath {t}) --module $(location {s}) --fn {fn} --params $(location {p}) {mat}" +
               "--step $(location {n}.step) --stl $(location {n}.stl) --3mf $(location {n}.3mf) " +
               "--report $(location {n}.report.json) > /dev/null").format(
            t = tool,
            s = src,
            fn = fn,
            p = params,
            mat = mat,
            n = name,
        ),
        tools = [tool],
        **kwargs
    )
    if committed_stl:
        py_test(
            name = name + "_test",
            srcs = ["//tools/bazel:stl_compare.py"],
            main = "//tools/bazel:stl_compare.py",
            args = [
                "$(location :{}.stl)".format(name),
                "$(location {})".format(committed_stl),
            ],
            data = [":{}.stl".format(name), committed_stl],
        )

def bed_fit_test(name, report, printers, margin_mm = 5.0, orientation = "as_built", **kwargs):
    """Assert a cad_part report bbox fits each named printer's build volume.

    Args:
      name: test name.
      report: the cad_part <name>.report.json label.
      printers: printer slugs from ssot/constants/printers.dhall
        (example_large, example_small in the template).
      margin_mm: free space kept on each side in X/Y and on top in Z.
      orientation: "as_built" (exported print orientation), "any" (any of the
        6 axis-aligned orientations), or a permutation such as "xzy".
      **kwargs: passed to py_test.
    """
    args = [
        "--report",
        "$(location {})".format(report),
        "--constants",
        "$(location {})".format(_CONSTANTS),
        "--margin",
        str(margin_mm),
        "--orientation",
        orientation,
    ]
    for p in printers:
        args += ["--printer", p]
    py_test(
        name = name,
        srcs = ["//tools/bazel:bed_fit.py"],
        main = "//tools/bazel:bed_fit.py",
        args = args,
        data = [report, _CONSTANTS],
        **kwargs
    )

def laser_sheet(
        name,
        src,
        params,
        fn = "build_sheet",
        vendor = "example_service",
        sku = None,
        material = None,
        kerf_comp = False,
        bed = None,
        margin_mm = 0.0,
        data = [],
        **kwargs):
    """Export a build123d 2D builder to a layered DXF and lint it.

    Args:
      name: target name; output <name>.dxf and <name>.dxf.json.
      src: module whose `fn(params)` returns a 2D shape (all CUT) or a dict
        of layer -> shape with layers CUT, SCORE, ENGRAVE.
      params: the mod's rendered params.json.
      fn: builder function name (default build_sheet).
      vendor: laser_vendors slug from ssot/generated/constants.json. The
        default "example_service" compensates kerf itself (draw nominal), takes
        CUT only (other layers are dropped) and lints holes and webs against
        the SKU. A repo's shop profile (laser_vendors_local.dhall) offsets
        CUT by its measured kerf and checks its bed. None: no vendor, the
        legacy material/kerf_comp/bed path.
      sku: vendor SKU (for example "AL-2.3", "ACRYLIC-3.0"); required by
        vendors that list SKUs (thickness drives the hole and web rules).
      material: laser material key in materials.json (acrylic3_cast, ...);
        recorded in the report, and its kerf_mm used when kerf_comp is set.
      kerf_comp: vendor = None only: offset CUT by the material kerf/2 in CAD
        (then do not compensate again in the laser software).
      bed: "WxH" mm for an extra lint extents check; None skips it (vendor
        profiles carry their own max part / bed extents).
      margin_mm: offset of the CUT extents from the origin.
      data: extra files the module reads.
      **kwargs: passed to the genrule.
    """
    if vendor and kerf_comp:
        fail("laser_sheet: kerf comes from the vendor profile (kerf_in_cad); drop kerf_comp or set vendor = None")
    flags = "--margin {} ".format(margin_mm)
    if vendor:
        flags += "--constants $(location {c}) --vendor {v} ".format(c = _CONSTANTS, v = vendor)
        if sku:
            flags += "--sku {} ".format(sku)
    if material:
        flags += "--materials $(location {m}) --material {k} ".format(m = _MATERIALS, k = material)
    if kerf_comp:
        if not material:
            fail("laser_sheet: kerf_comp needs material")
        flags += "--kerf-comp "
    native.genrule(
        name = name,
        srcs = [src, params, _MATERIALS, _CONSTANTS] + data,
        outs = [name + ".dxf", name + ".dxf.json"],
        cmd = ("$(execpath {t}) --module $(location {s}) --fn {fn} --params $(location {p}) {f}" +
               "--out $(location {n}.dxf) --report $(location {n}.dxf.json) > /dev/null").format(
            t = _LASER_EXPORT,
            s = src,
            fn = fn,
            p = params,
            f = flags,
            n = name,
        ),
        tools = [_LASER_EXPORT],
        **kwargs
    )
    args = ["$(location :{}.dxf)".format(name)]
    if bed:
        args += ["--bed", bed]
    if vendor:
        args += ["--constants", "$(location {})".format(_CONSTANTS), "--vendor", vendor]
        if sku:
            args += ["--sku", sku]
    py_test(
        name = name + "_test",
        srcs = [_DXF_LINT],
        main = _DXF_LINT,
        args = args,
        data = [":{}.dxf".format(name), _CONSTANTS],
        deps = ["@pypi//ezdxf"],
    )

def sheet_order_test(name, data = None, **kwargs):
    """Fail when the mod's committed sheet order package (order/) is stale.

    Rebuilds the package from order/spec.json (written by `just sheet-quote MOD`
    from sheet_order.dhall) and the committed DXF/STEP files, lints every part
    against its vendor SKU (sheet_quote.py), and compares the result byte for byte
    with order/. `just sheet-verify` checks spec.json against sheet_order.dhall.

    Args:
      name: test name.
      data: files the spec names (default: DXF/** and CAD/*.step).
      **kwargs: passed to py_test.
    """
    if data == None:
        data = native.glob(["DXF/**", "CAD/*.step"], allow_empty = True)
    py_test(
        name = name,
        srcs = [_SHEET_QUOTE, _DXF_LINT],
        main = _SHEET_QUOTE,
        args = [
            native.package_name(),
            "--spec-json",
            "$(location order/spec.json)",
            "--constants",
            "$(location {})".format(_CONSTANTS),
            "--verify",
        ],
        data = data + native.glob(["order/**"]) + [_CONSTANTS],
        deps = ["@pypi//ezdxf"],
        **kwargs
    )

def slice_check(
        name,
        model,
        profile = "example_large",
        params = None,
        max_grams = None,
        max_hours = None,
        max_toolchanges = None,
        **kwargs):
    """Slice a model with the OrcaSlicer CLI and assert print budgets.

    Args:
      name: test name.
      model: 3MF (or STL) label, usually a cad_part <name>.3mf.
      profile: directory under third_party/slicer_profiles holding printer.json,
        process.json and filament.json for one printer (the repo supplies it).
      params: optional params.json; keys slice_budget_g and
        slice_budget_toolchanges_count are used when max_grams /
        max_toolchanges are None (no unit suffix exists for hours: use max_hours).
      max_grams: grams budget.
      max_hours: print-time budget in hours.
      max_toolchanges: tool-change budget for a multi-tool printer.
      **kwargs: passed to py_test (size, tags, ...).
    """
    printer_json = "//:third_party/slicer_profiles/{}/printer.json".format(profile)
    env = {
        "SLICE_INPUT": "$(rootpath {})".format(model),
        "SLICE_PRINTER_JSON": "$(rootpath {})".format(printer_json),
        "SLICE_REPORT_PY": "$(rootpath {})".format(_SLICE_REPORT),
        "SLICE_MAX_GRAMS": "" if max_grams == None else str(max_grams),
        "SLICE_MAX_HOURS": "" if max_hours == None else str(max_hours),
        "SLICE_MAX_TOOLCHANGES": "" if max_toolchanges == None else str(max_toolchanges),
    }
    data = [
        model,
        printer_json,
        "//:slicer_profiles",
        _SLICE_REPORT,
        "//tools/bazel:orca_profiles.py",
        "//tools/bazel:slice_check_test.py",
    ]
    if params:
        env["SLICE_PARAMS"] = "$(rootpath {})".format(params)
        data.append(params)
    tags = kwargs.pop("tags", [])
    pytest_test(
        name = name,
        paths = ["tools/bazel/slice_check_test.py"],
        data = data,
        env = env,
        env_inherit = ["PATH", "HOME", "ORCA_SLICER", "ORCA_PROFILE_CACHE", "ORCA_PROFILE_TAG"],
        # requires-network: vendor presets are fetched once per OrcaSlicer tag
        # (tools/bazel/orca_profiles.py); offline, the test skips with the reason.
        tags = tags + ["external-tool", "requires-network", "slice"],
        **kwargs
    )

def metadata_test(name, metadata = ".metadata.yml", data = [], **kwargs):
    """Check a rendered .metadata.yml against the mod layout.

    Args:
      name: test name.
      metadata: the mod's .metadata.yml.
      data: extra files the manifest lists outside CAD/, STLs/, 3MF/, DXF/,
        images/ and docs/ (for example cad entries under fem/ or sim/), so the
        checker finds them in the sandbox; `just metadata-check` reads the tree
        and needs no list.
      **kwargs: passed to py_test.
    """
    py_test(
        name = name,
        srcs = ["//tools/bazel:metadata_check.py"],
        main = "//tools/bazel:metadata_check.py",
        args = ["$(location {})".format(metadata)],
        data = [metadata] + data + native.glob(_MOD_FILES, allow_empty = True),
        deps = ["@pypi//pyyaml"],
        **kwargs
    )

def pytest_test(name, paths, data = [], deps = [], **kwargs):
    """Run pytest over workspace-relative paths inside the runfiles tree.

    Args:
      name: test name.
      paths: files or directories handed to pytest.
      data: files the tests read (include the test files themselves).
      deps: py deps (pytest is added).
      **kwargs: passed to py_test (size, tags, env, env_inherit, ...).
    """
    py_test(
        name = name,
        srcs = ["//tools/bazel:pytest_main.py"],
        main = "//tools/bazel:pytest_main.py",
        args = paths,
        data = data,
        deps = ["@pypi//pytest"] + deps,
        **kwargs
    )
