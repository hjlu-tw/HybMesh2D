#!/usr/bin/env python3
"""The sidebar is a module with an interface, not a widget bag the controllers key by hand.

Controllers used to name 214 distinct sidebar widgets, through the alias
``sb = self.main_window.sidebar_view``. The alias is also what hid the coupling
from review: a grep for ``sidebar_view`` finds nine call sites, an AST walk that
resolves the alias finds four hundred.

The enabling mechanism is ``Sidebar.__getattr__`` (app/views/sidebar.py), a
catch-all that forwards any unknown attribute to whichever sub-panel owns it. So
most of those names are not attributes of Sidebar at all — no rename, no
deletion, and no signature change on a sub-panel widget is visible to the
controllers that depend on it.

This file is the RATCHET for closing that seam, and it is deliberately two
gates, because neither is sufficient alone:

  * The frozen BASELINE below fails the build on a NEW reach-through. It may
    only shrink. Adding a name to it is not the fix for a failure here —
    routing the call through a Sidebar verb is.
  * ``Sidebar.__getattr__`` must eventually go. A static list can be worked
    around by anyone who edits it; deleting the forwarder cannot. Check 4
    reports it as the endgame marker and turns into a hard failure the moment
    BASELINE reaches zero, so the last slice cannot be declared done while the
    door is still open.

INTERFACE is the other half: the names that ARE the sidebar's interface. Verbs
(``show_segment_props``, ``get_transform_dict``, …) and the two sub-modules that
already have interfaces of their own (``geometry_tree``, ``geom_stats_panel`` —
wrapping those in verbs would add a layer without adding leverage, which is the
definition of shallow). Reaching for these is correct and is not counted.

The scan mechanism is copied from tests/test_user_log_seam.py:142-170, including
its anti-vacuity assertion: a walk that silently stops covering a file still
passes, so the files a reach-through would hide in are asserted to have been
reached.

Run:  python3 tools/PreProcessor/tests/test_sidebar_seam.py
"""
import ast
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.join(_HERE, "..", "gui")

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


# ── The sidebar's actual interface — reaching for these is correct ────────
# Split three ways so check 1 can prove each name is the KIND it claims to be: a
# "signal" that is quietly a plain attribute would let a widget back through the
# seam wearing an interface name.
INTERFACE_VERBS = {
    "show_segment_props", "show_curve_segment", "show_file_segment",
    "show_details_for_mode", "get_transform_dict", "set_transform_from_dict",
    "switch_param_form", "open_distribution_dialog", "open_transform_dialog",
    # point distribution
    "distribution_spec", "show_distribution_spec", "distribution_tool_visible",
    # the footer button the sidebar really owns (the three CAD toolbar
    # buttons it used to hand out belong to the main window)
    "set_save_enabled",
    # Duplicate & Transform
    "transform_spec", "set_transform_reference",
    "set_transform_reference_applicable", "use_custom_transform_reference",
    "set_transform_handle", "show_transform_panel",
}
INTERFACE_SIGNALS = {
    "distribution_edited", "distribution_open_requested",
    "distribution_apply_requested", "distribution_closed",
    "duplicate_edited", "duplicate_type_changed",
    "duplicate_base_mode_changed", "duplicate_requested",
    "transform_open_requested", "transform_closed",
}
# Sub-modules that own their own interface. Q8: expose them by name, do not wrap
# them — a wrapper over a deep module is a shallow module.
INTERFACE_SUBMODULES = {"geometry_tree", "geom_stats_panel"}

INTERFACE = INTERFACE_VERBS | INTERFACE_SIGNALS | INTERFACE_SUBMODULES

