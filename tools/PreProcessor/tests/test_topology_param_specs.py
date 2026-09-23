#!/usr/bin/env python3
"""Template parameters <-> family functions, compared IN BOTH DIRECTIONS
(issue #134, parent #133).

Its own gate, because the existing field-spec gates cannot hold this. Those compare
a table against the mesher's ``Config.hpp`` keys (``test_gui_cpp_config_parity.py``)
or against what a panel hand-authors on ``MeshConfig``
(``test_field_spec_tables.py``); a template parameter has NO C++ counterpart — the
mesher never sees a block count, it sees the document one produced — and authors a
field of ``TopologyModel`` rather than of ``MeshConfig``. There is nothing on the
other side of either existing comparison to compare these against.

What they ARE compared against is the family functions, and NEITHER DIRECTION ALONE
IS ENOUGH. One direction leaves a control that does nothing (a row the user can set
that no family reads); the other leaves a parameter the user cannot reach (a value
the family reads that has no widget). Both are silent: the mesh simply comes out
different from the one the panel described.

THE READS ARE DERIVED, NOT LISTED. What a family reads is found by walking its
module with :mod:`ast` for ``<param>.<attr>`` accesses, so adding a parameter to a
family function and forgetting the row fails here rather than passing a hand-kept
list that was updated in the same edit. A derivation that answers on input it did
not understand is worse than none (#116), so check 1 fails when the walk finds NO
reads at all — the shape a renamed parameter or a moved function would take.

INJECTIONS: run by hand, 2026-09-22, each reverted.

  A. delete the ``topo_hgrid_cell`` row from the table -> check 2 red ("hgrid_cell
     is read by hgrid and has no row"), check 3 green — which is the point of
     having two directions rather than one.
  B. add a row ``topo_hgrid_bogus`` (model ``hgrid_bogus``) that no family reads ->
     check 3 red, check 2 green. The mirror of A, and it also went red on check 4,
     because a row whose model field does not exist on ``TopologyModel`` is a third
     failure the same edit can make.
  C. rename ``model.hgrid_cell`` to ``model.hgrid_cellsize`` inside the family ->
     ONLY check 3 red, and check 1's per-family count fell from 10 to 9. This
     corrected the prediction written here first ("checks 2 and 4 red too"), and
     the correction is the blind spot below rather than a detail.

NAMED BLIND SPOT: the ast walk is SCOPED to attributes ``TopologyModel`` actually
declares, so a read of an attribute that is NOT a model field is invisible to it —
a typo'd ``model.hgrid_cellsize`` is not reported as an undeclared parameter, it
simply does not appear in the reads at all. It is still caught, but from the other
direction: the row whose field is no longer read goes red on check 3, and check 1's
count drops. Measured, not assumed (injection C). The scoping is deliberate and the
alternative is worse — collecting every ``<name>.<attr>`` in the module would make
``os.path``, ``str.strip`` and every local object's attribute into a "parameter" —
but it means check 2 alone cannot be read as "the family reads nothing undeclared".
"""
from __future__ import annotations

import ast
import os
import sys
from dataclasses import fields as dc_fields

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
sys.path.insert(0, _GUI)

from app.models.mesh_config import MeshConfig  # noqa: E402
from app.services import topology_model as tm  # noqa: E402
from app.services.topology_field_specs import (  # noqa: E402
    TOPOLOGY_READONLY, TOPOLOGY_SPECS, TOPOLOGY_STATE_ROWS,
)

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


_MODEL_FIELDS = {f.name for f in dc_fields(tm.TopologyModel)}


def module_path(mod) -> str:
    return mod.__file__


def reads_of(module_file: str) -> set:
    """Every ``<name>.<attr>`` read in ``module_file`` whose attr is a model field.

    Scoped to attributes the model actually declares rather than to a parameter
    name, so a helper that takes the model under another name (``m``, ``cfg``) is
    still seen — the alternative is a walk that silently returns nothing the first
    time someone renames the parameter, which is the failure check 1 exists for.
    """
    tree = ast.parse(open(module_file, encoding="utf-8").read())
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            if node.attr in _MODEL_FIELDS:
                out.add(node.attr)
    return out


#: family name -> the model fields its module reads.
FAMILY_READS = {f.name: reads_of(module_path(sys.modules[f.build.__module__]))
                for f in tm.FAMILIES}

