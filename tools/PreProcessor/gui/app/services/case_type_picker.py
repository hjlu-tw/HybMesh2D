"""WHICH case type is in play, and how an operator says so. Qt-free.

Issue #169, parent #158. Everything behind this module was already built and
gated — the four-state verdict and its advice (#160), the config overlay and the
deviation marking (#162), Trial and Generate (#166), the reference meshes a
threshold rests on (#168) — and all of it was reachable only through
`HYBMESH_CASE_TYPE`. `case_type.active_case_type()` had exactly one call site in
the repo and no controller, view or worker read the variable, so an operator had
no way to discover that the mechanism existed. This module is the channel that
replaces it, and `case_type.py`'s own docstring records that the picker was
forecast for #162 and then for #166 and missed both times.

THE CHOICE IS A MESH-CONFIG FIELD, `MeshConfig.case_type_file`, and that is what
makes every other property fall out rather than be arranged. It rides the
panel->model sync, the undo snapshot, the `.hws` workspace and the pipeline
script's `mesh` section because all four are `MeshConfig.to_dict()`; it needs no
allowance in `tests/test_gui_cpp_config_parity.py` because the parity gate reads
the `.dat` KEY map and a key-less field is structurally invisible to it. The
precedent is `topology`, `group_bc`, `bc_configured` and `geom_roles`, which are
key-less for the same reason: the mesher never sees this parameter.

STORED REPO-RELATIVE INSIDE THE REPO, CANONICAL ABSOLUTE OUTSIDE — the rule
`services/topology_detach.py` applies to `mesh_topology_file`, which is the
other path a mesh config carries. A repo-relative spelling is what keeps an
exported case package portable and a committed pipeline script runnable from
another checkout; an absolute one is right for a file the operator keeps outside
the tree. `case_workspace`'s rebasing walks every string in a workspace (`_walk`),
so this field is REACHED with no edit there — but what actually keeps the choice
portable is the repo-relative spelling, since a case type is not one of the files
the export SHIPS and so has no path under the package root to be swapped.

PRECEDENCE: THE DOCUMENT IN HAND BEATS THE ENVIRONMENT. In the window the
operator's choice is the only channel there is. For a headless host the SCRIPT
wins and `HYBMESH_CASE_TYPE` is the default when the script names none — #166
writes a pipeline script into a committed case so the mesh can be regenerated
without remembering what was done, and a script that does not carry its case
type delivers half of that. A single variable across a batch queue of many
scripts stays a legitimate use, which is why the variable is a FALLBACK and not
a thing the script has to override. `for_config` is the one place that rule is
spelled; `case_type.active_case_type()` is now reached from here and nowhere
else.

JUDGING, NOT APPLYING. Picking a case type here selects what will JUDGE the next
run. It does not write the case type's overlay into the configuration, scale its
geometry-driven sizes or bind its family to the operator's curves — that is
`apply_case_type.py`'s job, every part of it needs ROLES, and roles are #170. A
half-apply would create a third state (a case type that owns some fields and not
others), which is exactly the question the deviation marking exists to answer,
so it would blur its own denominator.

A FILE THAT WILL NOT LOAD IS LISTED, NOT DROPPED. `catalogue` returns an entry
for every candidate it finds and says per entry whether it loads and why not.
The panel shows an unloadable one DISABLED with the reason, because "a case type
the operator named and the tool quietly ignored is how a verdict goes missing"
is the rule this whole seam exists for, and omitting the file from the list is
that silence wearing a tidier coat.
"""
from __future__ import annotations

import glob
import os

from app.services import case_type as case_type_mod
from app.services import case_type_fields, case_type_scale, paths
from app.services.case_type_reference import CaseTypeError
from app.services.logging_setup import get_logger

logger = get_logger(__name__)

#: Where the shipped case types live, repo-relative. ONE directory and no
#: configurable search path: #169 is deliberately small, the tree holds one case
#: type today, and `Browse…` already covers a file that lives somewhere else —
#: a search-path setting would be a second persistence surface to get right.
CATALOG_DIR = os.path.join("examples", "case_types")

#: The suffix a case type file wears, re-exported from the document that owns it
#: so the catalogue scan, the Browse filter and the committed copy agree by
#: reading ONE constant rather than by three modules spelling the same string.
SUFFIX = case_type_mod.FILE_SUFFIX

