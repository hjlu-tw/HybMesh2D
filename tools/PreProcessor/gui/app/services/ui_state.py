"""Persist and restore the window layout between sessions.

``QSettings`` was already used for the recent-files list, but nothing else: every
launch reset the window size and position, the Log Console dock, which stage was
open, and every collapsible section in every panel. An engineer who works with the
Boundary Layer section open and the log dock tall had to rebuild that view on every
start — the kind of small daily friction industrial tools do not have.

What is persisted, and why only this:

* **Window geometry** and **dock state** — Qt's own opaque blobs, which cover
  size/position/maximised plus the dock's size, visibility and floating state.
* **The active stage** (mode combo), so work resumes where it stopped.
* **Collapsible section expanded flags**, keyed by owning panel + section title.

Deliberately NOT persisted: anything that is *case data* rather than view state.
A restored layout must never change what would be meshed or solved.

Two safety rules:

* Everything lives under a ``LAYOUT_VERSION`` namespace. When the layout changes
  incompatibly, bump it: stale state is then ignored rather than restored into a
  window it no longer describes (a restored-but-wrong layout is worse than a
  default one, and users cannot easily reset it themselves).
* Headless platforms neither save nor restore. Tests and batch runs would
  otherwise overwrite the real user's saved layout with an offscreen one.
"""
from __future__ import annotations

from PyQt6.QtCore import QSettings

from app.services.logging_setup import get_logger

_log = get_logger(__name__)

ORGANISATION = "HybMesh"
APPLICATION = "PreProcessor"

# Bump when the window/panel layout changes in a way that makes previously saved
# state wrong (docks added or removed, panels reordered, sections restructured).
LAYOUT_VERSION = 1

_PREFIX = f"ui/v{LAYOUT_VERSION}"


def _settings() -> QSettings:
    return QSettings(ORGANISATION, APPLICATION)


def _headless() -> bool:
    from app.utils import is_headless
    return is_headless()


def _section_key(scope: str, title: str, suffix: str = "") -> str:
    return f"{_PREFIX}/sections/{scope}/{title}{suffix}"


def _sections(main_window):
    """Yield ``(key, section)`` for every collapsible section in the sidebar.

    Scoped by the owning sidebar page's class name, so two panels that both have
    an "Output" section keep separate state instead of sharing one flag.
    """
    from app.views.collapsible import CollapsibleSection

    stack = getattr(main_window, "sidebar_stack", None)
    if stack is None:
        return
    for i in range(stack.count()):
        page = stack.widget(i)
        if page is None:
            continue
        scope = type(page).__name__
        seen: dict[str, int] = {}
        for sec in page.findChildren(CollapsibleSection):
            title = getattr(sec, "title", "") or sec.toggle_btn.text().strip()
            # Two same-titled sections on one page get a stable ordinal suffix.
            n = seen.get(title, 0)
            seen[title] = n + 1
            suffix = "" if n == 0 else f"#{n}"
            yield _section_key(scope, title, suffix), sec


def save_section_states(scope: str, sections) -> None:
    """Persist the expanded flag of collapsible sections that do NOT live in the
    sidebar — a dialog's own accordion, which :func:`_sections` cannot reach
    (it walks ``sidebar_stack``). ``scope`` namespaces the keys, so pass a stable
    string (the dialog's class name). Never raises."""
    if _headless():
        return
    try:
        s = _settings()
        for sec in sections:
            title = getattr(sec, "title", "")
            if not title:
                continue
            s.setValue(_section_key(scope, title), bool(sec.is_expanded))
        s.sync()
    except Exception:
        _log.warning("could not save the %s section state", scope, exc_info=True)


def restore_section_states(scope: str, sections) -> None:
    """Apply the flags saved by :func:`save_section_states`. Sections never saved
    keep whatever default the caller built them with. Never raises."""
    if _headless():
        return
    try:
        s = _settings()
        for sec in sections:
            title = getattr(sec, "title", "")
            if not title:
                continue
            saved = s.value(_section_key(scope, title))
            if saved is None:
                continue                      # never saved -> keep the default
            want = saved if isinstance(saved, bool) else str(saved).lower() == "true"
            if want != sec.is_expanded:
                sec.expand() if want else sec.collapse()
    except Exception:
        _log.warning("could not restore the %s section state", scope, exc_info=True)


def save_ui_state(main_window) -> None:
    """Write the current layout to QSettings. Never raises."""
    if _headless():
        return
    try:
        s = _settings()
        s.setValue(f"{_PREFIX}/geometry", main_window.saveGeometry())
        s.setValue(f"{_PREFIX}/windowState", main_window.saveState())
        combo = getattr(main_window, "mode_combo", None)
        if combo is not None:
            s.setValue(f"{_PREFIX}/mode", int(combo.currentIndex()))
        for key, sec in _sections(main_window):
            s.setValue(key, bool(sec.is_expanded))
        s.sync()
    except Exception:
        # Layout persistence is a convenience; failing it must never affect exit.
        _log.warning("could not save the window layout", exc_info=True)


def restore_ui_state(main_window) -> None:
    """Apply the saved layout, if any. Never raises."""
    if _headless():
        return
    try:
        s = _settings()
        geom = s.value(f"{_PREFIX}/geometry")
        if geom is not None:
            main_window.restoreGeometry(geom)
        state = s.value(f"{_PREFIX}/windowState")
        if state is not None:
            main_window.restoreState(state)
        for key, sec in _sections(main_window):
            saved = s.value(key)
            if saved is None:
                continue                      # never saved -> keep the default
            want = saved if isinstance(saved, bool) else str(saved).lower() == "true"
            if want != sec.is_expanded:
                sec.expand() if want else sec.collapse()
    except Exception:
        _log.warning("could not restore the window layout", exc_info=True)


def restore_active_stage(main_window) -> None:
    """Re-select the stage that was open last.

    Separate from :func:`restore_ui_state` because it has to run *after* the
    controller has wired its mode signals and opened a session — switching stage
    triggers panel population, which needs a live controller behind it.
    """
    if _headless():
        return
    combo = getattr(main_window, "mode_combo", None)
    if combo is None:
        return
    try:
        idx = _settings().value(f"{_PREFIX}/mode")
        if idx is None:
            return
        idx = int(idx)
        if 0 <= idx < combo.count() and idx != combo.currentIndex():
            combo.setCurrentIndex(idx)
    except Exception:
        _log.warning("could not restore the active stage", exc_info=True)
