#!/usr/bin/env python3
"""The Edit-Boundary-Layer dialog is grouped and progressively disclosed.

The dialog carries 21 parameters. As one flat form the three numbers that
actually define the layer stack (first-cell height, growth rate, layer count)
sat above a wall of corner/junction/transition knobs, all expanded, so finding
anything meant scrolling the whole list. They are now collapsible groups
(``_BL_FIELD_GROUPS``), and USER-REQUESTED, all of them start CLOSED: the dialog
opens as a short list of headers and the window is only as tall as what you
opened. A group is still opened by the state you left it in, or by holding a
per-geometry override — that second one is a safety property (an override must
not hide behind a collapsed header), not a default.

The risk that grouping introduces is a parameter that no group lists: it would
never be built, so the dialog would silently write back whatever value it was
seeded with — a setting the user cannot reach and cannot see. Hence checks 1-3.

Checks:
 1. The groups PARTITION the field specs: every spec key is listed exactly once,
    and no group names a key that does not exist.
 2. The built dialog really has a widget for every spec key (the invariant that
    matters — a table can be right while the build drops rows).
 3. Every group is non-empty and its keys keep the spec order within the group.
 4. NO group starts expanded, and a dialog without overrides opens collapsed.
 5. A per-geometry override whose value differs from the global default expands
    its own group, so an override can never hide behind a collapsed header.
 6. _value_differs is relative: it separates 1e-8 first-cell heights and does
    not fire on float round-trip noise.
 7. The dialog still round-trips every parameter through result_params().
 8. Section state persistence is scoped and headless-safe (ui_state contract).

Checks 13-14 are the OTHER half of a greyed-out field: the lock and its reason.
BL_JUNCTION_ANGLE_C1 is dead under the default junction scheme and is disabled for
it (13), and USER-REPORTED (issue #23) that a silent lock reads as a bug — so the row
must also SAY why, on screen, with no hover (14). 14 binds the two in both directions
and proves the binding is not vacuous by breaking the real wiring.

Run:  python3 tools/PreProcessor/tests/test_bl_dialog_sections.py
"""
import ast
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
from app.utils import HelpButton, help_label                         # noqa: E402
from app.views.collapsible import CollapsibleSection                # noqa: E402
from app.views.panels.mesh_bl_dialog_layout import (                 # noqa: E402
    BLDialogLayoutMixin,
)
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

# ── 4. nothing starts expanded ─────────────────────────────────────────────
# USER-REQUESTED: the dialog opens as a short list of headers, so the window is only as
# tall as what the user asked to see. Anything that opens a group from here on is either
# the user's own remembered choice or the override rule in check 5 — never a default.
expanded = [t for t, e, _h, _k in _BL_FIELD_GROUPS if e]
check(expanded == [],
      f"4. no group starts expanded (got {expanded})")
open_now = [s.title for s in dlg._sections if s.is_expanded]
check(open_now == [],
      f"4. ...and a dialog with no overrides opens fully collapsed (got {open_now})")

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

# The global dialog seeds current == defaults, so nothing differs and nothing opens.
dlg3 = PerGeomBLDialog("Global default", dict(defaults), dict(defaults))
check([s.title for s in dlg3._sections if s.is_expanded] == [],
      "5. the GLOBAL editor (current == defaults) opens fully collapsed")
