"""Modeless pop-up stacking: above the app's own main window, below other apps.

Split out of ``app/utils.py`` (which was over the file-size budget) — the
behaviour and the public names are unchanged, and ``app.utils`` re-exports
``keep_on_top`` / ``offset_popup`` so every existing call site still works.

Two things are load bearing here and both were shipped wrong once:

* The window LEVEL (see :func:`keep_on_top`) — ``Qt.Tool`` auto-hides on macOS,
  ``WindowStaysOnTopHint`` floats above other applications.
* WHEN the raise happens (see :func:`raise_later`) — a raise issued from inside
  the event that reorders the windows is undone by the platform when that event
  finishes.
"""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtWidgets import QWidget

# Marker written by keep_on_top(); _PopupRaiser lifts only the windows carrying
# it, so ordinary children (docks, the central widget) are left alone.
KEEP_ON_TOP_PROP = "_hybmesh_keep_on_top"
_RAISER_PROP = "_hybmesh_popup_raiser"
_SHOW_RAISER_PROP = "_hybmesh_popup_show_raiser"


def raise_later(widget: QWidget) -> None:
    """Raise ``widget`` on the NEXT event-loop turn, not now.

    Raising synchronously from inside the event that CHANGES the stacking does
    not stick on macOS: the platform finishes ordering the clicked/activated
    window front after the event is delivered, which puts it back over the
    pop-up. Both of the app's raises are issued from exactly such an event —
    the activation the raiser filters, and the canvas mouse press that opens a
    shape dialog (``curve_draw_ctrl._begin_pending_edit`` shows the Arc/Line/…
    editor while the press is still being handled, so the window that ends up
    on top is the main window, under which the brand-new dialog is buried).
    One turn later the ordering has settled and the raise holds.
    """
    def _do():
        try:
            if widget.isVisible():
                widget.raise_()
        except RuntimeError:
            # The pop-up was closed and deleted between the event and this turn
            # (modeless dialogs are deleteLater()'d on close) — nothing to lift.
            from app.services.logging_setup import get_logger
            get_logger(__name__).debug(
                "pop-up deleted before its deferred raise", exc_info=True)

    QTimer.singleShot(0, _do)


