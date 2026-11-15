# just/template.just: stamp a new hardware repository from this template.

# Stamp a new repo: just stamp cam-box [--owner penguincam] [--visibility private|public] [--keep-example] [--gh]
[positional-arguments]
stamp name *args:
    bash tools/template/stamp.sh "$@"

# Test the stamping script against the committed HEAD (needs one commit).
stamp-test:
    bash tools/template/test_stamp.sh
