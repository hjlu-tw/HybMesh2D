#!/usr/bin/env python3
"""Headless end-to-end pipeline runner.

Reads a single JSON pipeline script and runs CAD resample -> mesh generation ->
solver -> contour render, writing a contour PNG at the end. No GUI / display
required.

Usage:
    python3 tools/PreProcessor/run_pipeline.py config/pipeline/my_case.json
    python3 tools/PreProcessor/run_pipeline.py my_case.json --png out.png
    python3 tools/PreProcessor/run_pipeline.py my_case.json --no-solver

Prefer the ``run_pipeline.sh`` wrapper at the repo root, which also exports the
Gmsh dylib path (DYLD_LIBRARY_PATH) that HybMesh2D needs.
"""
from __future__ import annotations
import os
import sys
import argparse

# Make the GUI's ``app`` package importable (models/services are Qt-free).
_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI_DIR = os.path.join(_HERE, "gui")
if _GUI_DIR not in sys.path:
    sys.path.insert(0, _GUI_DIR)

from app.models.pipeline_config import PipelineConfig, PIPELINE_FORMAT_VERSION
from app.services import pipeline_runner
from app.services.contour_render import render_contour


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run the full HybMesh CAD -> mesh -> solver -> contour "
                    "pipeline from a single JSON script.")
    ap.add_argument("config", help="pipeline JSON file")
    ap.add_argument("--png", help="override the output contour PNG path")
    ap.add_argument("--no-solver", action="store_true",
                    help="stop after mesh generation (no solve / contour)")
    ap.add_argument("--no-contour", action="store_true",
                    help="run the solver but skip contour rendering")
    args = ap.parse_args()

    def log(msg):
        print(msg, flush=True)

    if not os.path.exists(args.config):
        log(f"[FAILED] pipeline config not found: {args.config}")
        return 2

    try:
        ver = PipelineConfig.file_version(args.config)
        if ver > PIPELINE_FORMAT_VERSION:
            log(f"[WARNING] pipeline_version {ver} is newer than this build "
                f"supports ({PIPELINE_FORMAT_VERSION}); loading best-effort.")
        pcfg = PipelineConfig.load_from_file(args.config)
    except (ValueError, TypeError, OSError) as e:
        log(f"[FAILED] could not parse pipeline config {args.config}: {e}")
        return 2
    log(f"=== HybMesh pipeline: {pcfg.name} ===")

    try:
        out = pipeline_runner.run_pipeline(
            pcfg, log=log, run_solver=not args.no_solver)
    except pipeline_runner.PipelineError as e:
        log(f"[FAILED] {e}")
        return 1

    result = out.get("result")
    if result and not args.no_contour:
        png = (args.png or pcfg.results.get("save_png")
               or os.path.splitext(result)[0] + ".png")
        try:
            var = render_contour(
                result, png,
                variable=pcfg.results.get("variable"),
                cmap=pcfg.results.get("cmap", "jet"),
                mesh_overlay=bool(pcfg.results.get("mesh_overlay")))
            log(f"[Contour] {var} -> {png}")
        except Exception as e:  # rendering must not mask a successful solve
            log(f"[WARNING] contour render failed: {e}")

    log("=== DONE ===")
    for key, val in out.items():
        if val:
            log(f"  {key}: {val}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
