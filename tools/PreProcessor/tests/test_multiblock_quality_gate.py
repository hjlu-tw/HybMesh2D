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

  shipped O-grid (config/multiblock_ogrid.dat), 9216 cells — REMEASURED 2026-09-08
  after #95 resolved the far field; every bar is #55's again

    inverted          == 0       #80's acceptance                              0
    nonortho max      <  2.250   #55's recorded baseline                  2.0250
    nonortho mean     <= 1.8750  #55's recorded baseline                   1.8750
    wall first cell   <= 0.0812% #55's recorded baseline                  0.0371%

#80's O-GRID BULLET IS MET, AND THE BAR IS #55's AGAIN (#95, 2026-09-08). That
bullet asks for "nothing worse than 2.25 / 1.875 / 0.08". For four tickets the
worst angle came out at 2.2760 and this gate held a 2.2761 bar that was #85's own
measurement rather than a recorded baseline, plus a check that the 1.2% shortfall
could not grow. Both are DELETED rather than loosened: the shipped far field is now
a 320-facet polyline instead of an 80-facet one, and the worst angle is 2.0250 —
under #55's figure with 0.225 deg of margin, on a mesh that needed no kernel change
at all.

WHY THE GEOMETRY WAS THE ANSWER (#93). #55's 2.250 was itself a SAMPLING artefact:
an 80-facet circle under a 96-node ring is 0.833 facets per mesh interval, so the
ring meshed an irregular polygon and the polyline's turning fell unevenly on the
nodes. Resolved past the mesh, the far field stops binding and the residue moves to
the BODY — 160 facets under the same ring — which is the whole of today's 2.0250,
and is why refining further does not move it. THE MEAN IS MET EXACTLY AND
STRUCTURALLY, never with margin: 1.875 is half a 96-gon's sector angle (360/96/2)
and no far-field density moves it. See docs/design_notes/mesher.md, "THE O-GRID's
RESIDUE IS A SAMPLING RATIO, NOT A FROZEN WALL".

A BAR ALONE CANNOT CATCH A SMOOTHER THAT STOPPED WORKING, because every threshold
here is an upper bound and a mesh that never moved would sit under three of the
four. So check 3 also drives each case with ``MB_SMOOTH_ITERS 0`` and compares — a
DIRECTION, which is what the smoothing gate next door uses for the same reason.

IT IS NOT ONE DIRECTION FOR BOTH CASES SINCE #95. The C-grid's wall first cell is
still strictly BETTER at the default (0.4368% -> 0.0968%), which is what #83's
control functions were built for. The O-grid's is no longer better and cannot be:
with the far field resolved, its UNSMOOTHED wall spacing is 0.0036% — 22x inside
#55's bar and an order better than anything the smoother has ever delivered on this
case — so the default moves it to 0.0371%, which is a cost rather than a
regression, and still 2.2x inside the bar. What catches a dead smoother there is
that the figure MOVES AT ALL, asserted as such rather than as an improvement it
cannot make. The threshold it must not break is #80's, and check 2 holds it.

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
    golden_mesh.py), and most bars carry slack far above that floor — but **the
    O-grid's MEAN bar passes on EXACT EQUALITY** (1.875000 <= 1.875000), so that
    one has no slack at all. It survives because the figure is structural rather
    than computed: a 96-gon's every quad corner deviates by half the sector angle
    whatever the radial distribution is, which is why it reads the same at every
    cap from 0 to 200 and at every far-field density #95 measured. (It said
    "48-gon" until #95; the ring is 96 nodes — 4704 vertices over 49 radial
    stations — and 360/96/2 is what gives 1.875. #93 corrected the same slip in the
    design note and this copy was missed.) If it ever wobbles, this is the bar that will say so first,
    and the fix is a tolerance rather than a looser number. The arithmetic behind
    every figure is the C++ ruler's, pinned in tests/cpp/test_mb_quality.cpp.
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
from test_multiblock_cgrid_surface import (  # noqa: E402
    CGRID_BASELINE, base_config as cgrid_config)
from test_multiblock_ogrid_surface import (  # noqa: E402
    OGRID_BASELINE, base_config as ogrid_config)