# ── 1. the derivation answered at all ───────────────────────────────────────
empty = [n for n, r in FAMILY_READS.items() if not r]
check(f"1. every family's module yielded at least one model-field read, so the "
      f"ast walk understood what it was given ({ {n: len(r) for n, r in FAMILY_READS.items()} }): "
      + (", ".join(empty) + " read nothing" if empty else "all non-empty"),
      bool(FAMILY_READS) and not empty)

# ── 2. every parameter a family reads has a row ────────────────────────────
_row_models = {s.model_name for s in TOPOLOGY_SPECS if s.model_name}
_by_attr = {s.attr: s for s in TOPOLOGY_SPECS}
missing = sorted({a for r in FAMILY_READS.values() for a in r} - _row_models)
check("2. every model field a family function reads has a field-spec row "
      "(otherwise: a parameter the user cannot reach): "
      + (", ".join(missing) + " have none" if missing else "all declared"),
      not missing)

# ── 3. every row is read by a family ───────────────────────────────────────
# The STATE rows are excluded, and they are excluded by NAME from a list the table
# declares rather than by a condition written here: `family` SELECTS the function
# that does the reading and `detached` (#139) decides whether it is called at all,
# so neither can appear in any family's reads by construction. Check 3b below holds
# the exclusion honest in the other direction.
_state_models = {_by_attr[a].model_name for a in TOPOLOGY_STATE_ROWS
                 if a in _by_attr and _by_attr[a].model_name}
_read_any = {a for r in FAMILY_READS.values() for a in r}
unread = sorted(m for m in _row_models
                if m not in _state_models and m not in _read_any)
check("3. every field-spec row is read by some family (otherwise: a control that "
      f"does nothing), the {len(_state_models)} STATE rows aside "
      f"({sorted(_state_models)}): "
      + (", ".join(unread) + " are read by none" if unread else "all read"),
      not unread)

# ── 3b. ...and the exclusion list is not a place to hide a parameter ───────
# The whole risk of naming an exclusion is that the next unread row is added to it
# instead of being fixed. Two things stop that: every entry must BE a row of this
# table (so the list cannot drift into fiction), and no entry may be read by a
# family (so a real parameter cannot be parked here — it would fail rather than
# fall silently out of check 3).
_bad_state = [a for a in TOPOLOGY_STATE_ROWS if a not in _by_attr]
_bad_state += [m for m in _state_models if m in _read_any]
check("3b. every declared STATE row is a row of this table and is read by NO "
      "family, so the exclusion above cannot become a parking space for a "
      "parameter the templates forgot: "
      + (", ".join(_bad_state) + " disagree" if _bad_state else "all hold"),
      bool(TOPOLOGY_STATE_ROWS) and not _bad_state)

# ── 4. every row names a field the model actually has ──────────────────────
bogus = sorted(m for m in _row_models if m not in _MODEL_FIELDS)
check("4. every row's model field exists on TopologyModel: "
      + (", ".join(bogus) + " do not" if bogus else "all present"), not bogus)

# ── 5. a read-out authors nothing, and says so ─────────────────────────────
bad = [s.attr for s in TOPOLOGY_SPECS
       if (s.attr in TOPOLOGY_READONLY) != (s.model_name is None)]
check("5. exactly the rows named in TOPOLOGY_READONLY author no model field — "
      "declared in one place rather than inferred from a None: "
      + (", ".join(bad) + " disagree" if bad else "the two agree"), not bad)

# ── 6. a family's parameters carry its own prefix ──────────────────────────
# What lets the gate attribute a row to a family at all, and what stops two
# families colliding on a parameter name when the second one arrives (#137).
bad = []
for f in tm.FAMILIES:
    for a in FAMILY_READS[f.name]:
        if not a.startswith(f.prefix):
            bad.append(f"{f.name} reads {a}, which is not {f.prefix}*")
check("6. every parameter a family reads carries that family's declared prefix, "
      "which is what lets a row be attributed to a family: "
      + ("; ".join(bad) if bad else "all prefixed"), not bad)

# ── 7. every row is reachable: one group, and it is the builder's ─────────
groups = {s.group for s in TOPOLOGY_SPECS}
check(f"7. every row declares the one group the builder section walks ({groups}), "
      "so a row cannot be written-but-unreachable",
      groups == {"topology"})

# ── 8. no row carries a .dat key ──────────────────────────────────────────
keyed = [s.attr for s in TOPOLOGY_SPECS if s.key]
check("8. no template row carries a .dat/Config.hpp key — the mesher never sees a "
      "parameter, it sees the document one produced, and a key here would be "
      "compared against a C++ field that does not exist: "
      + (", ".join(keyed) if keyed else "none do"), not keyed)

