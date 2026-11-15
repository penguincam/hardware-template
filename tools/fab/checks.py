"""Parameter check() convention for build123d part modules.

Every part module exposes `check(params) -> None` that raises ValueError
listing EVERY rule the parameter set breaks (joined by "; "), not just the
first: a reviewer fixing params.dhall sees all of them at once.
build() calls check() first, so a bad params.json never exports. An earlier
enclosure used about 40 such rules (plate fit, gland grip, insert depth, rib
ratios, keep-out, label bands).

The mod test proves each rule is live: perturb one param and assert the
message (pytest.raises(ValueError, match="gland land")).

    from tools.fab.checks import Checks

    def check(params):
        c = Checks()
        c.need(params, "wall_mm", "floor_mm")
        c.require(params["rib_t_mm"] <= 0.7 * params["wall_mm"], "rib_t_mm over 0.7 x wall")
        c.extend(keepout.violations(rep, 1.0), prefix="keepout: ")
        c.raise_if_any()
"""

from __future__ import annotations


class Checks:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def need(self, params: dict, *keys: str) -> bool:
        """Record missing keys; True when all are present."""
        missing = [k for k in keys if k not in params]
        if missing:
            self.errors.append(f"params missing: {missing}")
        return not missing

    def require(self, ok: bool, message: str, *args) -> bool:
        """Record `message % args` when ok is false; returns ok."""
        if not ok:
            self.errors.append(message % args if args else message)
        return bool(ok)

    def extend(self, messages, prefix: str = "") -> None:
        self.errors += [prefix + m for m in messages]

    def raise_if_any(self) -> None:
        if self.errors:
            raise ValueError("; ".join(self.errors))

    def __bool__(self) -> bool:
        return not self.errors
