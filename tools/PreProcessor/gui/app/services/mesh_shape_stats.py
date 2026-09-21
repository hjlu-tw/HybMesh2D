"""Read the mesher's CELL SHAPE summary back out of the mesh's provenance sidecar.

**The mesher owns the summary; this reads it.** Every `MESH_MODE` writes the
figures it measured into `<mesh>.provenance.json` (`include/Provenance.hpp`,
`MeshQuality`), under `mesh.quality`, in the shape

    "quality": { "metric": "tri_edge_ratio", "cells": 15233,
                 "median": 1.158103, "p95": 52.185741, "max": 78.703074,
                 "layer": { "cells": 3215, "median": 35.281749,
                            "p95": 70.541670, "max": 78.703074 },
                 "bulk":  { "cells": 12018, "median": 1.112154,
                            "p95": 1.411765, "max": 11.901852 } }

so a mesh opened three sessions later still carries the numbers the run that
produced it printed, and the GUI, `run_pipeline` and the batch queue all quote
one producer instead of each computing its own (issue #131, parent #128).

**`layer` and `bulk` are the SPLIT, and they are OPTIONAL** (issues #143/#144,
read here by #145). The whole-mesh four sit flat on `quality` where #129 put them
and have not moved; the two halves are nested objects, written only by a path
that split, so a sidecar produced before that work carries neither key. That is
not an error and not a zero: `split` is False, the whole-mesh figures read
exactly as they always did, and every host shows the split as ABSENT. `layer` is
the band of cells clustered against a surface — the boundary layer on the hybrid
path, the wall band in `MESH_MODE 1` — and the sidecar's own word is the neutral
one, because the two paths' banners use their own vocabulary while the key does
not.

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


# metric key -> what the LAYER half is called in that path's own vocabulary, for
# a tooltip. The sidecar's key is `layer` for both paths on purpose — it names the
# band of cells a mesher clusters against a surface without claiming anything
# about the BC on that surface — while each path's BANNER uses its own word
# (`boundary layer`, `wall band`). A reader who saw one of those banners needs to
# recognise the row, so the gloss carries the word and the key stays neutral.
LAYER_MEANING = {
    "quad_midline_ratio": (
        "`layer` is the WALL BAND: the rows of structured cells clustered against "
        "a wall side, identified from the block's own indexing. `bulk` is every "
        "other structured cell, including every cell of a block with no wall side."),
    "tri_edge_ratio": (
        "`layer` is the cells the BOUNDARY LAYER emitted, marked where they were "
        "emitted rather than guessed at from distance to a wall. `bulk` is the "
        "far-field cells Gmsh filled."),
}


class ShapeFigures:
    """One set of the mesher's four published figures: a count and three numbers.

    Three sets share this shape — the whole mesh, and since #143/#144 the two
    halves of the split — and they share this class so that a host cannot render
    one of them differently from another by writing the same four lines twice.

    `measured` is false when the run looked and could not measure anything: the
    mesher then writes `cells: 0` with NEGATIVE figures rather than zeros,
    because the metric's floor is 1.0 and a 0.0 could only ever be an absent
    measurement wearing a number. That is a different state from "no sidecar",
    which is `read_shape_summary` returning ``None`` — one says the tool measured
    nothing, the other says nothing measured — and a different state again from
    an absent HALF, which is the attribute being ``None`` because the producing
    path did not split at all.
    """

    __slots__ = ("cells", "median", "p95", "max")

    def __init__(self, cells: int, median: float, p95: float, maximum: float):
        # `maximum` rather than `max`: the ATTRIBUTE is `max`, matching the
        # sidecar's own key, and a parameter of that name would shadow the
        # builtin this class's own `measured` calls.
        self.cells = cells
        self.median = median
        self.p95 = p95
        self.max = maximum

    @property
    def measured(self) -> bool:
        return self.cells > 0 and min(self.median, self.p95, self.max) >= 0.0

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("ShapeFigures(cells=%d, median=%r, p95=%r, max=%r)"
                % (self.cells, self.median, self.p95, self.max))


class ShapeSummary(ShapeFigures):
    """The `mesh.quality` object of one sidecar, as the mesher wrote it.

    IS the whole-mesh figures, because that is where the sidecar puts them — flat
    on `quality`, not in a nested object — plus the metric that names what was
    measured, the two optional halves of the split, and where it was read from.

    `layer` and `bulk` are ``None`` together when the sidecar carries no split:
    a mesh written before #143/#144, or by a path that does not split. `split`
    is the question a host asks; it is never inferred from a zero, because a
    half that IS present and empty (a geometry meshed with no boundary layer)
    is an ordinary measured state and must read as `not measured`, not as absent.
    """

    __slots__ = ("metric", "source", "layer", "bulk")

    def __init__(self, metric: str, cells: int, median: float, p95: float,
                 maximum: float, source: str = "",
                 layer: "ShapeFigures | None" = None,
                 bulk: "ShapeFigures | None" = None):
        super().__init__(cells, median, p95, maximum)
        self.metric = metric
        self.source = source
        self.layer = layer
        self.bulk = bulk

    @property
    def split(self) -> bool:
        """True when this sidecar carries BOTH halves.

        Both or neither: the writer emits the pair under one flag
        (`include/Provenance.hpp`, `MeshQuality::split`), and a host shown one
        half could not say what the other one is — the whole point of the split
        is the comparison between them.
        """
        return self.layer is not None and self.bulk is not None

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("ShapeSummary(metric=%r, cells=%d, median=%r, p95=%r, max=%r, "
                "split=%r)" % (self.metric, self.cells, self.median, self.p95,
                               self.max, self.split))


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


def _figures(obj) -> ShapeFigures | None:
    """One half of the split, or ``None`` when the sidecar carries none.

    ABSENCE is tolerated and nothing else is: a sidecar written before #143/#144
    has no `layer` key at all, and that must still read its whole-mesh figures
    out. A key that IS there but malformed raises out of here into
    `read_shape_summary`'s own handler, exactly as a malformed `median` on the
    whole-mesh set already does — a corrupt sidecar is one state, not two.
    """
    if obj is None:
        return None
    return ShapeFigures(cells=int(obj["cells"]), median=float(obj["median"]),
                        p95=float(obj["p95"]), maximum=float(obj["max"]))


def read_shape_summary(mesh_path: str) -> ShapeSummary | None:
    """The mesh's shape summary, or ``None`` when there is none to read.

    ``None`` covers every way the numbers can be absent — no sidecar, an
    unreadable or malformed one, a sidecar from a run that measured nothing and
    therefore wrote no `quality` object at all — because the caller does the same
    honest thing in all of them: show a blank. What it never covers is a sidecar
    that HAS a `quality` object: that comes back as a `ShapeSummary`, `measured`
    or not, so "the tool looked and could not measure" reaches the user as its
    own answer instead of as a blank.

    The SPLIT is read here too, and its absence is not one of those ways: a
    sidecar with no `layer`/`bulk` keys is a complete, ordinary sidecar from
    before #143/#144 and still returns its whole-mesh figures. That is the state
    this ticket's acceptance is written around.
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
        # The two halves are read with `.get`, the whole-mesh four by subscript:
        # the split is OPTIONAL and its absence is an ordinary sidecar, while a
        # `quality` object missing `median` is a broken one.
        layer = _figures(quality.get("layer"))
        bulk = _figures(quality.get("bulk"))
        if layer is None or bulk is None:
            # Both or neither, matching the writer. Half a split is a sidecar
            # this tool did not write, and showing one band with nothing to
            # compare it against would be worse than showing no split.
            layer = bulk = None
        return ShapeSummary(
            metric=metric,
            cells=int(quality["cells"]),
            median=float(quality["median"]),
            p95=float(quality["p95"]),
            maximum=float(quality["max"]),
            source=path,
            layer=layer,
            bulk=bulk,
        )
    except (KeyError, TypeError, ValueError, OSError) as exc:
        # A sidecar written before the mesher measured shape has no `quality`
        # key at all, which is the ordinary path through here and not a defect —
        # hence debug rather than warning. A malformed one lands here too and is
        # worth the traceback in the log file.
        logger.debug("No shape summary in '%s': %s", path, exc, exc_info=True)
        return None


