from __future__ import annotations
import numpy as np

from app.services.geometry_service import GeometryService, _parse_vertices_str
from app.commands.stitch_cmds import StitchCmd


class StitchControllerMixin:
    """Detect open / unstitched boundary endpoints and offer a one-click stitch.

    Mirrors the industrial CAD/mesh workflow (ICEM "stitch", Pointwise "join"):
    free endpoints are highlighted in red and never silently merged; the user
    triggers the merge explicitly, and it is undoable.
    """

    # ── Tolerance ─────────────────────────────────────────────────────────
    def _stitch_tolerance(self, session) -> float:
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

    # ── Detection / warning ───────────────────────────────────────────────
    def detect_open_endpoints(self, session=None):
        """Highlight open endpoints in red and report near-miss gaps in the log.
        Safe to call after any geometry load / edit / preview."""
        session = session or self.active_session()
        canvas = self.main_window.canvas_view
        if not session:
            canvas.clear_open_endpoint_markers()
            return
        eps = self._collect_open_endpoints(session)
        if not eps:
            canvas.clear_open_endpoint_markers()
            session._open_warn_sig = ()
            return
        canvas.show_open_endpoint_markers([e["pt"] for e in eps])
        # Avoid repeating the same warning on every geometry refresh.
        sig = tuple(sorted((round(float(e["pt"][0]), 6), round(float(e["pt"][1]), 6))
                           for e in eps))
        if getattr(session, "_open_warn_sig", None) == sig:
            return
        session._open_warn_sig = sig
        tol = self._stitch_tolerance(session)
        clusters = self._cluster_endpoints(eps, tol)
        pairs = [c for c in clusters if len(c) >= 2]
        msg = f"⚠ {len(eps)} open endpoint(s) detected."
        if pairs:
            gaps = []
            for c in pairs:
                p = np.array([eps[i]["pt"] for i in c])
                gaps.append(float(np.max(np.linalg.norm(p - p.mean(axis=0), axis=1)) * 2))
            msg += (f" {len(pairs)} within stitch tolerance ({tol:.4g}); "
                    f"max gap {max(gaps):.4g}. Press Stitch to merge.")
        else:
            msg += f" None within tolerance ({tol:.4g}); endpoints are far apart."
        self.main_window.log_panel.log(msg)

    # ── One-click stitch ──────────────────────────────────────────────────
    def stitch_open_endpoints(self):
        session = self.active_session()
        if not session:
            return
        pm = session.project_model
        eps = self._collect_open_endpoints(session)
        if not eps:
            self.main_window.log_panel.log("Stitch: no open endpoints found.")
            return
        tol = self._stitch_tolerance(session)
        clusters = [c for c in self._cluster_endpoints(eps, tol) if len(c) >= 2]
        if not clusters:
            self.main_window.log_panel.log(
                f"Stitch: no endpoints within tolerance ({tol:.4g}); nothing to merge.")
            return

        # Working copies of everything a stitch may mutate.
        new_gp = (None if session.original_points is None
                  else np.array(session.original_points, dtype=float, copy=True))
        new_is_closed = pm.is_closed
        # seg_idx -> working list of [x, y] vertices for polygon segments
        poly_verts: dict[int, list] = {}
        poly_close: set[int] = set()

        def poly_working(idx):
            if idx not in poly_verts:
                seg = pm.get_segment(idx)
                vs = _parse_vertices_str(seg.parameters.get("vertices_str", ""))
                poly_verts[idx] = [list(map(float, v)) for v in vs]
            return poly_verts[idx]

        merged = 0
        skipped_other = 0
        for c in clusters:
            centroid = np.mean([eps[i]["pt"] for i in c], axis=0)
            kinds_in_cluster = {eps[i]["ref"][0] for i in c}
            if kinds_in_cluster == {"other"}:
                skipped_other += len(c)
                continue
            # File polyline self-closure: both its ends in this cluster.
            file_ends = {eps[i]["ref"][2] for i in c if eps[i]["ref"][0] == "file"}
            if file_ends == {"start", "end"}:
                new_is_closed = True
            # Polygon self-closure: a polygon's own two ends in this cluster.
            for idx in {eps[i]["ref"][1] for i in c if eps[i]["ref"][0] == "polygon"}:
                ends = {eps[i]["ref"][2] for i in c
                        if eps[i]["ref"][0] == "polygon" and eps[i]["ref"][1] == idx}
                if ends == {"start", "end"}:
                    poly_close.add(idx)
            # Snap every writeable endpoint to the cluster centroid.
            for i in c:
                kind, idx, which = eps[i]["ref"]
                if kind == "file" and new_gp is not None:
                    new_gp[0 if which == "start" else -1] = centroid
                    merged += 1
                elif kind == "polygon":
                    verts = poly_working(idx)
                    verts[0 if which == "start" else -1] = list(centroid)
                    merged += 1
                else:
                    skipped_other += 1

        if merged == 0:
            self.main_window.log_panel.log(
                "Stitch: matched endpoints are on analytic edges that can't be "
                "auto-merged; adjust them manually.")
            return

        # Build new/old state for the undoable command.
        seg_states_new: dict[int, dict] = {}
        seg_states_old: dict[int, dict] = {}
        touched_idx = set(poly_verts) | poly_close
        for idx in touched_idx:
            seg = pm.get_segment(idx)
            if seg is None:
                continue
            seg_states_old[idx] = {
                "closed": getattr(seg, "closed", True),
                "parameters": dict(seg.parameters),
            }
            new_params = dict(seg.parameters)
            if idx in poly_verts:
                new_params["vertices_str"] = ";".join(
                    f"{x:.6g},{y:.6g}" for x, y in poly_verts[idx])
            seg_states_new[idx] = {
                "closed": True if idx in poly_close else getattr(seg, "closed", True),
                "parameters": new_params,
            }

        old_state = {
            "is_closed": pm.is_closed,
            "original_points": (None if session.original_points is None
                                else np.array(session.original_points, copy=True)),
            "segments": seg_states_old,
        }
        new_state = {
            "is_closed": new_is_closed,
            "original_points": new_gp,
            "segments": seg_states_new,
        }

        cmd = StitchCmd(session, old_state, new_state,
                        refresh_cb=lambda: self._after_stitch(session))
        session.command_history.execute(cmd)
        note = f"Stitched {merged} endpoint(s) across {len(clusters)} junction(s)."
        if skipped_other:
            note += f" {skipped_other} analytic endpoint(s) left for manual edit."
        self.main_window.log_panel.log(note)

    def _after_stitch(self, session):
        """Refresh canvas + warnings + undo/redo state after a stitch / its undo.
        (_apply_geometry_update already re-runs open-endpoint detection.)"""
        session._open_warn_sig = None  # force a fresh warning/clear after the change
        self._apply_geometry_update(session)