# ── The frozen leak baseline — may only shrink ────────────────────────────
# Generated 2026-08-14 at 854f53e, trimmed as groups migrate:
# 114 (file, widget) pairs over 11 files.
# A pair NOT listed here is a new reach-through and fails check 2.
BASELINE = {
    "app/controllers/signal_wiring_ctrl.py": {
        'add_curve_seg_btn', 'arc_cx', 'arc_cy', 'arc_r', 'arc_theta0',
        'arc_theta1', 'auto_detect_btn', 'auto_split_btn', 'circle_cx',
        'circle_cy', 'circle_r', 'curve_bake_btn', 'curve_end_node',
        'curve_formula', 'curve_mode_param', 'curve_n', 'curve_start_node',
        'curve_t_max', 'curve_t_min', 'curve_type_combo', 'curve_x_formula',
        'curve_y_formula', 'extrude_stl_btn', 'generate_btn',
        'global_spline_cb', 'group_btn', 'h_line_x_end', 'h_line_x_start',
        'h_line_y', 'insert_btn', 'is_closed_combo', 'join_edges_btn',
        'line_x0', 'line_x1', 'line_y0', 'line_y1', 'load_btn', 'load_json_btn',
        'load_stl_btn', 'match_previous_cb', 'move_btn', 'new_tab_btn',
        'poly_vertices', 'quad_x0', 'quad_x1', 'quad_x2', 'quad_x3', 'quad_y0',
        'quad_y1', 'quad_y2', 'quad_y3', 'remove_seg_btn', 'remove_split_btn',
        'save_btn', 'select_mode_combo', 'split_btn', 'strategy_combo',
        'tri_x0', 'tri_x1', 'tri_x2', 'tri_y0', 'tri_y1', 'tri_y2', 'v_line_x',
        'v_line_y_end', 'v_line_y_start'
    },
    "app/controllers/curve_ctrl.py": {
        'curve_dist_mode', 'curve_end_node', 'curve_formula',
        'curve_mode_param', 'curve_n', 'curve_spacing', 'curve_start_node',
        'curve_t_max', 'curve_t_min', 'curve_type_combo', 'curve_x_formula',
        'curve_y_formula'
    },
    "app/controllers/segment_ctrl.py": {
        'curve_bake_btn', 'file_name_label', 'global_spline_cb',
        'join_edges_btn', 'match_previous_cb', 'param_stack', 'remove_seg_btn',
        'remove_split_btn', 'segment_type_label', 'selected_info', 'split_btn',
        'strategy_combo'
    },
    "app/controllers/segment_vertex_ctrl.py": {
        'insert_x', 'insert_y', 'keep_vertex_cb', 'move_btn', 'move_x',
        'move_y', 'remove_split_btn', 'selected_info', 'split_btn'
    },
    "app/controllers/segment_canvas_ctrl.py": {
        'curve_bake_btn', 'remove_split_btn', 'selected_info', 'split_btn'
    },
    "app/controllers/segment_props_ctrl.py": {
        'closed_mode_status', 'global_spline_cb', 'is_closed_combo',
        'match_previous_cb'
    },
    "app/controller.py": {
        'remove_split_btn', 'selected_info', 'split_btn'
    },
    "app/controllers/curve_draw_ctrl.py": {
        'arc_lock_radius'
    },
    "app/controllers/curve_edit_ctrl.py": {
        'arc_lock_radius'
    },
    "app/controllers/curve_join_ctrl.py": {
        'join_force_close_cb'
    },
    "app/controllers/segment_autodetect_ctrl.py": {
        'auto_split_angle_sb'
    },
}
BASELINE_TOTAL = sum(len(v) for v in BASELINE.values())


def _is_sidebar(node):
    """True for `<anything>.main_window.sidebar_view` (or `.sidebar`)."""
    return (isinstance(node, ast.Attribute)
            and node.attr in ("sidebar_view", "sidebar")
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "main_window")


def scan(path):
    """Every attribute name taken off the sidebar in one file, alias resolved.

    Resolving the alias is the point: `sb = self.main_window.sidebar_view`
    followed by `sb.dup_rot_px` is the shape 389 of the 403 uses actually took,
    and a scanner that only matches the full dotted path sees fourteen of them.
    """
    tree = ast.parse(open(path, encoding="utf-8").read())
    aliases = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and _is_sidebar(node.value)):
            aliases.add(node.targets[0].id)
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        base = node.value
        if _is_sidebar(base) or (isinstance(base, ast.Name) and base.id in aliases):
            found.setdefault(node.attr, node.lineno)
    return found