# ONE RENDERING OF ONE SET OF FIGURES, used by every surface that shows any of
# the three (issue #145). The headless report below builds its line out of it,
# and the Mesh Statistics panel's two split rows are this string verbatim — so
# the whole-mesh set, the layer and the bulk cannot end up at three precisions,
# and the panel and the hosts cannot disagree about how a half is written. The
# `.3f` is the precision the panel has always shown.
def format_figures(figures: ShapeFigures | None) -> str:
    """`median … , p95 … , max … (N cells)`, or what is true instead.

    Three answers, because there are three states and rendering two of them the
    same way is the defect this whole batch exists to remove:

    * ``None`` — there is no such set. Only a HALF is ever absent, and only on a
      sidecar from a path that did not split; `not split` names that rather than
      claiming a measurement failed.
    * not measured — the set exists and is empty (a geometry meshed with no
      boundary layer has an empty `layer`, which is ordinary). Never `0.000`,
      which on a metric whose floor is 1.0 reads as a perfect mesh.
    * measured — the three figures and the cell count they cover.
    """
    if figures is None:
        return "not split"
    if not figures.measured:
        return "not measured"
    return (f"median {figures.median:.3f}, p95 {figures.p95:.3f}, "
            f"max {figures.max:.3f} ({figures.cells} cells)")


