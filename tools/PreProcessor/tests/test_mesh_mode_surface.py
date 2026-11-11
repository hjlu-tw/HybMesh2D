#!/usr/bin/env python3
"""The multi-block MODE SELECTION surface, end to end (issue #49).

#49 adds the configuration surface for a second generation path before any of the
path exists: a mode parameter, a topology-file parameter, two exit codes, and the
rule that a parameter the active mode never reads is NAMED rather than silently
doing nothing. Everything here drives the real binary, because that is where the
three claims a user can check actually live -- the exit code, the machine-readable
error line and the warning text. The DECISION behind the warning (which keys, and
"set" meaning "differs from the default") is pinned next door in
``tests/cpp/test_mesh_mode.cpp``, which links the pure layer alone and can assert
on the list as data instead of scraping a log.

What this pins down:

  1. The mode DEFAULTS to the existing behaviour, and a config that never mentions
     it runs the hybrid path exactly as before -- the claim the whole ticket rests
     on.
  2. An invalid topology declaration refuses with the TOPOLOGY exit code, names
     what is wrong, and exports nothing. This check is the INVERTED version of the
     one #49 shipped, which asserted the mode said "not implemented yet": that
     sentence was true only while the path did not exist, and #50 built it. What
     the ticket actually promised -- code 8, a machine-readable line, and nothing
     written -- is unchanged and is still what is pinned here.
  3. Every inert parameter the user actually SET is named, one line each.
  4. The four surviving boundary-layer parameters are NOT named INERT. A negative,
     and the half that a "does it warn?" test is most likely to skip. Two of the
     four are also silent in the SECOND sentence, because issue #55's wall
     clustering genuinely reads them; the other two are still named as not read
     yet.
  5. The topology file is read from its own declaration and reported in the banner.
  6. An unknown mode is a CONFIG failure, not a silent fall back to mode 0.
  7. A command-line argument the parser recognises NOTHING of is NAMED, stated to
     have had no effect, and changes nothing else -- the run still exits 0 and
     still writes its mesh. The two-sided half is the one that matters: every
     argument this repo's own scripts and READMEs pass stays SILENT, including the
     ones consumed in phase 1 and every recognised flag's VALUE. ``-mb_smooth_iters``
     is pinned BY NAME, because that flag does not exist and a published
     measurement in #183 was nearly gathered through it: both arms ran at the
     shipped default of 20 and agreed to six decimals, which reads as a clean
     negative result. A flag that exists but was handed no value gets a DIFFERENT
     sentence, because calling it unknown would be false.

THE GOLDEN BASELINE, recorded here because #49's first acceptance item is that the
existing path is untouched and because a procedure nobody wrote down is one nobody
can repeat:

    ref=25bd1cf                                    # the commit this work started from
    mkdir -p /tmp/base && git archive $ref | tar -x -C /tmp/base
    (cd /tmp/base && ./build.sh)                   # the PRE-CHANGE binary
    HYBMESH_GOLDEN_BIN=/tmp/base/build/HybMesh2D \\
        python3 tools/scripts/golden_mesh.py capture /tmp/golden_base
    ./build.sh                                     # the changed tree
    python3 tools/scripts/golden_mesh.py compare /tmp/golden_base

Measured on 2026-08-27, against reference commit ``25bd1cf`` ("fix(gui): the Solver
panel scrolls sideways when the window is too narrow"): **9 cases, 9 SAME, 0 DIFF,
worst coordinate deviation 0.000e+00 on every one** -- run once as a control before
any edit, and again after the C++, GUI and writer changes had all landed. The
``git archive`` route is used rather than "the working tree is currently clean"
because a baseline captured from the tree that is about to be edited is not
evidence about the edit. ``HYBMESH_GOLDEN_BIN`` is what makes the two-binary
comparison possible at all.

Blind spot, named rather than papered over: the comparator does NOT compare the
``.bnd`` source-segment column, so a defect confined to a boundary edge's source
key would still read as SAME. That is unchanged by this ticket and is recorded in
``tools/scripts/golden_mesh.py``'s own docstring.

Run:  python3 tools/PreProcessor/tests/test_mesh_mode_surface.py
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
sys.path.insert(0, _HERE)
from mesher_bin import mesher_env as _mesher_env  # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(tmp, body: str, args=None, conf: bool = True):
    """Run the mesher on a one-off config; return (returncode, combined output).

    ``args`` are appended to the command line, and ``conf=False`` hands the config
    over as the BARE POSITIONAL path instead of through ``-conf`` -- a route the
    argument loop treats differently (phase 1 consumes it by position), so section
    7 has to drive both."""
    dat = os.path.join(tmp, "mode.dat")
    with open(dat, "w", encoding="utf-8") as f:
        f.write(body)
    argv = [_BIN] + (["-conf", dat] if conf else [dat]) + list(args or [])
    p = subprocess.run(argv, cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=180)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def warned_keys(out: str) -> set:
    """The parameter names the mesher reported as INERT in the active mode."""
    return set(re.findall(r"never reads '([A-Z][A-Z0-9_]*)'", out))


def unread_keys(out: str) -> set:
    """The parameter names reported as declared for this mode but not read YET.

    A deliberately different sentence from the one above, matched separately: a
    single regex over both would let one claim be reported as the other, and the
    two ask the user for different things (delete the setting, versus keep it —
    the next increment reads it)."""
    return set(re.findall(r"does not read '([A-Z][A-Z0-9_]*)' yet", out))


def unknown_args(out: str) -> set:
    """The command-line tokens the mesher reported as recognising nothing of."""
    return set(re.findall(r"Unknown command-line argument '([^']*)'", out))


def novalue_args(out: str) -> set:
    """The flags reported as KNOWN but handed no value.

    A deliberately different sentence from the one above, matched separately for
    the same reason ``unread_keys`` is: the two say different things about the
    token -- "no such argument" versus "this argument exists and you left its
    value off" -- and a single regex over both would let one be reported as the
    other."""
    return set(re.findall(r"Command-line argument '([^']*)' expects a value", out))


#: A square duct so the DEFAULT mode has something real to mesh. Written here
#: rather than imported, because what is under test is the config surface and the
#: geometry only has to be meshable.
def write_square(path, n=24, side=2.0):
    with open(path, "w", encoding="utf-8") as f:
        for j in range(4):
            ax, ay = [(0, 0), (side, 0), (side, side), (0, side)][j]
            bx, by = [(0, 0), (side, 0), (side, side), (0, side)][(j + 1) % 4]
            for m in range(n):
                t = m / n
                f.write(f"{ax + (bx - ax) * t:.10f} {ay + (by - ay) * t:.10f}\n")
        f.write("0.0000000000 0.0000000000\n")


def main() -> int:
    if not os.path.exists(_BIN):
        print("SKIP: build/HybMesh2D not found (run ./build.sh first)")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        geom = os.path.join(tmp, "square.dat")
        write_square(geom)

        def plain(stem):
            """A small hybrid case that meshes, named so the caller can find it."""
            return f"""
