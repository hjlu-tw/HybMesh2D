"""The block-topology skeleton drawn over the geometry (issue #136, parent #133).

READ-ONLY, deliberately and not for lack of time. Dragging a BOUND corner means
editing a normalized arc-length position while dragging a FREE one means moving a
coordinate, and those are two different interactions behind two identical-looking
dots — so v1 draws and nothing more. There is no handle, no ``movable=True`` and no
click handler in this file, which is the form that statement takes in code.

IT DECIDES NOTHING ABOUT THE TOPOLOGY. Every question with an answer — is there a
skeleton to draw at all, where is each corner, what node count did each edge END UP
with — is answered by ``services/topology_skeleton``, which is Qt-free and gated
against the real mesher's own report. What is left here is pens, symbols and z-order,
which is the whole reason the resolution does not live in a canvas.

WHY THE COUNT IS LABELLED AND NOT JUST THE OUTLINE: a count in the document is a
SEED. Opposite sides of a block carry equal counts and a shared edge is one edge two
blocks name, so one declaration fixes a chain of edges nobody touched — on the shipped
four-block H-grid, four declarations decide twelve edges. An overlay showing the shape
alone would show the easy half and hide the half that is actually hard to predict.
Declared and propagated counts are drawn in DIFFERENT COLOURS for the same reason the
mesher's own banner splits them: "which of these numbers did I write down" is the
question a surprising resolution sends the user looking for.
"""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt

from app.services.topology_skeleton import skeleton_for_config

#: Boundary edges of the topology (kind ``wall``) — solid, the strongest line here.
_SKEL_WALL = '#00E5FF'
#: Interior lines (``interface`` / ``cut``) — the same family, dashed, because they
#: are not a boundary of anything and must not read as one.
_SKEL_INNER = '#00B4CC'
#: A corner the document places by its own coordinates.
_SKEL_FREE = '#00E5FF'
#: A corner attached to a geometry by arc length. A different SYMBOL as well as a
#: different colour: two dots that differ only in hue are two dots.
_SKEL_BOUND = '#FF79C6'
#: A count this edge DECLARES...
_SKEL_DECLARED = '#FFD700'
#: ...and one that reached it by propagation.
_SKEL_PROPAGATED = '#8FE3FF'

#: Above the geometry previews (5/6), the domain box (15) and the BC overlays
#: (18-25), below the coordinate read-out (100).
_Z_EDGES = 26
_Z_CORNERS = 28
_Z_LABELS = 29


class MeshCanvasSkeletonMixin:
    """Draws the topology skeleton. Runs on the composed MeshCanvasView."""

    def _init_skeleton_overlay(self):
        """Create the (empty) overlay state. Called from ``__init__``."""
        #: What is currently drawn, or None. Read by ``auto_range`` — a template
        #: case may legally have NO geometry at all, so the skeleton is sometimes
        #: the only thing on the canvas to fit to.
        self.topology_skeleton = None
        self.skeleton_edge_items: list[pg.PlotDataItem] = []
        self.skeleton_corner_items: list[pg.ScatterPlotItem] = []
        #: The same two items by the distinction they draw — ``"free"`` and
        #: ``"bound"``. Keyed rather than positional because "which of these is
        #: the bound one" is a question with a name, and a gate asking it by
        #: index would pass on a file that swapped the two pens.
        self.skeleton_corner_marks: dict = {}
        self.skeleton_label_items: list[pg.TextItem] = []

    # ── the overlay ──────────────────────────────────────────────────────
    def _rebuild_topology_skeleton(self):
        """Redraw the skeleton for the current mesh config, or clear it.

        Called from ``update_mesh_config``, which is the ONE place this canvas
        learns that the configuration changed — so the overlay follows a parameter
        edit and a case switch by the same route, and neither can be the one that
        forgets. ``skeleton_for_config`` returning None is what makes the overlay
        clear on the way into a case with no topology model rather than surviving
        from the last one.
        """
        self.update_topology_skeleton(skeleton_for_config(self.mesh_config))

    def update_topology_skeleton(self, skel):
        """Draw ``skel``; ``None`` clears the overlay."""
        self.clear_topology_skeleton()
        self.topology_skeleton = skel
        if skel is None:
            return

        for kind_is_wall, col, style in (
                (True, _SKEL_WALL, Qt.PenStyle.SolidLine),
                (False, _SKEL_INNER, Qt.PenStyle.DashLine)):
            # One item per STYLE rather than per edge, with the segments handed
            # over as endpoint pairs: a four-by-four H-grid is 40 edges, and 40
            # plot items is 40 of everything pyqtgraph does per item.
            pts = [e.xy for e in skel.edges
                   if e.xy is not None and (e.kind == "wall") == kind_is_wall]
            if not pts:
                continue
            flat = np.asarray([p for seg in pts for p in seg], dtype=float)
            item = self.plot_widget.plot(
                flat[:, 0], flat[:, 1], connect='pairs',
                pen=pg.mkPen(col, width=2.0 if kind_is_wall else 1.4, style=style))
            item.setZValue(_Z_EDGES)
            self.skeleton_edge_items.append(item)

        for bound, col, symbol, size in ((False, _SKEL_FREE, 's', 9),
                                         (True, _SKEL_BOUND, 'd', 13)):
            pts = [c.xy for c in skel.corners if c.xy is not None and c.bound is bound]
            if not pts:
                continue
            arr = np.asarray(pts, dtype=float)
            item = pg.ScatterPlotItem(
                arr[:, 0], arr[:, 1], symbol=symbol, size=size,
                pen=pg.mkPen(col, width=1.6), brush=pg.mkBrush(12, 13, 22, 210))
            item.setZValue(_Z_CORNERS)
            self.plot_widget.addItem(item)
            self.skeleton_corner_items.append(item)
            self.skeleton_corner_marks["bound" if bound else "free"] = item

        for e in skel.edges:
            mid = e.midpoint
            if mid is None:
                continue
            lbl = pg.TextItem(
                e.label, anchor=(0.5, 0.5),
                color=_SKEL_DECLARED if e.declared else _SKEL_PROPAGATED)
            lbl.setZValue(_Z_LABELS)
            lbl.setPos(mid[0], mid[1])
            # ignoreBounds: a text item's extent is in PIXELS, so letting it into
            # the auto-range makes the fitted view depend on the zoom it produced.
            self.plot_widget.addItem(lbl, ignoreBounds=True)
            self.skeleton_label_items.append(lbl)

        # A template case's `cads` may be empty — legal in MESH_MODE 1, where a
        # topology that declares its own corners is the whole input — and then
        # nothing else on this canvas has an extent to fit to.
        if not self._did_initial_fit:
            self.auto_range()

    def clear_topology_skeleton(self):
        """Remove every skeleton item. Idempotent."""
        for group in (self.skeleton_edge_items, self.skeleton_corner_items,
                      self.skeleton_label_items):
            for it in group:
                self.plot_widget.removeItem(it)
            group.clear()
        self.skeleton_corner_marks.clear()
        self.topology_skeleton = None

    def skeleton_bounds(self):
        """``(xmin, xmax, ymin, ymax)`` of the drawn skeleton, or ``None``."""
        skel = getattr(self, "topology_skeleton", None)
        return None if skel is None else skel.bounds()
