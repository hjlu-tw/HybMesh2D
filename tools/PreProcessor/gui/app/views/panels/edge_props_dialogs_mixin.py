from __future__ import annotations
from PyQt6.QtCore import Qt


class EdgePropsDialogsMixin:
    def _show_dialog(self, dlg):
        # Re-parent to the MAIN WINDOW (not this panel, which gets hidden when
        # the selection changes) as a normal (modeless) Dialog window. A Dialog
        # stays above its parent window but is NOT globally always-on-top, and it
        # behaves normally when you switch to another application (it keeps its
        # place instead of dropping behind the main window, as a Tool window did
        # on macOS). See #2.
        mw = self.window()
        if mw is not None and dlg.parent() is not mw:
            dlg.setParent(mw, Qt.WindowType.Dialog)
        # A plain Dialog could still drop behind the main window on macOS; force
        # it to stay above the app's windows (#2/#8).
        dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def open_distribution_dialog(self):
        self._show_dialog(self._distribution_dialog)

    def _open_split_dialog(self):
        self._show_dialog(self._split_dialog)

    def open_transform_dialog(self):
        self._transform_dup_group.setVisible(True)
        self._show_dialog(self._transform_dialog)