# The ONE parser for each machine-readable line, each imported from the gate that
# owns it: `qlines` reports the MESH, `smooth_line` the SOLVE. Hand-rolling the
# second is what `.claude/rules/mesher-smoothing.md` forbids in as many words —
# "the ONE parser every gate imports rather than four near-copies" — and this file
# did exactly that for one commit.
from test_multiblock_quality_surface import qlines  # noqa: E402
from test_multiblock_smooth_surface import smooth_line  # noqa: E402
from mesher_bin import NO_SMOOTH, mesher_env as _mesher_env  # noqa: E402

# The default this gate is written against. Stated here as well as in the C++ so
# check 1 can fail by NAME when the two drift, rather than every bar below moving
# for a reason the failure text does not mention.
DEFAULT_SWEEPS = 20

# THE RECORDED BASELINES ARE IMPORTED, NOT RETYPED: `CGRID_BASELINE` is #57's and
# `OGRID_BASELINE` is #55's, each declared in the gate that owns its case. That is
# the direction the dependency has to run — this file already reads `base_config`
# from both — and it is what makes "the thresholds have one owner" a property of
# the modules rather than a promise in this docstring. It was three owners for one
# commit, and a review counted them.
# THERE IS NO LONGER A FIGURE HERE THAT IS NOT A RECORDED BASELINE. `OGRID_MAX_ACHIEVED
# = 2.2761` and `OGRID_MAX_GAP_FRAC = 0.02` lived here for four tickets, holding #80's
# O-grid shortfall visible and stopping it growing in silence. #95 resolved the geometry
# that caused it, so both are DELETED rather than loosened — the bar below is #55's own
# 2.250 again, and check 4 now asserts the bullet is met instead of that it is not.

