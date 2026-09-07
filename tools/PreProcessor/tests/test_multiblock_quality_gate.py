#!/usr/bin/env python3
"""The multi-block quality baseline is a GATE, not a record (#85).

#57 refused to make non-orthogonality a pass condition and said why: transfinite
interpolation was not expected to beat the boundary-layer path, and a binary gate
is what stops "not pretty enough yet" from blocking a release. **That reasoning
expires here.** #80's five-ticket arc exists to move exactly these numbers, so a
figure that nothing enforces is a quality feature whose quality is a claim. The
"a BASELINE here, never a gate" rule is therefore SUPERSEDED by this file, marked
in place in ``.claude/rules/mesher-multiblock.md`` rather than deleted.

ONE OWNER FOR THE THRESHOLDS. The two shipped cases' own gates
(``test_multiblock_cgrid_surface.py``, ``test_multiblock_ogrid_surface.py``)
still print their figures and still assert the report's "a negative means not
measured" rule; what they do NOT do is carry a second copy of the numbers. Every
threshold below is stated once, with the run that produced it, so a regression
names the figure it broke instead of reporting that quality got worse.

MEASURED AT THE DEFAULT, which since #85 is ``MB_SMOOTH_ITERS 20`` rather than 0.
That matters twice over: it is what a user who writes no smoothing line actually
gets, and a gate that had to set the key itself could pass while the shipped
default delivered something else. Check 1 pins the default so this file cannot
come back green because someone turned smoothing off.

THE THRESHOLDS, and where each number comes from:

  shipped C-grid (config/multiblock_cgrid.dat), 11520 cells

    figure            bar        origin                        measured 2026-09-07
    inverted          == 0       #80's acceptance                              0
    nonortho max      < 32.044   #57's recorded baseline                  29.895
    nonortho mean     < 4.562    #57's recorded baseline                   3.821
    wall first cell   <= 0.4368% #57's recorded baseline                  0.0968%

  shipped O-grid (config/multiblock_ogrid.dat), 9216 cells

    inverted          == 0       #80's acceptance                              0
    nonortho max      <= 2.2761  #85's own measurement — NOT #55's 2.250   2.2760
    nonortho mean     <= 1.8750  #55's recorded baseline                   1.8750
    wall first cell   <= 0.0812% #55's recorded baseline                  0.0442%

#80's O-GRID BULLET IS NOT MET AND THIS GATE DOES NOT PRETEND IT IS. That bullet
asks for "nothing worse than 2.25 / 1.875 / 0.08" and the worst angle comes out at
2.2760 — 0.026 deg, 1.2%, worse. The bar above is therefore #85's own measurement
and not #55's, which is the honest way to hold a number that is not the one the
epic asked for: the gate still catches a regression, and the shortfall is recorded
rather than rounded away. #84 localised the residue and it is not the smoother's —
the unsmoothed mesh's own worst corner is 2.250 deg ON the faceted outer wall, the
smoothed one's is 2.276 one grid line in from it, and that wall is frozen because
#83 decided wall nodes do not slide. Closing it needs that decision revisited, not
a tighter threshold here. Check 4 asserts the gap is still under 2% so it cannot
grow in silence.

A BAR ALONE CANNOT CATCH A SMOOTHER THAT STOPPED WORKING, because every threshold
here is an upper bound and a mesh that never moved would sit under three of the
four. So check 3 also drives each case with ``MB_SMOOTH_ITERS 0`` and asserts the
default beats it where it should — a DIRECTION, which is what the smoothing gate
next door uses for the same reason.

WHAT THIS FILE DOES NOT DO, said plainly:

  * It does not run the solver or the grid converter. That is gate 2, and #85's
    dated acceptance run on a SMOOTHED mesh is recorded in
    ``test_multiblock_cgrid_surface.py``'s docstring beside #57's, in the same
    convention. A shape check is not an acceptance run.
  * It measures the two SHIPPED cases only. The other multi-block topologies in
    the golden set have no recorded baseline to hold them to, and inventing one
    here would be a threshold with no run behind it.
  * The bars are absolute figures from one dated run on one machine. The mesher is
    not bit-reproducible (coordinates wobble ~1e-13, see tools/scripts/
    golden_mesh.py), so each bar carries slack well above that floor — but a bar
    is not a proof of stability, and the arithmetic that produced these numbers is
    the C++ ruler's, pinned in tests/cpp/test_mb_quality.cpp.
  * Nothing here checks the cap is a GOOD one. 20 is the safe cap, not the best
    measured: the C-grid's worst angle keeps improving to a cap of 100. The
    derivation is at ``Config::mbSmoothIters``.

Run:  python3 tools/PreProcessor/tests/test_multiblock_quality_gate.py
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
# Each shipped config is retargeted by the gate that owns it, never composed here
# — the same rule the smoothing gate follows, so an edit to one of those files is
# visible from every gate that runs it.
from test_multiblock_cgrid_surface import base_config as cgrid_config  # noqa: E402
from test_multiblock_ogrid_surface import base_config as ogrid_config  # noqa: E402
# The ONE parser for the machine-readable quality line, in the gate that owns it.
from test_multiblock_quality_surface import qlines  # noqa: E402
from mesher_bin import mesher_env as _mesher_env  # noqa: E402

# The default this gate is written against. Stated here as well as in the C++ so
# check 1 can fail by NAME when the two drift, rather than every bar below moving
# for a reason the failure text does not mention.
DEFAULT_SWEEPS = 20

# case -> (figure, comparison, bar, origin). "<" is strict where the epic asked
# for "better than"; "<=" where the bar IS the measured figure or a recorded one
# the run reproduces exactly.
THRESHOLDS = {
    "cgrid": [
        ("inverted", "==", 0, "#80's acceptance"),
        ("nonortho_max_deg", "<", 32.044106, "#57's recorded baseline"),
        ("nonortho_mean_deg", "<", 4.561874, "#57's recorded baseline"),
        ("wall_first_cell_worst_rel", "<=", 0.004368, "#57's recorded baseline"),
    ],
    "ogrid": [
        ("inverted", "==", 0, "#80's acceptance"),
        # NOT #55's 2.250: see the docstring. #80's bullet is unmet by 1.2%.
        ("nonortho_max_deg", "<=", 2.2761, "#85's own measurement"),
        ("nonortho_mean_deg", "<=", 1.875000, "#55's recorded baseline"),
        ("wall_first_cell_worst_rel", "<=", 0.000812, "#55's recorded baseline"),
    ],
}

CONFIGS = {"cgrid": cgrid_config, "ogrid": ogrid_config}

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(tmp, name, config, extra=""):
    stem = os.path.join(tmp, name)
    conf = os.path.join(tmp, name + ".dat")
    with open(conf, "w", encoding="utf-8") as f:
        f.write(config().replace("@STEM@", stem) + extra)
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=900)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def holds(got, op, bar):
    if op == "==":
        return got == bar
    if op == "<":
        return got < bar
    return got <= bar


def main() -> int:
    if not os.path.exists(_BIN):
        print("SKIP: build/HybMesh2D not found (run ./build.sh first)")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        # ── 1. the DEFAULT is what this gate measures ───────────────────────
        #
        # Read off a run rather than off the source: the figure that matters is
        # what the binary does with a config that says nothing, and a gate that
        # trusted the header could pass against a stale build.
        rc, out = run(tmp, "dflt", CONFIGS["cgrid"])
        sm = [l for l in out.splitlines() if l.startswith("HYBMESH_MB_SMOOTH ")]
        cap = None
        for tok in (sm[0].split()[1:] if sm else []):
            k, _, v = tok.partition("=")
            if k == "cap":
                cap = int(v)
        check(f"1. smoothing is ON at the default and the cap is "
              f"{DEFAULT_SWEEPS} (rc={rc}, cap={cap}) — so every bar below is "
              f"measured on what a user who writes no MB_SMOOTH_ITERS line gets",
              rc == 0 and cap == DEFAULT_SWEEPS)
        check("1. ...and the run reports the before/after pair, because a default "
              "that smooths must show what it bought",
              "_BEFORE" in out and len(qlines(out)) == 1)

        # ── 2. every threshold, named ───────────────────────────────────────
        at_default = {}
        for case, rows in THRESHOLDS.items():
            rc, out = run(tmp, case + "_d", CONFIGS[case])
            q = qlines(out)
            check(f"2. the shipped {case} meshes at the default (rc={rc})",
                  rc == 0 and len(q) == 1)
            if not q:
                continue
            at_default[case] = q[0]
            for key, op, bar, origin in rows:
                got = q[0].get(key)
                shown = (f"{100 * got:.4f}%" if key.endswith("_rel")
                         else f"{got:.6f}")
                barshown = (f"{100 * bar:.4f}%" if key.endswith("_rel")
                            else f"{bar:g}")
                check(f"2. {case}: {key} {shown} {op} {barshown} ({origin})",
                      got is not None and holds(got, op, bar))

        # ── 3. the bars are not passing on a mesh nothing touched ───────────
        #
        # Three of the four thresholds are upper bounds, so a smoother that
        # stopped moving nodes would sit under them on the O-grid and under two of
        # them on the C-grid. The direction is what catches that.
        unsmoothed = {}
        for case in THRESHOLDS:
            rc0, out0 = run(tmp, case + "_off", CONFIGS[case],
                            "\nMB_SMOOTH_ITERS 0\n")
            q0 = qlines(out0)
            check(f"3. the shipped {case} also meshes with smoothing OFF "
                  f"(rc={rc0})", rc0 == 0 and len(q0) == 1)
            if not q0 or case not in at_default:
                continue
            unsmoothed[case] = q0[0]
            on, off = at_default[case], q0[0]
            check(f"3. {case}: the WALL FIRST CELL is strictly better at the "
                  f"default than with smoothing off "
                  f"({100 * off['wall_first_cell_worst_rel']:.4f}% -> "
                  f"{100 * on['wall_first_cell_worst_rel']:.4f}%) — the metric "
                  f"#83's control functions exist for, and the one that moves on "
                  f"BOTH shipped cases",
                  on["wall_first_cell_worst_rel"]
                  < off["wall_first_cell_worst_rel"])
            check(f"3. {case}: and the cell count is unchanged "
                  f"({off['cells']} -> {on['cells']}), so the comparison is two "
                  f"coordinate sets over one mesh", on["cells"] == off["cells"])
        # The C-grid's own off-run, reused rather than re-run: it is the same
        # config with the same extra line, and meshing it twice would be two
        # answers to one question as well as eight seconds.
        cg, cg_off = at_default.get("cgrid"), unsmoothed.get("cgrid")
        if cg and cg_off:
            check(f"3. cgrid: BOTH non-orthogonality figures are strictly better "
                  f"at the default too ({cg_off['nonortho_max_deg']:.3f} -> "
                  f"{cg['nonortho_max_deg']:.3f} max, "
                  f"{cg_off['nonortho_mean_deg']:.3f} -> "
                  f"{cg['nonortho_mean_deg']:.3f} mean) — #80's whole claim, and "
                  f"the case it was written about",
                  cg["nonortho_max_deg"] < cg_off["nonortho_max_deg"]
                  and cg["nonortho_mean_deg"] < cg_off["nonortho_mean_deg"])
            check(f"3. ...and the unsmoothed C-grid is still AT #57's recorded "
                  f"baseline, so the bars above are measured against the same "
                  f"mesh that ticket measured "
                  f"({cg_off['nonortho_max_deg']:.3f} vs 32.044)",
                  abs(cg_off["nonortho_max_deg"] - 32.044106) < 1e-3
                  and abs(cg_off["nonortho_mean_deg"] - 4.561874) < 1e-3)

        # ── 4. #80's O-grid bullet: unmet, and the gap cannot GROW ──────────
        og = at_default.get("ogrid")
        if og:
            gap = og["nonortho_max_deg"] - 2.250
            check(f"4. #80's O-grid bullet is NOT met and the shortfall is held: "
                  f"the worst angle is {og['nonortho_max_deg']:.4f} deg against "
                  f"#55's 2.250, a gap of {gap:.4f} deg ({100 * gap / 2.250:.2f}%) "
                  f"— under 2%, and #84 localised it to the FROZEN faceted outer "
                  f"wall rather than to the smoother. If this ever reaches 0, "
                  f"delete the check and close the bullet in #80.",
                  0.0 < gap < 0.045)
            check(f"4. ...while the O-grid's WALL accuracy is better than #55's "
                  f"0.0812%, which is the metric a viscous solve reads "
                  f"({100 * og['wall_first_cell_worst_rel']:.4f}%)",
                  og["wall_first_cell_worst_rel"] < 0.000812)

    print()
    if failures:
        print("%d check(s) failed:" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
