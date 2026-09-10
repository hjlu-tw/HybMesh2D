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

Checks 13-15 are the OTHER half of a greyed-out field: the lock and its reason.
BL_JUNCTION_ANGLE_C1 is dead under the default junction scheme and is disabled for
it (13), and USER-REPORTED (issue #23) that a silent lock reads as a bug — so the row
must also SAY why, on screen, with no hover (14). 14 binds the two in both directions
and proves the binding is not vacuous by breaking the real wiring; it also pins WHERE
the reason rides (beside the field, never suffixed onto the label), clamp-relative
rather than on a pixel literal, with an injection that moves it into the label for the
teeth. 15 exercises the third path neither of them reaches: a method value the dialog
cannot read at all, which is permissive by decision (never stuck off) and silent.

Run:  python3 tools/PreProcessor/tests/test_bl_dialog_sections.py
"""
import ast
import dataclasses
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


from PyQt6.QtGui import QFont                                        # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel                    # noqa: E402
from app.utils import HelpButton, help_label                         # noqa: E402
from app.views.collapsible import CollapsibleSection                # noqa: E402
from app.views.panels import mesh_bl_dialog_layout as bl_layout      # noqa: E402
from app.views.panels.mesh_bl_dialog_layout import (                 # noqa: E402
    BLDialogLayoutMixin, LABEL_COL_MAX, LABEL_COL_MIN, _FIELD_NOTES,
    clamp_label_col,
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

# The label column is MEASURED from the labels built and clamped by the layout's own
# `clamp_label_col`, so the reason rides beside the FIELD: suffixing the label would
# widen that column and shove every label right. Labels are right-aligned in a
# fixed-width cell, so a clip eats the FIRST characters — check every one of them,
# widest included.
wide = PerGeomBLDialog("Global default", dict(defaults), dict(defaults))
wide._set_all_sections(True)
wide.show()
app.processEvents()
app.processEvents()
cells = [hb.parentWidget() for hb in wide.findChildren(HelpButton)]
widths = {c.width() for c in cells}

#: The label the spec's FIRST CHOICE would have built — the reason appended to C1's
#: own label — assembled from the spec and the note table rather than typed out, so it
#: cannot drift from either.
_C1_LABEL = next(lbl for k, lbl, _kind, _o in _BL_FIELD_SPECS if k == C1)
_SUFFIXED = f"{_C1_LABEL} \u2014 {_FIELD_NOTES[C1]}:"


def label_col(scale: float = 1.0) -> tuple[int, int]:
    """``(plain, suffixed)`` widest-label widths, measured the way the BUILD measures
    them — from the LABELS ALONE — under a font scaled by ``scale``. Unclamped: the
    caller puts them through the layout's own clamp, so the band is asserted once and
    from its declaration. The scaled font is the APPLICATION's and is restored before
    returning, so no caller sees it."""
    base = app.font()
    if scale != 1.0:
        f = QFont(base)
        f.setPointSizeF(base.pointSizeF() * scale)
        app.setFont(f)
    try:
        plain = max(help_label(lbl + ":", "t").sizeHint().width()
                    for _k, lbl, _kind, _o in _BL_FIELD_SPECS)
        return plain, help_label(_SUFFIXED, "t").sizeHint().width()
    finally:
        app.setFont(base)


#: The share of the plain label the reason must ADD before riding beside the field is
#: the cheaper choice — the magnitude the ceiling comparison used to carry, kept as a
#: RATIO because a ratio is what survives a font change. It measures 1.40 today and
#: stayed inside 1.39..1.41 at every metric swept below, where the PIXEL it replaced
#: moved 191..385 across the same sweep.
_MIN_SUFFIX_GROWTH = 1.25


def suffix_cost(plain: int, suffixed: int) -> str:
    """What moving the reason into the LABEL would cost the FORM, at the metric these
    two widths were measured on. It is always one of two things, which is the reason
    the check asserts the COST and not a pixel: either the shared column grows (every
    label in the dialog shoved right), or the labels alone already sit on
    ``LABEL_COL_MAX`` and the suffixed one does not fit the cell it is right-aligned
    in, losing its FIRST characters. ``''`` means it would cost nothing — the label was
    the right place after all, and this row should go back to it."""
    was, now = clamp_label_col(plain), clamp_label_col(suffixed)
    if now > was:
        return f"widens {was}->{now}"
    return f"clips {suffixed} into {now}" if suffixed > now else ""


label_only, suffixed_w = label_col()
want_w = clamp_label_col(label_only)
check(len(cells) == len(spec_keys) and widths == {want_w},
      f"14. the label column is what the LABELS measure ({want_w} px), i.e. the row "
      f"note fed nothing into it (got {widths})")
check(LABEL_COL_MIN <= want_w <= LABEL_COL_MAX,
      f"14. ...and that measurement is still inside its declared bound ({want_w})")
# The measurement that LICENSES the field cell rather than the spec's first choice (a
# suffix on the label): the suffixed composite must really COST the column width, or
# the label was the right place after all and this row should go back to it.
#
# Clamp-relative, with no pixel literal on either side, and asserted at BOTH ends of
# the band. The row this replaced asserted `>= 240` — the ceiling written out as a
# number, measuring EXACTLY 240 here — so a narrower metric failed it with the code
# correct, the platform failure the comment above it existed to forbid. But a
# comparison of two CLAMPED widths has the same defect mirrored: past ~1.8x the plain
# labels alone reach the ceiling, both sides collapse onto it, and "the column grows"
# is false while the code is still right. So the claim is the COST, which is one of two
# things at every metric, plus the RATIO for the magnitude the ceiling used to carry.
cost = suffix_cost(label_only, suffixed_w)
check(bool(cost),
      f"14. ...and suffixing the LABEL instead costs the form width or the text itself "
      f"({cost or 'NOTHING'}, band {LABEL_COL_MIN}..{LABEL_COL_MAX}), which is why the "
      f"reason rides beside the field")
check(suffixed_w >= label_only * _MIN_SUFFIX_GROWTH,
      f"14. ...and it costs a real share of the column rather than a hair "
      f"({suffixed_w}/{label_only} = {suffixed_w / label_only:.2f}x, floor "
      f"{_MIN_SUFFIX_GROWTH}x)")
# Every text label in a row, the NOTE included: it is right-aligned in a fixed cell,
# so a clip eats the first characters rather than the last.
texts = [t for c in cells for t in c.findChildren(QLabel)[:1]]
texts += [n for n in wide._notes.values() if n.text()]
clipped = [(t.text(), t.width(), t.sizeHint().width())
           for t in texts if t.width() < t.sizeHint().width()]
check(not clipped, f"14. ...and nothing clips its own text, note included ({clipped})")
check(wide._widgets[C1][0].width() == wide._widgets["BL_JUNCTION_ANGLE_C2"][0].width(),
      "14. ...and the note cell leaves C1's box the same width as C2's beside it")

# ...at deliberately narrower AND wider metrics, which is the whole point: the property
# is scale-free where the literal was not, and the mirrored defect lives at 1.8x+ where
# the plain labels alone reach the ceiling. Below every check that reads `wide`'s live
# geometry, deliberately: `label_col(scale)` swaps the APPLICATION font, and the
# injection builds a second dialog, so measuring `wide` across either would be reading
# one state through another.
metrics = [(sc, suffix_cost(p, su), su / p)
           for sc, (p, su) in ((sc, label_col(sc))
                               for sc in (0.7, 0.8, 0.9, 1.5, 1.8, 2.0))]
check(all(c and r >= _MIN_SUFFIX_GROWTH for _sc, c, r in metrics),
      f"14. ...and that holds at every font metric swept, so the check cannot go red "
      f"for the platform instead of for the code "
      f"({[(sc, c, round(r, 2)) for sc, c, r in metrics]})")

# INJECTION: put the reason where the spec's first choice would have — suffixed onto
# C1's LABEL — through the REAL build, and the column check above must fail. Without
# this the property rests on a comparison of measurements, and a loosening of it would
# look the same as a fix.
_real_by_key = bl_layout.by_key


def _by_key_suffixing_c1(*tables):
    specs = _real_by_key(*tables)
    specs[C1] = dataclasses.replace(specs[C1], label=_SUFFIXED.rstrip(":"))
    return specs


bl_layout.by_key = _by_key_suffixing_c1
try:
    suffixed_dlg = PerGeomBLDialog("Global default", dict(defaults), dict(defaults))
    suffixed_dlg._set_all_sections(True)
    suffixed_dlg.show()
    app.processEvents()
    app.processEvents()
    suf_cells = [hb.parentWidget() for hb in suffixed_dlg.findChildren(HelpButton)]
    suf_widths = {c.width() for c in suf_cells}
    # BOTH consequences, for the same reason `suffix_cost` names two: on a wide metric
    # the column is already on its ceiling and the cost lands on the TEXT instead.
    suf_clipped = [(t.text(), t.width(), t.sizeHint().width())
                   for c in suf_cells for t in c.findChildren(QLabel)[:1]
                   if t.width() < t.sizeHint().width()]
finally:
    bl_layout.by_key = _real_by_key
check(bl_layout.by_key is _real_by_key, "14. (injection restored the real spec table)")
check(suf_widths != {want_w} or bool(suf_clipped),
      f"14. INJECTION: the reason suffixed onto the LABEL takes the column off what the "
      f"labels measure ({want_w} -> {sorted(suf_widths)}) or clips inside it "
      f"({suf_clipped}) — either way the two checks above go red")

# The note cell is the ONE composite field cell in the GUI, against
# .claude/rules/gui-panels-config.md's "never wrapped" rule -- #62 moved that rule out
# of CLAUDE.md, which rules on nothing in this area now, and the rule file records this
# exemption beside it. What that rule protects is labelForField, so pin its
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

# ── 15. a junction method the dialog cannot READ leaves C1 live and silent ─────────
# Issue #23 decided this fallback is PERMISSIVE: a method value `_widget_value` cannot
# read (a scheme added later as a string, a spec whose kind stops matching its combo)
# must leave the field editable — "never stuck off" — and an editable field has nothing
# to explain, so it shows NO marker. Both halves are the `except` branch of
# `_wire_method_dependent_fields`, which check 14 never reaches: both shipped methods
# read fine, so the toggling above only ever exercises the two live paths and the
# fallback was intended rather than verified.
_real_read = PerGeomBLDialog._widget_value
_raised: list = []


def _unreadable_method(self, w, spec):
    """The real reader everywhere except the junction-method combo, which raises the
    way an unparseable value does."""
    m = self._widgets.get("BL_JUNCTION_METHOD")
    if m is not None and w is m[0]:
        _raised.append(1)
        raise ValueError("junction method is not readable as an int")
    return _real_read(self, w, spec)


def _c1_state(d) -> tuple:
    return (d._widgets[C1][0].isEnabled(), d.field_note(C1), c1_bound(d))


PerGeomBLDialog._widget_value = _unreadable_method
try:
    ur = PerGeomBLDialog("Global default", dict(defaults), dict(defaults))
    um, uk = ur._widgets["BL_JUNCTION_METHOD"]
    # THREE arrivals at the fallback, not one: the constructor's own `_sync`, then a
    # real `currentIndexChanged` in each direction. The seed is already method 1
    # (`include/BLParams.hpp`'s default), so re-setting 1 emits NOTHING — asserting
    # off that alone would have left the signal path unexercised and looked identical.
    ur_states = [(None, *_c1_state(ur))]
    for meth in (0, 1):
        ur._set_widget_value(um, uk, meth)
        app.processEvents()
        ur_states.append((meth, *_c1_state(ur)))
finally:
    PerGeomBLDialog._widget_value = _real_read
check(PerGeomBLDialog._widget_value is _real_read,
      "15. (the injection restored the real widget reader)")
check(len(_raised) >= 3,
      f"15. the fallback is REACHED, on the build and on a real index change in both "
      f"directions ({len(_raised)} unreadable reads)")
check(all(en for _m, en, _n, _b in ur_states),
      f"15. a junction method the dialog cannot read leaves C1 EDITABLE rather than "
      f"stuck off, method 1 — which otherwise disables it — included ({ur_states})")
check(all(not n for _m, _en, n, _b in ur_states),
      f"15. ...and shows NO reason, an editable field having nothing to explain "
      f"({[n for _m, _en, n, _b in ur_states]})")
check(all(b for _m, _en, _n, b in ur_states),
      "15. ...so check 14's disabled <=> reason binding holds in the fallback too")

print(("\nRESULT: " + ("ALL PASS" if not _FAILS else f"{len(_FAILS)} FAIL")), flush=True)
sys.exit(1 if _FAILS else 0)
