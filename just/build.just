# just/build.just: Bazel build and test, and the tool tests that need no CAD kernel.

build:
    {{bazel}} build //...

test:
    {{bazel}} test //...

# Check every mods/*/*/.metadata.yml (same checker as the metadata_test macro).
metadata-check:
    uv run -q --python-preference only-system --python 3.12 --with pyyaml python tools/bazel/metadata_check.py mods/*/*/.metadata.yml

# Tool unit tests without Bazel or build123d: DXF lint, sheet quote, mesh check, slice report, macro helpers.
test-tools:
    uv run -q --python-preference only-system --python 3.12 --with pytest --with ezdxf --with pyyaml python -m pytest -q -p no:cacheprovider tools/laser tools/print tools/bazel/test_bazel_tools.py
