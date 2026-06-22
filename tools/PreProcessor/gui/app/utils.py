from __future__ import annotations
import os
import shutil
from contextlib import contextmanager

from PyQt6.QtCore import QObject, Qt, QPoint, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QPushButton,
    QFormLayout,
    QLabel,
    QHBoxLayout,
    QWidget
)

from app.styles import (
    COMBO_STYLE,
    SPIN_STYLE,
    BUTTON_QSS_TEMPLATE,
    LINEEDIT_STYLE,
    LIST_STYLE,
    LIST_INDICATOR_STYLE
)

# Boundary Condition Colors mapping
BC_COLORS = {
    "wall": '#ef4444',
    "farfield": '#06b6d4',
    "inlet": '#22c55e',
    "outlet": '#3b82f6',
    "symmetry": '#f97316',
    "symp": '#f97316',       # alias for symmetry
    "isothermal": '#a855f7', # purple — isothermal wall
    "free": '#eab308',       # yellow — free boundary
}
DEFAULT_BC_COLOR = '#9ca3af'

@contextmanager
def block_signals(*widgets: QObject):
    """Context manager to block signals of multiple Qt widgets temporarily."""
    for w in widgets:
        if w is not None:
            w.blockSignals(True)
    try:
        yield
    finally:
        for w in widgets:
            if w is not None:
                w.blockSignals(False)

# Curve type labels mapping
CURVE_TYPE_LABELS = {
    "custom": lambda seg: f"Curve ({'Param' if seg.curve_mode == 'parametric' else 'Explicit'})",
    "horizontal_line": "H Line",
    "vertical_line": "V Line",
    "line": "Line",
    "circle": "Circle",
    "triangle": "Triangle",
    "quadrilateral": "Quad",
    "polygon": "Polygon",
}


def make_button(text: str, color: str = '#26293c') -> QPushButton:
    b = QPushButton(text)
    b.setStyleSheet(BUTTON_QSS_TEMPLATE.format(color=color))
    return b

def align_form_labels(layout: QFormLayout, width: int = 120):
    layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
    layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    for i in range(layout.rowCount()):
        label_item = layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
        if label_item:
            lbl = label_item.widget()
            if lbl:
                lbl.setFixedWidth(width)
                if isinstance(lbl, QLabel):
                    lbl.setWordWrap(True)


# ---------------------------------------------------------------------------
# Custom floating tooltip popup (bypasses macOS QToolTip rendering issues)
# ---------------------------------------------------------------------------