#: What the picker's "pick a file somewhere else" row carries as its value. A
#: string no path can be, so it cannot collide with a real choice, and it never
#: reaches the model: `read_choice` maps it back to the last real selection, so
#: a `get_config()` that lands while the file dialog is open still reports the
#: configuration the operator actually has.
BROWSE = "\x00browse"

#: The label of the row that means "no case type": first in the list, and worded
#: as a consequence rather than as a blank, because a blank row in a picker reads
#: as "not set yet" when what it means is "nothing will judge this mesh".
NONE_LABEL = "(none — a Trial will not be judged)"

#: The label of the Browse row.
BROWSE_LABEL = "Browse for a case type file…"


class Entry:
    """One row of the picker: a candidate case type and whether it is usable.

    `stored` is the spelling that goes into the model (and so into the `.hws`
    and the pipeline script); `path` is the absolute one on this machine. Both
    are kept because the picker displays and compares the first while the
    loader needs the second, and deriving one from the other at every call site
    is how two spellings of one path come to disagree.

    `why` is empty exactly when `loadable` is true. A row that will not load is
    still a row — see the module docstring.
    """

    __slots__ = ("path", "stored", "label", "loadable", "why")

    def __init__(self, path: str, stored: str, label: str, loadable: bool,
                 why: str = ""):
        self.path = path
        self.stored = stored
        self.label = label
        self.loadable = loadable
        self.why = why

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("Entry(stored=%r, loadable=%r)" % (self.stored, self.loadable))


def stored_spelling(abs_path: str) -> str:
    """`abs_path` as it should be written down: repo-relative when it is inside.

    ONE OWNER, `services/paths.py::repo_relative`, which is where `repo_root`
    already lives. The first draft copied `topology_detach._stored` out by hand
    — byte-identical down to its Windows comment — with a docstring arguing that
    importing a private helper across two unrelated features was the worse
    dependency. It was right about the private helper and wrong about the
    remedy: both modules already import `paths`, so the rule had a home and two
    copies of it had nothing holding them in step.
    """
    return paths.repo_relative(abs_path)


def resolve(stored: str) -> str:
    """The absolute path a stored spelling names, or ``""`` for no choice.

    A relative spelling is resolved against the REPO ROOT and never against the
    process's working directory: the same workspace is opened from the GUI's
    launch directory, from `run_pipeline.sh` at the repo root and from a batch
    queue started anywhere, and a cwd-relative reading would make those three
    disagree about which file a case carries.
    """
    stored = str(stored or "").strip()
    if not stored:
        return ""
    if os.path.isabs(stored):
        return os.path.normpath(stored)
    return os.path.normpath(os.path.join(paths.repo_root(), stored))


def chosen(config) -> str:
    """The stored spelling `config` names, or ``""``. Never raises."""
    return str(getattr(config, "case_type_file", "") or "").strip()


def entry_for(stored: str) -> Entry:
    """One candidate, LOADED, so the row can say whether it is usable.

    Loading every candidate to build a list is deliberate and affordable: a case
    type is a few kilobytes of JSON and the directory holds one file today. The
    alternative — listing filenames and discovering on selection that one is
    broken — puts the discovery after the operator has committed to it.
    """
    path = resolve(stored)
    base = os.path.basename(path) or stored
    if not path or not os.path.isfile(path):
        return Entry(path, stored, "%s — missing" % base, False,
                     "this file is not there any more")
    try:
        ct = case_type_mod.load(path)
    except CaseTypeError as exc:
        # The loader's own sentence, not a second wording of it: it already
        # names the file and what is wrong with the document.
        reason = str(exc)
        return Entry(path, stored, "%s — will not load" % base, False, reason)
    return Entry(path, stored, "%s  (%s)" % (ct.name, base), True)


def catalogue(extra=()) -> list:
    """Every row the picker offers, in a stable order, EXCLUDING the sentinels.

    The shipped directory first, by filename, then any `extra` stored spellings
    the catalogue does not already hold — which is what keeps a file the
    operator browsed to, or one a reopened workspace carries, on the list
    instead of silently vanishing from it.
    """
    out, seen = [], set()
    root = paths.repo_root()
    pattern = os.path.join(root, CATALOG_DIR, "*" + SUFFIX)
    for path in sorted(glob.glob(pattern)):
        entry = entry_for(stored_spelling(path))
        out.append(entry)
        seen.add(os.path.normpath(entry.path))
    for stored in extra:
        stored = str(stored or "").strip()
        if not stored:
            continue
        path = os.path.normpath(resolve(stored))
        if path in seen:
            continue
        seen.add(path)
        out.append(entry_for(stored))
    return out