check(len(open2) == 1,
      f"5. ...while the override case opens exactly the group that holds it, not the "
      f"whole dialog ({open2})")

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
check([s.title for s in dlg._sections if s.is_expanded] == [],
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
check(fit.height() < h_open and abs(fit.height() - h_default) <= 2,
      f"11. 'Collapse all' folds it back to the height it opened at — with every group "
      f"closed by default that IS the fully-collapsed height, so the window must return "
      f"to it exactly rather than merely shrink ({h_default} -> {h_open} -> "
      f"{fit.height()})")

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

# ── 13. a parameter the selected scheme cannot read is not editable ────────
# BL_JUNCTION_ANGLE_C1 binned the old junction scheme. Method 1 — the default — decides
# its slide by a hard-coded 95 deg (below ~90 a perpendicular cap provably leaves the
# domain), so C1 has no effect there: editing it changed a number, was written back on
# OK, round-tripped through the config, and never changed a mesh. The explanation existed
# only on the mesh panel's HIDDEN backing widgets, i.e. not where it is edited.
spec_tips = {k: o.get("tip", "") for k, _lbl, _kind, o in _BL_FIELD_SPECS}
check("Method 0" in spec_tips.get("BL_JUNCTION_ANGLE_C1", ""),
      "13. the C1 field carries its own explanation, in the dialog the user edits")

jd = PerGeomBLDialog("Global default", dict(defaults), dict(defaults))
m_w, m_kind = jd._widgets["BL_JUNCTION_METHOD"]
c1_w = jd._widgets["BL_JUNCTION_ANGLE_C1"][0]
c2_w = jd._widgets["BL_JUNCTION_ANGLE_C2"][0]
jd._set_widget_value(m_w, m_kind, 1)
app.processEvents()
check(not c1_w.isEnabled(),
      "13. with the default 4-case scheme selected, C1 is greyed out rather than "
      "offering an adjustment it cannot make")
check(c2_w.isEnabled(),
      "13. ...while C2, which that scheme DOES read, stays editable")
jd._set_widget_value(m_w, m_kind, 0)
app.processEvents()
check(c1_w.isEnabled(),
      "13. and it comes back for Taper-to-zero, which is the scheme that reads it")
check("BL_JUNCTION_ANGLE_C1" in (jd.result_params() or {}),
      "13. a disabled field is still written back, so the value round-trips through "
      "the config instead of being lost on OK")

# ── 14. the lock and its REASON are one decision ──────────────────────────
# USER-REPORTED (issue #23): the greying is correct, its silence was the defect. On
# screen a field disabled with no explanation is indistinguishable from a field
# disabled for another reason, or from a bug — which is what it was reported as. And
# the disabled widget's own tooltip is not a fallback: MEASURED on this Qt, hovering an
# enabled spin box delivers Enter to it while hovering a disabled one delivers nothing
# to it OR to its parent, because Qt picks the mouse receiver by walking past disabled
# widgets. So the reason has to be VISIBLE in the row.
C1 = "BL_JUNCTION_ANGLE_C1"


def c1_bound(d) -> bool:
    """C1 disabled <=> a non-empty reason showing in its own row. Both directions:
    a lock with no reason is the reported bug, and a reason beside a live field is a
    form describing a method it is not on."""
    return (not d._widgets[C1][0].isEnabled()) == bool(d.field_note(C1))


bd = PerGeomBLDialog("Global default", dict(defaults), dict(defaults))
m_w, m_kind = bd._widgets["BL_JUNCTION_METHOD"]
seen = []
for meth in (1, 0, 1, 0):          # repeatedly, in both directions
    bd._set_widget_value(m_w, m_kind, meth)
    app.processEvents()
    seen.append((meth, bd._widgets[C1][0].isEnabled(), bd.field_note(C1), c1_bound(bd)))
check(all(ok for _m, _e, _n, ok in seen),
      f"14. C1 disabled <=> a reason is visible in its row, on every toggle ({seen})")
check([n for m, _e, n, _ok in seen if m == 1] and all(
          n for m, _e, n, _ok in seen if m == 1),
      "14. ...the default 4-case scheme leaves a non-empty reason on screen")
check(all(not n for m, _e, n, _ok in seen if m == 0),
      "14. ...and Taper-to-zero, which reads C1, leaves none")
check("method 0" in seen[0][2].lower(),
      f"14. the reason names the scheme that does read it (got {seen[0][2]!r})")

# The reason is the SHORT pointer; the prose stays the spec's single declaration and
# still reaches the '?' together with the .dat KEY.
c1_tips = [hb._tooltip_text for hb in bd.findChildren(HelpButton)
           if C1 in hb._tooltip_text]
check(len(c1_tips) == 1 and "Method 0" in c1_tips[0] and f"({C1})" in c1_tips[0],
      "14. the long form still reaches the '?' with its .dat KEY")
# Read from the method-1 state captured above, not from bd's CURRENT state: the loop
# above left it on method 0, where the marker is empty and any length bound passes.
check(0 < len(seen[0][2]) < 30,
      f"14. ...and the row marker stays a short pointer, not a copy of it "
      f"({len(seen[0][2])} chars)")

# INJECTION: break the real wiring — disable the field without saying why, exactly as
# it shipped before this issue — and check 14 must fail. Without this the binding
# could hold because nothing ever disables C1.
_real_wire = BLDialogLayoutMixin._wire_method_dependent_fields


def _wire_silently(self):
    """The pre-issue-#23 body: greys the field, explains nothing."""
    m = self._widgets.get("BL_JUNCTION_METHOD")
    c1 = self._widgets.get(C1)
    if not m or not c1:
        return

    def _s(*_a):
        c1[0].setEnabled(self._widget_value(m[0], m[1]) == 0)

    m[0].currentIndexChanged.connect(_s)
    _s()


PerGeomBLDialog._wire_method_dependent_fields = _wire_silently
try:
    broken = PerGeomBLDialog("Global default", dict(defaults), dict(defaults))
    bm, bk = broken._widgets["BL_JUNCTION_METHOD"]
    broken._set_widget_value(bm, bk, 1)
    app.processEvents()
    silent = (not broken._widgets[C1][0].isEnabled()) and not broken.field_note(C1)
finally:
    del PerGeomBLDialog._wire_method_dependent_fields
check(BLDialogLayoutMixin._wire_method_dependent_fields is _real_wire,
      "14. (injection restored the real wiring)")
check(silent and not c1_bound(broken),
      "14. INJECTION: wiring that disables C1 without a reason fails this check")

# The other direction: a reason beside a field the scheme DOES read must fail too, so
# the marker cannot simply be left on permanently.
stuck = PerGeomBLDialog("Global default", dict(defaults), dict(defaults))
sm, sk = stuck._widgets["BL_JUNCTION_METHOD"]
stuck._set_widget_value(sm, sk, 0)
app.processEvents()
stuck._notes[C1].setText("method 0 only")
check(not c1_bound(stuck),
      "14. INJECTION: a reason left showing beside an ENABLED C1 fails it as well")

# The label column is MEASURED from the labels built (bounded 120..240), so the reason
# rides beside the FIELD: suffixing the label measures 240 against today's 171 and
# would shove every label right. Labels are right-aligned in a fixed-width cell, so a
# clip eats the FIRST characters — check every one of them, widest included.
wide = PerGeomBLDialog("Global default", dict(defaults), dict(defaults))
wide._set_all_sections(True)
wide.show()
app.processEvents()
app.processEvents()
cells = [hb.parentWidget() for hb in wide.findChildren(HelpButton)]
widths = {c.width() for c in cells}
# Recomputed from the LABELS ALONE, the way the build measures them: the invariant is
# that the note fed no measurement, not that the answer is any particular number of
# pixels. A literal here would be a macOS font metric asserted on an Ubuntu CI runner
# — a gate that goes red for the platform rather than for the code.
label_only = max(help_label(lbl + ":", "t").sizeHint().width()
                 for _k, lbl, _kind, _o in _BL_FIELD_SPECS)
want_w = min(max(label_only, 120), 240)
check(len(cells) == len(spec_keys) and widths == {want_w},
      f"14. the label column is what the LABELS measure ({want_w} px), i.e. the row "
      f"note fed nothing into it (got {widths})")
check(120 <= want_w <= 240,
      f"14. ...and that measurement is still inside its declared bound ({want_w})")
# The number that LICENSES the field cell rather than the spec's first choice (a
# suffix on the label): the suffixed composite must really reach the 240 clamp, or
# the label was the right place after all and this row should go back to it.
suffixed = help_label("Junction \u03b8 C1 (deg) \u2014 method 0 only:", "t")
check(suffixed.sizeHint().width() >= 240 > want_w,
      f"14. ...and suffixing the LABEL instead would push the column from {want_w} to "
      f"its 240 ceiling ({suffixed.sizeHint().width()}), which is why the reason rides "
      f"beside the field")
# Every text label in a row, the NOTE included: it is right-aligned in a fixed cell,
# so a clip eats the first characters rather than the last.
texts = [t for c in cells for t in c.findChildren(QLabel)[:1]]
texts += [n for n in wide._notes.values() if n.text()]
clipped = [(t.text(), t.width(), t.sizeHint().width())
           for t in texts if t.width() < t.sizeHint().width()]
check(not clipped, f"14. ...and nothing clips its own text, note included ({clipped})")
check(wide._widgets[C1][0].width() == wide._widgets["BL_JUNCTION_ANGLE_C2"][0].width(),
      "14. ...and the note cell leaves C1's box the same width as C2's beside it")

# The note cell is the ONE composite field cell in the GUI, against CLAUDE.md's
# "never wrapped" rule. What that rule protects is labelForField, so pin its
# precondition: nothing may resolve a label on this dialog's forms. Without this the
# exemption is a comment, and a visibility helper added here would silently find no
# label instead of failing the build.
# Every class actually mixed into the dialog, read off its own MRO rather than from
# two hand-named files: a visibility helper added in a THIRD mixin would evade a
# hand-written list, and the list would go stale exactly when the class grew a base.
_own = {sys.modules[c.__module__].__file__ for c in PerGeomBLDialog.__mro__
        if c.__module__.startswith("app.")}
# A CALL, not the word: the docstring that records this exemption names the method,
# and a substring check would fire on the prose explaining itself.
_calls = [(os.path.basename(f), n.lineno) for f in sorted(_own)
          for n in ast.walk(ast.parse(open(f).read()))
          if isinstance(n, ast.Attribute) and n.attr == "labelForField"]
check(len(_own) >= 2 and not _calls,
      f"14. nothing in the dialog's own {len(_own)} mixin(s) resolves a label on its "
      f"forms ({_calls}), which is the precondition the wrapped C1 field cell needs")

print(("\nRESULT: " + ("ALL PASS" if not _FAILS else f"{len(_FAILS)} FAIL")), flush=True)
sys.exit(1 if _FAILS else 0)
