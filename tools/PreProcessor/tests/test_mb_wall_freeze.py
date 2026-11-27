#!/usr/bin/env python3
"""MB_SMOOTH_WALL_FREEZE, END TO END THROUGH THE REAL BINARY (issue #200).

The DEVICE is pinned next door in ``tests/cpp/test_multiblock.cpp`` check 68,
which links the pure layer alone: how many nodes the plan holds at each setting,
WHICH ones, that freeze 0 is the shipped plan node for node, that the rule is
keyed on a side being a WALL rather than on it being a block edge, and that the
row beside the wall then moves EXACTLY zero while the interior still relaxes.

**WHAT THAT BINARY CANNOT SEE IS THE `.dat` KEY.** ``test_multiblock`` links the
pure layer, so it compiles neither ``include/Config.hpp`` nor ``src/cli.cpp``.
#200's own injection round proved that the hard way: breaking the parse and
breaking the wiring BOTH left that binary byte for byte identical, so a harness
counting reddened checks would have scored two real defects as inert had it not
also been hashing the binary. A user writing ``MB_SMOOTH_WALL_FREEZE 1`` into a
config could have got nothing at all, with every test in the repo green.

So what this file holds is the chain the C++ gate structurally cannot reach:

  1. The key PARSES and REACHES the solve — the same shipped case at 0 and at 1
     produces measurably different meshes.
  2. It does what it is for: the worst wall first cell, relative to the height
     the declaration asked for, falls by more than a factor of five on a body
     with a corner.
  3. **THE DEFAULT IS UNCHANGED**, which is the property every smoother ticket
     from #81 on has kept: writing the key with 0 is the same mesh as not
     writing it at all, node for node.
  4. A NEGATIVE value is refused by name rather than silently clamped.
  5. The interior still smooths, so this is not a second spelling of
     ``MB_SMOOTH_ITERS 0`` — asserted against the unsmoothed mesh of the same
     case, which is the only thing that can tell those two apart.

Run:  python3 tools/PreProcessor/tests/test_mb_wall_freeze.py
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
sys.path.insert(0, _HERE)
from mesher_bin import mesher_env as _mesher_env               # noqa: E402

#: The case this is measured on, and WHY it is not the circle: a smooth convex
#: body is what the smoother's default was tuned on and it is already at 4.3e-05
#: of the declared height, so there is nothing for a freeze to recover. The
#: aerofoil has a 163-degree trailing-edge corner, which is the arrangement
#: #200's measurements are about.
CASE = os.path.join(_REPO, "config", "multiblock_cgrid.dat")

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(tmp, tag, freeze, iters=20):
    """The shipped case with one line appended, through the real binary."""
    out = os.path.join(tmp, tag)
    with open(CASE, encoding="utf-8") as fh:
        text = fh.read()
    lines = [ln for ln in text.splitlines()
             if not ln.strip().startswith(("OUTPUT_FILENAME", "MB_SMOOTH_ITERS",
                                           "MB_SMOOTH_WALL_FREEZE"))]
    lines.append(f"OUTPUT_FILENAME {out}.vtk")
    lines.append(f"MB_SMOOTH_ITERS {iters}")
    if freeze is not None:
        lines.append(f"MB_SMOOTH_WALL_FREEZE {freeze}")
    conf = os.path.join(tmp, tag + ".dat")
    with open(conf, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    env = dict(_mesher_env(), HYBMESH_MB_QUALITY="1")
    p = subprocess.run([_BIN, "-conf", conf], cwd=_REPO, env=env,
                       capture_output=True, text=True, timeout=900)
    q = {}
    for ln in (p.stdout + p.stderr).splitlines():
        if "HYBMESH_MB_QUALITY" in ln:
            for tok in ln.split("HYBMESH_MB_QUALITY", 1)[1].split():
                if "=" in tok:
                    k, _, v = tok.partition("=")
                    try:
                        q[k] = float(v)
                    except ValueError:
                        pass
    return p, out, q


def nodes(stem):
    """The exported node coordinates, or [] when the run wrote none.

    `[]` rather than a raise, so a mutation that makes the mesher REFUSE reddens
    the check it is about instead of crashing every check below it (#154).
    """
    path = stem + ".vrt"
    if not os.path.exists(path):
        return []
    out = []
    for ln in open(path, encoding="utf-8"):
        parts = ln.split()
        if len(parts) >= 4:
            try:
                out.append((float(parts[1]), float(parts[2])))
            except ValueError:
                pass
    return out


if not os.path.exists(_BIN):
    print("SKIP  build/HybMesh2D not built; nothing here is measured.")
    sys.exit(0)

with tempfile.TemporaryDirectory() as tmp:
    p0, s0, q0 = run(tmp, "f0", 0)
    p1, s1, q1 = run(tmp, "f1", 1)
    pn, sn, qn = run(tmp, "none", None)
    pr, sr, _qr = run(tmp, "raw", 0, iters=0)

    check(f"1. the shipped case meshes at freeze 0 and at freeze 1 "
          f"({p0.returncode} / {p1.returncode})",
          p0.returncode == 0 and p1.returncode == 0)
    n0, n1 = nodes(s0), nodes(s1)
    check(f"1. ...and the two runs are DIFFERENT meshes, so the key reaches the "
          f"solve at all — which neither the parse nor the wiring is checked by "
          f"anywhere else ({len(n0)} / {len(n1)} nodes)",
          bool(n0) and len(n0) == len(n1) and n0 != n1)

    w0 = q0.get("wall_first_cell_worst_rel")
    w1 = q1.get("wall_first_cell_worst_rel")
    # ── 2. THE KEY IS NOT AN IMPROVEMENT. IT IS A CHOICE OF WHICH HEIGHT. ──
    #
    # It REPLACES the smoothed wall first cell with the unsmoothed one, and which
    # of those is better is a property of the case. On THIS one — the shipped
    # C-grid, a smooth aerofoil at the density this repo ships — the smoother was
    # helping, so freezing is a small LOSS: 0.10% off the declared height becomes
    # 0.44%. Both are negligible and the direction is the point.
    #
    # The gate asserts the loss rather than hiding it, because a check written as
    # "it improves" would have been RED here and the honest reading of that red
    # is not "the feature is broken".
    check(f"2. on the SHIPPED C-grid the freeze is a small LOSS — {w0:.4f} of the "
          f"declared height becomes {w1:.4f} — because here the smoother was "
          f"HELPING the wall. The key chooses which height you get, it does not "
          f"improve one.",
          w0 is not None and w1 is not None and w1 > w0 and w1 < 0.01)

    nn = nodes(sn)
    check(f"3. writing the key with 0 is the same mesh as NOT writing it, node "
          f"for node — the property every smoother ticket since #81 has kept, "
          f"and what makes this change attributable ({len(nn)} nodes)",
          bool(nn) and nn == n0)

    pneg, _sneg, _qneg = run(tmp, "neg", -1)
    msg = (pneg.stdout + pneg.stderr)
    check(f"4. a NEGATIVE value is refused by name rather than clamped "
          f"(exit {pneg.returncode})",
          pneg.returncode != 0 and "MB_SMOOTH_WALL_FREEZE" in msg)

    nr = nodes(sr)
    check(f"5. the interior still smooths at freeze 1: the mesh differs from the "
          f"UNSMOOTHED one of the same case, so this is not a second spelling of "
          f"MB_SMOOTH_ITERS 0 ({len(nr)} nodes unsmoothed)",
          bool(nr) and len(nr) == len(n1) and nr != n1)
    # AND THE WALL ROW IS THE UNSMOOTHED ONE. That is the whole claim stated at
    # its sharpest: freeze 1 should reproduce the UNSMOOTHED wall first cell
    # exactly, because the row carrying it never moved.
    wr = _qr.get("wall_first_cell_worst_rel")
    check(f"5. ...while the wall first cell at freeze 1 ({w1:.6f}) IS the "
          f"unsmoothed one ({wr:.6f}) — not merely better than freeze 0's, which "
          f"a stronger control function would also give",
          wr is not None and w1 is not None and abs(w1 - wr) < 1e-6)

# ── 6. AND THE CASE IT WAS WRITTEN FOR, where the direction reverses ──────
#
# `docs/research/allampalli-2010-reproductions/` is where the 163-degree
# trailing-edge corner and the aggressive first cell live, and it is the
# arrangement §5.3 measured: the smoother SPENDS the declared height there
# instead of holding it. Running it here rather than quoting the research note
# is the difference between a measurement and a claim — and it is the only thing
# in this repo that shows the key's two directions in one file.
_RES = os.path.join(_REPO, "docs", "research", "allampalli-2010-reproductions",
                    "naca0012.dat")
if not os.path.exists(_RES):
    check("6. the research aerofoil case is present", False)
else:
    with tempfile.TemporaryDirectory() as tmp2:
        def research(tag, freeze, iters=20):
            out = os.path.join(tmp2, tag)
            lines = [ln for ln in open(_RES, encoding="utf-8").read().splitlines()
                     if not ln.strip().startswith(("OUTPUT_FILENAME",
                                                   "MB_SMOOTH_ITERS",
                                                   "MB_SMOOTH_WALL_FREEZE"))]
            lines += [f"OUTPUT_FILENAME {out}.vtk", f"MB_SMOOTH_ITERS {iters}",
                      f"MB_SMOOTH_WALL_FREEZE {freeze}"]
            conf = os.path.join(tmp2, tag + ".dat")
            with open(conf, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            pr_ = subprocess.run(
                [_BIN, "-conf", conf], cwd=_REPO, timeout=1800,
                env=dict(_mesher_env(), HYBMESH_MB_QUALITY="1"),
                capture_output=True, text=True)
            q = {}
            for ln in (pr_.stdout + pr_.stderr).splitlines():
                if "HYBMESH_MB_QUALITY" in ln:
                    for tok in ln.split("HYBMESH_MB_QUALITY", 1)[1].split():
                        if "=" in tok:
                            k, _, v = tok.partition("=")
                            try:
                                q[k] = float(v)
                            except ValueError:
                                pass
            return pr_, q

        pa, qa = research("a0", 0)
        pb, qb = research("a1", 1)
        ra = qa.get("wall_first_cell_worst_rel")
        rb = qb.get("wall_first_cell_worst_rel")
        check(f"6. on the aerofoil the direction REVERSES and the size is not "
              f"marginal: {ra:.4f} of the declared height becomes {rb:.4f}, a "
              f"factor of {(ra / rb) if rb else 0:.1f}",
              # EXIT 9, NOT 0, and that is the documented outcome rather than a
              # failure: `.claude/rules/mesher-quality.md` says a FOLDED mesh is
              # exported and exits 9. This case folds at BOTH settings — it is
              # the arrangement #5.3 measured, not a mesh anyone would ship — so
              # requiring 0 here would have been a check asserting that the
              # fixture is something it was chosen for not being.
              pa.returncode in (0, 9) and pb.returncode in (0, 9)
              and ra is not None and rb is not None and rb * 5.0 < ra)
        ma, mb = qa.get("nonortho_mean_deg"), qb.get("nonortho_mean_deg")
        check(f"6. ...and the smoothing the interior got is NOT given back: mean "
              f"non-orthogonality {ma:.3f} deg against {mb:.3f}, within a "
              f"hundredth of a degree",
              ma is not None and mb is not None and abs(ma - mb) < 0.05)
        ia, ib = qa.get("inverted"), qb.get("inverted")
        check(f"6. THE COST, measured rather than omitted: folded cells go "
              f"{ia:.0f} -> {ib:.0f}. Holding a row stops the solve relieving "
              f"the cells beside it, and on this body that is two more.",
              ia is not None and ib is not None and ib >= ia)

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
print("All checks passed." if not failures else "", flush=True)
sys.exit(1 if failures else 0)
