"""Read the mesher's CELL SHAPE summary back out of the mesh's provenance sidecar.

**The mesher owns the summary; this reads it.** Every `MESH_MODE` writes the
figures it measured into `<mesh>.provenance.json` (`include/Provenance.hpp`,
`MeshQuality`), under `mesh.quality`, in the shape

    "quality": { "metric": "tri_edge_ratio", "cells": 11396,
                 "median": 1.584671, "p95": 9.901041, "max": 35.608279 }

so a mesh opened three sessions later still carries the numbers the run that
produced it printed, and the GUI, `run_pipeline` and the batch queue all quote
one producer instead of each computing its own (issue #131, parent #128).

Two rules this module exists to hold:

* **No fallback computation.** A mesh with no sidecar — made before this work, or
  by another tool — returns ``None`` and the caller shows a blank. Computing the
  summary here instead would be the second implementation the single-owner rule
  removes, and its numbers would not mean the same thing: the GUI's per-cell
  aspect ratio is longest-edge/shortest-edge over EVERY cell, while a multi-block
  sidecar reports the ratio of opposite-edge midline distances over the
  STRUCTURED quads, where a square reads 1.0 and its two split triangles √2.
* **`metric` is carried, never dropped.** The two generation paths measure two
  different quantities (`quad_midline_ratio`, `tri_edge_ratio`) and a reader that
  compares one against the other is comparing nothing, so the name travels with
  the numbers to whatever displays them.

Qt-free on purpose: the sidecar read is the half a headless test can exercise,
and `views/panels/mesh_stats_panel.py` is left with formatting only.
"""
from __future__ import annotations

import json
import os

from app.services import case_sources
from app.services.logging_setup import get_logger

logger = get_logger(__name__)

# metric key -> the quantity it names, for a tooltip. The KEY itself is what the
# panel shows, because it is the token the banner, the machine-readable line and
# the sidecar all spell the same way — a prettified label would be a fourth
# spelling of a name whose whole job is to be matched against the other three.
METRIC_MEANING = {
    "quad_midline_ratio": (
        "Ratio of the distances between the midpoints of opposite edges, over the "
        "structured quads MESH_MODE 1 built (a square reads 1.0). Independent of "
        "MB_SPLIT_QUADS."),
    "tri_edge_ratio": (
        "Longest edge / shortest edge, over the triangles the hybrid path exported "
        "(1.0 is equilateral)."),
}


class ShapeSummary:
    """The `mesh.quality` object of one sidecar, as the mesher wrote it.

    `measured` is false when the run looked and could not measure anything: the
    mesher then writes `cells: 0` with NEGATIVE figures rather than zeros,
    because the metric's floor is 1.0 and a 0.0 could only ever be an absent
    measurement wearing a number. That is a different state from "no sidecar",
    which is this module returning ``None`` — one says the tool measured nothing,
    the other says nothing measured.
    """

    __slots__ = ("metric", "cells", "median", "p95", "max", "source")

    def __init__(self, metric: str, cells: int, median: float, p95: float,
                 maximum: float, source: str = ""):
        self.metric = metric
        self.cells = cells
        self.median = median
        self.p95 = p95
        self.max = maximum
        self.source = source

    @property
    def measured(self) -> bool:
        return self.cells > 0 and min(self.median, self.p95, self.max) >= 0.0

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("ShapeSummary(metric=%r, cells=%d, median=%r, p95=%r, max=%r)"
                % (self.metric, self.cells, self.median, self.p95, self.max))


def sidecar_for(mesh_path: str) -> str:
    """The provenance sidecar that exists beside `mesh_path`, or "".

    The candidates come from `case_sources.mesh_provenance_paths`, the SAME
    name computation the case export already stages a run's provenance with, so
    the GUI and the export cannot disagree about where a mesh's sidecar is. That
    function is a pure name computation and returns candidates that do not
    exist; deciding which one is on disk is this caller's job, as it is the
    staging service's.
    """
    if not mesh_path:
        return ""
    for cand in case_sources.mesh_provenance_paths(mesh_path):
        if os.path.isfile(cand):
            return cand
    return ""


def read_shape_summary(mesh_path: str):
    """The mesh's shape summary, or ``None`` when there is none to read.

    ``None`` covers every way the numbers can be absent — no sidecar, an
    unreadable or malformed one, a sidecar from a run that measured nothing and
    therefore wrote no `quality` object at all — because the caller does the same
    honest thing in all of them: show a blank. What it never covers is a sidecar
    that HAS a `quality` object: that comes back as a `ShapeSummary`, `measured`
    or not, so "the tool looked and could not measure" reaches the user as its
    own answer instead of as a blank.
    """
    path = sidecar_for(mesh_path)
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        quality = doc["mesh"]["quality"]
        metric = str(quality["metric"])
        if not metric:
            return None
        return ShapeSummary(
            metric=metric,
            cells=int(quality["cells"]),
            median=float(quality["median"]),
            p95=float(quality["p95"]),
            maximum=float(quality["max"]),
            source=path,
        )
    except (KeyError, TypeError, ValueError, OSError) as exc:
        # A sidecar written before the mesher measured shape has no `quality`
        # key at all, which is the ordinary path through here and not a defect —
        # hence debug rather than warning. A malformed one lands here too and is
        # worth the traceback in the log file.
        logger.debug("No shape summary in '%s': %s", path, exc, exc_info=True)
        return None