GEOM_FILE {geom}
DOMAIN_X_MIN -6
DOMAIN_X_MAX 6
DOMAIN_Y_MIN -6
DOMAIN_Y_MAX 6
BL_LAYERS 3
EXPORT_VTK 1
OUTPUT_FILENAME {os.path.join(tmp, stem)}
"""

        # ── 1. the default is the existing path ─────────────────────────────
        rc, out = run(tmp, plain("plain"))
        check("1. a config that never mentions MESH_MODE still meshes (rc=0)", rc == 0)
        check("1. ...and reports mode 0 in the banner, so a finished mesh records "
              "which path made it",
              re.search(r"Mesh Mode\s*:\s*0 \(hybrid", out) is not None)
        check("1. ...and warns about NOTHING: the existing path reads every key it "
              "parses, so a warning here would be a behaviour change on the very "
              f"path this ticket promises is untouched ({sorted(warned_keys(out))})",
              not warned_keys(out))
        check("1. ...and really wrote a mesh",
              os.path.exists(os.path.join(tmp, "plain.vtk")))

        # ── 2-4. the multi-block mode: refusal, named inert keys, silent survivors ──
        topo = os.path.join(tmp, "blocks.json")
        with open(topo, "w", encoding="utf-8") as f:
            f.write('{"format_version": 1, "corners": [], "edges": [], "blocks": []}')
        out_name = os.path.join(tmp, "mb")
        rc, out = run(tmp, f"""
MESH_MODE 1
MESH_TOPOLOGY_FILE {topo}
GEOM_FILE {geom}