# ── 1. the sidebar exposes the verbs the rule points callers at ───────────
_sb_src = open(os.path.join(_GUI, "app/views/sidebar.py"), encoding="utf-8").read()
_sb_tree = ast.parse(_sb_src)
_sb_cls = [n for n in _sb_tree.body if isinstance(n, ast.ClassDef)]
_sb_methods = {m.name for cls in _sb_cls for m in cls.body
               if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
_sb_signals = {t.id for cls in _sb_cls for n in cls.body
               if isinstance(n, ast.Assign)
               and isinstance(n.value, ast.Call)
               and isinstance(n.value.func, ast.Name)
               and n.value.func.id == "pyqtSignal"
               for t in n.targets if isinstance(t, ast.Name)}
_missing_verbs = sorted(INTERFACE_VERBS - _sb_methods)
check("1. every interface VERB is a method on Sidebar "
      + (f"(missing: {_missing_verbs})" if _missing_verbs
         else f"({len(INTERFACE_VERBS)} verbs)"),
      not _missing_verbs)
_missing_signals = sorted(INTERFACE_SIGNALS - _sb_signals)
check("1. every interface SIGNAL is a pyqtSignal on Sidebar "
      + (f"(missing: {_missing_signals})" if _missing_signals
         else f"({len(INTERFACE_SIGNALS)} signals)"),
      not _missing_signals)

# ── 2. no NEW reach-through ───────────────────────────────────────────────
# A pair absent from BASELINE is a name a controller learned since the freeze.
# The fix is a verb on Sidebar, never a new line in BASELINE.
offenders, live, scanned = [], {}, set()
for dirpath, _d, files in os.walk(_GUI):
    if os.path.basename(dirpath) == "__pycache__":
        continue
    for fn in sorted(files):
        if not fn.endswith(".py"):
            continue
        path = os.path.join(dirpath, fn)
        rel = os.path.relpath(path, _GUI).replace(os.sep, "/")
        scanned.add(rel)
        names = {n: ln for n, ln in scan(path).items() if n not in INTERFACE}
        if not names:
            continue
        live[rel] = set(names)
        allowed = BASELINE.get(rel, set())
        for name, lineno in sorted(names.items()):
            if name not in allowed:
                offenders.append(f"{rel}:{lineno} -> sidebar.{name}")
check("2. no new sidebar reach-through "
      f"({len(offenders)} found)" + (f": {offenders[:5]}" if offenders else ""),
      not offenders)

# ── 3. the ratchet only turns one way ─────────────────────────────────────
live_total = sum(len(v) for v in live.values())
check(f"3. the leak count never rises (now {live_total}, frozen at {BASELINE_TOTAL})",
      live_total <= BASELINE_TOTAL)

stale = sorted(
    f"{f}: {sorted(names - live.get(f, set()))}"
    for f, names in BASELINE.items() if names - live.get(f, set())
)
if stale:
    print(f"     .. {BASELINE_TOTAL - live_total} baseline entries are now unused; "
          "trim them from BASELINE so the ratchet stays tight:")
    for s in stale:
        print("        " + s)

# ── 4. the endgame: the catch-all forwarder must not outlive the migration ─
# `__getattr__` is what makes a widget name reachable without Sidebar declaring
# it. While the baseline is non-empty it is still load-bearing, so this only
# reports; once the baseline is empty, keeping it would leave the door open for
# the next controller and the check becomes fatal.
_has_getattr = "__getattr__" in _sb_methods
if live_total:
    print(f"PASS 4. Sidebar.__getattr__ still present, with {live_total} leaks "
          "left to migrate (this becomes a failure at zero)")
else:
    check("4. Sidebar.__getattr__ is gone now that nothing reaches through it",
          not _has_getattr)

# ── 5. the scan actually reached the files a reach-through hides in ───────
# Copied from the log-seam gate for the same reason: a walk that quietly stops
# covering a file still reports a clean pass.
for must in ("app/controller.py", "app/views/sidebar.py",
             "app/controllers/signal_wiring_ctrl.py",
             "app/controllers/transform_ctrl.py"):
    check(f"5. the reach-through scan actually covers {must}", must in scanned)

print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print(f"All sidebar seam checks passed ({live_total} leaks remaining).")
