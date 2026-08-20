"""JSON persistence for :class:`SolverConfig`, split out to keep that file under the
GUI's 500-line limit.

``load_from_dict`` carries the backward-compatibility rule that matters most for units:
a config written before units existed has a hand-set ``linf`` and no ``length_unit``, and
silently re-deriving ``linf`` would change the Reynolds number of a case that used to run
correctly (Re = fs_UnitRe x Linf). Such a file keeps its value and stops deriving; the
discrepancy is reported by ``unit_check()`` instead of being corrected behind the user's
back.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict


class SolverConfigIOMixin:
    """to_dict / load_from_dict / save_to_file / load_from_file for SolverConfig."""

    # ------------------------------------------------------------------ #
    # Persistence (JSON)
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        return asdict(self)

    def load_from_dict(self, d: dict):
        # A config written before units existed carries a hand-set linf and no
        # length_unit. Deriving linf from the default unit would silently replace that
        # physical setting with 1.0 and change Re, so the derivation is switched off
        # for exactly those files and unit_check() reports the discrepancy instead.
        # An explicit linf_from_unit in the file always wins over this inference.
        if "linf_from_unit" not in d and "length_unit" not in d and "linf" in d:
            self.linf_from_unit = False

        # Coerce each value to the type of the current field default, mirroring
        # MeshConfig.load_from_dict: a hand-written pipeline JSON that quotes a
        # number (e.g. "num_half_iter": "200") still lands as the right type
        # instead of a str that later crashes ":g"/arithmetic formatting. A value
        # that can't be converted is kept as-is (no worse than a raw assignment).
        for k, v in d.items():
            if not hasattr(self, k):
                continue
            cur = getattr(self, k)
            try:
                if isinstance(cur, bool):
                    v = (v.strip().lower() in ("1", "true", "yes", "on")
                         if isinstance(v, str) else bool(v))
                elif isinstance(cur, int):        # bool already handled above
                    v = int(float(v))
                elif isinstance(cur, float):
                    v = float(v)
            except (TypeError, ValueError):
                pass
            setattr(self, k, v)

    def save_to_file(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    def load_from_file(self, path: str):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Solver config not found: {path}")
        with open(path, encoding="utf-8") as f:
            self.load_from_dict(json.load(f))
