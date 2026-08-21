"""Persist and restore the window layout between sessions.

``QSettings`` was already used for the recent-files list, but nothing else: every
launch reset the window size and position and the Log Console dock. An engineer
who works with the log dock tall and the window on the second monitor had to
rebuild that on every start — the kind of small daily friction industrial tools
do not have.

What is persisted, and why only this:

* **Window geometry** and **dock state** — Qt's own opaque blobs, which cover
  size/position/maximised plus the dock's size, visibility and floating state.

Deliberately NOT persisted, and this is the interesting half:

* **The active stage** (mode combo) and **every sidebar collapsible section's
  expanded flag**. Both *were* saved and restored here, on the same
  resume-where-you-stopped argument as the geometry. The user weighed that and
  reversed it (issue #27): a launch must land on one known state — the **CAD**
  stage, with **every** sidebar section collapsed — because an unpredictable
  stage and an arbitrary set of open sections cost more than the view they
  saved, and nothing offered a way to reset them. The convenience removed was
  real; it was the user's call. Do not reinstate either as a bug fix: the CAD
  default now comes from ``mode_combo``'s own index 0 and the collapsed default
  from ``CollapsibleSection(start_collapsed=True)``, and
  ``tests/test_ui_state_and_dialogs.py`` fails if a launch stops landing there.
* Anything that is *case data* rather than view state. A restored layout must
  never change what would be meshed or solved.

A **dialog's own** accordion is a different feature and is still persisted, by
:func:`save_section_states` / :func:`restore_section_states` under an explicit
scope — the Edit-BL dialog opens all-closed and reopens what the user left it in,
which is itself user-requested. Those two never walked the sidebar, so the code
path above is not theirs. Their *stored* state is not exempt from the version
bump, though: :func:`_section_key` is built from ``_PREFIX``, so v2 orphans a
dialog's saved flags exactly as it orphans the geometry — see the note on
``LAYOUT_VERSION`` below.

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
#
# v2 was requested as part of issue #27, and what it orphans is EVERYTHING under
# v1 — not only the stage and sidebar-section keys this module stopped writing
# (which the deleted readers had already made unreachable), but also every user's
# saved geometry, dock state and dialog-accordion flags, because those share the
# prefix. That one-time loss is the accepted cost of keeping the namespace honest:
# nothing under v1 is read again, so a v1 key can never be a live value in some
# later session that nothing wrote.
LAYOUT_VERSION = 2

_PREFIX = f"ui/v{LAYOUT_VERSION}"


def _settings() -> QSettings:
    return QSettings(ORGANISATION, APPLICATION)


def _headless() -> bool:
    from app.utils import is_headless
    return is_headless()


def _section_key(scope: str, title: str) -> str:
    return f"{_PREFIX}/sections/{scope}/{title}"


def save_section_states(scope: str, sections) -> None:
    """Persist the expanded flag of a **dialog's** own collapsible accordion.
    Sidebar sections are deliberately not persisted at all (see the module
    docstring), so this is the only section state there is. ``scope`` namespaces
    the keys, so pass a stable string (the dialog's class name). Never raises."""
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
    """Write the current window furniture to QSettings. Never raises."""
    if _headless():
        return
    try:
        s = _settings()
        s.setValue(f"{_PREFIX}/geometry", main_window.saveGeometry())
        s.setValue(f"{_PREFIX}/windowState", main_window.saveState())
        s.sync()
    except Exception:
        # Layout persistence is a convenience; failing it must never affect exit.
        _log.warning("could not save the window layout", exc_info=True)


def restore_ui_state(main_window) -> None:
    """Apply the saved window furniture, if any. Never raises."""
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
    except Exception:
        _log.warning("could not restore the window layout", exc_info=True)
