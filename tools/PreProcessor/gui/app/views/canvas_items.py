"""Standalone canvas widgets/items extracted from canvas.py (behaviour
unchanged): the color-bar legend (ColorBarWidget), the quality-heatmap pyqtgraph
item (ColorCodedSegmentsItem) and the rubber-band selection ViewBox
(SelectableViewBox). None reads CanvasView state — CanvasView constructs and
wires them — so they live outside the interactive-core file."""
from __future__ import annotations
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QLinearGradient, QPainterPath


class ColorBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(70)
        self.min_val = 0.0
        self.max_val = 0.0
        self.title_text = "Length"
        self.quality_mode = "length"
        self.setStyleSheet("background-color: #0c0d16; color: #a0a8c0;")

    def set_range(self, min_val: float, max_val: float):
        self.min_val = min_val
        self.max_val = max_val
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        painter.fillRect(rect, QColor("#0c0d16"))
        
        margin_top = 30
        margin_bottom = 20
        bar_width = 12
        bar_left = 10
        bar_height = rect.height() - margin_top - margin_bottom
        
        if bar_height <= 0:
            return
            
        gradient = QLinearGradient(QPointF(bar_left, rect.height() - margin_bottom),
                                    QPointF(bar_left, margin_top))
        if self.quality_mode == "ratio":
            gradient.setColorAt(0.0, QColor.fromHsvF(0.6666, 1.0, 1.0)) # blue (small ratio)
            gradient.setColorAt(0.5, QColor.fromHsvF(0.3333, 1.0, 1.0)) # green/yellow
            gradient.setColorAt(1.0, QColor.fromHsvF(0.0, 1.0, 1.0))    # red (large ratio)
        else:
            gradient.setColorAt(0.0, QColor.fromHsvF(0.0, 1.0, 1.0))    # red (small distance)
            gradient.setColorAt(0.5, QColor.fromHsvF(0.3333, 1.0, 1.0)) # green/yellow
            gradient.setColorAt(1.0, QColor.fromHsvF(0.6666, 1.0, 1.0)) # blue (large distance)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRect(bar_left, margin_top, bar_width, bar_height)
        
        painter.setPen(QColor("#a0a8c0"))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        
        min_str = f"{self.min_val:.4g}"
        painter.drawText(bar_left + bar_width + 6, rect.height() - margin_bottom + 4, min_str)
        
        max_str = f"{self.max_val:.4g}"
        painter.drawText(bar_left + bar_width + 6, margin_top + 4, max_str)
        
        mid_val = 0.5 * (self.min_val + self.max_val)
        mid_str = f"{mid_val:.4g}"
        painter.drawText(bar_left + bar_width + 6, margin_top + bar_height // 2 + 4, mid_str)
        
        painter.drawText(8, 18, self.title_text)


class ColorCodedSegmentsItem(pg.GraphicsObject):
    def __init__(self):
        super().__init__()
        self.points = None
        self.pens = []
        self.show_symbols = True
        self.symbol_brushes = []
        self._bounds = None
        self.gap_indices = set()

    def setData(self, points, lengths, min_len, max_len, show_symbols, symbol_brushes, quality_mode='length', gap_indices=None):
        self.points = points
        self.show_symbols = show_symbols
        self.symbol_brushes = symbol_brushes
        self.gap_indices = gap_indices if gap_indices is not None else set()
        
        self.pens = []
        if points is not None and len(points) >= 2:
            span = max_len - min_len
            for l in lengths:
                t = (l - min_len) / span if span > 1e-12 else 0.0
                t = max(0.0, min(1.0, t))
                if quality_mode == 'ratio':
                    color = QColor.fromHsvF((1.0 - t) * 0.6666, 1.0, 1.0)
                else:
                    color = QColor.fromHsvF(t * 0.6666, 1.0, 1.0)
                self.pens.append(pg.mkPen(color, width=2.5))
            
            x = points[:, 0]
            y = points[:, 1]
            self._bounds = QRectF(x.min(), y.min(), x.max() - x.min(), y.max() - y.min())
        else:
            self._bounds = None
            
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self):
        if self._bounds is None:
            return QRectF()
        return self._bounds

    def paint(self, painter, option, widget):
        if self.points is None or len(self.points) < 2:
            return

        pts = self.points
        n = len(pts)
        gap_indices = getattr(self, 'gap_indices', set())

        # Viewport culling: restrict drawing to the exposed rect (item coords)
        # with a small margin, so pan/zoom stays fast on large datasets instead
        # of redrawing every off-screen segment each frame.
        clip = getattr(option, "exposedRect", None)
        if clip is not None and clip.isValid() and clip.width() > 0:
            m = max(clip.width(), clip.height()) * 0.05 + 1e-12
            cx0, cy0 = clip.left() - m, clip.top() - m
            cx1, cy1 = clip.right() + m, clip.bottom() + m
        else:
            cx0 = cy0 = -1e308
            cx1 = cy1 = 1e308

        # Batch consecutive segments sharing a colour into one QPainterPath so
        # we issue far fewer setPen/draw calls than one drawLine per segment.
        npens = len(self.pens)
        path = None
        cur_pen = None
        cur_key = None

        def flush():
            nonlocal path, cur_pen, cur_key
            if path is not None and cur_pen is not None:
                painter.setPen(cur_pen)
                painter.drawPath(path)
            path = None
            cur_pen = None
            cur_key = None

        for i in range(n - 1):
            if i in gap_indices or i >= npens:
                flush()
                continue
            ax, ay = pts[i][0], pts[i][1]
            bx, by = pts[i + 1][0], pts[i + 1][1]
            if (max(ax, bx) < cx0 or min(ax, bx) > cx1
                    or max(ay, by) < cy0 or min(ay, by) > cy1):
                flush()
                continue
            pen = self.pens[i]
            key = pen.color().rgba()
            if key != cur_key:
                flush()
                cur_key = key
                cur_pen = pen
                path = QPainterPath()
                path.moveTo(ax, ay)
                path.lineTo(bx, by)
            else:
                # Segments are contiguous (share pts[i]); extend the polyline.
                path.lineTo(bx, by)
        flush()

        if self.show_symbols and self.symbol_brushes:
            painter.setPen(pg.mkPen(None))
            nb = len(self.symbol_brushes)
            for i in range(min(n, nb)):
                px, py = pts[i][0], pts[i][1]
                if px < cx0 or px > cx1 or py < cy0 or py > cy1:
                    continue
                painter.setBrush(self.symbol_brushes[i])
                painter.drawEllipse(QPointF(px, py), 3.0, 3.0)


