"""Industrial-style polygon vertex editor.

A drop-in replacement for the single-line ``QLineEdit`` that used to hold a
polygon's ``vertices_str``.  It exposes the same minimal contract the rest of
the app relies on — ``text()`` / ``setText()`` / ``setStyleSheet()`` /
``blockSignals()`` and a ``textChanged(str)`` signal — so ``shape_spec``'s
``read_widget_params`` / ``write_widget_params``, the controller's live-preview
wiring, and the modal ``ShapeParamDialog`` keep working unchanged.

On top of that contract it adds what precise CAD/meshing tools expect:

* a per-row **X / Y table** (add / insert / delete / move); non-numeric or
  non-finite cell input is rejected and the cell reverts to its last value, so
  the serialised vertex list is always a faithful, lossless view of the table
  (the table is a *view* of an internal ``_points`` model);
* **Load from file…** (``.dat`` / ``.csv`` / ``.txt`` — ``x y`` or ``x,y`` per
  line, ``#`` comments ignored);
* a **regular-polygon generator** (centre, radius, sides, start angle,
  inscribed / circumscribed);
* an **append box** accepting absolute ``x,y``, relative ``@dx,dy`` or polar
  ``@r<deg`` (AutoCAD/SolidWorks convention), relative to the last vertex;
* a live read-out: vertex count, open/closed, area, perimeter, self-intersection
  warning.

The canonical serialisation stays ``"x,y; x,y; …"`` formatted with ``%.6g`` so it
round-trips with ``shape_spec.apply_drag`` (the canvas drag handles) and the
tolerant ``geometry_service._parse_vertices_str`` parser.
"""
from __future__ import annotations
import math

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QLabel, QFileDialog, QDialog, QFormLayout,
    QDialogButtonBox, QSpinBox, QComboBox, QAbstractItemView,
)
from PyQt6.QtCore import pyqtSignal

from app.utils import make_button
from app.views.clean_double_spin_box import CleanDoubleSpinBox
from app.styles import SPIN_STYLE

_TABLE_QSS = (
    "QTableWidget{background:#181b2a;color:#a0a8c0;border:1px solid #333852;"
    "gridline-color:#2c2e43;} QHeaderView::section{background:#1e2235;"
    "color:#a0a8c0;border:none;padding:3px;}")


def _fmt(x: float) -> str:
    return f"{x:.6g}"


def _parse_vertices(s: str):
    """Tolerant ``"x,y; x,y; …"`` → ``[(x, y), …]`` (malformed pairs dropped).

    Kept local to stay decoupled from ``geometry_service`` (which sits behind a
    circular-import chain); the downstream backend re-parses via that module's
    ``_parse_vertices_str`` and applies its own fallbacks."""
    pts = []
    for pair in (s or "").split(";"):
        parts = pair.split(",")
        if len(parts) == 2:
            try:
                pts.append((float(parts[0].strip()), float(parts[1].strip())))
            except ValueError:
                pass
    return pts


def _parse_point_line(line: str):
    """Parse one file line into ``(x, y)`` or ``None``. Accepts whitespace- or
    comma-separated; ignores blank lines and ``#`` comments."""
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    parts = s.replace(",", " ").split()
    if len(parts) < 2:
        return None
    try:
        x, y = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    return x, y


def _segments_intersect(p, q, r, s) -> bool:
    """Proper intersection test for open segments pq and rs (shared endpoints
    of consecutive polygon edges do not count)."""
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    d1, d2 = cross(r, s, p), cross(r, s, q)
    d3, d4 = cross(p, q, r), cross(p, q, s)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return True
    return False


def _self_intersects(pts, closed: bool) -> bool:
    n = len(pts)
    if n < 4 or n > 400:  # skip the brute-force test on very large polygons
        return False
    # Test only the segments actually drawn: consecutive pairs i→i+1. The
    # backend samples the boundary as an open polyline, so we never synthesise a
    # wrap edge (last→first) it would not have; an explicitly-closed polygon
    # already carries that edge as its final duplicated-vertex segment.
    edges = [(pts[i], pts[i + 1]) for i in range(n - 1)]
    m = len(edges)
    for i in range(m):
        for j in range(i + 1, m):
            if abs(i - j) <= 1:
                continue  # adjacent edges share an endpoint
            if closed and i == 0 and j == m - 1:
                continue  # first/last edges meet at the duplicated vertex
            if _segments_intersect(*edges[i], *edges[j]):
                return True
    return False