# ── 9. the binding pairing is DECLARED, and both halves are rows ───────────
# It used to be spelled inside the panel, where a second binding family would need a
# view edit and nothing could compare the pair against the table (#137 review).
from app.services.topology_field_specs import BINDING_ROWS  # noqa: E402

_attrs = {s.attr for s in TOPOLOGY_SPECS}
bad = [a for pair in BINDING_ROWS for a in pair if a not in _attrs]
check(f"9. every half of every geometry->binding pair is a row of this table "
      f"({[list(p) for p in BINDING_ROWS]}): "
      + (", ".join(bad) + " are not" if bad else "all present"),
      bool(BINDING_ROWS) and not bad)

# ── 10. ...and the binding half is READ-ONLY ──────────────────────────────
# #133: "Which edges bind is the template's decision, not the user's". A row the
# user can type a segment id into is a more internal control than the arc-length
# position that decision was protecting them from.
bad = [segs for _g, segs in BINDING_ROWS
       if not _by_attr[segs].opts.get("readonly")]
check("10. every captured binding row is declared read-only, so which edges bind "
      "stays the template's decision: "
      + (", ".join(bad) + " are editable" if bad else "all read-only"), not bad)

# ── 11. what a family reads from the CONTEXT is declared too ───────────────
# The mirror of check 2, one layer out, added by #139's review. A family may read a
# physical quantity from the RUN rather than from the model — #133's decision that a
# template uses the existing name rather than an alias, which is why the O-grid's
# first cell is BL_INITIAL_THICKNESS and carries no `ogrid_` prefix. Nothing derived
# from the prefix can see one, so the detached provenance summary dropped it while
# looking complete. `Family.reads_context` declares them, and this holds that
# declaration against the same `ast` walk checks 1-3 use.
#
# `geoms` is EXEMPT and named rather than filtered silently: the geometries a family
# binds to are already rows of the table (`ogrid_body_geom`, `ogrid_far_geom`), so
# declaring them again would print a geometry twice in the summary.
from app.services.topology_binding import BindingContext  # noqa: E402

_CTX_EXEMPT = {"geoms": "already a field-spec row per bound geometry"}
_CTX_FIELDS = {f.name for f in dc_fields(BindingContext)}


def ctx_reads_of(module_file: str) -> set:
    tree = ast.parse(open(module_file, encoding="utf-8").read())
    return {n.attr for n in ast.walk(tree)
            if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load)
            and n.attr in _CTX_FIELDS}


# PAIRED EXACTLY, not counted: the first draft failed only when a family declared
# NOTHING, so one declaration would have covered two reads. Each entry names the
# context field it explains, so the two sets can be compared in both directions.
_ctx_bad = []
for _f in tm.FAMILIES:
    _declared = {c for c, _lbl, _a in _f.reads_context}
    _read = ctx_reads_of(module_path(sys.modules[_f.build.__module__]))
    _read -= set(_CTX_EXEMPT)
    for _attr in sorted(_read - _declared):
        _ctx_bad.append(f"{_f.name} reads ctx.{_attr} and declares it nowhere")
    for _attr in sorted(_declared - _read):
        _ctx_bad.append(f"{_f.name} declares ctx.{_attr} and reads it nowhere")
check(f"11. every BindingContext field a family reads is declared in its "
      f"`reads_context`, so the provenance summary can name it "
      f"({ {f.name: sorted(ctx_reads_of(module_path(sys.modules[f.build.__module__])) - set(_CTX_EXEMPT)) for f in tm.FAMILIES} }, "
      f"exempt: {_CTX_EXEMPT}): "
      + ("; ".join(_ctx_bad) if _ctx_bad else "all declared"), not _ctx_bad)

# ── 11b. ...and no declaration is stale ────────────────────────────────────
_stale = []
for _f in tm.FAMILIES:
    for _cf, _lbl, _attr in _f.reads_context:
        if _cf not in _CTX_FIELDS:
            _stale.append(f"{_f.name}'s {_lbl!r} names no BindingContext field "
                          f"({_cf})")
        if not hasattr(MeshConfig(), _attr):
            _stale.append(f"{_f.name}'s {_lbl!r} names no MeshConfig field ({_attr})")
check("11b. ...and every declaration resolves at BOTH ends: the BindingContext "
      "field it explains and the MeshConfig attribute the summary reads it from: "
      + ("; ".join(_stale) if _stale else "all resolve"), not _stale)

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("All checks passed.")
