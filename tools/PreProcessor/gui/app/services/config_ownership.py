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

There are now two ways a panel authors a field, and this module knows both:

* **From its field-spec TABLE** (:func:`spec_authored`) — the normal case since each
  panel got one. A table entry is a declaration, so no parsing is involved.
* **By hand in ``get_config``** (:func:`authored_fields`) — the residue: facts one
  widget holds for many things (the geometry list, the BC-definition table) and the
  three unit fields one ``UnitSelector`` declares.

The hand-written half is found by parsing the panel's own sources with :mod:`ast`, so
the answer cannot drift from the code. A regex was tried first and had a false negative
that matters: ``cfg.xmin, cfg.xmax = ...`` is a tuple target, and half of the IB panel's
grid fields looked unauthored.

:func:`preserved_fields` is what the panel→model sync uses, and it deliberately does
NOT parse anything: it is the model's fields minus the tables minus each panel's
declared residue. That keeps the sync free of an ``ast``/``glob`` dependency on every
GUI start, and leaves the comparison of the two answers — declared residue versus
actual code — as the property ``tests/test_field_spec_tables.py`` gates.
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

#: Each panel's field-spec tables, as ``(module, attribute)`` pairs imported on demand.
#: Deferred so this module's IMPORT stays Qt-free, which is what
#: tests/test_qt_free_seam.py's services/ sweep checks. Deferral is not Qt-freedom, and
#: the distinction is one CLAUDE.md already records: the tables live under
#: ``views/panels/``, whose package ``__init__`` pulls in Qt, so the first CALL loads
#: five PyQt6 modules. Measured to be unchanged from the deferred
#: ``mesh_dialogs`` import this replaced, and every caller is Qt-side anyway (one
#: controller, two gate tests) — but do not read the deferral as "answerable headlessly".
PANEL_SPEC_TABLES = {
    "mesh_config_panel": (
        ("app.views.panels.mesh_field_specs", "MESH_SPECS"),
        ("app.views.panels.mesh_bl_field_specs", "PANEL_BL_SPECS"),
    ),
    "solver_config_panel": (
        ("app.views.panels.solver_field_specs", "SOLVER_SPECS"),
    ),
    "stl3d_config_panel": (
        ("app.views.panels.stl3d_field_specs", "STL3D_SPECS"),
    ),
}

#: Each panel's declaration of what it authors OUTSIDE its table, kept beside the table
#: it belongs to. One list per panel instead of two in two files.
PANEL_EXTRA_AUTHORED = {
    "mesh_config_panel": ("app.views.panels.mesh_field_specs", "MESH_EXTRA_AUTHORED"),
    "solver_config_panel": ("app.views.panels.solver_field_specs",
                            "SOLVER_EXTRA_AUTHORED"),
    "stl3d_config_panel": ("app.views.panels.stl3d_field_specs",
                           "STL3D_EXTRA_AUTHORED"),
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


def _load(mod_name: str, attr: str):
    """One table (or residue list) by name, imported on demand."""
    import importlib
    return getattr(importlib.import_module(mod_name), attr)


def spec_tables(panel_attr: str) -> tuple:
    """The panel's field-spec tables."""
    return tuple(_load(m, a) for m, a in PANEL_SPEC_TABLES.get(panel_attr, ()))


def spec_authored(panel_attr: str) -> set:
    """Model fields the panel's field-spec tables author — declared, not parsed."""
    from app.services.field_spec import authored
    return set(authored(*spec_tables(panel_attr)))


def extra_authored(panel_attr: str) -> set:
    """The panel's own declaration of what it authors outside its table."""
    entry = PANEL_EXTRA_AUTHORED.get(panel_attr)
    return set(_load(*entry)) if entry else set()


def hand_authored(panel_attr: str, var: str = "cfg") -> set:
    """Model fields the panel's sources assign BY NAME, found with :mod:`ast`.

    ``var`` is the local name the panel uses for the config it fills in; every panel
    here calls it ``cfg``.
    """
    root = _gui_root()
    found = set()
    for pattern in PANEL_SOURCES.get(panel_attr, ()):
        for path in sorted(glob.glob(os.path.join(root, pattern))):
            with open(path, encoding="utf-8") as f:
                found |= _targets(ast.parse(f.read(), filename=path), var)
    return found


def authored_fields(panel_attr: str, var: str = "cfg") -> set:
    """Every model field ``panel_attr``'s ``get_config`` writes, however it writes it."""
    return hand_authored(panel_attr, var) | spec_authored(panel_attr)


def unauthored_fields(panel_attr: str, model_cls) -> set:
    """Model fields the panel does NOT author — the set a sync must preserve."""
    import dataclasses
    names = {f.name for f in dataclasses.fields(model_cls)}
    return names - authored_fields(panel_attr)


def preserved_fields(panel_attr: str, model_cls) -> frozenset:
    """:func:`unauthored_fields`, computed from DECLARATIONS rather than from source.

    The model's fields, minus what the panel's tables author, minus the residue the
    panel declares. Nothing is parsed, so the panel→model sync can use this on import
    without dragging ``ast`` and a source-tree glob into every GUI start — and the two
    answers disagreeing is exactly what the gate test looks for.
    """
    from app.services.field_spec import preserved
    return preserved(model_cls, spec_tables(panel_attr), extra_authored(panel_attr))
