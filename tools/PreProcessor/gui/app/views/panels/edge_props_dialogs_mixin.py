from __future__ import annotations
from PyQt6.QtCore import Qt


class EdgePropsDialogsMixin:
    def _show_dialog(self, dlg):
        # Re-parent to the MAIN WINDOW (not this panel, which gets hidden when
        # the selection changes) then keep it above the app's own windows only
        # (a Tool window — above the main window but NOT above other apps) and
        # nudged off centre so it doesn't cover the geometry. See #2/#8.
        from app.utils import keep_on_top, offset_popup
        mw = self.window()
        if mw is not None and dlg.parent() is not mw:
            dlg.setParent(mw, Qt.WindowType.Dialog)
        keep_on_top(dlg)
        offset_popup(dlg, mw)
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