# The one report string every HEADLESS host shows (issue #132). `run_pipeline`
# prints it at the end of its mesh stage and the batch queue puts it in the
# case's row, so the two cannot quote different figures for the same mesh: a
# second formatter would be free to round differently, drop the metric name, or
# render an unmeasured run as numbers, which is the whole failure this batch
# exists to remove. The precision matches the panel's `.3f` for the same reason.
def format_shape_report(summary: ShapeSummary | None) -> str:
    """One line describing `summary`, in all three of its states.

    The three read differently ON PURPOSE, because they are three different
    facts and a batch of forty cases is read by scanning this column:

    * ``None`` — the mesh carries no published figures at all (no sidecar, or one
      written before the mesher measured shape). Says so; never a blank, which
      in a table of numbers is read as a zero. It does NOT name the sidecar's
      file: #131's gate refuses any `provenance` spelling in this module's code
      strings, because the module that could compose a second path convention is
      this one, and a message is not worth a hole in that check.
    * measured — the metric's NAME, then median / p95 / max and the cell count
      the three cover. The name travels because `quad_midline_ratio` and
      `tri_edge_ratio` are different quantities (#130). When the sidecar carries
      the split, the layer's and the bulk's own figures follow on the same line
      (#145), after everything that was there before them.
    * not measured — the mesher looked and could not measure (a run that exported
      no cells). Named as such rather than printed, since its stored figures are
      negative sentinels and `0.000` on this metric would read as perfection.
    """
    if summary is None:
        return "not published (no quality sidecar beside this mesh)"
    if not summary.measured:
        return f"{summary.metric}: not measured"
    line = f"{summary.metric}: {format_figures(summary)}"
    if summary.split:
        # APPENDED, never substituted: every token this line carried before
        # #145 is still in it, in the same order and at the same precision, so a
        # log a user greps or an eye that learned the old shape is not broken by
        # the split arriving. A sidecar with no split appends nothing at all —
        # the absence reads as absence, not as a pair of dashes.
        line += (f"; layer {format_figures(summary.layer)}"
                 f"; bulk {format_figures(summary.bulk)}")
    return line


def shape_report(mesh_path: str) -> str:
    """Read `mesh_path`'s published figures and format them. The host call.

    Read-and-format in one, because the two headless hosts have no reason to
    hold a `ShapeSummary` — they display it and move on. A host that wants the
    numbers themselves (the GUI panel does, to lay them out in rows) calls
    `read_shape_summary` instead; both go through the same reader, and there is
    no path here that computes anything.
    """
    return format_shape_report(read_shape_summary(mesh_path))
