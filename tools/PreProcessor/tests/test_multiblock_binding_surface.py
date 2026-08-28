#!/usr/bin/env python3
"""Boundary conditions BY CONSTRUCTION, end to end through the real binaries (#52).

The decisions live next door in ``tests/cpp/test_multiblock.cpp``, which drives the
pure seam with hand-built geometry fixtures. What can only be checked out here is
that the chain CONNECTS to the real thing: that the ``.meta`` sidecar the real
``surface_resampler`` writes is the one ``buildMultiBlock`` reads, that a
per-segment condition set in the PreProcessor reaches the ``.bnd`` the solver's
converter consumes, and — the ticket's central rule — that re-resampling the
geometry leaves an attached corner where it was.

What this pins down:

  1. A topology attached to a REAL resampling meshes, and its bound sides carry the
     geometry's own per-segment conditions into the ``.bnd`` while its unbound
     sides carry the config default. Three differing conditions on one block.
  2. The labels resolve through ``GROUP_BC``: the sidecar carries a per-segment
     LABEL and a label -> type map, and the patch NAME written is the TYPE. That
     is the distinction the "changed the BCs, same result" defect turned on.
  3. Re-resampling the geometry to a different point count leaves the attached
     corners in the same physical place — the same topology, meshed against two
     resamplings of one geometry, byte-identical corner coordinates.
  4. ...and that is a MEASUREMENT rather than a coincidence: neither resampling
     has a sample point at the attached position, so no implementation that
     snapped a corner to a geometry point could have produced it, and the point
     index nearest the position differs between the two.
  5. A corner attached to a segment that does not exist is refused with the
     TOPOLOGY exit code, names the segment, and exports nothing.
  6. Position-based classification is not used in this path at all: every boundary
     edge reaches the exporter already recorded, so ``classifyBoundaryBc`` returns
     at its per-edge lookup and never reaches ``pointOnSegment``. Checked by
     construction — a bound side is DECLARED as one condition while lying on a
     stretch of geometry that the position-based fallback would have to guess.

BLIND SPOTS, named rather than papered over:

  * Nothing here runs the solver or the grid converter. That the mesh a bound
    topology produces is accepted downstream is #50's dated acceptance run plus
    the acceptance run recorded at the bottom of this docstring — not something
    this file measures on every run.
  * The geometry is straight-sided, so an arc-length position is EXACT under
    resampling and check 3 can assert byte equality. On a curved segment the
    polyline itself changes with the point count, so the corner moves by a chord
    sagitta; that is a discretisation limit of the geometry, not of the binding,
    and no check here claims otherwise. The curve-following half is pinned in the
    C++ test (its check 15) where the geometry can be stated exactly.

ACCEPTANCE RUN, measured 2026-08-28 on the case check 1 builds (the `bound` stem):

    ./build/HybMesh2D -conf <conf>
        -> 3 boundary patch names in the .bnd: inlet, outlet, wall
           banner reports each patch and the segment it was read off

Run:  python3 tools/PreProcessor/tests/test_multiblock_binding_surface.py
Skips cleanly if ./build/HybMesh2D or ./build/surface_resampler is not built.
"""
import json
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_RESAMPLER = os.path.join(_REPO, "build", "surface_resampler")
for _p in (_HERE, _GUI):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from mesher_bin import mesher_env as _mesher_env  # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        failures.append(msg)


# ── the geometry, and two resamplings of it ────────────────────────────────

# Label -> physical BC type, exactly as the GUI persists it in the sidecar
# trailer. The two namespaces are the point: a segment carries a LABEL, and the
# patch name in the .bnd is the TYPE this map resolves it to.
GROUP_BC = {"g_bot": "inlet", "g_rgt": "wall", "g_top": "outlet", "g_lft": "wall"}
LABELS = {1: "g_bot", 2: "g_rgt", 3: "g_top", 4: "g_lft"}


