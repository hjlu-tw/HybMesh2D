#!/usr/bin/env python3
"""Capture and compare a CANONICAL form of the mesher's output.

Why this exists: `HybMesh2D` is not byte-reproducible. Eight runs on identical
input produced two distinct byte outputs, differing only in node NUMBERING — so
diffing mesh files to prove "this refactor changed nothing" reports differences
that are not there. This canonicalises by COORDINATE instead: nodes sorted
lexicographically by (x, y), every cell rewritten as its node ranks in that
order (rotated to a fixed starting point and direction, so winding does not
matter), and the cell list sorted. Two runs of the same source then agree
exactly, and a real change still shows up.

It also compares the STAR-CD files, and both of them for a reason:

  * `.bnd` — the face count per patch name, each face's own coordinates, AND the
    per-segment group PARTITION (not the group numbers, which are handed out in
    encounter order). The two most expensive junction bugs this repo has had
    produced a geometrically perfect mesh with the boundary conditions on the
    wrong patches; a comparator that only looked at node positions would have
    passed both. The partition is what carries a boundary edge's source segment
    to the solver, so without it a defect confined to that key stayed invisible
    while every name, count and coordinate matched.
  * `.cel` — the connectivity the SOLVER consumes, which is not the `.vtk`. The
    `.cel` writer owns a winding normalisation, a degenerate-cell skip and a
    duplicate-cell dedupe that exist nowhere else, so a change confined to any of
    them was invisible here until a review of this tool pointed it out. A
    triangle is written as `v1 v2 v3 v3` and which vertex repeats follows the
    element's node order, so the duplicate is collapsed before comparing —
    but the winding is NOT, since normalising it away would hide the flip.

Boundary faces are keyed by their coordinates rather than by vertex id, because
`.bnd` ids index the `.vrt` numbering while cells index the `.vtk` numbering,
and those are exactly the numbers that are free to move between runs.

Usage:
    tools/scripts/golden_mesh.py capture <dir> [--only NAME ...]
    tools/scripts/golden_mesh.py compare <dir> [--only NAME ...]
    tools/scripts/golden_mesh.py list

`capture` runs every case and writes <dir>/<case>.json. `compare` runs them all
again into a temp dir and diffs against <dir>, reporting the worst coordinate
deviation seen — so a match at exactly 0.0 stays distinguishable from a match
that merely fits inside the tolerance. That distinction is load bearing: one
case genuinely wobbles run to run (see TOL), so a comparator that only printed
SAME/DIFF would leave you unable to tell noise from a real change you had just
happened to make small.

Dependency direction, deliberately: the duct / wedge geometries are IMPORTED
from tools/PreProcessor/tests/test_nobl_junction_acute.py, and the multi-block
TOPOLOGY writer from tools/PreProcessor/tests/test_multiblock_surface.py — not
copied. A tool reaching into a test directory is unusual, but a second copy of a
geometry (or topology) generator is a guaranteed future divergence, and those
test files are where the shapes are specified, dimensioned and explained.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", ".."))
# HYBMESH_GOLDEN_BIN points the capture at a DIFFERENT build of the mesher. That
# is what makes a behaviour-preserving claim checkable across a refactor: extract
# the starting commit (`git archive`, which touches no git state), build it
# elsewhere, capture the baseline from THAT binary, then compare with this tree's.
# Without it a baseline can only ever be captured from the working tree, i.e.
# after the change it is supposed to be evidence about.
_BIN = os.environ.get("HYBMESH_GOLDEN_BIN") or os.path.join(_REPO, "build", "HybMesh2D")
_LIB = os.path.join(_REPO, "build")
_GEOM = os.path.join(_REPO, "examples", "geometries")
_CONF = os.path.join(_REPO, "config", "Background_para.dat")

sys.path.insert(0, os.path.join(_REPO, "tools", "PreProcessor", "tests"))
sys.path.insert(0, os.path.join(_REPO, "tools", "PreProcessor", "gui"))

import numpy as np                                    # noqa: E402
import test_nobl_junction_acute as junc               # noqa: E402
import test_multiblock_surface as mb                  # noqa: E402
from app.models.vtk_mesh import VTKMesh               # noqa: E402
from app.services.logging_setup import get_logger     # noqa: E402

_log = get_logger(__name__)

# The junction cases run through the test module's own launcher, so it has to
# resolve the same binary this tool does — otherwise HYBMESH_GOLDEN_BIN would
# silently apply to two of the nine cases.
junc._BIN = _BIN

# Relative tolerance on a node coordinate.
#
# MEASURED, not guessed, and the measurement corrects a belief this repo held:
# the mesher's nondeterminism is NOT confined to node numbering. `wedge_45`
# returns a coordinate that differs by ~1.2e-13 in roughly 1 run out of 12 (two
# such wobbles compounding gave 2.5e-13, the worst seen in ~20 runs); the other
# eight cases were bit-identical every time. So exact equality would flake on one
# case in ten, and a tolerance is required rather than merely prudent.
#
# 1e-10 sits ~400x above that noise and still several orders of magnitude below
# anything an algorithmic change produces. It deliberately DOES hide pure
# floating-point reassociation, which is not the kind of change this tool exists
# to detect.
TOL = 1e-10


def _env() -> dict:
    return dict(os.environ, DYLD_LIBRARY_PATH=_LIB, LD_LIBRARY_PATH=_LIB)


# ── Cases ──────────────────────────────────────────────────────────────────
# Each builder runs the mesher in `tmp` and returns (returncode, output stem).

def _duct(theta, bc_labels=None):
    def build(tmp, name):
        dat = os.path.join(tmp, name + ".dat")
        junc.write_duct(dat, theta, bc_labels=bc_labels)
        rc, _log, stem = junc.run(tmp, dat, name, starcd=True)
        return rc, stem
    return build


def _shape(writer, *args):
    def build(tmp, name):
        dat = os.path.join(tmp, name + ".dat")
        writer(dat, *args)
        rc, _log, stem = junc.run(tmp, dat, name, starcd=True)
        return rc, stem
    return build


def _external(*geoms):
    def build(tmp, name):
        stem = os.path.join(tmp, name)
        cmd = [_BIN, "-conf", _CONF, "-geom"]
        cmd += [os.path.join(_GEOM, g) for g in geoms]
        cmd += ["-out_name", stem + ".vtk", "-out_vtk", "1", "-out_starcd", "1"]
        p = subprocess.run(cmd, cwd=tmp, env=_env(), capture_output=True,
                           text=True, timeout=1800)
        return p.returncode, stem
    return build


def _multiblock_example(split=True):
    """The multi-block case on the topology document this repo SHIPS.

    Deliberately the file itself, not a regenerated copy: examples/topology is
    documentation a user runs, and a case that rebuilt an equivalent document
    would leave an edit to the shipped one invisible here."""
    def build(tmp, name):
        stem = os.path.join(tmp, name)
        topo = os.path.join(_REPO, "examples", "topology", "square_block.json")
        conf = mb.write_config(os.path.join(tmp, name + ".dat"), topo, stem,
                               split=split)
        p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_env(),
                           capture_output=True, text=True, timeout=600)
        return p.returncode, stem
    return build


def _multiblock(ni, nj, split=True, spacing=None):
    """A case on the multi-block path (MESH_MODE 1).

    Its own family rather than a variant of the others: this path shares nothing
    with them but the exporters — no domain box, no boundary layer, no far field,
    and Gmsh nowhere — so what it regression-covers is the topology engine and the
    adapter into the mesh container. The `split=False` member is here because the
    quad mesh is a SHIPPED setting, and a switch nothing compares is a switch that
    can rot; the graded member covers the spacing-law path, which is otherwise
    exercised only by a unit test on node coordinates.
    """
    def build(tmp, name):
        stem = os.path.join(tmp, name)
        topo = mb.write_topology(os.path.join(tmp, name + ".json"),
                                 ni=ni, nj=nj, spacing=spacing)
        conf = mb.write_config(os.path.join(tmp, name + ".dat"), topo, stem,
                               split=split)
        p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_env(),
                           capture_output=True, text=True, timeout=600)
        return p.returncode, stem
    return build


CASES = {
    # Junction bins reachable through a real mesh. theta <= 95 is the slide
    # (case 1); 120 is a perpendicular cap (case 2). Cases 3 and 4 need
    # theta > 270, i.e. a strongly CONVEX junction, and no geometry writer
    # produces one today — see the note printed by `list`.
    "duct_90": _duct(90.0),
    "duct_85": _duct(85.0),
    "duct_120": _duct(120.0),
    "duct_90_bc": _duct(90.0, bc_labels=["bot", "rgt", "top", "lft"]),
    "curved_duct": _shape(junc.write_curved_duct),
    "wedge_45": _shape(junc.write_wedge, 45.0),
    "isolated_corner": _shape(junc.write_isolated_corner_duct),
    # External flow, through the repo's own default config.
    "naca0012": _external("naca0012.dat"),
    "multi_30p30n": _external("30p30n_jaxa_main.dat", "30p30n_jaxa_slat.dat",
                              "30p30n_jaxa_flap.dat"),
    # The multi-block path. Uniform, the same topology left unsplit, and a graded
    # one — see _multiblock for why the family has three members.
    "mb_square": _multiblock_example(),
    "mb_square_quads": _multiblock_example(split=False),
    "mb_graded": _multiblock(17, 13, spacing={"law": "geometric", "growth": 1.15}),
}


# ── Canonicalisation ───────────────────────────────────────────────────────

def _ring(idx: list[int]) -> list[int]:
    """A cell's node ranks, rotated to start at the smallest and oriented so the
    two traversal directions cannot disagree. Keeps cyclic adjacency (unlike a
    plain sort, which would call any two cells sharing four nodes identical)."""
    best = None
    for seq in (idx, idx[::-1]):
        k = seq.index(min(seq))
        rot = seq[k:] + seq[:k]
        if best is None or rot < best:
            best = rot
    return best


def _read_vrt(path: str, bad: dict) -> dict[int, tuple[float, float]]:
    """id -> (x, y) from a STAR-CD vertex file.

    A row this cannot parse is COUNTED, not silently dropped: every downstream
    comparison resolves through this table, so a swallowed row would quietly
    shrink what gets compared and the case would still print SAME. The count
    travels into the canonical form, which makes a change in it a diff in its own
    right."""
    verts: dict[int, tuple[float, float]] = {}
    if not os.path.exists(path):
        return verts
    with open(path) as f:
        for line in f:
            s = line.split()
            if len(s) < 3:
                continue
            try:
                verts[int(s[0])] = (float(s[1]), float(s[2]))
            except ValueError:
                bad["vrt"] = bad.get("vrt", 0) + 1
                _log.warning("unparsable .vrt row in %s: %r", path, line.rstrip())
    return verts


def _fmt(p: tuple[float, float]) -> str:
    return f"{p[0]:.9e},{p[1]:.9e}"


def _patch_faces(stem: str, verts: dict, bad: dict
                 ) -> tuple[dict[str, int], list[list[str]], list[list[str]]]:
    """(faces per patch name, one entry per boundary face, the group partition).

    A face is keyed by the coordinates of its own vertices, formatted, so it
    survives the renumbering that makes byte comparison useless. The `.bnd`
    layout the exporter writes is `bndId v1 v2 0 0 groupId 0 bcName`, the two
    zeros padding the unused vertex slots of a 2D (two-node) face.

    `groupId` is the third thing compared, and it is NOT compared as a number:
    it is handed out in encounter order (`nextGroup++`), so the value itself
    moves with the numbering that already varies run to run. What is stable, and
    what the group exists to express, is the PARTITION — which faces share a
    group. That is what carries `recordBoundaryEdge`'s source-segment key
    through to the solver, so without it a defect confined to that key was
    invisible here: every patch could keep its name, its face count and its
    coordinates while the per-segment grouping silently collapsed."""
    counts: dict[str, int] = {}
    faces: list[list[str]] = []
    groups: dict[tuple[str, str], list[str]] = {}
    if not os.path.exists(stem + ".bnd") or not verts:
        return counts, faces, []
    with open(stem + ".bnd") as f:
        for line in f:
            s = line.split()
            if len(s) < 8:
                continue
            try:
                ids = [int(v) for v in s[1:5]]
            except ValueError:
                bad["bnd"] = bad.get("bnd", 0) + 1
                _log.warning("unparsable .bnd row in %s: %r", stem, line.rstrip())
                continue
            name, gid = s[-1], s[5]
            pts = [verts[i] for i in ids if i in verts]
            if not pts:
                continue
            counts[name] = counts.get(name, 0) + 1
            key = ";".join(sorted(_fmt(p) for p in pts))
            faces.append([name, key])
            groups.setdefault((name, gid), []).append(key)
    faces.sort()
    partition = sorted([name] + sorted(keys) for (name, _g), keys in groups.items())
    return counts, faces, partition


def _cel_cells(stem: str, verts: dict, bad: dict) -> list[list[str]]:
    """The STAR-CD connectivity, canonicalised by coordinate.

    This is the file the SOLVER consumes, and it is not the `.vtk`: `.cel` owns a
    winding normalisation, a degenerate-cell skip and a duplicate-cell dedupe that
    exist nowhere else (see the exporter). A comparator that only read the `.vtk`
    could report SAME while the grid actually handed to the solver had changed —
    which is what a review of this tool found.

    Layout: `cellId v1 v2 v3 v4 1 1`, with a TRIANGLE written as `v1 v2 v3 v3`.
    Which vertex is repeated depends on the element's node ORDER, which is free to
    vary between runs, so consecutive duplicates are collapsed (with wrap) to
    recover the polygon before comparing. The ring is then rotated to a fixed
    start but its DIRECTION is kept, unlike the `.vtk` cells: winding here is
    normalised by the exporter, so a flip is a real change and must not be
    canonicalised away."""
    cells: list[list[str]] = []
    if not os.path.exists(stem + ".cel") or not verts:
        return cells
    with open(stem + ".cel") as f:
        for line in f:
            s = line.split()
            if len(s) < 5:
                continue
            try:
                ids = [int(v) for v in s[1:5]]
            except ValueError:
                bad["cel"] = bad.get("cel", 0) + 1
                _log.warning("unparsable .cel row in %s: %r", stem, line.rstrip())
                continue
            pts = [_fmt(verts[i]) for i in ids if i in verts]
            ring = [p for k, p in enumerate(pts) if p != pts[k - 1]] if pts else []
            if len(ring) < 3:
                continue
            k = ring.index(min(ring))
            cells.append(ring[k:] + ring[:k])
    cells.sort()
    return cells


def _canonical(rc: int, stem: str) -> dict:
    bad: dict = {}
    mesh = VTKMesh.from_file(stem + ".vtk")
    pts = np.asarray(mesh.points, dtype=float).reshape(-1, 2)
    order = np.lexsort((pts[:, 1], pts[:, 0]))
    rank = np.empty(len(order), dtype=np.int64)
    rank[order] = np.arange(len(order))
    # Coincident nodes make the ranking itself numbering-dependent: lexsort is
    # stable, so two nodes at the same coordinate keep their ORIGINAL relative
    # order — and the original numbering is exactly what varies between runs. The
    # cells would then differ with every coordinate still identical. Count them
    # and carry the count, so that failure mode announces itself instead of
    # looking like a real connectivity change.
    srt = pts[order]
    coincident = int(np.sum(np.all(srt[1:] == srt[:-1], axis=1))) if len(srt) > 1 else 0
    if coincident:
        _log.warning("%s: %d coincident node(s); cell canonicalisation is "
                     "numbering-dependent there", stem, coincident)
    cells = []
    for kind, group in (("tri", mesh.triangles), ("quad", mesh.quads),
                        ("poly", mesh.polygons)):
        for c in group:
            cells.append([kind] + _ring([int(rank[i]) for i in c]))
    cells.sort(key=lambda c: (c[0], len(c), c[1:]))
    verts = _read_vrt(stem + ".vrt", bad)
    counts, faces, groups = _patch_faces(stem, verts, bad)
    cel = _cel_cells(stem, verts, bad)
    return {
        "rc": rc,
        "n_nodes": int(len(pts)),
        "n_cells": len(cells),
        "n_cel_cells": len(cel),
        "coincident_nodes": coincident,
        "malformed_rows": bad,
        "nodes": [[float(x), float(y)] for x, y in pts[order]],
        "cells": cells,
        "cel_cells": cel,
        "patch_counts": counts,
        "patch_faces": faces,
        "patch_groups": groups,
    }


def _run_case(name: str) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"golden_{name}_") as tmp:
        rc, stem = CASES[name](tmp, name)
        if rc != 0 or not os.path.exists(stem + ".vtk"):
            return {"rc": rc, "error": "no mesh produced"}
        return _canonical(rc, stem)


# ── Comparison ─────────────────────────────────────────────────────────────

def _diff(ref: dict, new: dict) -> tuple[list[str], float]:
    """(human-readable differences, worst relative coordinate deviation)."""
    out: list[str] = []
    worst = 0.0
    if "error" in ref or "error" in new:
        if ref.get("error") != new.get("error") or ref.get("rc") != new.get("rc"):
            out.append(f"run outcome changed: ref={ref.get('error', ref.get('rc'))} "
                       f"new={new.get('error', new.get('rc'))}")
        return out, worst
    for key in ("rc", "n_nodes", "n_cells", "n_cel_cells", "coincident_nodes",
                "malformed_rows"):
        if ref.get(key) != new.get(key):
            out.append(f"{key}: {ref.get(key)} -> {new.get(key)}")
    if ref["n_nodes"] == new["n_nodes"]:
        a = np.asarray(ref["nodes"], dtype=float)
        b = np.asarray(new["nodes"], dtype=float)
        scale = np.maximum(1.0, np.maximum(np.abs(a), np.abs(b)))
        dev = np.abs(a - b) / scale
        worst = float(dev.max()) if dev.size else 0.0
        if worst > TOL:
            i = int(np.unravel_index(dev.argmax(), dev.shape)[0])
            out.append(f"node coordinates differ (worst {worst:.3e} at canonical "
                       f"node {i}: {a[i].tolist()} -> {b[i].tolist()})")
    if ref["cells"] != new["cells"]:
        rs, ns = {tuple(c) for c in ref["cells"]}, {tuple(c) for c in new["cells"]}
        out.append(f"connectivity differs ({len(rs - ns)} cells only in ref, "
                   f"{len(ns - rs)} only in new)")
    if ref.get("cel_cells") != new.get("cel_cells"):
        rs = {tuple(c) for c in ref.get("cel_cells", [])}
        ns = {tuple(c) for c in new.get("cel_cells", [])}
        out.append(f"STAR-CD connectivity differs ({len(rs - ns)} cells only in "
                   f"ref, {len(ns - rs)} only in new) — this is the grid the "
                   f"solver reads, not the .vtk")
    if ref["patch_counts"] != new["patch_counts"]:
        out.append(f"patch face counts: {ref['patch_counts']} -> {new['patch_counts']}")
    if ref.get("patch_groups") != new.get("patch_groups"):
        out.append(f"per-segment boundary GROUPING differs "
                   f"({len(ref.get('patch_groups', []))} groups -> "
                   f"{len(new.get('patch_groups', []))}) — this is what carries a "
                   f"boundary edge's source segment to the solver")
    if ref["patch_counts"] == new["patch_counts"] and \
            ref["patch_faces"] != new["patch_faces"]:
        rs = {tuple(f) for f in ref["patch_faces"]}
        ns = {tuple(f) for f in new["patch_faces"]}
        moved = sorted({f[0] for f in (rs - ns) | (ns - rs)})
        out.append(f"boundary faces moved between patches (per-name totals "
                   f"unchanged); patches involved: {moved}")
    return out, worst


# ── CLI ────────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=["capture", "compare", "list"])
    ap.add_argument("dir", nargs="?", help="golden directory")
    ap.add_argument("--only", nargs="+", metavar="NAME", help="subset of cases")
    args = ap.parse_args(argv)

    if args.action == "list":
        for name in CASES:
            print(name)
        print("\nNote: junction cases 3 and 4 (theta > 270 deg, a strongly convex "
              "BL/no-BL junction) are NOT covered here — no geometry writer "
              "produces one. They are reachable only as a unit test of the "
              "classifier itself.")
        return 0

    if not args.dir:
        ap.error(f"{args.action} needs a directory")
    if not os.path.exists(_BIN):
        print(f"SKIP: {_BIN} not built", file=sys.stderr)
        return 0

    names = args.only or list(CASES)
    unknown = [n for n in names if n not in CASES]
    if unknown:
        ap.error(f"unknown case(s): {unknown}")

    if args.action == "capture":
        os.makedirs(args.dir, exist_ok=True)
        for name in names:
            data = _run_case(name)
            with open(os.path.join(args.dir, name + ".json"), "w") as f:
                json.dump(data, f)
            # A case that produces no mesh is a legitimate golden value (one
            # junction shape is expected to refuse rather than emit an empty
            # mesh), so record the outcome instead of treating it as an error.
            note = (f"rc={data['rc']}: {data['error']}" if "error" in data
                    else f"{data['n_nodes']} nodes, {data['n_cells']} cells")
            print(f"captured {name}: {note}")
        return 0

    failed = []
    for name in names:
        path = os.path.join(args.dir, name + ".json")
        if not os.path.exists(path):
            print(f"MISSING  {name} (no golden at {path})")
            failed.append(name)
            continue
        with open(path) as f:
            ref = json.load(f)
        new = _run_case(name)
        diffs, worst = _diff(ref, new)
        if diffs:
            print(f"DIFF     {name}")
            for d in diffs:
                print(f"         | {d}")
            failed.append(name)
        else:
            print(f"SAME     {name}  (worst coordinate deviation {worst:.3e})")
    print("-------------------------------------------")
    print(f"TOTAL: {len(names)}   SAME: {len(names) - len(failed)}   DIFF: {len(failed)}")
    if failed:
        print(f"DIFFERED: {failed}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
