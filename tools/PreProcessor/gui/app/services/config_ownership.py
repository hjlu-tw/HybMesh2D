"""Which config fields a panel authors — derived from the source, not asserted.

The GUI has two representations of every stage's settings: the widgets on a panel, and
the model instance the controller holds (``global_mesh_config`` and friends, referenced
about a hundred times between them). Nothing forced them to agree, and the model was
only refreshed when a stage actually ran, so in between it lagged the panel. Every
workaround for that lag is a symptom: the dirty-detection snapshot reads panels instead
of models, ``mesh_layers_ctrl`` copies fields one by one with a hand-kept exclusion
list, and ``handle_mesh_config_changed`` copies a *different* three fields. One quantity,
several sources of truth.

Converging on "the model is the truth, the panel is a view" needs one fact per field:
**does this panel author it?** A field the panel authors must be copied from the panel on
every edit. A field it does NOT author must be preserved, or syncing would reset it to a
dataclass default — which is not hypothetical: the solver panel has no widgets for the
length unit, so a naive wholesale copy would silently wipe the unit system and with it
``Linf``.

This module answers that question by parsing the panel's own ``get_config`` sources with
:mod:`ast`, so the answer cannot drift from the code. A regex was tried first and had a
false negative that matters: ``cfg.xmin, cfg.xmax = ...`` is a tuple target, and half of
the IB panel's grid fields looked unauthored.
"""
from __future__ import annotations

import ast
import glob
import os

#: Panel source globs, relative to the ``gui`` directory. A panel is assembled from
#: mixins, so its authoring code is spread over several files by design.
PANEL_SOURCES = {
    "mesh_config_panel": ("app/views/panels/mesh_*.py",),
    "solver_config_panel": ("app/views/panels/solver_config_*.py",),
    "stl3d_config_panel": ("app/views/panels/stl3d_panel.py",),
}

#: Fields written through ``setattr`` from a table rather than by name. The mesh panel's
#: BL block does this (`_apply_global_bl_to_cfg` walks `_BL_OVERRIDE_KEYS`), so no
#: syntactic target exists to find. Listed here rather than pretended away.
_DYNAMIC = {
    "mesh_config_panel": "_bl_override_attrs",
}


def _gui_root() -> str:
    """The ``gui`` directory PANEL_SOURCES globs are relative to.

    This file is ``gui/app/services/config_ownership.py``, so that is three levels up.
    Getting it wrong is silent and dangerous: the globs simply match nothing, every
    field looks unauthored, and a sync built on that would preserve everything and
    therefore sync nothing.
    """
    here = os.path.dirname(os.path.abspath(__file__))          # gui/app/services
    return os.path.dirname(os.path.dirname(here))              # gui


def _targets(tree: ast.AST, var: str) -> set:
    """Every ``<var>.<field>`` assigned to anywhere in ``tree``.

    Covers plain assignment, tuple/list targets, augmented and annotated assignment,
    and ``setattr(<var>, "field", ...)`` with a literal name.
    """
    found = set()

    def note(node):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id == var:
            found.add(node.attr)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for el in node.elts:
                note(el)
        elif isinstance(node, ast.Starred):
            note(node.value)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                note(t)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            note(node.target)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "setattr" and len(node.args) >= 2:
            obj, name = node.args[0], node.args[1]
            if isinstance(obj, ast.Name) and obj.id == var \
                    and isinstance(name, ast.Constant) and isinstance(name.value, str):
                found.add(name.value)
    return found


def authored_fields(panel_attr: str, var: str = "cfg") -> set:
    """Model fields ``panel_attr``'s ``get_config`` writes.

    ``var`` is the local name the panel uses for the config it fills in; every panel
    here calls it ``cfg``.
    """
    root = _gui_root()
    found = set()
    for pattern in PANEL_SOURCES.get(panel_attr, ()):
        for path in sorted(glob.glob(os.path.join(root, pattern))):
            with open(path, encoding="utf-8") as f:
                found |= _targets(ast.parse(f.read(), filename=path), var)

    dynamic = _DYNAMIC.get(panel_attr)
    if dynamic == "_bl_override_attrs":
        # The BL block writes via setattr over a (key, attr) table; the table is the
        # authority, so read it rather than guessing from the loop.
        from app.views.panels.mesh_dialogs import _BL_OVERRIDE_KEYS
        found |= {attr for _key, attr in _BL_OVERRIDE_KEYS}
    return found


def unauthored_fields(panel_attr: str, model_cls) -> set:
    """Model fields the panel does NOT author — the set a sync must preserve."""
    import dataclasses
    names = {f.name for f in dataclasses.fields(model_cls)}
    return names - authored_fields(panel_attr)
