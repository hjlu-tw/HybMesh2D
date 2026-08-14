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

  * BASELINE fails the build on a NEW reach-through. It held the migration's
    remaining leaks and may only shrink; it is now empty. Adding a name to it is
    not the fix for a failure here — routing the call through a Sidebar verb is.
  * ``Sidebar.__getattr__`` is gone, and check 4 keeps it gone. A static list
    can be worked around by anyone willing to edit it; a deleted forwarder
    cannot, because the attribute simply does not resolve.

Both were needed. The list alone would not have stopped the forwarder quietly
serving new callers; deleting the forwarder alone would not stop a new caller
reaching a widget through a panel it names directly.

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
    "set_transform_reference_editable",
    # the model's length unit, shown on the fields that hold a length
    "set_length_suffix",
    # analytic edges
    "curve_spec",
    # actions
    "set_shape_tool_menu", "selection_mode",
    # what the sidebar is told, and what it can be asked
    "show_vertex_selection", "vertex_move_target", "vertex_insert_point",
    "keep_vertex_on_remove", "set_remove_edge_enabled", "set_join_edges_enabled",
    "set_bake_curve_enabled", "join_force_close", "show_edge_summary",
    "set_match_previous", "auto_split_angle", "arc_radius_locked",
    "show_geometry_name", "set_closure_mode", "set_global_spline",
}
INTERFACE_SIGNALS = {
    "distribution_edited", "distribution_open_requested",
    "distribution_apply_requested", "distribution_closed",
    "duplicate_edited", "duplicate_type_changed",
    "duplicate_base_mode_changed", "duplicate_requested",
    "transform_open_requested", "transform_closed",
    "curve_edited", "curve_type_changed",
    # actions: an intent per user gesture, bound by SidebarView._ACTIONS
    "load_requested", "load_stl_requested", "load_json_requested",
    "save_requested", "generate_requested", "extrude_stl_requested",
    "new_tab_requested", "split_requested", "remove_split_requested",
    "insert_point_requested", "move_vertex_requested", "remove_edge_requested",
    "join_edges_requested", "bake_curve_requested", "patch_name_requested",
    "auto_detect_requested", "auto_split_requested", "strategy_changed",
    "closure_mode_changed", "selection_mode_changed", "match_previous_toggled",
    "global_spline_toggled",
}
# Sub-modules that own their own interface. Q8: expose them by name, do not wrap
# them — a wrapper over a deep module is a shallow module.
INTERFACE_SUBMODULES = {"geometry_tree", "geom_stats_panel"}

INTERFACE = INTERFACE_VERBS | INTERFACE_SIGNALS | INTERFACE_SUBMODULES

# ── The frozen leak baseline — may only shrink ────────────────────────────
# EMPTY, and it stays empty. It was frozen at 214 (file, widget) pairs over 15
# files on 2026-08-14 and trimmed as each group migrated; the last entry left
# when Sidebar.__getattr__ was deleted. A pair here would be a reach-through
# that someone chose to record instead of route through a verb.
BASELINE: dict[str, set[str]] = {}
BASELINE_TOTAL = sum(len(v) for v in BASELINE.values())


_SIDEBAR_ATTRS = ("sidebar_view", "sidebar")


def _is_sidebar(node):
    """True for the sidebar however it was fetched.

    Both spellings count: `<anything>.main_window.sidebar_view`, and
    `getattr(<anything>, "sidebar_view", None)` — the defensive form, which is
    how one controller held the sidebar without this scanner ever seeing it.
    """
    if (isinstance(node, ast.Attribute) and node.attr in _SIDEBAR_ATTRS
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "main_window"):
        return True
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "getattr" and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value in _SIDEBAR_ATTRS)