class SelectableViewBox(pg.ViewBox):
    """ViewBox with rubber-band box ("圈選") selection.

    A plain left-drag still pans (pyqtgraph default).  Holding a modifier
    while left-dragging draws a selection rectangle; on release the
    data-space rect is reported via ``box_select_cb``:
      • Shift+drag      → replace the current selection with the box contents
      • Ctrl/Cmd+drag   → add the box contents to the current selection
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.box_select_cb = None   # fn(x0, y0, x1, y1, extend: bool)
        self.box_enabled = False    # only active in edge selection mode

    def mouseDragEvent(self, ev, axis=None):
        mods = ev.modifiers()
        is_box = (
            self.box_enabled
            and ev.button() == Qt.MouseButton.LeftButton
            and axis is None
            and bool(mods & (Qt.KeyboardModifier.ShiftModifier
                             | Qt.KeyboardModifier.ControlModifier
                             | Qt.KeyboardModifier.MetaModifier))
        )
        if not is_box:
            super().mouseDragEvent(ev, axis=axis)
            return

        ev.accept()
        p1, p2 = ev.buttonDownPos(), ev.pos()
        if ev.isFinish():
            self.rbScaleBox.hide()
            rect = self.childGroup.mapRectFromParent(QRectF(p1, p2))
            extend = bool(mods & (Qt.KeyboardModifier.ControlModifier
                                  | Qt.KeyboardModifier.MetaModifier))
            if self.box_select_cb is not None:
                self.box_select_cb(rect.left(), rect.top(),
                                   rect.right(), rect.bottom(), extend)
        else:
            self.updateScaleBox(p1, p2)