# case -> (figure, comparison, bar, origin). "<" is strict where the epic asked
# for "better than"; "<=" where the bar IS the measured figure or a recorded one
# the run reproduces exactly.
THRESHOLDS = {
    "cgrid": [
        ("inverted", "==", 0, "#80's acceptance"),
        ("nonortho_max_deg", "<", CGRID_BASELINE["nonortho_max_deg"],
         "#57's recorded baseline"),
        ("nonortho_mean_deg", "<", CGRID_BASELINE["nonortho_mean_deg"],
         "#57's recorded baseline"),
        ("wall_first_cell_worst_rel", "<=",
         CGRID_BASELINE["wall_first_cell_worst_rel"], "#57's recorded baseline"),
    ],
    "ogrid": [
        ("inverted", "==", 0, "#80's acceptance"),
        # #55's own again since #95, and STRICT: the case beats it by 0.225 deg
        # rather than reproducing it, so "<" is what the measurement supports.
        ("nonortho_max_deg", "<", OGRID_BASELINE["nonortho_max_deg"],
         "#55's recorded baseline"),
        ("nonortho_mean_deg", "<=", OGRID_BASELINE["nonortho_mean_deg"],
         "#55's recorded baseline"),
        ("wall_first_cell_worst_rel", "<=",
         OGRID_BASELINE["wall_first_cell_worst_rel"], "#55's recorded baseline"),
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
    # A TYPO IN `THRESHOLDS` MUST NOT SILENTLY WEAKEN A BAR, which a fall-through
    # to "<=" would do — the loosest of the three, and the one a mistake would land
    # on. Raising is the only answer that cannot pass.
    if op == "==":
        return got == bar
    if op == "<":
        return got < bar
    if op == "<=":
        return got <= bar
    raise ValueError(f"unknown comparison {op!r} in THRESHOLDS")


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
        cap = smooth_line(out).get("cap")
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
        #
        # WHAT THE DEFAULT MUST DO TO THE WALL METRIC, PER CASE. It was one rule for
        # both until #95 resolved the O-grid's far field; see the docstring. The
        # C-grid still improves; the O-grid's unsmoothed spacing is now so far
        # inside #55's bar that the smoother cannot improve on it, so what is
        # asserted there is that the metric MOVED. Stated as a table rather than as
        # an `if case ==`, so a third shipped case has to declare which it is.
        wall_direction = {"cgrid": "better", "ogrid": "moves"}
        unsmoothed = {}
        for case in THRESHOLDS:
            rc0, out0 = run(tmp, case + "_off", CONFIGS[case],
                            NO_SMOOTH)
            q0 = qlines(out0)
            check(f"3. the shipped {case} also meshes with smoothing OFF "
                  f"(rc={rc0})", rc0 == 0 and len(q0) == 1)
            if not q0 or case not in at_default:
                continue
            unsmoothed[case] = q0[0]
            on, off = at_default[case], q0[0]
            want = wall_direction[case]
            moved = f"({100 * off['wall_first_cell_worst_rel']:.4f}% -> " \
                    f"{100 * on['wall_first_cell_worst_rel']:.4f}%)"
            if want == "better":
                check(f"3. {case}: the WALL FIRST CELL is strictly better at the "
                      f"default than with smoothing off {moved} — the metric "
                      f"#83's control functions exist for",
                      on["wall_first_cell_worst_rel"]
                      < off["wall_first_cell_worst_rel"])
            else:
                check(f"3. {case}: the WALL FIRST CELL MOVES at the default {moved} "
                      f"— since #95 the unsmoothed spacing on this case is already "
                      f"inside #55's bar by 22x, so the smoother cannot improve on "
                      f"it and a direction would be asserting the wrong thing; what "
                      f"a dead smoother could not do is move it at all",
                      on["wall_first_cell_worst_rel"]
                      != off["wall_first_cell_worst_rel"])
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
                  all(abs(cg_off[k] - v) < 1e-3
                      for k, v in CGRID_BASELINE.items()
                      if not k.endswith("_rel")))

        # ── 4. #80's O-grid bullet: MET, on all three figures ───────────────
        #
        # This check was the mirror of itself for four tickets — "NOT met and the
        # shortfall is held under 2%" — and said in as many words that when the gap
        # reached 0 it should be deleted and the bullet closed. #95 took it to 0, so
        # it is rewritten in the direction it now measures rather than kept as a
        # loosened bound. The margin is stated per figure because the three are met
        # in three different ways: the worst angle beats #55's by 0.225 deg, the
        # wall by 2.2x, and the MEAN is met EXACTLY and can never be met by more —
        # 1.875 is half the 96-gon's sector angle, so it is structural.
        og = at_default.get("ogrid")
        og_off = unsmoothed.get("ogrid")
        if og:
            bar = OGRID_BASELINE["nonortho_max_deg"]
            check(f"4. #80's O-grid bullet is MET on the worst angle: "
                  f"{og['nonortho_max_deg']:.4f} deg against #55's {bar:g}, a "
                  f"margin of {bar - og['nonortho_max_deg']:.4f} deg — and #55's "
                  f"figure was itself a sampling artefact of an 80-facet far field "
                  f"under 96 mesh nodes (#93), which #95 resolved to 320",
                  og["nonortho_max_deg"] < bar)
            mbar = OGRID_BASELINE["nonortho_mean_deg"]
            check(f"4. ...the MEAN exactly and structurally, never with margin "
                  f"({og['nonortho_mean_deg']:.6f} vs {mbar:.6f}): it is half a "
                  f"96-gon's sector angle, 360/96/2, so no geometry density moves "
                  f"it and a figure BELOW it would mean the ring stopped being "
                  f"polar",
                  og["nonortho_mean_deg"] == mbar)
            wbar = OGRID_BASELINE["wall_first_cell_worst_rel"]
            check(f"4. ...and the WALL accuracy, the metric a viscous solve reads, "
                  f"better than #55's {100 * wbar:.4f}% "
                  f"({100 * og['wall_first_cell_worst_rel']:.4f}%)",
                  og["wall_first_cell_worst_rel"] < wbar)
        if og and og_off:
            # THE NEGATIVE CONTROL #80 ASKED FOR AND THIS CASE COULD NOT GIVE. A
            # smoother run on a mesh that is already good must not make it worse;
            # for four tickets it added 0.026 deg here, which was the whole of the
            # unmet bullet. Exact equality is the right comparison and not a
            # tolerance dodge: at a far-field density the mesh can sample, the
            # smoother's excess is not small but ZERO, to all six printed digits.
            check(f"4. ...and the SMOOTHER'S EXCESS over its own unsmoothed "
                  f"baseline is exactly zero on this case "
                  f"({og_off['nonortho_max_deg']:.6f} -> "
                  f"{og['nonortho_max_deg']:.6f}), which is #80's negative control "
                  f"and what the shipped geometry could not demonstrate before #95",
                  og["nonortho_max_deg"] == og_off["nonortho_max_deg"])

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
