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

It also compares the STAR-CD `.bnd` patches — the face count per patch name AND
each face's own coordinates — which the mesh geometry alone cannot see. The two
most expensive junction bugs this repo has had produced a geometrically perfect
mesh with the boundary conditions on the wrong patches; a comparator that only
looked at node positions would have passed both.

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
that merely fits inside the tolerance.

Dependency direction, deliberately: the duct / wedge geometries are IMPORTED
from tools/PreProcessor/tests/test_nobl_junction_acute.py, not copied. A tool
reaching into a test directory is unusual, but a second copy of a geometry
generator is a guaranteed future divergence, and that test file is where those
shapes are specified, dimensioned and explained.
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
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_LIB = os.path.join(_REPO, "build")
_GEOM = os.path.join(_REPO, "examples", "geometries")
_CONF = os.path.join(_REPO, "config", "Background_para.dat")

sys.path.insert(0, os.path.join(_REPO, "tools", "PreProcessor", "tests"))
sys.path.insert(0, os.path.join(_REPO, "tools", "PreProcessor", "gui"))

import numpy as np                                    # noqa: E402
import test_nobl_junction_acute as junc               # noqa: E402
from app.models.vtk_mesh import VTKMesh               # noqa: E402

# Relative tolerance on a node coordinate. Pure code motion should give exactly
# 0.0; the tolerance exists so a genuinely equivalent but differently-ordered
# floating-point expression is not reported as a mesh change.
TOL = 1e-12


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


def _read_vrt(path: str) -> dict[int, tuple[float, float]]:
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
                continue
    return verts


def _patch_faces(stem: str) -> tuple[dict[str, int], list[list[str]]]:
    """(faces per patch name, one canonical entry per boundary face).

    A face is keyed by the coordinates of its own vertices, formatted, so it
    survives the renumbering that makes byte comparison useless. The `.bnd`
    layout is `id v1 v2 v3 v4 region segm_no name`, with 0 padding the unused
    vertex slots of a 2D (two-node) face."""
    verts = _read_vrt(stem + ".vrt")
    counts: dict[str, int] = {}
    faces: list[list[str]] = []
    if not os.path.exists(stem + ".bnd") or not verts:
        return counts, faces
    with open(stem + ".bnd") as f:
        for line in f:
            s = line.split()
            if len(s) < 8:
                continue
            try:
                ids = [int(v) for v in s[1:5]]
            except ValueError:
                continue
            name = s[-1]
            pts = [verts[i] for i in ids if i in verts]
            if not pts:
                continue
            counts[name] = counts.get(name, 0) + 1
            faces.append([name] + sorted(f"{x:.9e},{y:.9e}" for x, y in pts))
    faces.sort()
    return counts, faces


def _canonical(rc: int, stem: str) -> dict:
    mesh = VTKMesh.from_file(stem + ".vtk")
    pts = np.asarray(mesh.points, dtype=float).reshape(-1, 2)
    order = np.lexsort((pts[:, 1], pts[:, 0]))
    rank = np.empty(len(order), dtype=np.int64)
    rank[order] = np.arange(len(order))
    cells = []
    for kind, group in (("tri", mesh.triangles), ("quad", mesh.quads),
                        ("poly", mesh.polygons)):
        for c in group:
            cells.append([kind] + _ring([int(rank[i]) for i in c]))
    cells.sort(key=lambda c: (c[0], len(c), c[1:]))
    counts, faces = _patch_faces(stem)
    return {
        "rc": rc,
        "n_nodes": int(len(pts)),
        "n_cells": len(cells),
        "nodes": [[float(x), float(y)] for x, y in pts[order]],
        "cells": cells,
        "patch_counts": counts,
        "patch_faces": faces,
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
    for key in ("rc", "n_nodes", "n_cells"):
        if ref[key] != new[key]:
            out.append(f"{key}: {ref[key]} -> {new[key]}")
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
    if ref["patch_counts"] != new["patch_counts"]:
        out.append(f"patch face counts: {ref['patch_counts']} -> {new['patch_counts']}")
    elif ref["patch_faces"] != new["patch_faces"]:
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