class RegularPolygonDialog(QDialog):
    """Generate the vertices of a regular N-gon from centre / radius / sides."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Regular Polygon")
        self.setStyleSheet("background:#121422; color:#cdd6f4;")
        form = QFormLayout(self)

        def spin(v, lo=-1e6, hi=1e6, dec=4):
            s = CleanDoubleSpinBox()
            s.setRange(lo, hi); s.setDecimals(dec); s.setValue(v)
            s.setStyleSheet(SPIN_STYLE)
            return s

        self.cx = spin(0.0); self.cy = spin(0.0)
        self.radius = spin(1.0, lo=1e-6)
        self.sides = QSpinBox(); self.sides.setRange(3, 1000); self.sides.setValue(6)
        self.sides.setStyleSheet(SPIN_STYLE)
        self.start_angle = spin(0.0, lo=-360.0, hi=360.0, dec=2)
        self.fit = QComboBox()
        self.fit.addItems(["Circumscribed (vertices on circle)",
                           "Inscribed (edge midpoints on circle)"])
        self.fit.setStyleSheet(SPIN_STYLE)

        form.addRow(QLabel("Centre X:"), self.cx)
        form.addRow(QLabel("Centre Y:"), self.cy)
        form.addRow(QLabel("Radius:"), self.radius)
        form.addRow(QLabel("Sides:"), self.sides)
        form.addRow(QLabel("Start angle (deg):"), self.start_angle)
        form.addRow(QLabel("Fit:"), self.fit)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def vertices(self):
        n = self.sides.value()
        cx, cy, r = self.cx.value(), self.cy.value(), self.radius.value()
        a0 = math.radians(self.start_angle.value())
        # "Inscribed" here means the circle touches the edge midpoints, so the
        # circumradius is r / cos(pi/n).
        if self.fit.currentIndex() == 1:
            r = r / math.cos(math.pi / n)
        return [(cx + r * math.cos(a0 + 2 * math.pi * i / n),
                 cy + r * math.sin(a0 + 2 * math.pi * i / n)) for i in range(n)]


class PolygonEditor(QWidget):
    """Drop-in replacement for the polygon ``vertices_str`` QLineEdit."""

    textChanged = pyqtSignal(str)

    def __init__(self, initial: str = "0,0; 1,0; 1,1; 0,1", parent=None):
        super().__init__(parent)
        self._loading = False
        self._points: list[list[float]] = []   # model; the table is its view
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        # ── Vertex table ────────────────────────────────────────────────
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["X", "Y"])
        self.table.setStyleSheet(_TABLE_QSS)
        self.table.setFixedHeight(150)
        self.table.verticalHeader().setDefaultSectionSize(20)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.cellChanged.connect(self._on_cell_changed)
        lay.addWidget(self.table)

        # ── Row ops ─────────────────────────────────────────────────────
        ops = QHBoxLayout(); ops.setSpacing(3)
        self._add_btn = make_button("+ Add", "#1a2a3a")
        self._ins_btn = make_button("Insert", "#1a2a3a")
        self._del_btn = make_button("Delete", "#301a1a")
        self._up_btn = make_button("▲", "#26293c")
        self._down_btn = make_button("▼", "#26293c")
        for b in (self._add_btn, self._ins_btn, self._del_btn,
                  self._up_btn, self._down_btn):
            ops.addWidget(b)
        self._add_btn.clicked.connect(self._add_row)
        self._ins_btn.clicked.connect(self._insert_row)
        self._del_btn.clicked.connect(self._delete_rows)
        self._up_btn.clicked.connect(lambda: self._move_row(-1))
        self._down_btn.clicked.connect(lambda: self._move_row(1))
        lay.addLayout(ops)

        # ── Append box (absolute / relative / polar) ────────────────────
        ar = QHBoxLayout(); ar.setSpacing(3)
        self._append_edit = QLineEdit()
        self._append_edit.setPlaceholderText("x,y  ·  @dx,dy  ·  @r<deg")
        self._append_edit.setStyleSheet(SPIN_STYLE)
        self._append_edit.setToolTip(
            "Append a vertex:\n"
            "  x,y      absolute coordinate\n"
            "  @dx,dy   relative to the last vertex\n"
            "  @r<deg   polar (length, angle) from the last vertex")
        self._append_edit.returnPressed.connect(self._append_typed)
        ar.addWidget(self._append_edit)
        lay.addLayout(ar)

        # ── File / generator ────────────────────────────────────────────
        tools = QHBoxLayout(); tools.setSpacing(3)
        self._file_btn = make_button("Load from file…", "#15303a")
        self._file_btn.setToolTip(
            "Load vertices from a .dat / .csv / .txt file (x y or x,y per line)")
        self._reg_btn = make_button("Regular polygon…", "#1b2a4a")
        tools.addWidget(self._file_btn)
        tools.addWidget(self._reg_btn)
        self._file_btn.clicked.connect(self._load_from_file)
        self._reg_btn.clicked.connect(self._make_regular)
        lay.addLayout(tools)

        # ── Live read-out ────────────────────────────────────────────────
        self._info = QLabel("")
        self._info.setStyleSheet("color:#7a82a0; font-size:10px;")
        self._info.setWordWrap(True)
        lay.addWidget(self._info)

        self.setText(initial)

    # ──────────────────────────────────────────────────────────────────
    # QLineEdit-compatible contract
    # ──────────────────────────────────────────────────────────────────
    def text(self) -> str:
        # Pure getter: serialises the model, which is always a faithful, lossless
        # view of the table (rejected input never reaches it).
        return "; ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in self._points)

    def setText(self, s: str):
        self._set_points(_parse_vertices(s))

    # ──────────────────────────────────────────────────────────────────
    # Model ↔ table sync
    # ──────────────────────────────────────────────────────────────────
    def _set_points(self, pts):
        """Replace the model with ``pts`` (any iterable of (x, y)), resync the
        table and emit. The single points→table→emit path shared by setText,
        file load and the regular-polygon generator."""
        self._points = [[float(x), float(y)] for x, y in pts]
        self._sync_table_from_points()
        self._refresh_info()
        if not self.signalsBlocked():
            self.textChanged.emit(self.text())

    def _sync_table_from_points(self):
        """Reconcile the table to ``self._points`` in place — only changed cells
        are rewritten and the row count is grown/shrunk as needed, so the common
        drag case (same count, one coordinate moved) neither tears down the table
        nor drops the user's row selection."""
        self._loading = True
        try:
            if self.table.rowCount() != len(self._points):
                self.table.setRowCount(len(self._points))
            for r, (x, y) in enumerate(self._points):
                self._set_cell(r, 0, x)
                self._set_cell(r, 1, y)
        finally:
            self._loading = False

    def _set_cell(self, r: int, c: int, v: float):
        txt = _fmt(v)
        it = self.table.item(r, c)
        if it is None:
            self.table.setItem(r, c, QTableWidgetItem(txt))
        elif it.text() != txt:
            it.setText(txt)

    def _selected_rows(self) -> list:
        return sorted({i.row() for i in self.table.selectedIndexes()})

    def _selected_row_or(self, default: int) -> int:
        rows = self._selected_rows()
        return rows[0] if rows else default

    def _emit(self):
        self._refresh_info()
        if not self.signalsBlocked():
            self.textChanged.emit(self.text())

    # ──────────────────────────────────────────────────────────────────
    # Cell edits / row ops (all mutate self._points, then resync)
    # ──────────────────────────────────────────────────────────────────
    def _on_cell_changed(self, r: int, c: int):
        if self._loading:
            return
        it = self.table.item(r, c)
        raw = it.text().strip() if it is not None else ""
        try:
            v = float(raw)
            if not math.isfinite(v):
                raise ValueError
        except ValueError:
            # Reject non-numeric / non-finite input: revert the cell from the
            # model so a typo can never silently drop or corrupt a vertex.
            self._loading = True
            if it is not None:
                it.setText(_fmt(self._points[r][c]))
            self._loading = False
            self._info.setText("⚠ not a number — reverted")
            return
        self._points[r][c] = v
        self._emit()

    def _add_row(self):
        x, y = ((self._points[-1][0] + 1.0, self._points[-1][1])
                if self._points else (0.0, 0.0))
        self._points.append([x, y])
        self._sync_table_from_points()
        self.table.selectRow(len(self._points) - 1)
        self._emit()

    def _insert_row(self):
        r = self._selected_row_or(-1)
        if r < 0:                       # no selection → append at the end
            r = len(self._points)
        self._points.insert(r, [0.0, 0.0])
        self._sync_table_from_points()
        self.table.selectRow(r)
        self._emit()

    def _delete_rows(self):
        rows = self._selected_rows()
        if not rows and self._points:
            rows = [len(self._points) - 1]
        if len(self._points) - len(rows) < 3:
            self._info.setText("⚠ a polygon needs at least 3 vertices")
            return
        for r in sorted(rows, reverse=True):
            if 0 <= r < len(self._points):
                del self._points[r]
        self._sync_table_from_points()
        self._emit()

    def _move_row(self, delta: int):
        r = self._selected_row_or(-1)
        t = r + delta
        if r < 0 or t < 0 or t >= len(self._points):
            return
        self._points[r], self._points[t] = self._points[t], self._points[r]
        self._sync_table_from_points()
        self.table.selectRow(t)
        self._emit()

    # ──────────────────────────────────────────────────────────────────
    # Append box / file / generator
    # ──────────────────────────────────────────────────────────────────
    def _append_typed(self):
        raw = self._append_edit.text().strip()
        if not raw:
            return
        lx, ly = (self._points[-1] if self._points else (0.0, 0.0))
        try:
            if raw.startswith("@") and "<" in raw:           # polar @r<deg
                r_str, a_str = raw[1:].split("<", 1)
                r, a = float(r_str), math.radians(float(a_str))
                x, y = lx + r * math.cos(a), ly + r * math.sin(a)
            elif raw.startswith("@"):                         # relative @dx,dy
                dx, dy = (float(v) for v in raw[1:].split(",", 1))
                x, y = lx + dx, ly + dy
            else:                                             # absolute x,y
                x, y = (float(v) for v in raw.replace(";", ",").split(",", 1))
            if not (math.isfinite(x) and math.isfinite(y)):
                raise ValueError
        except (ValueError, IndexError):
            self._info.setText("⚠ Could not parse — use x,y · @dx,dy · @r<deg")
            return
        self._points.append([x, y])
        self._sync_table_from_points()
        self._append_edit.clear()
        self.table.selectRow(len(self._points) - 1)
        self._emit()

    def _load_from_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load polygon vertices", "",
            "Geometry/Data (*.dat *.csv *.txt);;All files (*)")
        if not path:
            return
        pts = []
        try:
            with open(path, "r") as fh:
                for line in fh:
                    p = _parse_point_line(line)
                    if p is not None:
                        pts.append(p)
        except OSError as e:
            self._info.setText(f"⚠ {e}")
            return
        if len(pts) < 3:
            self._info.setText("⚠ File yielded fewer than 3 vertices")
            return
        self._set_points(pts)

    def _make_regular(self):
        dlg = RegularPolygonDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._set_points(dlg.vertices())

    # ──────────────────────────────────────────────────────────────────
    # Read-out
    # ──────────────────────────────────────────────────────────────────
    def _refresh_info(self):
        pts = self._points
        n = len(pts)
        if n < 2:
            self._info.setText(f"{n} vertex" if n == 1 else "no valid vertices")
            return
        # Closed only when the user explicitly repeats the first point as the
        # last — that mirrors how the backend samples the boundary (an open
        # polyline otherwise), so the read-out never claims an area the geometry
        # does not enclose.
        closed = math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-9
        length = sum(math.hypot(pts[i + 1][0] - pts[i][0],
                                pts[i + 1][1] - pts[i][1])
                     for i in range(n - 1))
        parts = [f"{n} verts", "closed" if closed else "open"]
        if closed:
            area = 0.5 * abs(sum(pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1]
                                 for i in range(n - 1)))
            parts += [f"A={area:.4g}", f"P={length:.4g}"]
        else:
            parts.append(f"L={length:.4g}")
        if _self_intersects(pts, closed):
            parts.append("⚠ self-intersecting")
        self._info.setText("  ·  ".join(parts))
