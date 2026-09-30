#!/usr/bin/env python3
"""Measure every shipped MESH_MODE 1 config at several smoothing caps, for both fills.

THE HARNESS FOR ISSUE #157's SPIKE, kept beside the note it produced rather than
in ``tools/PreProcessor/tests/``: it is not a gate, nothing runs it in CI, and it
measures a fill that is NOT in the tree. Every variant but 0 needs
``prototype.patch`` applied and the binary rebuilt; without the patch the binary
ignores ``HYBMESH_MB_FILL_HERMITE`` and every variant measures the linear fill,
which is a silent wrong answer — so check that variant 0 and variant 1 differ
before reading anything else.

Run (from the repo root)::

    git apply docs/research/hermite-wall-normal-fill/prototype.patch && ./build.sh
    python3 docs/research/hermite-wall-normal-fill/measure.py --out <dir> --variant 0 --folds
    python3 docs/research/hermite-wall-normal-fill/measure.py --out <dir> --variant 1 --folds
    python3 docs/research/hermite-wall-normal-fill/measure.py --out <dir> --variant 2 --folds
    python3 docs/research/hermite-wall-normal-fill/measure.py --report <dir>

Variant 0 is the SHIPPED linear fill and is the control; the patch leaves it
reachable and unchanged, which is itself measured (see the note).

Each run writes one JSON row per (case, fill, cap) into ``<dir>/rows.json`` so a
re-run tops the file up instead of starting again. **The `rows.json` COMMITTED
beside this file holds the CAPS grid only** — the several hundred extra rows the
fold search produced are not kept, because `folds.json` is their conclusion and
they are reproducible from it.

WHAT IS MEASURED, per row: the exit code, the ``HYBMESH_MB_QUALITY`` line as
exported (inverted, non-orthogonality max/mean, wall first-cell worst relative,
the cell-shape triple and its wall-band split) and the ``HYBMESH_MB_SMOOTH``
line (sweeps actually run, converged, diverged, residual, best sweep, clipped).

THE FIRST-INVERSION FIGURE IS A CAP, NOT A SWEEP, and the difference is real: the
solve stops early on convergence and ROLLS BACK to its best iterate on
divergence, so the sweep count that produced the exported mesh is
``sweeps=`` and is reported beside the cap that asked for it.
"""
import argparse
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

CASES = ["square", "cavity", "hgrid", "ogrid", "cgrid", "tworing", "tworing_offset"]

# The caps the table is read at. 0 is the fill alone (what the spike's question is
# really about), 20 is the shipped default, and the tail is where #157's stability
# hypothesis lives.
CAPS = [0, 1, 2, 5, 10, 20, 40, 60, 100, 200]

# The ladder the first-inversion search walks before scanning, one cap at a time,
# between the last clean rung and the first folded one. A LINEAR scan and not a
# bisection: whether the inverted count is monotone in the cap is exactly the kind
# of thing this spike must not assume about a solve it is here to measure.
LADDER = list(range(10, 201, 10)) + list(range(250, 501, 50)) + [600, 800, 1000]

QUAL = "HYBMESH_MB_QUALITY "
SMOOTH = "HYBMESH_MB_SMOOTH "


def parse_line(out, prefix):
    for line in out.splitlines():
        i = line.find(prefix)
        if i < 0:
            continue
        toks = line[i + len(prefix):].split()
        return {k: float(v) for k, _, v in (t.partition("=") for t in toks) if k}
    return None


def temp_config(case, cap, workdir):
    """The shipped `.dat` with the cap forced and the output redirected."""
    src = os.path.join(REPO, "config", "multiblock_%s.dat" % case)
    with open(src) as fh:
        text = fh.read()
    text = re.sub(r"(?m)^\s*MB_SMOOTH_ITERS\b.*$", "", text)
    out = os.path.join(workdir, "mesh_%s.vtk" % case)
    text = re.sub(r"(?m)^\s*OUTPUT_FILENAME\b.*$", "OUTPUT_FILENAME " + out, text)
    text += "\nMB_SMOOTH_ITERS %d\n" % cap
    path = os.path.join(workdir, "cfg_%s_%d.dat" % (case, cap))
    with open(path, "w") as fh:
        fh.write(text)
    return path


def fill_name(variant):
    return "linear" if variant == 0 else "hermite%d" % variant


def run(case, cap, variant, workdir):
    cfg = temp_config(case, cap, workdir)
    env = dict(os.environ)
    if variant:
        env["HYBMESH_MB_FILL_HERMITE"] = str(variant)
    else:
        env.pop("HYBMESH_MB_FILL_HERMITE", None)
    p = subprocess.run([os.path.join(REPO, "run.sh"), "-conf", cfg],
                       cwd=REPO, env=env, capture_output=True, text=True,
                       timeout=1800)
    out = p.stdout + p.stderr
    row = {"case": case, "cap": cap, "fill": fill_name(variant),
           "exit": p.returncode}
    q = parse_line(out, QUAL)
    s = parse_line(out, SMOOTH)
    if q:
        row["q"] = q
    if s:
        row["s"] = s
    if q is None:
        row["stderr_tail"] = out[-600:]
    return row