def for_config(config=None):
    """The case type that judges a run of `config`, or ``None``.

    THE ONE PLACE PRECEDENCE IS SPELLED (see the module docstring): the
    configuration's own choice wins, and `HYBMESH_CASE_TYPE` is the default when
    it names none. Raises `CaseTypeError` when a NAMED case type will not load —
    missing, malformed, or a document from a later build — because the operator
    asked for a judgement and must be told why there is none, which is a
    different answer from "nobody is judging this".
    """
    path = resolve(chosen(config)) if config is not None else ""
    if path:
        return case_type_mod.load(path)
    return case_type_mod.active_case_type()


# ── what the panel shows beside the picker ─────────────────────────────────

def summary(config) -> str:
    """The read-only block under the picker: what this case type owns and what moved.

    #158's user stories 24 and 20, which until now were computed on the GUI path
    and shown to nobody: the deviation list rides every `Verdict` and is written
    into the commit sidecar, and no panel, log line or dialog ever displayed it.

    AGAINST THE FITTED OVERLAY, not the authored one, through the same
    `case_type_scale.fit` the verdict uses — so the panel and the verdict cannot
    disagree about which fields this run has moved. When the ruler cannot be
    read off this drawing the reason is SAID here as it is said there, because a
    deviation list computed on the wrong ground is a plausible wrong answer
    rather than an error.
    """
    stored = chosen(config)
    if not stored:
        return ("No case type is chosen, so nothing will judge the next Trial. "
                "Pick one above to have the mesh graded against a problem class.")
    try:
        ct = case_type_mod.load(resolve(stored))
    except CaseTypeError as exc:
        return ("This case type cannot be read, so the next Trial will say so "
                "and run anyway:\n    %s" % exc)
    wanted, _scale, why_not = case_type_scale.fit(ct, config)
    lines = ["%s — thresholds on %s, %d of them."
             % (ct.name, ct.metric, len(ct.thresholds))]
    if not wanted.values:
        lines.append("It has an opinion about no configuration field, so "
                     "nothing here can deviate from it.")
    else:
        lines.append("Fields it has an opinion about (%d):" % len(wanted.values))
        moved = {d.name: d for d in case_type_fields.deviations(wanted, config)}
        for name, value in wanted.values.items():
            dev = moved.get(name)
            if dev is None:
                lines.append("    %s = %s"
                             % (name, case_type_fields.show_value(value)))
            else:
                # MOVED is marked on the row itself rather than listed
                # separately, so "which fields does it own" and "which of them
                # have I moved" are one reading instead of two lists the eye
                # has to join.
                lines.append("    %s = %s  — MOVED: this run uses %s"
                             % (name, case_type_fields.show_value(dev.wanted),
                                case_type_fields.show_value(dev.actual)))
        if not moved:
            lines.append("None of them has been moved on this run.")
    if why_not:
        lines.append("The case type's characteristic length could not be "
                     "measured on this case (%s), so its fields are compared "
                     "as AUTHORED rather than fitted to this geometry."
                     % why_not)
    return "\n".join(lines)


# ── what a reopened case says about itself ─────────────────────────────────

def committed_note(mesh_path: str) -> str:
    """One line naming the case type that judged a committed case, or ``""``.

    #158's story 7 read exactly: being TOLD which case type judged this case,
    without that silently becoming the current choice. `<stem>.casetype.json` is
    a FROZEN copy whose whole purpose is not to be rewritten by later
    corrections (#166), so selecting it automatically would judge the operator's
    next Trial against a historical document — and the operator would never have
    been asked. The sentence therefore states the history and the host changes
    nothing.

    ``""`` for a case that carries no embedded document, which is every case
    generated before #166 and every one committed with no case type in play.
    A copy that will not load is NAMED rather than skipped, for the reason an
    unloadable catalogue row is listed: a record nobody can read is a fact about
    this case, not an absence.
    """
    if not mesh_path:
        return ""
    path = os.path.splitext(mesh_path)[0] + SUFFIX
    if not os.path.isfile(path):
        return ""
    where = stored_spelling(os.path.abspath(path))
    try:
        ct = case_type_mod.load(path)
    except CaseTypeError as exc:
        logger.warning("the case type embedded in %s did not load: %s",
                       path, exc, exc_info=True)
        return ("This case was judged by a case type whose embedded copy (%s) "
                "cannot be read: %s. Your own choice is unchanged." % (where, exc))
    return ("This case was judged by the case type %r, whose whole document is "
            "embedded beside the mesh (%s). Your own choice is unchanged — "
            "that copy is frozen so a later correction cannot rewrite a "
            "finished case's judgement." % (ct.name, where))


