"""The topology MODEL, the family registry, and the projection to JSON (issue #134).

Qt-free, and gated as such by ``tests/test_qt_free_seam.py``'s ``services/`` sweep:
the whole template library — declaring a family, deriving its counts, building its
document and writing that document out — is exercisable from a headless process, and
the GUI is one caller of it rather than its home.

THE JSON IS A PROJECTION, NOT A SECOND HOME FOR THE TRUTH. What the user edits, what
the project file carries and what undo restores is the MODEL below; the document the
mesher reads is produced from it on the way to the run. Two homes for one fact is the
shape this repo has been bitten by before (a per-segment BC that lived both as a label
and as a map, and exported an all-wall mesh when one was rewritten and the other was
not). Here the model is the only writer and the JSON has no readers but the mesher.

WHY THE PARAMETERS OF EVERY FAMILY LIVE ON ONE OBJECT rather than in a per-family
dict: the field-spec machinery reads and writes a model by ATTRIBUTE
(``field_widgets.read_specs`` does ``setattr(cfg, spec.model_name, ...)``), so a
parameter that is a dict entry cannot be declared as a field-spec row — and the
bidirectional gate this ticket asks for is exactly "every parameter a family reads has
a row, and every row is read by a family", which is a comparison over attribute names.
A family prefixes its own parameters (``hgrid_*``), so two families cannot collide and
the gate can attribute a row to a family by its prefix.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, fields

from app.services import topology_hgrid

#: ``family`` value meaning "no template" — the user names a topology file by hand,
#: which is the path that existed before this ticket and still works unchanged.
FAMILY_NONE = ""


@dataclass
class TopologyModel:
    """Which family, and every family's parameters.

    Defaults are a WORKING CASE, not zeros: the ticket's demo is "pick H-grid, accept
    the defaults, generate, see a mesh", so the defaults have to mesh. These describe
    a 2x1 unit-ish duct at a target cell of 0.1 — four blocks, a clustered floor.
    """

    family: str = FAMILY_NONE

    # ── H-grid ───────────────────────────────────────────────────────────────
    hgrid_x_min: float = 0.0
    hgrid_x_max: float = 2.0
    hgrid_y_min: float = 0.0
    hgrid_y_max: float = 1.0
    hgrid_nx: int = 2
    hgrid_ny: int = 2
    hgrid_cell: float = 0.1
    hgrid_wall_bottom: bool = True
    hgrid_counts_x: str = ""
    hgrid_counts_y: str = ""

    def to_dict(self) -> dict:
        """Every parameter, as plain JSON-able values.

        ALL of them, not only the selected family's: a user who tries the H-grid,
        switches to '(none)' and comes back expects the numbers they typed to still
        be there, and a serialiser that dropped the unselected families would make
        switching family a destructive act.
        """
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def load_from_dict(self, d: dict) -> None:
        """Restore from :meth:`to_dict`, coercing through each field's own type.

        A value that will not convert keeps the default rather than landing as a
        string that crashes the family function later — the rule
        ``MeshConfig.load_from_dict`` already follows, for the same reason: a
        hand-written project file may quote a number.
        """
        for f in fields(self):
            if f.name not in d:
                continue
            try:
                setattr(self, f.name, _COERCE[f.name](d[f.name]))
            except (TypeError, ValueError):
                pass

    def is_configured(self) -> bool:
        """True once anything here has been touched — the OPTIONAL-section test.

        Not ``bool(self.family)``: a user who types a domain range and a block
        count before choosing the family from the combo has configured something,
        and a writer that asked only about the family would drop every number they
        typed. Compared against a freshly built model rather than against a
        remembered snapshot of the defaults, so a new parameter is covered with no
        edit here.

        The other direction is :meth:`MeshConfig.load_from_dict`, where an ABSENT
        section restores exactly this state. The two are inverses on purpose: the
        project-undo snapshot is ``MeshConfig.to_dict()``, so the snapshot taken
        before the first template edit has no section at all, and an absent section
        that did nothing would make that edit the one thing Ctrl+Z cannot walk back.
        """
        return self != TopologyModel()

    def copy(self) -> "TopologyModel":
        """A detached copy — what the undo snapshot and the panel round-trip need."""
        return TopologyModel(**{f.name: getattr(self, f.name) for f in fields(self)})

    def __eq__(self, other) -> bool:
        if not isinstance(other, TopologyModel):
            return NotImplemented
        return all(getattr(self, f.name) == getattr(other, f.name)
                   for f in fields(self))


#: One converter per field, so a restore coerces rather than trusts. Derived from
#: the dataclass's own annotations, so a new parameter is covered without an edit
#: here — and an annotation this map does not know RAISES at import time rather than
#: quietly picking one.
#:
#: MATCHED ON THE ANNOTATION TEXT, not on the type object. ``from __future__ import
#: annotations`` is in force in this module, so ``dataclasses.fields()`` reports
#: ``f.type`` as the STRING ``"int"`` and an ``f.type is int`` test is False for
#: every field. The first draft did exactly that, fell through to ``str`` for all of
#: them, and restored ``hgrid_nx`` as ``'7'`` — a silent degradation that looked like
#: a working round-trip. That is why an unknown annotation raises here instead of
#: defaulting to anything.
_CONVERTERS = {"bool": bool, "int": int, "float": float, "str": str}


def _coercers() -> dict:
    out = {}
    for f in fields(TopologyModel):
        t = f.type if isinstance(f.type, str) else getattr(f.type, "__name__", "")
        if t not in _CONVERTERS:
            raise TypeError(
                f"TopologyModel.{f.name}: annotation {f.type!r} has no converter. "
                f"Add one to _CONVERTERS — a parameter restored without coercion "
                f"lands as whatever the project file happened to hold.")
        out[f.name] = _CONVERTERS[t]
    return out


_COERCE = _coercers()


@dataclass(frozen=True)
class Family:
    """One entry of the registry: a name, a label, and the pure function."""

    name: str
    label: str
    build: object          # (TopologyModel) -> dict
    #: The parameter attribute prefix this family owns, which is how the
    #: parameters-to-families gate attributes a field-spec row to a family.
    prefix: str


#: The registry. Adding a family is adding a function and a row here — and a
#: field-spec row per parameter, which the bidirectional gate then requires.
FAMILIES: tuple[Family, ...] = (
    Family(topology_hgrid.FAMILY, "H-grid (rectangular blocks)",
           topology_hgrid.build, "hgrid_"),
)

#: ``(value, label)`` pairs for the family combo, with "no template" first because it
#: is the state every existing project is in.
FAMILY_CHOICES: list[tuple[str, str]] = (
    [(FAMILY_NONE, "(none — name a topology file)")]
    + [(f.name, f.label) for f in FAMILIES])


def family_for(name: str) -> Family | None:
    """The registry entry called ``name``, or ``None`` for "no template"."""
    for f in FAMILIES:
        if f.name == name:
            return f
    return None


def build_document(model: TopologyModel) -> dict:
    """The topology document ``model`` describes.

    Raises ``ValueError`` when the model names no family: a caller asking for the
    document of a model that has none has asked a question with no answer, and
    returning an empty document would put that answer in a file the mesher then
    refuses with a message about the document rather than about the request.
    """
    fam = family_for(model.family)
    if fam is None:
        raise ValueError(
            "this configuration names no topology family, so there is no document "
            "to build. Pick a family, or name a topology file by hand.")
    return fam.build(model)


def document_text(doc: dict) -> str:
    """``doc`` as the JSON text to write. Trailing newline, stable key order."""
    return json.dumps(doc, indent=2) + "\n"


def projection_path(config_path: str) -> str:
    """Where the document goes for a mesher config written at ``config_path``.

    Beside the config and named after it, so a case directory holding several
    configs holds one document per config rather than one they overwrite between
    them. Absolute, because the mesher opens ``MESH_TOPOLOGY_FILE`` exactly as
    written and relative to ITS OWN working directory (``src/cli.cpp``:
    ``std::ifstream tin(config.topologyFile)``) — which is not the config's
    directory, and is not the same for the two hosts.
    """
    p = os.path.abspath(config_path)
    stem = os.path.splitext(os.path.basename(p))[0]
    return os.path.join(os.path.dirname(p), f"{stem}_topology.json")


def project(model: TopologyModel, config_path: str) -> str:
    """Write ``model``'s document beside ``config_path``; return its absolute path."""
    out = projection_path(config_path)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(document_text(build_document(model)))
    return out
