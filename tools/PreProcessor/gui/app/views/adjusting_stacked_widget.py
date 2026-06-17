from __future__ import annotations
from PyQt6.QtWidgets import QStackedWidget, QSizePolicy


class AdjustingStackedWidget(QStackedWidget):
    """A QStackedWidget that takes the height of its *current* page.

    A plain QStackedWidget always reserves the height of its tallest page, so
    switching to a short page (e.g. a 1-field 'Circle' or 'cosine' form) leaves
    a band of dead space below it. Here every non-current page is given an
    Ignored vertical size policy so it contributes nothing to the layout, and
    the size hints track the visible page — the stack shrinks to fit whatever is
    shown."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentChanged.connect(self._sync_policies)

    def addWidget(self, w):
        index = super().addWidget(w)
        self._sync_policies(self.currentIndex())
        return index

    def _sync_policies(self, current: int):
        for i in range(self.count()):
            page = self.widget(i)
            if page is None:
                continue
            vpol = (QSizePolicy.Policy.Preferred if i == current
                    else QSizePolicy.Policy.Ignored)
            page.setSizePolicy(QSizePolicy.Policy.Preferred, vpol)
        self.updateGeometry()

    def sizeHint(self):
        w = self.currentWidget()
        return w.sizeHint() if w is not None else super().sizeHint()

    def minimumSizeHint(self):
        w = self.currentWidget()
        return w.minimumSizeHint() if w is not None else super().minimumSizeHint()