# Inert in this mode, and every one of them SET to something other than its
# default, so each must be named. One per group the acceptance criteria list.
DOMAIN_X_MIN -7
DOMAIN_X_MAX 7
DOMAIN_Y_MIN -7
DOMAIN_Y_MAX 7
FARFIELD_MESH_SIZE 2.5
AUTO_FARFIELD_SIZE 1
FARFIELD_GROWTH_RATE 0.42
FARFIELD_BIDIRECTIONAL 1
FARFIELD_GROWTH_RATE_OUTER 0.31
GMSH_ALGORITHM 5
GMSH_OPTIMIZE 0
SEED_SIZE 0.02
SEED_RADIUS 0.9
SEED_MODE embed
BL_MERGE_CONCAVE 1
BL_SMOOTHING_ITERS 4
BL_FAN_NODES 9
BL_AUTO_FAN_NODES 2
BL_FAN_ANGLE_THRESHOLD 55
BL_CONVEX_METHOD 2
BL_PARA_FALLBACK_ANGLE 290
BL_CONVEX_ANGLE_THRESHOLD 250
BL_CONCAVE_METHOD 5
BL_CONCAVE_INFLUENCE_MULTIPLIER 3.0
BL_CONCAVE_ANGLE_THRESHOLD 110
BL_JUNCTION_METHOD 0
BL_JUNCTION_ANGLE_C1 130
BL_JUNCTION_ANGLE_C2 265
BL_JUNCTION_ANGLE_C3 310
BL_TRANSITION_LAYERS 4
BL_AUTO_TRANSITION_LAYERS 1
BL_TRANSITION_GROWTH_RATE 1.3
BL_TRANSITION_BUFFER 2.5
BL_FRONT_SMOOTHING_ITERS 2

# The four that SURVIVE into this mode, all set well away from their defaults so
# a warning about them could not be missed -- and, since #55, so that the SILENCE
# of the two the wall-clustering law reads cannot be mistaken for them sitting at
# a default nothing reports anyway.
BL_INITIAL_THICKNESS 2.5e-6
BL_GROWTH_RATE 1.35
BL_LAYERS 17
BL_USE_ANALYTIC_GEOM 1

