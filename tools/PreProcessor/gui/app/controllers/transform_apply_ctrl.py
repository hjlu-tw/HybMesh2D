from __future__ import annotations
import math
import numpy as np
from app.models.segment import SegmentModel
from app.commands.segment_cmds import DuplicateMultipleTransformCmd
from app.services.geometry_service import (
    GeometryService, _parse_vertices_str, format_vertices_str)

class TransformApplyControllerMixin:
    """Mixin containing the transform application / duplication logic:
    building the transformed segment and applying the point-wise transform."""

    def duplicate_with_transform(self):
        """Apply the selected geometric transform to every selected edge.

        The transform is type-preserving (like industrial CAD): a line stays a
        line, a circle stays a circle, an arc stays an arc (radius, centre and
        sweep transformed), polygons/triangles/quads keep their type — only
        their defining parameters change. Discrete (file) edges and
        custom-formula curves, which have no closed-form image under the
        transform, fall back to a Polygon of the transformed sample points, and
        the log says so per edge rather than leaving the user to notice.
        Operates on all edges selected in the model tree; originals are kept
        unless 'Delete original' is set."""
        session = self.active_session()
        if not session:
            self.log("No segment selected.")
            return
        sb = self.main_window.sidebar_view

        indices = self.get_selected_segment_indices()
        if not indices:
            self.log("No segment selected.")
            return

        # A zero-length custom mirror axis is the only fully-degenerate case;
        # reject it once up front so a per-edge None can mean "no valid points".
        spec = sb.transform_spec()
        if spec.is_degenerate:
            self.log("Mirror axis direction is zero — cannot mirror.")
            return

        delete_original = spec.delete_original

        new_segs = []
        seg_indices = []
        new_ids = []
        baked = []
        next_id = session.project_model._next_curve_id

        for idx in indices:
            seg = session.project_model.get_segment(idx)
            if not seg:
                continue

            # Only the active curve segment carries unsaved UI edits.
            if seg.type == "curve" and idx == session.current_segment_idx:
                self._sync_active_curve_segment_from_ui()

            src_type = ("discrete" if seg.type != "curve"
                        else getattr(seg, "curve_type", "custom"))
            new_seg = self._build_transformed_segment(session, seg, next_id)
            if new_seg is None:
                self.log(
                    f"Edge {seg.id} has no valid points — skipped.")
                continue
            if new_seg.curve_type == "polygon" and src_type != "polygon":
                baked.append((seg.id, src_type))

            new_segs.append(new_seg)
            seg_indices.append(idx)
            new_ids.append(new_seg.id)
            next_id += 1

        if not new_segs:
            self.log("No valid edges to transform.")
            return

        def select_cb(idx):
            self._select_segment_by_index(idx)

        # When the originals are deleted, point data changes, so redraw the
        # base geometry (via _apply_geometry_update) — otherwise the moved
        # edge's old vertices linger on the canvas as a stale, unselectable
        # ghost. A plain duplicate leaves points untouched, so the lighter
        # list refresh suffices. (Both run on undo too.)
        refresh_cb = ((lambda: self._apply_geometry_update(session))
                      if delete_original else self._refresh_segment_list)
        cmd = DuplicateMultipleTransformCmd(
            session=session,
            seg_indices=seg_indices,
            new_segs=new_segs,
            delete_original=delete_original,
            refresh_cb=refresh_cb,
            select_cb=select_cb,
        )
        session.command_history.execute(cmd)
        session.is_geometry_modified = True
        self.main_window.update_title(session.display_name, True)

        action_name = "Moved/Transformed" if delete_original else "Duplicated"
        ids_str = ", ".join(str(i) for i in new_ids)
        self.log(
            f"{action_name} {len(new_segs)} edge(s) as Edge {ids_str} "
            f"({spec.label}).")
        for sid, src_type in baked:
            # Say WHICH edge lost its type and why. Everything analytic keeps
            # it; these two kinds have no closed-form image under a transform,
            # so the copy is the transformed sample points.
            self.log(
                f"Edge {sid} ({src_type}) has no transformed closed form — the "
                f"copy is a Polygon of its points.")
        self._show_duplicate_preview = False
        self.main_window.canvas_view.clear_duplicate_preview()
        self.main_window.canvas_view.clear_transform_handles()

    def _build_transformed_segment(self, session, seg, new_id):
        """Build a new curve segment that is `seg` after the active transform,
        preserving the analytic type where the (similarity) transform allows it.

        Returns None when the edge has no usable points. The mirror-axis
        degenerate case is rejected by the caller before this is reached."""
        def T(pts):
            """Transform a short list of defining points; None if degenerate."""
            xs = np.array([p[0] for p in pts], dtype=float)
            ys = np.array([p[1] for p in pts], dtype=float)
            res = self._apply_transform(xs, ys)
            if res is None:
                return None
            txs, tys = res
            return [(float(x), float(y)) for x, y in zip(txs, tys)]

        new_seg = SegmentModel(new_id, -1, -1)
        new_seg.type = "curve"
        # Carry the source edge's resampling strategy and spacing params so a
        # moved/duplicated edge keeps its feel instead of resetting to uniform.
        new_seg.strategy = seg.strategy
        new_seg.parameters = dict(seg.parameters)
        new_seg.start_index = -1
        new_seg.end_index = -1
        # Inherit the source edge's closure so a moved/duplicated closed loop
        # stays closed (and an open polyline stays open) after the transform.
        # This is the right answer for the type-preserving branches below, where
        # the copy is the same KIND of shape as the source. The polygon-bake
        # fallback re-derives it from the actual points instead — see
        # `_baked_edge_is_closed`. C++ re-adds the closing vertex only when this
        # is True, so a closed loop keeps a clean single seam.
        new_seg.closed = getattr(seg, "closed", True)

        ct = getattr(seg, "curve_type", "custom")
        p = seg.parameters

        # ── Lines (incl. axis-aligned, re-classified after the transform) ────
        if seg.type == "curve" and ct in ("line", "horizontal_line", "vertical_line"):
            if ct == "horizontal_line":
                ends = [(p.get("x0", 0.0), p.get("y", 0.0)),
                        (p.get("x1", 1.0), p.get("y", 0.0))]
            elif ct == "vertical_line":
                ends = [(p.get("x", 0.0), p.get("y0", 0.0)),
                        (p.get("x", 0.0), p.get("y1", 1.0))]
            else:
                ends = [(p.get("x0", 0.0), p.get("y0", 0.0)),
                        (p.get("x1", 1.0), p.get("y1", 1.0))]
            t = T(ends)
            if t is None:
                return None
            (ax, ay), (bx, by) = t
            tol = 1e-9 * max(1.0, abs(ax) + abs(ay) + abs(bx) + abs(by))
            for k in ("x", "y", "x0", "y0", "x1", "y1"):
                new_seg.parameters.pop(k, None)
            if abs(ay - by) <= tol:          # stayed horizontal
                new_seg.curve_type = "horizontal_line"
                new_seg.parameters.update({"y": ay, "x0": ax, "x1": bx})
            elif abs(ax - bx) <= tol:        # became vertical
                new_seg.curve_type = "vertical_line"
                new_seg.parameters.update({"x": ax, "y0": ay, "y1": by})
            else:                            # general line
                new_seg.curve_type = "line"
                new_seg.parameters.update({"x0": ax, "y0": ay, "x1": bx, "y1": by})
            return new_seg

        # ── Arc (same similarity argument as the circle, plus its sweep) ─────
        # The image of an arc under any of these transforms is another arc of
        # the same radius-times-scale: the centre moves like a point, and the
        # two sweep angles move like directions. Baking it into a polygon (what
        # this used to do) threw away the radius, the angles and every later
        # edit — USER-REPORTED. A non-uniform scale makes it an elliptic arc,
        # which the model cannot hold, so that one still falls through.
        if seg.type == "curve" and ct == "arc" and not self._nonuniform_scale_active():
            arc = self._transformed_arc(p, T)
            if arc is None:
                return None
            new_seg.curve_type = "arc"
            new_seg.parameters.update(arc)
            # The inherited `closed` is the meaningless True default for an arc
            # (nothing reads it outside polygons). Set it from the sweep anyway,
            # so the flag still tells the truth if this copy is later baked or
            # joined — same rule as `_baked_edge_is_closed`.
            new_seg.closed = abs(arc["theta1"] - arc["theta0"]) >= 2.0 * math.pi - 1e-9
            return new_seg

        # ── Circle (similarity transforms keep it circular) ──────────────────
        # A non-uniform scale turns a circle into an ellipse, which the circle
        # model can't represent (one radius); skip the analytic path so it falls
        # through to the polygon bake below (samples then transforms the rim).
        if seg.type == "curve" and ct == "circle" and not self._nonuniform_scale_active():
            cx, cy, r = p.get("cx", 0.0), p.get("cy", 0.0), p.get("r", 1.0)
            # Transform the centre and a rim point; |Δ| recovers the new radius
            # (handles rotation/mirror = unchanged, uniform scale = r·factor).
            t = T([(cx, cy), (cx + r, cy)])
            if t is None:
                return None
            (ncx, ncy), (ex, ey) = t
            new_seg.curve_type = "circle"
            new_seg.parameters.update(
                {"cx": ncx, "cy": ncy, "r": math.hypot(ex - ncx, ey - ncy)})
            return new_seg

        # ── Triangle / Quadrilateral / Polygon (transform the vertices) ──────
        if seg.type == "curve" and ct in ("triangle", "quadrilateral", "polygon"):
            if ct == "triangle":
                src = [(p.get("x0", 0.0), p.get("y0", 0.0)),
                       (p.get("x1", 1.0), p.get("y1", 0.0)),
                       (p.get("x2", 0.5), p.get("y2", 1.0))]
            elif ct == "quadrilateral":
                src = [(p.get(f"x{i}", 0.0), p.get(f"y{i}", 0.0)) for i in range(4)]
            else:
                src = [(float(x), float(y))
                       for x, y in _parse_vertices_str(p.get("vertices_str", ""))]
            t = T(src)
            if t is None:
                return None
            new_seg.curve_type = ct
            if ct in ("triangle", "quadrilateral"):
                for i, (x, y) in enumerate(t):
                    new_seg.parameters[f"x{i}"] = x
                    new_seg.parameters[f"y{i}"] = y
            else:
                new_seg.parameters["vertices_str"] = format_vertices_str(t)
            return new_seg

        # ── Fallback: discrete (file) edges, custom-formula curves, and the
        # circle/arc under a non-uniform scale (an ellipse the model can't hold).
        # No closed-form image under the transform → bake the transformed sample
        # points into a Polygon (the industrial 'explode' equivalent).
        pts_tuple = GeometryService.get_segment_points(session, seg)
        if pts_tuple is None:
            return None
        xs, ys = pts_tuple
        res = self._apply_transform(np.asarray(xs, dtype=float),
                                    np.asarray(ys, dtype=float))
        if res is None:
            return None
        txs, tys = res
        new_seg.curve_type = "polygon"
        new_seg.closed = self._baked_edge_is_closed(seg, xs, ys)
        new_seg.parameters["vertices_str"] = format_vertices_str(zip(txs, tys))
        new_seg.parameters["n_points"] = len(txs)
        return new_seg

    @staticmethod
    def _transformed_arc(p, T):
        """Map an arc's ``(cx, cy, r, theta0, theta1)`` through the transform.

        Every output is read off three transformed POINTS — the centre, the arc
        start, and the quarter-sweep point — so ONE code path covers rotation,
        translation, mirroring, point symmetry and uniform scale. In particular
        a mirror's reversed sweep (``theta1 < theta0``, which both samplers walk
        happily) falls out of the geometry instead of needing a per-transform
        sign rule that only the mirrors would exercise.

        The quarter point rather than the midpoint is what keeps a full-turn arc
        unambiguous: the midpoint's cross product carries ``sin(sweep/2)``, which
        vanishes at |sweep| = 2π — exactly the arc that is hardest to notice
        going the wrong way round.
        """
        cx = float(p.get("cx", 0.0))
        cy = float(p.get("cy", 0.0))
        r = float(p.get("r", 1.0))
        t0 = float(p.get("theta0", 0.0))
        t1 = float(p.get("theta1", math.pi / 2))
        sweep = t1 - t0
        tq = t0 + 0.25 * sweep
        # ``theta_m`` is the cosmetic radius-grab handle. It is an angle on the
        # same circle, so it maps the same way — copied verbatim it would leave
        # the copy's handle parked somewhere the user never put it.
        has_m = "theta_m" in p
        tm = float(p.get("theta_m", 0.0))
        probe = [(cx, cy),
                 (cx + r * math.cos(t0), cy + r * math.sin(t0)),
                 (cx + r * math.cos(tq), cy + r * math.sin(tq))]
        if has_m:
            probe.append((cx + r * math.cos(tm), cy + r * math.sin(tm)))
        pts = T(probe)
        if pts is None:
            return None
        (ncx, ncy), (sx, sy), (qx, qy) = pts[:3]
        nr = math.hypot(sx - ncx, sy - ncy)
        if nr <= 0.0:                    # a zero scale factor: nothing to draw
            return None
        ntheta0 = math.atan2(sy - ncy, sx - ncx)
        cross = (sx - ncx) * (qy - ncy) - (sy - ncy) * (qx - ncx)
        nsweep = abs(sweep) if cross >= 0.0 else -abs(sweep)
        out = {"cx": ncx, "cy": ncy, "r": nr,
               "theta0": ntheta0, "theta1": ntheta0 + nsweep}
        if has_m:
            mx, my = pts[3]
            out["theta_m"] = math.atan2(my - ncy, mx - ncx)
        return out

    @staticmethod
    def _baked_edge_is_closed(seg, xs, ys) -> bool:
        """Is the edge being baked into a Polygon actually a LOOP?

        USER-REPORTED: duplicating an OPEN edge produced a closed one. The
        `closed` flag is only ever consulted for polygons, so every other kind
        of edge carries the `True` default while drawing perfectly open — an
        arc, a formula curve, a sub-edge of an imported outline. Copying that
        flag onto the baked polygon is what added the closing chord. The source
        edge's own points answer the question instead, and they answer it for
        the case the old ``project_model.is_closed`` fallback got wrong too: one
        segment of a CLOSED imported geometry is itself an open polyline.

        An arc is decided from its sweep rather than its samples: a nearly-full
        arc's endpoint gap can fall inside the spacing-relative loop tolerance,
        and "closed" for an arc means exactly 'goes all the way round'.
        """
        if seg.type == "curve" and getattr(seg, "curve_type", "") == "arc":
            sweep = abs(float(seg.parameters.get("theta1", math.pi / 2))
                        - float(seg.parameters.get("theta0", 0.0)))
            return sweep >= 2.0 * math.pi - 1e-9
        pts = np.column_stack([np.asarray(xs, dtype=float),
                               np.asarray(ys, dtype=float)])
        return GeometryService.detect_closed(pts)

    def _apply_transform(self, xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
        """Apply the selected geometric transform to the points xs and ys."""
        return self.main_window.sidebar_view.transform_spec().apply(xs, ys)

    def _nonuniform_scale_active(self) -> bool:
        """True when the active transform is a Scale with different X and Y
        factors. Such a scale is affine but not a similarity: lines and polygons
        keep their type (vertices just move), but a circle becomes an ellipse the
        circle model can't hold — so its builder bakes it into a polygon instead
        of emitting a wrong-radius circle."""
        return self.main_window.sidebar_view.transform_spec().is_nonuniform_scale
