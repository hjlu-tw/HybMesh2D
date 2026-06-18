from __future__ import annotations
import numpy as np

from app.services.geometry_service import GeometryService


class OpenEndpointControllerMixin:
    """Detect and warn about open / unstitched boundary endpoints.

    Mirrors the industrial CAD/mesh convention (ICEM, Pointwise): free endpoints
    are highlighted in red and reported in the log, but never silently merged or
    auto-closed — the user fixes them deliberately by editing the geometry.
    """

    # ── Tolerance ─────────────────────────────────────────────────────────
    def _endpoint_tolerance(self, session) -> float:
        """A fraction of the geometry's bounding-box diagonal (model-relative,
        like a CAD merge tolerance), with a small absolute floor."""
        pts = session.original_points
        bbox_pts = []
        if pts is not None and len(pts) > 0:
            bbox_pts.append(np.asarray(pts, dtype=float))
        for seg in session.project_model.segments:
            if seg.type == "curve":
                pr = GeometryService.get_segment_points(session, seg)
                if pr is not None:
                    bbox_pts.append(np.column_stack(pr))
        if not bbox_pts:
            return 1e-6
        allp = np.vstack(bbox_pts)
        diag = float(np.hypot(np.ptp(allp[:, 0]), np.ptp(allp[:, 1])))
        return max(0.01 * diag, 1e-9)

    # ── Endpoint collection ───────────────────────────────────────────────
    def _collect_open_endpoints(self, session) -> list[dict]:
        """Free endpoints of every OPEN piece. Each entry:
        {pt: np.array([x,y]), ref: (kind, seg_idx_or_None, which)} where
        kind ∈ {'file','polygon','other'} and which ∈ {'start','end'}."""
        pm = session.project_model
        eps: list[dict] = []

        gp = session.original_points
        if gp is not None and len(gp) >= 2 and not pm.is_closed:
            gp = np.asarray(gp, dtype=float)
            eps.append({"pt": gp[0].copy(), "ref": ("file", None, "start")})
            eps.append({"pt": gp[-1].copy(), "ref": ("file", None, "end")})

        for idx, seg in enumerate(pm.segments):
            if seg.type != "curve":
                continue
            ct = getattr(seg, "curve_type", "custom")
            if ct in ("triangle", "quadrilateral", "circle"):
                continue  # inherently closed
            if ct == "polygon" and getattr(seg, "closed", True):
                continue  # already a closed loop
            pr = GeometryService.get_segment_points(session, seg)
            if pr is None:
                continue
            xs, ys = pr
            if len(xs) < 2:
                continue
            kind = "polygon" if ct == "polygon" else "other"
            eps.append({"pt": np.array([xs[0], ys[0]]), "ref": (kind, idx, "start")})
            eps.append({"pt": np.array([xs[-1], ys[-1]]), "ref": (kind, idx, "end")})
        return eps

    @staticmethod
    def _cluster_endpoints(eps: list[dict], tol: float) -> list[list[int]]:
        """Group endpoint indices that lie within ``tol`` of each other."""
        n = len(eps)
        parent = list(range(n))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        for i in range(n):
            for j in range(i + 1, n):
                if np.hypot(*(eps[i]["pt"] - eps[j]["pt"])) <= tol:
                    parent[find(i)] = find(j)
        groups: dict[int, list[int]] = {}
        for i in range(n):
            groups.setdefault(find(i), []).append(i)
        return list(groups.values())

    # ── Internal gaps (a moved edge leaves a jump mid-polyline) ───────────
    def find_geometry_gaps(self, session) -> list[dict]:
        """Find anomalously large jumps between consecutive points of the active
        file polyline (and the closing seam when ``is_closed``). A moved-away
        edge leaves such a jump — the thing preview would silently bridge.

        Returns a list of {idx, j, p0, p1, dist, wrap}: ``idx``/``j`` index the
        two straddling points in ``original_points`` (``wrap`` marks the closing
        seam where j wraps to 0)."""
        pts = session.original_points
        if pts is None or len(pts) < 3:
            return []
        pts = np.asarray(pts, dtype=float)
        n = len(pts)
        d = np.hypot(pts[1:, 0] - pts[:-1, 0], pts[1:, 1] - pts[:-1, 1])
        closed = bool(session.project_model.is_closed)
        wrap_d = float(np.hypot(*(pts[0] - pts[-1]))) if closed else 0.0
        alld = np.concatenate([d, [wrap_d]]) if closed else d
        pos = alld[alld > 1e-12]
        if len(pos) == 0:
            return []
        thresh = max(4.0 * float(np.median(pos)), self._endpoint_tolerance(session))
        gaps = []
        for i in range(n - 1):
            if d[i] > thresh:
                gaps.append({"idx": i, "j": i + 1,
                             "p0": pts[i].copy(), "p1": pts[i + 1].copy(),
                             "dist": float(d[i]), "wrap": False})
        if closed and wrap_d > thresh:
            gaps.append({"idx": n - 1, "j": 0,
                         "p0": pts[-1].copy(), "p1": pts[0].copy(),
                         "dist": wrap_d, "wrap": True})
        return gaps

    @staticmethod
    def gaps_signature(gaps: list[dict]):
        return tuple(sorted((g["idx"], g["j"]) for g in gaps))

    # ── Detection / warning ───────────────────────────────────────────────
    def detect_open_endpoints(self, session=None):
        """Highlight open endpoints / internal gaps in red and report them in the
        log. Safe to call after any geometry load / edit / preview."""
        session = session or self.active_session()
        canvas = self.main_window.canvas_view
        if not session:
            canvas.clear_open_endpoint_markers()
            return
        eps = self._collect_open_endpoints(session)
        gaps = self.find_geometry_gaps(session)
        marker_pts = [e["pt"] for e in eps]
        for g in gaps:
            marker_pts.append(g["p0"])
            marker_pts.append(g["p1"])
        if not marker_pts:
            canvas.clear_open_endpoint_markers()
            session._open_warn_sig = ()
            return
        canvas.show_open_endpoint_markers(marker_pts)
        # Avoid repeating the same warning on every geometry refresh.
        sig = tuple(sorted((round(float(p[0]), 6), round(float(p[1]), 6))
                           for p in marker_pts))
        if getattr(session, "_open_warn_sig", None) == sig:
            return
        session._open_warn_sig = sig
        parts = []
        if gaps:
            parts.append(f"{len(gaps)} unclosed gap(s) (max {max(g['dist'] for g in gaps):.4g})")
        if eps:
            parts.append(f"{len(eps)} open endpoint(s)")
        self.main_window.log_panel.log("⚠ " + ", ".join(parts) + " — boundary not closed.")

    # ── Stitching (dialog-driven, undoable) ───────────────────────────────
    def stitch_gaps(self, session, gaps: list[dict], method: str):
        """Close the detected gaps using one of three methods, undoably.

        - 'midpoint': move both straddling points to their midpoint (merge).
        - 'snap':     move the later point onto the earlier one.
        - 'line':     leave the points unchanged (the bridging line is accepted).
        """
        if method == "line" or not gaps:
            return  # nothing to mutate; closure/bridge is accepted as-is
        pts = session.original_points
        if pts is None:
            return
        new = np.array(pts, dtype=float, copy=True)
        for g in gaps:
            i, j = g["idx"], g["j"]
            if method == "midpoint":
                mid = 0.5 * (new[i] + new[j])
                new[i] = mid
                new[j] = mid
            elif method == "snap":
                new[j] = new[i]
        from app.commands.stitch_cmds import StitchCmd
        cmd = StitchCmd(session,
                        old_points=np.array(pts, copy=True), new_points=new,
                        refresh_cb=lambda: self._apply_geometry_update(session))
        session.command_history.execute(cmd)
        self._update_undo_redo_buttons(session)