EXPORT_VTK 1
OUTPUT_FILENAME {out_name}
""")
        check("2. an invalid topology declaration exits with the TOPOLOGY code (8)",
              rc == 8)
        check("2. ...and prints the machine-readable line a script branches on",
              "HYBMESH_ERROR 8 TOPOLOGY" in out)
        check("2. ...and names WHAT is wrong with the document, rather than failing "
              "obscurely", "'corners' must be a non-empty array" in out)
        check("2. ...and exports NOTHING: the refusal is before any mesh is written",
              not os.path.exists(out_name + ".vtk"))

        got = warned_keys(out)
        want = {
            "DOMAIN_X_MIN", "DOMAIN_X_MAX", "DOMAIN_Y_MIN", "DOMAIN_Y_MAX",
            "FARFIELD_MESH_SIZE", "AUTO_FARFIELD_SIZE", "FARFIELD_GROWTH_RATE",
            "FARFIELD_BIDIRECTIONAL", "FARFIELD_GROWTH_RATE_OUTER",
            "GMSH_ALGORITHM", "GMSH_OPTIMIZE",
            "SEED_SIZE", "SEED_RADIUS", "SEED_MODE",
            "BL_MERGE_CONCAVE", "BL_SMOOTHING_ITERS",
            "BL_FAN_NODES", "BL_AUTO_FAN_NODES", "BL_FAN_ANGLE_THRESHOLD",
            "BL_CONVEX_METHOD", "BL_PARA_FALLBACK_ANGLE", "BL_CONVEX_ANGLE_THRESHOLD",
            "BL_CONCAVE_METHOD", "BL_CONCAVE_INFLUENCE_MULTIPLIER",
            "BL_CONCAVE_ANGLE_THRESHOLD",
            "BL_JUNCTION_METHOD", "BL_JUNCTION_ANGLE_C1", "BL_JUNCTION_ANGLE_C2",
            "BL_JUNCTION_ANGLE_C3",
            "BL_TRANSITION_LAYERS", "BL_AUTO_TRANSITION_LAYERS",
            "BL_TRANSITION_GROWTH_RATE", "BL_TRANSITION_BUFFER",
            "BL_FRONT_SMOOTHING_ITERS",
        }
        check(f"3. every inert parameter that was SET is named ({sorted(want - got)})",
              not (want - got))
        # 18 declared BL parameters do not survive; BL_MERGE_CONCAVE and
        # BL_SMOOTHING_ITERS are global-only settings outside that declaration and
        # are inert for the same reason, so 20 BL_* names are expected here.
        check(f"3. ...including all 18 non-surviving BL parameters plus the two "
              f"global-only BL settings ({len([k for k in got if k.startswith('BL_')])})",
              len([k for k in got if k.startswith("BL_")]) == 20)

        survivors = {"BL_INITIAL_THICKNESS", "BL_GROWTH_RATE", "BL_LAYERS",
                     "BL_USE_ANALYTIC_GEOM"}
        check(f"4. the four surviving BL parameters are NOT called inert, although "
              f"all four are set far from their defaults ({sorted(got & survivors)})",
              not (got & survivors))
        check(f"4. ...and nothing outside the declared inert set is named "
              f"({sorted(got - want)})", not (got - want))
        # But surviving is not the same as READ, and the split moved with issue
        # #55. BL_INITIAL_THICKNESS is now the global wall spacing an edge takes
        # when it names a wall end, and BL_GROWTH_RATE the global ratio a
        # 'geometric' edge takes when it names none, so those two are genuinely
        # read here and must be SILENT -- warning that a value does nothing while
        # the mesh is being built from it is the one wrong answer this pair of
        # sentences can give. The other two are still unread and must still be
        # SAID, in their own words, rather than left to look like a setting that
        # worked. (BL_LAYERS: node counts on this path are declared and propagated,
        # and a class with no seed is refused BY NAME rather than defaulted.
        # BL_USE_ANALYTIC_GEOM: a bound edge follows the resampled polyline.)
        read = {"BL_INITIAL_THICKNESS", "BL_GROWTH_RATE"}
        unread = unread_keys(out)
        check(f"4. ...the two the wall-clustering law READS are silent, although "
              f"both are set far from their defaults ({sorted(read & unread)})",
              not (read & unread))
        check(f"4. ...and each of the other two is named as not read YET "
              f"({sorted((survivors - read) - unread)})",
              unread == survivors - read)
        check(f"4. ...and the two sentences stay disjoint, so a key is never both "
              f"'never read here' and 'not read yet' ({sorted(got & unread)})",
              not (got & unread))

        # ── 5. the topology file is declared, and reported ──────────────────
        check("5. the topology file reaches the banner from its own key",
              re.search(r"Topology File\s*:\s*" + re.escape(topo), out) is not None)
        rc2, out2 = run(tmp, f"MESH_MODE 1\nGEOM_FILE {geom}\n")
        check("5. ...and a multi-block run with none declared says so rather than "
              "picking one up from the geometry's directory",
              "(none declared)" in out2 and rc2 == 8)

        # ── 6. an unknown mode is refused, not clamped ──────────────────────
        rc3, out3 = run(tmp, f"MESH_MODE 3\nGEOM_FILE {geom}\n")
        check("6. an unknown MESH_MODE fails validation with the CONFIG code (2), "
              "rather than silently meshing the hybrid path for someone who asked "
              "for something else", rc3 == 2)
        check("6. ...and the message names the value and the modes that exist",
              "MESH_MODE 3 is not a known mode" in out3)

        # ── 7. an argument the parser recognises nothing of is NAMED ───────
        # The defect this pins is not hypothetical: the smoothed-versus-unsmoothed
        # figures in issue #183 were first gathered as `-mb_smooth_iters 0` against
        # `-mb_smooth_iters 20`. There is no such flag. Both arms ran at the shipped
        # default of 20, every number agreed to six decimals, and that reads as a
        # clean negative result -- "the smoother does not touch this figure". It was
        # caught only because the banner happens to print `Smoothing Sweeps : 20`.
        rc, out = run(tmp, plain("invented"), ["-mb_smooth_iters", "0"])
        check("7. an invented command-line flag is NAMED, with the exact token the "
              f"user typed ({sorted(unknown_args(out))})",
              "-mb_smooth_iters" in unknown_args(out))
        check("7. ...and the message says it was IGNORED and had no effect on this "
              "run, so the caveat arrives with the numbers rather than after them",
              "Unknown command-line argument '-mb_smooth_iters'; it was IGNORED "
              "and had no effect on this run." in out)
        check("7. ...and the run still exits 0: this is advisory, never a refusal",
              rc == 0)
        check("7. ...and still wrote its mesh",
              os.path.exists(os.path.join(tmp, "invented.vtk")))
        # The VALUE of an unknown flag is named too, and that is deliberate: it had
        # no effect either. Whether it should additionally be REFUSED -- because a
        # bare token can be promoted to the positional config path -- is the
        # question #187 exists to answer, and is NOT decided here.
        check("7. ...and the invented flag's value is named on its own, having had "
              f"no effect of its own ({sorted(unknown_args(out))})",
              unknown_args(out) == {"-mb_smooth_iters", "0"})

        # The two-sided half. A warning that fires on everything is as useless as
        # one that fires on nothing, and only one of the two looks broken.
        seed = os.path.join(tmp, "seed.dat")
        nobl = os.path.join(tmp, "nobl.dat")
        dom = os.path.join(tmp, "dom.dat")
        write_square(seed, n=8, side=0.4)
        write_square(nobl, n=8, side=0.6)
        write_square(dom, n=8, side=12.0)
        every_flag = [
            "-geom", geom, nobl,          # the multi-value collectors, two files
            "-geom_nobl", nobl,
            "-seed", seed,
            "-seed_size", "0.05", "-seed_radius", "0.5", "-seed_mode", "source",
            "-domain", dom, "-domain_bl",
            "-bc_xmin", "farfield", "-bc_xmax", "farfield",
            "-bc_ymin", "farfield", "-bc_ymax", "farfield", "-bc_geom", "wall",
            "-out_vtk", "1", "-out_starcd", "0", "-out_cgns", "0",
            "-out_name", os.path.join(tmp, "everyflag"),
        ]
        # MESH_MODE 3 makes this fail validation the moment parsing is over, so the
        # check costs no mesh -- and the exit code is the positive control proving
        # the argument loop really ran rather than the binary dying before it.
        rc, out = run(tmp, f"MESH_MODE 3\nGEOM_FILE {geom}\n", every_flag)
        check("7. every argument the parser knows -- `-conf`, the three multi-value "
              "collectors, `-domain`/`-domain_bl`, the five `-bc_*`, the three "
              "`-out_*` toggles, `-out_name` and the three `-seed_*` -- is SILENT, "
              f"all eighteen in one command line ({sorted(unknown_args(out))})",
              not unknown_args(out))
        check("7. ...and the run still reached validation, so that silence is a "
              "parse that happened rather than one that never ran", rc == 2)
        # Phase 1 collects -conf/-geom/-seed/-geom_nobl and skips the value of each
        # phase-2 flag; phase 2 must not then report any of them unknown. The set
        # above is empty, so this holds for EVERY one of them, not just the first.
        check("7. ...which covers each argument consumed in the EARLY pass "
              "individually, not merely one of them",
              not ({"-conf", "-geom", "-seed", "-geom_nobl"} & unknown_args(out)))
        check("7. ...and no recognised flag's VALUE is reported as an argument of "
              "its own",
              not ({"farfield", "wall", "source", "0.05", "0.5", "1", "0", geom,
                    nobl, seed, dom} & unknown_args(out)))

        # The command lines this repo's own scripts actually use. `-conf <path>`
        # alone is the GUI worker's, the pipeline runner's and the multi-block half
        # of the golden comparator's; the second is golden_mesh.py's hybrid shape.
        rc, out = run(tmp, plain("shipped"),
                      ["-geom", geom, "-out_name", os.path.join(tmp, "shipped2"),
                       "-out_vtk", "1", "-out_starcd", "1"])
        check(f"7. the command line the golden comparator itself runs is silent "
              f"({sorted(unknown_args(out))})", not unknown_args(out))
        check("7. ...and still meshes", rc == 0 and
              os.path.exists(os.path.join(tmp, "shipped2.vtk")))
        rc, out = run(tmp, plain("positional"), conf=False)
        check(f"7. a config handed over as the BARE POSITIONAL path is silent -- it "
              f"was consumed in phase 1 by position, which phase 2 cannot see from "
              f"the token alone ({sorted(unknown_args(out))})",
              not unknown_args(out))
        check("7. ...and still meshes", rc == 0 and
              os.path.exists(os.path.join(tmp, "positional.vtk")))

        # A flag that EXISTS but was handed no value gets its own sentence. Calling
        # it unknown would be false, and would send a user looking for a flag they
        # had spelled correctly.
        rc, out = run(tmp, plain("novalue"), ["-out_name"])
        check(f"7. a recognised flag with no value is reported as a MISSING VALUE "
              f"({sorted(novalue_args(out))})", novalue_args(out) == {"-out_name"})
        check(f"7. ...and is NOT called unknown, which would be false "
              f"({sorted(unknown_args(out))})", not unknown_args(out))
        check("7. ...and that is advisory too: still exit 0, still a mesh",
              rc == 0 and os.path.exists(os.path.join(tmp, "novalue.vtk")))

    print()
    if failures:
        print(f"RESULT: {len(failures)} FAILED")
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