def write_square_source(path, n=41):
    """A finely sampled closed unit square, walked counter-clockwise from (0, 0)."""
    pts = [(x / (n - 1.0), 0.0) for x in range(n)]
    pts += [(1.0, y / (n - 1.0)) for y in range(1, n)]
    pts += [(1.0 - x / (n - 1.0), 1.0) for x in range(1, n)]
    pts += [(0.0, 1.0 - y / (n - 1.0)) for y in range(1, n)]
    with open(path, "w", encoding="utf-8") as f:
        for x, y in pts:
            f.write(f"{x:.12f} {y:.12f}\n")
    return len(pts)


def resample(tmp, src, out, npts, per_side):
    """Run the REAL surface_resampler: 4 segments, `per_side` points on each.

    The per-segment config is built from real ``SegmentModel``s rather than from
    hand-authored JSON, for the reason ``test_seg_edit_carryover`` gives: the
    label reaching the sidecar through ``to_dict()`` is part of what is under
    test, and a literal dict would prove something the GUI does not do.
    """
    from app.models.segment import SegmentModel
    from app.services import meta_io
    step = (npts - 1) // 4
    segs = []
    for i in range(4):
        s0 = i * step
        e0 = (npts - 1) if i == 3 else (i + 1) * step
        seg = SegmentModel(i + 1, s0, e0)
        seg.strategy = "uniform"
        seg.parameters = {"n_points": per_side}
        seg.bc = LABELS[i + 1]
        segs.append(seg.to_dict())
    cfg = {"elements": [{"name": "sq", "input_file": src, "output_file": out,
                         "is_closed": True, "segments": segs}]}
    cfg_path = os.path.join(tmp, f"resample_{per_side}.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    p = subprocess.run([_RESAMPLER, cfg_path], cwd=_REPO,
                       capture_output=True, text=True, timeout=120)
    # The label -> type map is GUI state that lives only in the trailer; the
    # resampler carries a trailer through but never invents one.
    if p.returncode == 0 and os.path.exists(out + ".meta"):
        meta_io.write_meta_group_bc(out, GROUP_BC)
    return p


# ── the topology: one block, two of whose sides lie on the geometry ────────

# South lies on segment 1 (label g_bot -> inlet) between t = 0.25 and t = 0.75;
# north lies on segment 3 (g_top -> outlet), which runs the other way round the
# loop, so its two corners are declared t = 0.75 -> t = 0.25 and the edge walks
# its segment BACKWARDS. East and west declare no binding and take the config
# default. Three differing conditions on one block, which is what makes the
# boundary-file comparison say anything.
def write_topology(path, geom):
    def att(cid, seg, t):
        return {"id": cid, "kind": "on_geometry", "geom": geom, "seg": seg, "t": t}
    doc = {
        "format_version": 1,
        "corners": [att("sw", 1, 0.25), att("se", 1, 0.75),
                    att("ne", 3, 0.25), att("nw", 3, 0.75)],
        "edges": [
            {"id": "south", "corners": ["sw", "se"], "kind": "wall", "count": 7,
             "binding": {"geom": geom, "seg": 1}},
            {"id": "east", "corners": ["se", "ne"], "kind": "wall", "count": 5},
            {"id": "north", "corners": ["nw", "ne"], "kind": "wall", "count": 7,
             "binding": {"geom": geom, "seg": 3}},
            {"id": "west", "corners": ["sw", "nw"], "kind": "wall", "count": 5},
        ],
        "blocks": [{"id": "b0", "edges": ["south", "east", "north", "west"]}],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    return path


def write_config(path, topology, geom, out_stem):
    with open(path, "w", encoding="utf-8") as f:
        f.write("MESH_MODE 1\n"
                f"MESH_TOPOLOGY_FILE {topology}\n"
                f"GEOM_FILE {geom}\n"
                "MB_SPLIT_QUADS 1\n"
                "EXPORT_VTK 1\n"
                "EXPORT_STARCD 1\n"
                "BC_GEOM wall\n"
                f"OUTPUT_FILENAME {out_stem}.vtk\n")
    return path


def build_bound_case(tmp, stem, per_side=6):
    """The whole case on disk — geometry, resampling, topology, config.

    Exported so ``tools/scripts/golden_mesh.py`` can regression-cover a mesh whose
    walls carry DIFFERING conditions through its boundary-file comparison, without
    a second copy of the case. That is the reason `golden_mesh` already imports the
    duct geometries from the junction test and `write_topology` from #50's surface
    test: a case written twice is a guaranteed future divergence, and here it would
    be a divergence in exactly the declaration under test.

    Returns the config path; the caller runs the mesher, so it can use its own
    binary (``HYBMESH_GOLDEN_BIN``) and its own environment.
    """
    src = os.path.join(tmp, "bind_src.dat")
    npts = write_square_source(src)
    geom = os.path.join(tmp, "bind_geom.dat")
    p = resample(tmp, src, geom, npts, per_side)
    if p.returncode != 0:
        raise RuntimeError(f"surface_resampler failed: {p.stdout}{p.stderr}")
    topo = write_topology(os.path.join(tmp, "bind_topo.json"), geom)
    return write_config(os.path.join(tmp, "bind.dat"), topo, geom, stem)


def run(tmp, conf):
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=300)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def bnd_patches(stem):
    """patch name -> face count, from the file the solver's converter reads."""
    out = {}
    with open(stem + ".bnd", encoding="utf-8") as f:
        for line in f:
            s = line.split()
            if s:
                out[s[-1]] = out.get(s[-1], 0) + 1
    return out