class _PopupRaiser(QObject):
    """Lift a window's ``keep_on_top`` pop-ups whenever that window is activated.

    This is the half of keep_on_top() that replaces the ``Qt.Tool`` window
    level: a normal-level pop-up CAN be buried by the main window when the user
    clicks it, so it is raised again on activation. Which pop-ups exist is read
    back from Qt's own child list each time rather than kept in a registry —
    modeless dialogs are ``deleteLater()``d on close, and a registry of C++
    objects that die behind Python's back is exactly the bookkeeping this avoids.
    """

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.WindowActivate:
            for child in obj.findChildren(
                    QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
                if (child.isWindow() and child.isVisible()
                        and child.property(KEEP_ON_TOP_PROP)):
                    raise_later(child)          # after the OS finishes ordering
        return False                       # never consume the activation


class _ShowRaiser(QObject):
    """Re-raise a pop-up one turn after it is shown.

    Call sites already do ``show(); raise_(); activateWindow()``, but that raise
    lands inside the mouse press that opened the dialog and is overridden when
    the press completes. Filtering the pop-up's own Show event covers every call
    site at once, including the ones that only call ``show()``.
    """

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show:
            raise_later(obj)
        return False


def _install_raiser(window: QWidget):
    """One _PopupRaiser per top-level window; parenting it there keeps it alive."""
    if window.property(_RAISER_PROP):
        return
    window.installEventFilter(_PopupRaiser(window))
    window.setProperty(_RAISER_PROP, True)


def _install_show_raiser(widget: QWidget):
    """One _ShowRaiser per pop-up (parented to it, so it dies with it)."""
    if widget.property(_SHOW_RAISER_PROP):
        return
    widget.installEventFilter(_ShowRaiser(widget))
    widget.setProperty(_SHOW_RAISER_PROP, True)


def keep_on_top(widget: QWidget) -> QWidget:
    """Keep a modeless pop-up above the app's OWN main window, without floating
    above other applications and without vanishing when the user switches to
    one. Call BEFORE show(). Returns the widget for chaining.

    Both of the obvious flags are wrong, each in its own direction:

    * ``WindowStaysOnTopHint`` floats the pop-up above EVERY application, even
      with HybMesh in the background — users found that intrusive.
    * ``Qt.Tool`` fixes that, but on macOS a Tool window is an NSPanel with
      ``hidesOnDeactivate``: clicking another app makes the pop-up DISAPPEAR
      while the main window stays visible (measured — ``isExposed()`` goes
      False), which users read as "my dialog is gone". Switching the auto-hide
      off is not a way out either: Qt6 ignores ``WA_MacAlwaysShowToolWindow``
      (the cocoa plugin reads the ``_q_macAlwaysShowToolWindow`` *window
      property*), and a Tool window sits at NSFloatingWindowLevel, so a panel
      that no longer auto-hides is back to floating over the other app.

    So the pop-up stays an ordinary normal-level window — visible while another
    app is in front, and coverable by it — and it is raised back above the main
    window on two occasions: when that window is activated (_PopupRaiser) and
    when the pop-up itself is shown (_ShowRaiser). Both raises are DEFERRED by
    one event-loop turn; see :func:`raise_later` for why a synchronous one is
    silently undone.

    Parenting to the TOP-LEVEL window is what makes this work: the raiser finds
    the pop-up in that window's child list, and a pop-up parented to a
    panel/canvas/sidebar would be hidden along with that panel when the
    selection changes (mirrors the explicit ``setParent(main_window, ...)``
    template in edge_props_dialogs_mixin)."""
    parent = widget.parentWidget()
    top = parent.window() if parent is not None else None
    if top is not None and top is not widget and parent is not top:
        # setParent clears the window flags; they are (re)applied just below.
        widget.setParent(top)
    flags = widget.windowFlags()
    flags &= ~Qt.WindowType.WindowStaysOnTopHint
    flags &= ~Qt.WindowType.WindowType_Mask          # drop Tool/Window type bits
    flags |= (Qt.WindowType.Dialog
              | Qt.WindowType.WindowTitleHint
              | Qt.WindowType.WindowCloseButtonHint
              | Qt.WindowType.WindowSystemMenuHint)
    widget.setWindowFlags(flags)
    widget.setProperty(KEEP_ON_TOP_PROP, True)
    _install_show_raiser(widget)
    host = top if top is not None else widget.parentWidget()
    if host is not None and host is not widget:
        _install_raiser(host)
    return widget


def offset_popup(widget: QWidget, ref: QWidget | None = None) -> QWidget:
    """Position a pop-up OFF the centre of its parent window so it does not sit
    on top of the object being edited (which is usually near the canvas centre).

    Call after the dialog's contents are built and just before show()/exec();
    moving the window also sets ``WA_Moved`` so Qt won't re-centre it on show.
    ``ref`` is the window to offset from (defaults to the widget's parent
    top-level window, else the primary screen)."""
    from PyQt6.QtGui import QGuiApplication
    ref_widget = ref
    if ref_widget is None:
        p = widget.parentWidget()
        ref_widget = p.window() if p is not None else None
    widget.adjustSize()
    w, h = widget.width(), widget.height()
    if (ref_widget is not None and ref_widget is not widget
            and ref_widget.isVisible()):
        base = ref_widget.frameGeometry()
    else:
        scr = QGuiApplication.primaryScreen()
        if scr is None:
            return widget
        base = scr.availableGeometry()
    # Offset toward the upper-right of the reference so the canvas centre/left
    # stays visible while the dialog is open.
    cx = base.center().x() + int(0.22 * base.width())
    cy = base.center().y() - int(0.18 * base.height())
    x, y = cx - w // 2, cy - h // 2
    # Clamp fully onto the screen the dialog lands on.
    scr = (ref_widget.screen() if ref_widget is not None
           else QGuiApplication.primaryScreen())
    if scr is not None:
        av = scr.availableGeometry()
        x = max(av.left(), min(x, av.right() - w))
        y = max(av.top(), min(y, av.bottom() - h))
    widget.move(x, y)
    return widget