class _FloatingTooltip(QWidget):
    """A frameless, always-on-top popup label used as a custom tooltip."""

    def __init__(self):
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(260)
        self._label.setStyleSheet(
            "color: #e2e8f0;"
            "background: transparent;"
            "padding: 0px;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.addWidget(self._label)
        self.setStyleSheet(
            "background-color: #1e2235;"
            "border: 1px solid #3b82f6;"
            "border-radius: 5px;"
        )
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_near(self, global_pos: QPoint, text: str):
        self._hide_timer.stop()
        self._label.setText(text)
        self._label.adjustSize()
        self.adjustSize()
        # Position slightly below-right of cursor
        x = global_pos.x() + 14
        y = global_pos.y() + 14
        # Keep on screen
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            if x + self.width() > geom.right():
                x = global_pos.x() - self.width() - 4
            if y + self.height() > geom.bottom():
                y = global_pos.y() - self.height() - 4
        self.move(x, y)
        self.show()
        self.raise_()

    def schedule_hide(self, delay_ms: int = 200):
        self._hide_timer.start(delay_ms)


# Singleton tooltip popup (one per application)
_tooltip_popup: _FloatingTooltip | None = None

def _get_tooltip_popup() -> _FloatingTooltip:
    global _tooltip_popup
    if _tooltip_popup is None:
        _tooltip_popup = _FloatingTooltip()
    return _tooltip_popup


class HelpButton(QPushButton):
    """A small '?' button that shows a custom floating tooltip on hover."""

    def __init__(self, tooltip_text: str):
        super().__init__("?")
        self._tooltip_text = tooltip_text
        self.setFixedSize(16, 16)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.setMouseTracking(True)
        self.setStyleSheet("""
            QPushButton {
                background-color: #2a2d45;
                color: #8892b0;
                border: 1px solid #3a4060;
                border-radius: 8px;
                font-size: 10px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
                color: #ffffff;
                border-color: #60a5fa;
            }
        """)

    def enterEvent(self, event):
        popup = _get_tooltip_popup()
        cursor_pos = self.mapToGlobal(QPoint(self.width(), 0))
        popup.show_near(cursor_pos, self._tooltip_text)
        super().enterEvent(event)

    def leaveEvent(self, event):
        _get_tooltip_popup().schedule_hide(150)
        super().leaveEvent(event)


def make_help_label(tooltip: str) -> HelpButton:
    """Create a small '?' button with a custom floating tooltip."""
    return HelpButton(tooltip)


def help_label(label_text: str, tooltip: str) -> QWidget:
    """Create a composite label widget with text + '?' help icon for use as a QFormLayout label."""
    container = QWidget()
    hl = QHBoxLayout(container)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(3)
    text_lbl = QLabel(label_text)
    text_lbl.setStyleSheet("color: #a0a8c0;")
    text_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    hl.addWidget(text_lbl, 1)
    hl.addWidget(make_help_label(tooltip))
    return container


def help_widget(widget, tooltip: str) -> QWidget:
    """Wrap any widget (like a button, checkbox, or list) with a '?' help icon to its right."""
    container = QWidget()
    hl = QHBoxLayout(container)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(6)
    hl.addWidget(widget)
    hl.addWidget(make_help_label(tooltip))
    return container


def help_row(label_text: str, widget, tooltip: str) -> QWidget:
    """Backward compatibility helper mapping to help_label."""
    return help_label(label_text, tooltip)


def repo_root() -> str:
    """Absolute path to the repository root (the HybMesh project directory).

    Single source of truth for the project root. Callers in ``app/`` previously
    derived it ad-hoc as ``os.path.join(dirname(__file__), "../...")`` with the
    number of ``..`` segments depending on the file's depth — an easy off-by-one
    to get wrong. ``utils.py`` lives at ``gui/app/utils.py``, four levels below
    the repo root."""
    return os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))


def find_binary_executable(bin_name: str) -> str | None:
    """Locate binary executable in PATH environment or local build candidates."""
    path_run = shutil.which(bin_name)
    if path_run:
        return path_run

    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.abspath(os.path.join(base_dir, "../../../../../build")),
        os.path.abspath("../../../build"),
        os.path.abspath("./build"),
        os.path.abspath("."),
    ]
    for folder in candidates:
        full_path = os.path.join(folder, bin_name)
        if os.path.exists(full_path) and os.access(full_path, os.X_OK) and not os.path.isdir(full_path):
            return full_path
    return None


# Prebuilt solver-pipeline binaries shipped under solver/ (decision D5: use the
# existing binaries, no compilation step). Paths are relative to the repo root.
_SOLVER_BIN_REL = {
    "getpgrid": "solver/preprocess/getPGrid/work/getPGrid",
    "bdecompose": "solver/preprocess/bDecompose/work/bDecompose",
    "solver": "solver/execute/unicones.eqn6.mac",
}


def find_solver_executables() -> dict:
    """Locate the prebuilt getPGrid / bDecompose / unicones binaries.

    Returns a dict {name: abs_path | None}. Existence (not executability) is
    reported, since bDecompose ships without the +x bit and the solver worker
    chmods it on demand when domain decomposition is enabled.
    """
    repo = repo_root()
    found: dict[str, str | None] = {}
    for name, rel in _SOLVER_BIN_REL.items():
        full = os.path.join(repo, rel)
        found[name] = full if os.path.exists(full) else None
    return found

