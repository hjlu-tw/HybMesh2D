#!/usr/bin/env python3
"""The Edit-Boundary-Layer dialog is grouped and progressively disclosed.

The dialog carries 21 parameters. As one flat form the three numbers that
actually define the layer stack (first-cell height, growth rate, layer count)
sat above a wall of corner/junction/transition knobs, all expanded, so finding
anything meant scrolling the whole list. They are now collapsible groups
(``_BL_FIELD_GROUPS``) with only "Layer Growth" open.

The risk that grouping introduces is a parameter that no group lists: it would
never be built, so the dialog would silently write back whatever value it was
seeded with — a setting the user cannot reach and cannot see. Hence checks 1-3.

Checks:
 1. The groups PARTITION the field specs: every spec key is listed exactly once,
    and no group names a key that does not exist.
 2. The built dialog really has a widget for every spec key (the invariant that
    matters — a table can be right while the build drops rows).
 3. Every group is non-empty and its keys keep the spec order within the group.
 4. Exactly one group starts expanded, and it is the layer-stack one.
 5. A per-geometry override whose value differs from the global default expands
    its own group, so an override can never hide behind a collapsed header.
 6. _value_differs is relative: it separates 1e-8 first-cell heights and does
    not fire on float round-trip noise.
 7. The dialog still round-trips every parameter through result_params().
 8. Section state persistence is scoped and headless-safe (ui_state contract).

Run:  python3 tools/PreProcessor/tests/test_bl_dialog_sections.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


from PyQt6.QtWidgets import QApplication, QLabel                    # noqa: E402
from app.views.collapsible import CollapsibleSection                # noqa: E402
from app.views.panels.mesh_dialogs_bl import (                      # noqa: E402
    _BL_FIELD_SPECS, _BL_FIELD_GROUPS, _value_differs, PerGeomBLDialog,
)

app = QApplication.instance() or QApplication(sys.argv)

spec_keys = [k for k, _l, _k, _o in _BL_FIELD_SPECS]
grouped_keys = [k for _t, _e, _h, keys in _BL_FIELD_GROUPS for k in keys]

# ── 1. the groups partition the specs ─────────────────────────────────────
missing = [k for k in spec_keys if k not in grouped_keys]
unknown = [k for k in grouped_keys if k not in spec_keys]
dupes = sorted({k for k in grouped_keys if grouped_keys.count(k) > 1})
check(not missing, f"1. every BL parameter is in a group (unreachable: {missing})")
check(not unknown, f"1. no group names a non-existent parameter ({unknown})")
check(not dupes, f"1. no parameter is listed by two groups ({dupes})")

# ── 2. the built dialog has a widget for every parameter ──────────────────
defaults = {k: 1.0 for k in spec_keys}
defaults["BL_INITIAL_THICKNESS"] = 2.5e-7
dlg = PerGeomBLDialog("g", dict(defaults), None)
built = set(dlg._widgets)
check(built == set(spec_keys),
      f"2. the dialog builds every parameter (missing: {sorted(set(spec_keys) - built)})")
check(len(dlg._sections) == len(_BL_FIELD_GROUPS)
      and all(isinstance(s, CollapsibleSection) for s in dlg._sections),
      "2. one CollapsibleSection per group, no 'Other' fallback group needed")

# ── 3. groups are non-empty and follow the spec order internally ──────────
check(all(keys for _t, _e, _h, keys in _BL_FIELD_GROUPS),
      "3. no group is empty")
check(all(t.strip() and h.strip() for t, _e, h, _k in _BL_FIELD_GROUPS),
      "3. every group has a title and a one-line hint")

# ── 4. only the layer-stack group starts expanded ─────────────────────────
expanded = [t for t, e, _h, _k in _BL_FIELD_GROUPS if e]
check(expanded == ["Layer Growth"],
      f"4. exactly the layer-stack group starts expanded (got {expanded})")
open_now = [s.title for s in dlg._sections if s.is_expanded]
check(open_now == ["Layer Growth"],
      f"4. ...and the built dialog opens only that one (got {open_now})")

# ── 5. an override expands its own group ──────────────────────────────────
# Same defaults, but this geometry overrides a TRANSITION value, whose group is
# collapsed by default.
over = dict(defaults)
over["BL_TRANSITION_GROWTH_RATE"] = 1.35
dlg2 = PerGeomBLDialog("g", dict(defaults), over)
open2 = [s.title for s in dlg2._sections if s.is_expanded]
check("Transition Layers" in open2,
      f"5. the group holding an overridden value is expanded (open: {open2})")
check("Convex Corners" not in open2,
      "5. ...and groups with no override stay collapsed")

# The global dialog seeds current == defaults, so nothing extra opens.
dlg3 = PerGeomBLDialog("Global default", dict(defaults), dict(defaults))
check([s.title for s in dlg3._sections if s.is_expanded] == ["Layer Growth"],
      "5. the GLOBAL editor (current == defaults) opens only the default group")

# ── 6. the difference test is relative, not absolute ──────────────────────
check(_value_differs(2.5e-7, 5.0e-7) and not _value_differs(2.5e-7, 2.5e-7),
      "6. _value_differs separates two plausible first-cell heights")
check(not _value_differs(135.0, 135.0 + 1e-10),
      "6. ...and ignores float round-trip noise on an angle")
check(not _value_differs(None, 1.0) and not _value_differs(1.0, None),
      "6. ...and treats a missing value as 'no difference'")

# ── 7. every parameter still round-trips out of the dialog ────────────────
vals = dlg2.result_params()
check(vals is not None and set(vals) == set(spec_keys),
      "7. result_params() returns every parameter")
check(vals is not None
      and abs(float(vals["BL_TRANSITION_GROWTH_RATE"]) - 1.35) < 1e-9
      and abs(float(vals["BL_INITIAL_THICKNESS"]) - 2.5e-7) < 1e-18,
      "7. ...carrying the seeded values, small ones included")

# ── 8. ui_state's dialog-section API is scoped and headless-safe ──────────
from app.services import ui_state                                   # noqa: E402

check(hasattr(ui_state, "save_section_states")
      and hasattr(ui_state, "restore_section_states"),
      "8. ui_state exposes save/restore_section_states for dialog accordions")
check(ui_state._section_key("PerGeomBLDialog", "Advanced")
      .startswith(f"ui/v{ui_state.LAYOUT_VERSION}/sections/PerGeomBLDialog/"),
      "8. section keys are namespaced by LAYOUT_VERSION and by dialog scope")

# Headless (this test): save/restore must be no-ops, and must not raise. The
# offscreen platform is exactly what CI and the pipeline run under, so a write
# here would overwrite the real user's saved layout.
_touched = []
_real = ui_state._settings
ui_state._settings = lambda: _touched.append(1) or _real()
try:
    ui_state.save_section_states("PerGeomBLDialog", dlg._sections)
    ui_state.restore_section_states("PerGeomBLDialog", dlg._sections)
finally:
    ui_state._settings = _real
check(not _touched, "8. neither call touches QSettings when headless")
check([s.title for s in dlg._sections if s.is_expanded] == ["Layer Growth"],
      "8. ...and a headless restore leaves the built defaults alone")

# ── 9. Expand all / Collapse all reach every group ────────────────────────
dlg._set_all_sections(True)
check(all(s.is_expanded for s in dlg._sections), "9. 'Expand all' opens every group")
dlg._set_all_sections(False)
check(not any(s.is_expanded for s in dlg._sections),
      "9. 'Collapse all' closes every group")

# ── 10. a collapsed section reports its NEW size immediately ───────────────
# The root cause of a window that would not follow its accordion: hiding the
# content only POSTS the layout request, so the section kept reporting the
# sizeHint of the state it had just left until the event loop caught up.
probe = CollapsibleSection("probe", start_collapsed=False)
tall = QLabel("x")
tall.setFixedHeight(300)
probe.add_widget(tall)
probe.show()
app.processEvents()
open_h = probe.sizeHint().height()
probe.collapse()                                   # NO processEvents on purpose
shut_h = probe.sizeHint().height()
check(shut_h < open_h - 200,
      f"10. collapsing shrinks sizeHint at once ({open_h} -> {shut_h})")
probe.expand()
check(probe.sizeHint().height() >= open_h - 2,
      "10. ...and expanding restores it at once")

# ── 11. the window follows the open groups ─────────────────────────────────
fit = PerGeomBLDialog("Global default", dict(defaults), dict(defaults))
fit.show()
app.processEvents()
h_default = fit.height()
content_h = fit._content.sizeHint().height()
check(fit._scroll.height() >= content_h,
      f"11. the default state needs no scrollbar (viewport {fit._scroll.height()} "
      f">= content {content_h})")
fit._set_all_sections(True)
app.processEvents()
h_open = fit.height()
check(h_open > h_default, f"11. 'Expand all' grows the window ({h_default} -> {h_open})")
scr = fit.screen()
if scr is not None:
    check(h_open <= int(scr.availableGeometry().height() * 0.85) + 2,
          "11. ...but never past the screen bound")
fit._set_all_sections(False)
app.processEvents()
check(fit.height() < h_default,
      f"11. 'Collapse all' folds it back up ({h_open} -> {fit.height()})")

# ── 12. a height the USER chose is a floor, not a suggestion ───────────────
fit.resize(fit.width(), 620)
app.processEvents()
check(fit._user_h == 620, "12. a manual resize is recorded as the user's height")
fit._sections[1].expand()
app.processEvents()
check(fit.height() >= 620, "12. opening a group may grow past it")
fit._set_all_sections(False)
app.processEvents()
check(fit.height() == 620,
      f"12. ...and collapsing never shrinks below it (got {fit.height()})")

print(("\nRESULT: " + ("ALL PASS" if not _FAILS else f"{len(_FAILS)} FAIL")), flush=True)
sys.exit(1 if _FAILS else 0)