def first_inversion(case, variant, workdir, log):
    """The lowest cap whose EXPORTED mesh has an inverted cell.

    A ladder to find a bracket, then EVERY cap in that bracket in order. The
    bisection this replaced would have assumed the inverted count is monotone in
    the cap, which is a property of the solve rather than of arithmetic and is one
    of the things being measured.
    """
    fill = fill_name(variant)
    clean, dirty = 0, None
    for cap in LADDER:
        r = run(case, cap, variant, workdir)
        log(r)
        if r.get("q", {}).get("inverted", -1.0) > 0:
            dirty = cap
            break
        clean = cap
    if dirty is None:
        return {"case": case, "fill": fill,
                "first_inverted_cap": None, "clean_through": clean}
    for cap in range(clean + 1, dirty):
        r = run(case, cap, variant, workdir)
        log(r)
        if r.get("q", {}).get("inverted", -1.0) > 0:
            return {"case": case, "fill": fill, "first_inverted_cap": cap,
                    "last_clean_cap": cap - 1, "scanned_from": clean + 1}
    return {"case": case, "fill": fill, "first_inverted_cap": dirty,
            "last_clean_cap": dirty - 1, "scanned_from": clean + 1}


def load(path):
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return json.load(fh)


def save(path, rows):
    with open(path, "w") as fh:
        json.dump(rows, fh, indent=1, sort_keys=True)


def key(r):
    return (r["case"], r["fill"], r["cap"])


def measure(outdir, variant, cases, folds):
    workdir = os.path.join(outdir, "work")
    os.makedirs(workdir, exist_ok=True)
    rows_path = os.path.join(outdir, "rows.json")
    rows = {key(r): r for r in load(rows_path)}
    folds_path = os.path.join(outdir, "folds.json")
    fold_rows = {(f["case"], f["fill"]): f for f in load(folds_path)}

    def log(r):
        rows[key(r)] = r
        save(rows_path, sorted(rows.values(), key=key))

    for case in cases:
        for cap in CAPS:
            r = run(case, cap, variant, workdir)
            log(r)
            q = r.get("q", {})
            print("%-16s %-8s cap %4d  exit %d  inv %6.0f  nomax %8.4f  wall %.6f"
                  % (case, r["fill"], cap, r["exit"], q.get("inverted", -1),
                     q.get("nonortho_max_deg", -1),
                     q.get("wall_first_cell_worst_rel", -1)))
            sys.stdout.flush()
        if folds:
            f = first_inversion(case, variant, workdir, log)
            fold_rows[(f["case"], f["fill"])] = f
            save(folds_path, sorted(fold_rows.values(),
                                    key=lambda d: (d["case"], d["fill"])))
            print("  -> %s %s first inverted cap: %s" %
                  (case, f["fill"], f.get("first_inverted_cap")))
            sys.stdout.flush()


FIELDS = [("inverted", "inv", "%8.0f"),
          ("nonortho_max_deg", "nomax", "%9.4f"),
          ("nonortho_mean_deg", "nomean", "%9.4f"),
          ("wall_first_cell_worst_rel", "wall", "%10.6f"),
          ("quad_midline_ratio_median", "shp_med", "%9.4f"),
          ("quad_midline_ratio_p95", "shp_p95", "%9.4f"),
          ("quad_midline_ratio_max", "shp_max", "%10.4f")]


def report(outdir):
    rows = {key(r): r for r in load(os.path.join(outdir, "rows.json"))}
    cases = sorted({r["case"] for r in rows.values()}, key=CASES.index)
    for case in cases:
        print("\n## %s" % case)
        head = "  cap | fill    |" + "|".join(
            (" %%%ds " % (len(f) + 2)) % f for _, f, _ in FIELDS)
        print(head)
        for cap in CAPS:
            for fill in ("linear", "hermite1", "hermite2"):
                r = rows.get((case, fill, cap))
                if not r:
                    continue
                q = r.get("q", {})
                cells = "|".join(
                    (fmt % q.get(k, float("nan"))).rjust(len(f) + 4)
                    for k, f, fmt in FIELDS)
                print("%5d | %-7s |%s" % (cap, fill, cells))
    folds = load(os.path.join(outdir, "folds.json"))
    if folds:
        print("\n## first cap whose EXPORTED mesh has an inverted cell")
        for f in folds:
            print("  %-16s %-8s %s (last clean %s)" %
                  (f["case"], f["fill"], f.get("first_inverted_cap"),
                   f.get("last_clean_cap", f.get("clean_through"))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="directory for rows.json / folds.json")
    ap.add_argument("--variant", type=int, default=0,
                    help="0 = the shipped linear fill; 1 or 2 = "
                         "HYBMESH_MB_FILL_HERMITE (needs prototype.patch)")
    ap.add_argument("--folds", action="store_true",
                    help="also search for the first cap that folds a cell")
    ap.add_argument("--cases", default=",".join(CASES))
    ap.add_argument("--report", help="print the table from a measured directory")
    a = ap.parse_args()
    if a.report:
        report(a.report)
        return 0
    if not a.out:
        ap.error("--out or --report is required")
    os.makedirs(a.out, exist_ok=True)
    measure(a.out, a.variant, a.cases.split(","), a.folds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