def scan(path):
    """Every attribute name taken off the sidebar in one file, alias resolved.

    Resolving the alias is the point: `sb = self.main_window.sidebar_view`
    followed by `sb.dup_rot_px` is the shape 389 of the 403 uses actually took,
    and a scanner that only matches the full dotted path sees fourteen of them.
    """
    tree = ast.parse(open(path, encoding="utf-8").read())

    # Module-level tuples/lists of string literals, so a widget list held as a
    # constant and fed to getattr resolves to the names it actually reaches.
    consts = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, (ast.Tuple, ast.List))):
            items = [e.value for e in node.value.elts
                     if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if items and len(items) == len(node.value.elts):
                consts[node.targets[0].id] = items

    aliases = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and _is_sidebar(node.value)):
            aliases.add(node.targets[0].id)

    def on_sidebar(expr):
        return _is_sidebar(expr) or (isinstance(expr, ast.Name)
                                     and expr.id in aliases)

    found, dynamic = {}, []
    for node in ast.walk(tree):
        # (a) sb.<name>
        if isinstance(node, ast.Attribute) and on_sidebar(node.value):
            found.setdefault(node.attr, node.lineno)
            continue
        # (b) getattr(sb, ...) — invisible to an Attribute-only walk, and the
        # form that fails SILENTLY once __getattr__ is deleted, because getattr
        # returns the default instead of raising. That is the whole reason this
        # branch exists: a leak that cannot be seen and cannot be felt.
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "getattr" and node.args
                and on_sidebar(node.args[0])):
            continue
        name = node.args[1]
        if isinstance(name, ast.Constant) and isinstance(name.value, str):
            found.setdefault(name.value, node.lineno)
        elif isinstance(name, ast.Name) and name.id in consts:
            for resolved in consts[name.id]:
                found.setdefault(resolved, node.lineno)
        else:
            # A name this scanner cannot resolve is worse than a listed leak:
            # it is unreviewable AND silent. Report it rather than pass.
            dynamic.append(node.lineno)
    return found, dynamic


# ── 1. the sidebar exposes the verbs the rule points callers at ───────────
# SidebarView is composed from sidebar.py plus its own sidebar_*_mixin modules
# (the interface outgrew one file). "Defined on Sidebar" means reachable on the
# composed class, so all of them are scanned — otherwise moving a verb into a
# mixin would read as deleting it.
_SB_SOURCES = ["app/views/sidebar.py"] + sorted(
    "app/views/" + f for f in os.listdir(os.path.join(_GUI, "app/views"))
    if f.startswith("sidebar_") and f.endswith(".py"))
_sb_cls = []
for _rel in _SB_SOURCES:
    _t = ast.parse(open(os.path.join(_GUI, _rel), encoding="utf-8").read())
    _sb_cls += [n for n in _t.body if isinstance(n, ast.ClassDef)]
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
# A sub-module is excluded from the leak count on the grounds that it is NAMED
# by the sidebar. If it is not, it is resolving through __getattr__ like any
# leak, and Q8's exclusion is being claimed without being earned.
_sb_assigned = {t.attr for cls in _sb_cls for n in ast.walk(cls)
                if isinstance(n, ast.Assign) for t in n.targets
                if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                and t.value.id == "self"}
_missing_subs = sorted(INTERFACE_SUBMODULES - _sb_assigned)
check("1. every excluded sub-module is a NAMED attribute, not a __getattr__ hit "
      + (f"(missing: {_missing_subs})" if _missing_subs
         else f"({len(INTERFACE_SUBMODULES)} sub-modules)"),
      not _missing_subs)

# ── 2. no NEW reach-through ───────────────────────────────────────────────
# A pair absent from BASELINE is a name a controller learned since the freeze.
# The fix is a verb on Sidebar, never a new line in BASELINE.
offenders, live, scanned, unresolved = [], {}, set(), []
for dirpath, _d, files in os.walk(_GUI):
    if os.path.basename(dirpath) == "__pycache__":
        continue
    for fn in sorted(files):
        if not fn.endswith(".py"):
            continue
        path = os.path.join(dirpath, fn)
        rel = os.path.relpath(path, _GUI).replace(os.sep, "/")
        scanned.add(rel)
        raw, dyn = scan(path)
        unresolved += [f"{rel}:{ln}" for ln in dyn]
        names = {n: ln for n, ln in raw.items() if n not in INTERFACE}
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

# Check 3 alone can never fail once check 2 passes (BASELINE_TOTAL is derived
# from BASELINE, so "every live pair is allowed" already implies "no more of
# them than allowed"). This is the check that stands on its own: a name reached
# through getattr with a computed key is both unreviewable and SILENT — once
# __getattr__ goes it returns the default instead of raising.
check("3. no sidebar attribute is reached by a name this scan cannot resolve"
      + (f" ({unresolved})" if unresolved else ""),
      not unresolved)

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
