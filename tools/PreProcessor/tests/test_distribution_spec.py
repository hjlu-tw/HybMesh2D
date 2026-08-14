#!/usr/bin/env python3
"""The resampler contract for an edge's point distribution, exercised without Qt.

These rules used to live in AppController, reading thirteen sidebar spin boxes
by name, so none of them could be checked without building a QApplication and a
sidebar. Every case below is a rule the resampler depends on, not a restatement
of the dataclass fields:

1. A spacing of ZERO means "unspecified" and must be ABSENT from the dict — a
   written 0.0 makes readPositiveSpacing see a present-but-invalid value.
2. Presence of a spacing key IS the mode. from_parameters must recover the mode
   from the keys alone, so a hand-written or older config round-trips.
3. In tanh By-End-Spacing the clustering is SOLVED from the spacing, so
   `intensity` must not also be written; with the spacing left at zero it must
   fall back to intensity rather than emitting neither.
4. to_parameters returns a FRESH dict, so a key belonging to the previous
   strategy cannot survive a strategy change.

Run:  python3 tools/PreProcessor/tests/test_distribution_spec.py
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "gui"))

from app.models.distribution_spec import DistributionSpec  # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


check("0. the contract is Qt-free", "PyQt6" not in sys.modules)

# ── 1. uniform: mode decides which single key is written ──────────────────
check("1. uniform By Node Count writes n_points only",
      DistributionSpec("uniform", n_points=80).to_parameters() == {"n_points": 80})
check("1. uniform By Spacing writes spacing only",
      DistributionSpec("uniform", by_spacing=True, spacing=0.25).to_parameters()
      == {"spacing": 0.25})

# ── 2. a zero spacing is OMITTED, not written ─────────────────────────────
geo_one_sided = DistributionSpec("geometric", n_points=40, by_spacing=True,
                                 spacing_start=1e-5, spacing_end=0.0)
check("2. geometric one-sided omits the unset end entirely",
      geo_one_sided.to_parameters() == {"n_points": 40, "spacing_start": 1e-5})
geo_two_sided = DistributionSpec("geometric", n_points=40, by_spacing=True,
                                 spacing_start=1e-5, spacing_end=2e-3)
check("2. geometric two-sided writes both ends",
      geo_two_sided.to_parameters()
      == {"n_points": 40, "spacing_start": 1e-5, "spacing_end": 2e-3})
check("2. geometric By Growth Ratio drops ratio_end when it is 1.0",
      DistributionSpec("geometric", n_points=40, ratio=1.2,
                       ratio_end=1.0).to_parameters()
      == {"n_points": 40, "ratio": 1.2})
check("2. geometric keeps a ratio_end that is not 1.0",
      DistributionSpec("geometric", n_points=40, ratio=1.2,
                       ratio_end=1.05).to_parameters()
      == {"n_points": 40, "ratio": 1.2, "ratio_end": 1.05})

# ── 3. tanh: one source for the clustering, never two ─────────────────────
tanh_ds = DistributionSpec("tanh", n_points=60, by_spacing=True,
                           spacing_ends=3e-4, intensity=2.5).to_parameters()
check("3. tanh By End Spacing writes spacing_start and NOT intensity",
      tanh_ds == {"n_points": 60, "spacing_start": 3e-4})
check("3. tanh is symmetric, so spacing_end is never written",
      "spacing_end" not in tanh_ds)
check("3. tanh By End Spacing with a zero spacing falls back to intensity",
      DistributionSpec("tanh", n_points=60, by_spacing=True, spacing_ends=0.0,
                       intensity=2.5).to_parameters()
      == {"n_points": 60, "intensity": 2.5})
check("3. tanh By Intensity writes intensity",
      DistributionSpec("tanh", n_points=60, intensity=3.0).to_parameters()
      == {"n_points": 60, "intensity": 3.0})

# ── 4. the mode is recovered from the KEYS, with no mode flag stored ──────
check("4. uniform mode recovered from the spacing key",
      DistributionSpec.from_parameters("uniform", {"spacing": 0.25}).by_spacing)
check("4. uniform node-count mode recovered from its absence",
      not DistributionSpec.from_parameters("uniform", {"n_points": 80}).by_spacing)
check("4. tanh mode recovered from spacing_start",
      DistributionSpec.from_parameters(
          "tanh", {"n_points": 60, "spacing_start": 3e-4}).by_spacing)
# An older or hand-written config may carry spacing_end instead; either key
# restores tanh's single symmetric field.
_from_end = DistributionSpec.from_parameters(
    "tanh", {"n_points": 60, "spacing_end": 3e-4})
check("4. tanh mode recovered from spacing_end too", _from_end.by_spacing)
check("4. tanh's symmetric field takes either key", _from_end.spacing_ends == 3e-4)
check("4. geometric mode recovered from an end spacing",
      DistributionSpec.from_parameters(
          "geometric", {"n_points": 40, "spacing_start": 1e-5}).by_spacing)

# ── 5. round-trip: what the form shows must mean what was stored ──────────
for name, params in [
    ("uniform/count", {"n_points": 80}),
    ("uniform/spacing", {"spacing": 0.25}),
    ("tanh/intensity", {"n_points": 60, "intensity": 3.0}),
    ("tanh/spacing", {"n_points": 60, "spacing_start": 3e-4}),
    ("cosine", {"n_points": 30}),
    ("curvature", {"n_points": 30, "sensitivity": 2.0}),
    ("geometric/ratio", {"n_points": 40, "ratio": 1.2}),
    ("geometric/ratio+end", {"n_points": 40, "ratio": 1.2, "ratio_end": 1.05}),
    ("geometric/one-sided", {"n_points": 40, "spacing_start": 1e-5}),
    ("geometric/two-sided", {"n_points": 40, "spacing_start": 1e-5,
                             "spacing_end": 2e-3}),
]:
    strategy = name.split("/")[0]
    got = DistributionSpec.from_parameters(strategy, params).to_parameters()
    check(f"5. {name} round-trips unchanged" + ("" if got == params else f" (got {got})"),
          got == params)

# ── 6. a fresh dict, so a strategy change cannot leave a stale key ────────
spec = DistributionSpec.from_parameters("geometric", {"n_points": 40, "ratio": 1.3})
spec.strategy = "cosine"
check("6. switching strategy drops the previous strategy's keys",
      spec.to_parameters() == {"n_points": 40})

# ── 7. an unknown strategy yields nothing rather than a wrong dict ────────
check("7. an unrecognised strategy writes no parameters",
      DistributionSpec("spline", n_points=10).to_parameters() == {})

print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print("All distribution-spec checks passed.")
