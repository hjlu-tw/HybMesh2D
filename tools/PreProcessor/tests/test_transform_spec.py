#!/usr/bin/env python3
"""The Duplicate & Transform geometry, exercised without Qt.

`_apply_transform` was pure geometry that read its nine parameters off sidebar
spin boxes, so none of it could run without a QApplication and a sidebar — and
the two transforms easiest to get subtly wrong, mirror-about-an-arbitrary-axis
and non-uniform scale, were the two with no reachable test at all.

Mirrors and point symmetry are INVOLUTIONS: applying one twice must return the
original points exactly. That is the strongest property available here and it
catches a sign or factor-of-two error that eyeballing a preview would not.

Run:  python3 tools/PreProcessor/tests/test_transform_spec.py
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "gui"))

from app.models.transform_spec import (  # noqa: E402
    BASE_MODES, BASE_MODE_TEXT, KINDS, TransformSpec, base_mode_for_text,
    kind_for_index)

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def close(got, want):
    gx, gy = got
    wx, wy = want
    return (np.allclose(gx, wx, atol=1e-9) and np.allclose(gy, wy, atol=1e-9))


check("0. the geometry is Qt-free", "PyQt6" not in sys.modules)

XS = np.array([1.0, 2.0, -3.0])
YS = np.array([0.0, 5.0, 4.0])

# ── 1. the combo row is mapped by NAME, and out-of-range is not a transform ──
check("1. row 0 is rotate and row 6 is scale",
      kind_for_index(0) == "rotate" and kind_for_index(6) == "scale")
check("1. an out-of-range row names no transform",
      kind_for_index(7) == "" and kind_for_index(-1) == "")
check("1. every kind is reachable from some row", set(KINDS) == set(KINDS[:7]))

# ── 2. rotate ────────────────────────────────────────────────────────────
check("2. rotate 90 deg about the origin maps (1,0) -> (0,1)",
      close(TransformSpec("rotate", angle_deg=90.0).apply([1.0], [0.0]),
            ([0.0], [1.0])))
check("2. rotate about a pivot leaves the pivot fixed",
      close(TransformSpec("rotate", angle_deg=37.0,
                          rot_pivot=(2.0, -1.0)).apply([2.0], [-1.0]),
            ([2.0], [-1.0])))
check("2. rotating by 360 deg is the identity",
      close(TransformSpec("rotate", angle_deg=360.0,
                          rot_pivot=(0.5, 0.5)).apply(XS, YS), (XS, YS)))

# ── 3. mirrors reflect about the axis, and are involutions ───────────────
check("3. mirror_h reflects y about the axis",
      close(TransformSpec("mirror_h", axis_y=3.0).apply([1.0], [1.0]),
            ([1.0], [5.0])))
check("3. mirror_v reflects x about the axis",
      close(TransformSpec("mirror_v", axis_x=3.0).apply([1.0], [1.0]),
            ([5.0], [1.0])))
diag = TransformSpec("mirror_axis", axis_pivot=(0.0, 0.0), axis_dir=(1.0, 1.0))
check("3. mirror about the 45 deg line swaps x and y",
      close(diag.apply([2.0, 0.0], [0.0, 3.0]), ([0.0, 3.0], [2.0, 0.0])))
check("3. an unnormalised axis direction gives the same reflection",
      close(TransformSpec("mirror_axis", axis_dir=(7.0, 7.0)).apply([2.0], [0.0]),
            ([0.0], [2.0])))
check("3. a point ON the axis is its own reflection",
      close(diag.apply([4.0], [4.0]), ([4.0], [4.0])))
for name, spec in [
    ("mirror_h", TransformSpec("mirror_h", axis_y=3.0)),
    ("mirror_v", TransformSpec("mirror_v", axis_x=-2.0)),
    ("mirror_axis", TransformSpec("mirror_axis", axis_pivot=(1.0, 2.0),
                                  axis_dir=(2.0, -5.0))),
    ("point_symmetry", TransformSpec("point_symmetry", sym_centre=(3.0, -4.0))),
]:
    once = spec.apply(XS, YS)
    twice = spec.apply(*once)
    check(f"3. {name} applied twice is the identity", close(twice, (XS, YS)))

# ── 4. a zero-length axis is not a transform ─────────────────────────────
degenerate = TransformSpec("mirror_axis", axis_dir=(0.0, 0.0))
check("4. a zero-length mirror axis reports itself degenerate",
      degenerate.is_degenerate)
check("4. and returns None rather than NaNs", degenerate.apply(XS, YS) is None)
check("4. a tiny but non-zero axis is still a transform",
      not TransformSpec("mirror_axis", axis_dir=(1e-9, 0.0)).is_degenerate)
check("4. only mirror_axis can be degenerate",
      not TransformSpec("rotate").is_degenerate)

# ── 5. point symmetry / translate ────────────────────────────────────────
check("5. point symmetry about a centre maps (1,1) -> (5,7) for centre (3,4)",
      close(TransformSpec("point_symmetry", sym_centre=(3.0, 4.0)).apply([1.0], [1.0]),
            ([5.0], [7.0])))
check("5. translate shifts by the delta",
      close(TransformSpec("translate", delta=(2.0, -3.0)).apply(XS, YS),
            (XS + 2.0, YS - 3.0)))

# ── 6. scale, and the similarity question the callers branch on ──────────
check("6. scale about a pivot leaves the pivot fixed",
      close(TransformSpec("scale", factors=(3.0, 7.0),
                          scale_pivot=(1.0, 2.0)).apply([1.0], [2.0]),
            ([1.0], [2.0])))
check("6. scale multiplies the offset from the pivot per axis",
      close(TransformSpec("scale", factors=(2.0, 3.0),
                          scale_pivot=(1.0, 1.0)).apply([3.0], [2.0]),
            ([5.0], [4.0])))
check("6. equal factors are a similarity",
      not TransformSpec("scale", factors=(2.0, 2.0)).is_nonuniform_scale)
check("6. different factors are NOT a similarity (a circle becomes an ellipse)",
      TransformSpec("scale", factors=(2.0, 2.5)).is_nonuniform_scale)
check("6. only a scale can be non-uniform",
      not TransformSpec("rotate", angle_deg=30.0).is_nonuniform_scale)

# ── 7. translate is the only kind with no reference point ────────────────
check("7. translate has no reference point",
      not TransformSpec("translate").has_reference_point)
check("7. every other kind has one",
      all(TransformSpec(k).has_reference_point for k in KINDS if k != "translate"))

# ── 7b. the base mode is a NAME, not the combo's wording ─────────────────
# The wording was compared as a bare string in three places across two layers,
# so rewording "Custom (Manual)" would have stopped the manual-pivot branch
# matching, with nothing to notice.
check("7b. every base mode has display text, and only those",
      set(BASE_MODE_TEXT) == set(BASE_MODES))
check("7b. the combo's wording maps back to its name",
      base_mode_for_text("Custom (Manual)") == "custom"
      and base_mode_for_text("Start Point") == "start")
check("7b. unrecognised wording falls back to the centre, not to custom",
      base_mode_for_text("Reworded Later") == "centre")
check("7b. only the custom mode hands the pivot to the user",
      TransformSpec("rotate", base_mode="custom").manual_reference
      and not any(TransformSpec("rotate", base_mode=m).manual_reference
                  for m in BASE_MODES if m != "custom"))
check("7b. a spec defaults to the derived centre, not to manual",
      not TransformSpec("rotate").manual_reference)

# ── 8. the caller's arrays are never modified in place ───────────────────
xs, ys = XS.copy(), YS.copy()
TransformSpec("translate", delta=(9.0, 9.0)).apply(xs, ys)
check("8. apply does not mutate its inputs",
      np.allclose(xs, XS) and np.allclose(ys, YS))
check("8. a plain list is accepted as well as an array",
      close(TransformSpec("translate", delta=(1.0, 1.0)).apply([0.0], [0.0]),
            ([1.0], [1.0])))

# ── 9. an unrecognised kind moves nothing rather than guessing ───────────
check("9. an unknown kind returns the points unchanged",
      close(TransformSpec("shear").apply(XS, YS), (XS, YS)))

print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print("All transform-spec checks passed.")
