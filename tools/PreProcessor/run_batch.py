#!/usr/bin/env python3
"""Headless batch runner: several pipeline cases in one go.

Meshing a parameter sweep or a family of geometries meant launching the pipeline by
hand once per case. This queues them.

Usage:
    # explicit list
    python3 tools/PreProcessor/run_batch.py case_a.json case_b.json case_c.hws

    # a manifest (one path per line, '#' comments allowed)
    python3 tools/PreProcessor/run_batch.py @cases.txt

    # mesh only / skip the immersed-solid stage
    python3 tools/PreProcessor/run_batch.py @cases.txt --no-solver --no-ib

Prefer the ``run_batch.sh`` wrapper at the repo root, which also exports the Gmsh
library path the way run_pipeline.sh does.

Exit code is 0 only when EVERY queued case succeeded — a batch that finished with
failures must not report success to a scheduler.
"""
from __future__ import annotations

import argparse
import os
import sys

# Make the GUI's ``app`` package importable (models/services are Qt-free).
_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI_DIR = os.path.join(_HERE, "gui")
if _GUI_DIR not in sys.path:
    sys.path.insert(0, _GUI_DIR)

from app.services import batch_runner


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run several HybMesh pipeline cases in sequence.")
    ap.add_argument("cases", nargs="+",
                    help="pipeline JSON scripts / .hws workspaces, or @manifest")
    ap.add_argument("--no-solver", action="store_true",
                    help="stop each case after mesh generation")
    ap.add_argument("--no-ib", action="store_true",
                    help="skip the immersed-solid (STL -> phi) stage")
    ap.add_argument("--continue-on-error", action="store_true",
                    help="deprecated: a batch always continues past a failure "
                         "(kept so existing invocations do not break)")
    args = ap.parse_args()

    def log(msg):
        print(msg, flush=True)

    # Expand @manifest arguments into their listed paths.
    paths: list[str] = []
    for entry in args.cases:
        if entry.startswith("@"):
            manifest = entry[1:]
            if not os.path.exists(manifest):
                log(f"[FAILED] manifest not found: {manifest}")
                return 2
            try:
                paths.extend(batch_runner.read_manifest(manifest))
            except OSError as e:
                log(f"[FAILED] could not read manifest {manifest}: {e}")
                return 2
        else:
            paths.append(entry)

    if not paths:
        log("[FAILED] no cases to run")
        return 2

    jobs = batch_runner.load_jobs(paths, log=log)
    summary = batch_runner.run_batch(
        jobs, log=log,
        run_solver=not args.no_solver, run_ib=not args.no_ib)
    return batch_runner.exit_code(summary)


if __name__ == "__main__":
    sys.exit(main())