# ── the picker widget's own read/write pair ────────────────────────────────
#
# Duck-typed on a QComboBox, so this module stays Qt-free (the shape
# `views/panels/stl3d_field_specs.py`'s `ascii_combo` already has). They are the
# spec's `read`/`write` escape hatch because the combo's item list is BUILT AT
# RUNTIME from the directory — `field_widgets`'s generic `choice` path matches
# against `opts["choices"]`, which for this row would be a snapshot of the tree
# taken at import time and wrong by the first Browse.

#: Where the combo keeps the last REAL selection. On the widget because the
#: field-spec `read`/`write` pair is handed nothing else, and named through a
#: constant so the one place that reads it and the two that write it are
#: greppable. See the blind spot in `.claude/rules/gui-dispositions.md`: this is
#: the one module under `services/` that touches a widget's own state, and the
#: Qt-free gate is import-based, so no check watches the shape.
LAST_CHOICE_ATTR = "_case_type_stored"


def read_choice(w) -> str:
    """The stored spelling the combo currently holds. PURE — it remembers nothing.

    THE SENTINEL NEVER REACHES THE MODEL. `Browse…` is a row the operator
    selects in order to leave it, and a `get_config()` landing in that moment —
    the panel->model sync is wired to the same `currentIndexChanged` — would
    otherwise write a value no loader can resolve into the workspace. The last
    real selection is answered instead, which is what makes "cancelling restores
    the previous choice" a property of the VALUE rather than of the handler
    getting there first.

    It used to record that value itself, which made a function named "read" a
    writer and left `_populate_case_types` — a pure caller — installing state as
    a side effect. `remember_choice` is now that act, and it has two callers: a
    programmatic write, and the panel's own pick handler.
    """
    data = w.currentData()
    if data is None or data == BROWSE:
        return str(getattr(w, LAST_CHOICE_ATTR, "") or "")
    return str(data)


def remember_choice(w) -> None:
    """Record what the combo now shows as the choice to fall back to.

    Called by the panel the moment a pick lands on a real row. The sentinel is
    skipped, which is the whole point: the value to fall back to is the one it
    had BEFORE `Browse…` was selected.
    """
    data = w.currentData()
    if data is not None and data != BROWSE:
        setattr(w, LAST_CHOICE_ATTR, str(data))


def write_choice(w, value) -> None:
    """Select `value`, ADDING a row for it when the combo does not offer one.

    A value with no row is the ordinary case rather than an error: a workspace
    saved after a Browse names a file outside the catalogue, and a chosen case
    type whose file has since gone names one that no longer scans. Both must
    keep their value visible in the picker — a picker that silently fell back to
    `(none)` would turn "your case type has moved" into "you never chose one".
    """
    stored = str(value or "").strip()
    setattr(w, LAST_CHOICE_ATTR, stored)
    for i in range(w.count()):
        if str(w.itemData(i) or "") == stored:
            w.setCurrentIndex(i)
            return
    if not stored:
        # "No case type" never gets a row of its own added: the `(none)` row is
        # built with the list and, at CONSTRUCTION, the combo has no rows at all
        # — `add_spec_rows` seeds every widget from `MeshConfig()`'s default
        # before the section has populated anything. Without this the panel
        # would be built holding a row labelled "— missing" for the empty path,
        # and that row would then be the session's default.
        return
    # Before the Browse row, which is always last, so the sentinel stays the
    # bottom of the list however many files are added to it.
    entry = entry_for(stored)
    at = max(w.count() - 1, 0)
    w.insertItem(at, entry.label, stored)
    w.setCurrentIndex(at)
