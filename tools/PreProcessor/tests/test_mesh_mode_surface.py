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
  2. Selecting the multi-block mode refuses with the TOPOLOGY exit code and a
     message saying it is not implemented, and exports nothing.
  3. Every inert parameter the user actually SET is named, one line each.
  4. The four surviving boundary-layer parameters are NOT named. A negative, and
     the half that a "does it warn?" test is most likely to skip.
  5. The topology file is read from its own declaration and reported in the banner.
  6. An unknown mode is a CONFIG failure, not a silent fall back to mode 0.

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


def run(tmp, body: str):
    """Run the mesher on a one-off config; return (returncode, combined output)."""
    dat = os.path.join(tmp, "mode.dat")
    with open(dat, "w", encoding="utf-8") as f:
        f.write(body)
    p = subprocess.run([_BIN, "-conf", dat], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=180)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def warned_keys(out: str) -> set:
    """The parameter names the mesher reported as unread by the active mode."""
    return set(re.findall(r"never reads '([A-Z][A-Z0-9_]*)'", out))


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

        # ── 1. the default is the existing path ─────────────────────────────
        rc, out = run(tmp, f"""
GEOM_FILE {geom}
DOMAIN_X_MIN -6
DOMAIN_X_MAX 6
DOMAIN_Y_MIN -6
DOMAIN_Y_MAX 6
BL_LAYERS 3
EXPORT_VTK 1
OUTPUT_FILENAME {os.path.join(tmp, 'plain')}
""")
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
# a warning about them could not be missed.
BL_INITIAL_THICKNESS 2.5e-6
BL_GROWTH_RATE 1.35
BL_LAYERS 17
BL_USE_ANALYTIC_GEOM 1

EXPORT_VTK 1
OUTPUT_FILENAME {out_name}
""")
        check("2. selecting the multi-block mode exits with the TOPOLOGY code (8)",
              rc == 8)
        check("2. ...and prints the machine-readable line a script branches on",
              "HYBMESH_ERROR 8 TOPOLOGY" in out)
        check("2. ...and says it is not implemented yet, rather than failing "
              "obscurely", "not implemented yet" in out)
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
        check(f"4. the four surviving BL parameters do NOT warn, although all four "
              f"are set far from their defaults ({sorted(got & survivors)})",
              not (got & survivors))
        check(f"4. ...and nothing outside the declared inert set is named "
              f"({sorted(got - want)})", not (got - want))

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

    print()
    if failures:
        print(f"RESULT: {len(failures)} FAILED")
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