def vrt_points(stem):
    pts = []
    with open(stem + ".vrt", encoding="utf-8") as f:
        for line in f:
            s = line.split()
            if len(s) >= 4:
                pts.append((float(s[1]), float(s[2])))
    return pts


def dat_points(path):
    with open(path, encoding="utf-8") as f:
        return [tuple(float(v) for v in ln.split()[:2]) for ln in f if ln.split()]


def main() -> int:
    if not os.path.exists(_BIN) or not os.path.exists(_RESAMPLER):
        print("SKIP: build/HybMesh2D or build/surface_resampler not found "
              "(run ./build.sh first)")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "square.dat")
        npts = write_square_source(src)

        # Two resamplings of ONE geometry, at point counts chosen so that NEITHER
        # has a sample at the attached positions (x = 0.25 and x = 0.75): 6 points
        # per side lands on 0.2/0.4/0.6/0.8, and 11 on the tenths. That is what
        # makes check 3 a measurement of arc length rather than of snapping.
        coarse = os.path.join(tmp, "coarse.dat")
        fine = os.path.join(tmp, "fine.dat")
        rc_c = resample(tmp, src, coarse, npts, 6)
        rc_f = resample(tmp, src, fine, npts, 11)
        check(f"0. (precondition) the real resampler produced both resamplings "
              f"({rc_c.returncode}, {rc_f.returncode})",
              rc_c.returncode == 0 and rc_f.returncode == 0
              and os.path.exists(coarse + ".meta") and os.path.exists(fine + ".meta"))
        if failures:
            print(rc_c.stdout, rc_c.stderr)
            return 1
        n_coarse, n_fine = len(dat_points(coarse)), len(dat_points(fine))
        check(f"0. (precondition) ...at DIFFERENT point counts ({n_coarse} vs {n_fine})",
              n_coarse != n_fine)

        # ── 1 & 2. the declared conditions reach the .bnd ───────────────────
        stem = os.path.join(tmp, "bound")
        topo = write_topology(os.path.join(tmp, "topo.json"), coarse)
        rc, out = run(tmp, write_config(os.path.join(tmp, "b.dat"), topo, coarse, stem))
        check(f"1. a topology attached to a real resampling meshes (rc={rc})", rc == 0)
        if rc != 0:
            print(out)
            return 1
        patches = bnd_patches(stem)
        # south: 6 edges, north: 6, east + west: 4 + 4 = 8 on the config default.
        check(f"1. the bound south side carries segment 1's own condition ({patches})",
              patches.get("inlet") == 6)
        check("1. ...the bound north side carries segment 3's, walked backwards",
              patches.get("outlet") == 6)
        check("1. ...and the two unbound sides carry the config default",
              patches.get("wall") == 8)
        check("1. ...so one block exports three DIFFERING conditions, from the "
              "declaration", set(patches) == {"inlet", "outlet", "wall"})
        # 2. The names written are BC TYPES, not the segment labels. A patch called
        # 'g_bot' would mean the label reached the file unresolved, which is the
        # shape of the defect where every patch silently became `wall`.
        check(f"2. the patch names are resolved BC TYPES, not the sidecar's grouping "
              f"labels ({sorted(patches)})",
              not any(n.startswith("g_") for n in patches))
        check("2. ...and the run says which segment each condition was read off, so "
              "'declared, not discovered' is visible rather than merely claimed",
              "from segment 1 of" in out and "from segment 3 of" in out)

        # ── 6. no position-based classification anywhere in this path ───────
        # Every boundary edge is recorded at construction, so the exporter's
        # classifier returns at its per-edge lookup. The evidence is that the two
        # unbound sides come out `wall` while lying nowhere near a reference
        # segment, and the two bound sides come out as their DECLARED condition
        # while lying on a stretch of geometry a position test would have to guess
        # the segment of. A single mis-set patch would move a face count above.
        check("6. every boundary face is accounted for by a declaration "
              f"({sum(patches.values())} faces)", sum(patches.values()) == 20)

        # ── 3 & 4. re-resampling does not move an attached corner ───────────
        fine_stem = os.path.join(tmp, "bound_fine")
        topo2 = write_topology(os.path.join(tmp, "topo2.json"), fine)
        rc2, out2 = run(tmp, write_config(os.path.join(tmp, "f.dat"), topo2, fine,
                                          fine_stem))
        check(f"3. the same topology meshes against the OTHER resampling (rc={rc2})",
              rc2 == 0)
        if rc2 == 0:
            a, b = vrt_points(stem), vrt_points(fine_stem)
            check("3. ...producing the same node set, so nothing moved at all",
                  a == b)
            corners = {(0.25, 0.0), (0.75, 0.0), (0.75, 1.0), (0.25, 1.0)}
            check(f"3. ...with the attached corners at the arc-length positions they "
                  f"declared ({sorted(corners & set(a))})", corners <= set(a))
            check("3. ...and the same conditions on the same faces",
                  bnd_patches(stem) == bnd_patches(fine_stem))
        # NEGATIVE CONTROL. Without this, check 3 would pass just as well on an
        # implementation that snapped every corner to the nearest geometry point,
        # or on one that never read the geometry at all.
        cx = {round(p[0], 9) for p in dat_points(coarse) if abs(p[1]) < 1e-12}
        fx = {round(p[0], 9) for p in dat_points(fine) if abs(p[1]) < 1e-12}
        check(f"4. (negative control) NEITHER resampling has a sample at the attached "
              f"position, so no snapping could have produced it (coarse {sorted(cx)})",
              0.25 not in cx and 0.25 not in fx)
        check("4. (negative control) ...and the two samplings really do differ along "
              "the bound segment", cx != fx)

        # ── 5. a corner on a segment that is not there is refused ───────────
        bad_stem = os.path.join(tmp, "bad")
        bad = os.path.join(tmp, "bad.json")
        doc = json.load(open(os.path.join(tmp, "topo.json"), encoding="utf-8"))
        doc["corners"][0]["seg"] = 9
        with open(bad, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        rc3, out3 = run(tmp, write_config(os.path.join(tmp, "bad.dat"), bad, coarse,
                                          bad_stem))
        check("5. a corner on a segment the geometry does not have exits 8", rc3 == 8)
        check("5. ...printing the machine-readable line a script branches on",
              "HYBMESH_ERROR 8 TOPOLOGY" in out3)
        check("5. ...and naming the segment it could not find",
              "segment 9" in out3 and "sw" in out3)
        check("5. ...and exporting NOTHING",
              not any(os.path.exists(bad_stem + e) for e in (".vtk", ".vrt", ".bnd")))

    print("\nRESULT: " + ("ALL PASS" if not failures
                          else f"{len(failures)} FAILURE(S)"))
    for f in failures:
        print("  - " + f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
