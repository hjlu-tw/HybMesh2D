"""The CONFIG FIELDS a case type has an opinion about, as a SPARSE overlay. Qt-free.

The fifth file of the case-type seam (#162, parent #158): `case_type.py` is the
document, `case_type_reference.py` the figures and the provenance it holds,
`case_type_author.py` the step that produces one and `case_type_verdict.py` the
grading. This module is the half that says WHAT TO RUN WITH rather than how to
judge what came out — the settings that produced the reference mesh, carried so
the operator does not configure 104 fields to mesh a problem class they
recognise (#158's user story 1).

**SPARSE IS THE WHOLE DESIGN, not an optimisation.** A case type records only the
fields it actually takes a position on. A field it does not mention takes the
ordinary `MeshConfig` default, so adding a mesher field does not stale every
existing case type (user story 36) — the alternative, a full snapshot of every
field, would mean every case type in the tree disagreeing with the model the day
a parameter is added, and nobody able to tell which of those disagreements was
an opinion.

**WHAT MAY BE OWNED IS DERIVED, NEVER LISTED.** `ownable_names` reads the
dataclass fields of `MeshConfig` and `TopologyModel` and keeps the SCALAR ones,
minus a declared `EXCLUDED` set that states its reason per entry. A hand-written
vocabulary would be a second declaration of the mesh parameters, which is exactly
the duplication `models/mesh_config_keys.py` was built to remove.

**THREE KINDS ARE EXCLUDED, and each is somebody else's subject.**

- *Containers* — the geometry list, the per-geometry roles, the group BC map.
  These are the operator's own drawing, not a reusable opinion, and a case type
  that carried the maintainer's file paths would be pointing at a tree the
  operator does not have.
- *Bindings* — every `*_geom` / `*_segs` topology parameter. They are stable
  segment ids into the MAINTAINER's geometry and cannot carry over by
  construction; the operator assigns ROLES and the bindings are derived from
  those, which is #164. Excluded by SUFFIX rather than by name so a fifth
  family's bindings are excluded the day it is added rather than the day someone
  remembers; `tests/test_case_type_fields.py` pins today's fourteen.
- *Per-project state* — `output_filename` (the operator's own case name),
  `mesh_topology_file` (a path into the maintainer's tree; the FAMILY and its
  parameters are what carries over, and #139 made that path the one home for a
  hand-maintained document), `bc_configured` (whether the operator has touched
  the BC panel — a case type cannot have an opinion about what somebody did) and
  `topology.detached` (that THIS project abandoned its template).

**THE FAMILY IS A FIELD LIKE ANY OTHER.** `topology.family` and the four
families' parameters are in the same flat overlay as the mesh fields, under a
`topology.` prefix, because a case type's whole point is that picking it answers
"which family and with what parameters" as well as "what size cells". One
vocabulary, one apply, one deviation report.

**DEVIATION IS A COMPARISON, NOT A HISTORY.** `deviations` asks what the overlay
says and what the config says NOW, over the owned fields and only those. It does
not record edits, so putting a field back removes its deviation — which is user
story 20 ("so that I can put one back if I want the verdict's full standing")
read literally. What a deviation MEANS to a verdict is `case_type_verdict.py`'s:
standing downgraded, never withheld.
"""
from __future__ import annotations

from app.models.mesh_config import MeshConfig
from app.services import project_file_kind
from app.services.case_type_reference import CaseTypeError
from app.services.field_spec import model_types
from app.services.topology_params import TopologyModel

#: The prefix a topology parameter wears in the flat overlay. One string, so the
#: writer, the reader and the `MeshConfig`/`TopologyModel` router cannot disagree
#: about where the dot falls.
TOPOLOGY_PREFIX = "topology."

#: The declared field types an overlay can carry. Everything else on the two
#: models is a container, and a container is the operator's own geometry rather
#: than a case type's opinion — see the module docstring.
SCALAR_TYPES = ("bool", "int", "float", "str")

#: The two suffixes that mark a topology parameter as a BINDING into the
#: authoring geometry. Derived rather than listed so a fifth family is covered
#: the day it lands; the ten of today are pinned by the gate.
BINDING_SUFFIXES = ("_geom", "_segs")

#: Scalar fields a case type may NOT own, each with the reason. Keyed by the
#: overlay name, so a topology entry wears its prefix.
EXCLUDED = {
    "mesh_topology_file":
        "a path into the maintainer's tree; the family and its parameters are "
        "what carries over, and a hand-maintained document is this project's",
    "output_filename":
        "the operator's own case name, and the one field whose whole job is to "
        "differ between cases",
    "bc_configured":
        "GUI state — whether the operator has touched the BC panel. A case type "
        "cannot have an opinion about what somebody did",
    TOPOLOGY_PREFIX + "detached":
        "records that THIS project stopped projecting its template, which is "
        "provenance about one project rather than a reusable setting",
}

#: How far two floats may sit apart and still be the same value, and the number
#: is MEASURED rather than picked: `models/mesh_config_io.py` writes every float
#: in the mesher's `.dat` at `%.6g`, so the file the mesher actually reads cannot
#: represent a finer difference than about 5e-7 relative. A tighter tolerance
#: would report a deviation the operator could not have made and could not undo;
#: a looser one would hide an edit the mesher can see. Same reason
#: `Origin.REL_TOL` is not zero, with a different writer behind it.
REL_TOL = 1e-6


def _binding(name: str) -> bool:
    """True for a topology parameter that names the authoring geometry."""
    return (name.startswith(TOPOLOGY_PREFIX)
            and name.endswith(BINDING_SUFFIXES))


def ownable_types(model_cls=MeshConfig, topology_cls=TopologyModel) -> dict:
    """Overlay name -> declared type, for every field a case type MAY own.

    The classes are parameters rather than module globals so the gate can hand
    in a model carrying a field this build does not have — which is how "a
    mesher field no case type mentions does not invalidate any existing case
    type" is measured on the real derivation rather than on a mock.
    """
    out = {}
    for prefix, cls in (("", model_cls), (TOPOLOGY_PREFIX, topology_cls)):
        for name, kind in model_types(cls).items():
            full = prefix + name
            if kind not in SCALAR_TYPES or full in EXCLUDED or _binding(full):
                continue
            out[full] = kind
    return out


def ownable_names(model_cls=MeshConfig, topology_cls=TopologyModel) -> tuple:
    """Every field a case type may own, in declaration order."""
    return tuple(ownable_types(model_cls, topology_cls))


def _coerce(name: str, kind: str, value):
    """A JSON value as the model field's declared type, or raise.

    Separate from `models/mesh_config_keys`'s converters on purpose: those read
    a `.dat` TOKEN, which is always text, while a case type is JSON and arrives
    with real numbers and real booleans. One table reading both would have to
    treat `false` and `"false"` alike, and the `.dat` rule for a bool
    (`int(s) != 0`) says `"false"` is an error — which is right for a `.dat` and
    wrong here.
    """
    try:
        if kind == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return int(value) != 0
            return float(value) != 0.0
        if kind == "int":
            return int(value) if not isinstance(value, str) else int(float(value))
        if kind == "float":
            return float(value)
        if isinstance(value, bool) or value is None:
            # A `str` field handed a JSON `true` or `null` is a document that
            # means something other than what `str(value)` would store, and
            # "True" as a boundary condition name is not a value anybody meant.
            raise ValueError("%r is not text" % (value,))
        return str(value)
    except (TypeError, ValueError) as exc:
        raise CaseTypeError("field %r wants a %s and the case type gives %r"
                            % (name, kind, value)) from exc


def _get(config, name: str):
    """The value `name` names on a live config, routing the topology prefix."""
    if name.startswith(TOPOLOGY_PREFIX):
        return getattr(config.topology, name[len(TOPOLOGY_PREFIX):])
    return getattr(config, name)


def _set(config, name: str, value) -> None:
    if name.startswith(TOPOLOGY_PREFIX):
        setattr(config.topology, name[len(TOPOLOGY_PREFIX):], value)
    else:
        setattr(config, name, value)


def same(a, b) -> bool:
    """True when two overlay values are the same value.

    Floats compare within `REL_TOL`; everything else is equality. `bool` is
    checked before the numeric path because `True == 1` in Python and a case
    type that says `export_vtk: true` has not been deviated from by a config
    holding `1`.
    """
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) is bool(b)
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) <= REL_TOL * max(abs(float(b)), 1.0)
        except (TypeError, ValueError):
            return False
    return a == b


class FieldOverlay:
    """The fields one case type takes a position on, and the value it wants.

    Sparse: a name that is not here is a field the case type has no opinion
    about, which is a different thing from one it wants left at the default.
    Ordered by the model's own declaration, so a file written today and one
    written after a field is inserted still diff cleanly.
    """

    __slots__ = ("values",)

    def __init__(self, values: "dict | None" = None):
        types = ownable_types()
        clean = {}
        for name, value in dict(values or {}).items():
            name = str(name)
            if name not in types:
                raise CaseTypeError(_why_not_ownable(name))
            clean[name] = _coerce(name, types[name], value)
        # Declaration order, not insertion order: see the class docstring.
        self.values = {n: clean[n] for n in types if n in clean}

    @property
    def names(self) -> tuple:
        """The fields this case type owns, in declaration order."""
        return tuple(self.values)

    def owns(self, name: str) -> bool:
        return name in self.values

    def __len__(self) -> int:
        return len(self.values)

    def __bool__(self) -> bool:
        return bool(self.values)

    @classmethod
    def from_dict(cls, raw) -> "FieldOverlay":
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise CaseTypeError("`fields` must be an object mapping a mesh "
                                "field to the value this case type wants, got "
                                "%r" % (raw,))
        return cls(raw)

    def to_dict(self) -> dict:
        return dict(self.values)

    def describe(self) -> list:
        """One line per owned field — what the operator is being handed.

        User story 24: "I want to see which fields the case type had an opinion
        about, so that I know what I am overriding when I change one". A list
        rather than a string, because the two hosts indent it differently.
        """
        return ["%s = %s" % (name, _show(self.values[name]))
                for name in self.values]

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return "FieldOverlay(%d field(s))" % len(self.values)


def _why_not_ownable(name: str) -> str:
    """Why `name` cannot be owned — the declared reason, or that it is unknown.

    Written once because the message is the only thing a maintainer sees when a
    case type names a field it may not, and "unknown key" for a field that
    exists and is deliberately excluded would send them looking for a typo.
    """
    if name in EXCLUDED:
        return ("a case type may not own %r: %s" % (name, EXCLUDED[name]))
    if _binding(name):
        return ("a case type may not own %r: it is a BINDING into the "
                "authoring geometry, and the operator's segments have entirely "
                "different ids — roles are what attaches a case type to a "
                "drawing" % name)
    return ("%r is not a mesh field a case type can own; expected one of %s"
            % (name, ", ".join(ownable_names())))


def _show(value) -> str:
    """A value as the reports spell it. One owner, so two reports agree."""
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, float):
        return "%.10g" % value
    if isinstance(value, str):
        return repr(value) if value else "(blank)"
    return str(value)


def read_config(path: str) -> MeshConfig:
    """The mesh config a file holds — a `.dat`, a `.hws` workspace or a script.

    A PATH IS NOT A KIND, which this repo has a user-reported defect for: the
    classification goes through `services/project_file_kind`, the one owner, so
    this host cannot disagree with `main.py` about what a file is. A `.dat` is
    what is left when the file is not a JSON object at all.

    It exists here rather than in a host because BOTH hosts need it — the
    authoring step captures an overlay from a working case, and the inspecting
    step compares a case type against one — and two readers would be free to
    disagree about where a workspace keeps its mesh section.
    """
    config = MeshConfig()
    doc = project_file_kind.peek_json_object(path)
    if doc is None:
        config.load_from_file(path)
        return config
    if project_file_kind.looks_like_workspace(doc):
        section = (doc.get("project") or {}).get("mesh_config")
    elif project_file_kind.looks_like_pipeline(doc):
        section = doc.get("mesh")
    else:
        raise CaseTypeError(
            "'%s' is a JSON document but neither a workspace nor a pipeline "
            "script, so there is no mesh configuration in it to read" % path)
    if not isinstance(section, dict):
        raise CaseTypeError("'%s' carries no mesh configuration" % path)
    config.load_from_dict(section)
    return config


def capture(config, names) -> FieldOverlay:
    """An overlay holding exactly `names`, read off a live config."""
    return FieldOverlay({n: _get(config, n) for n in names})


def capture_differences(config, extra=()) -> FieldOverlay:
    """Every ownable field `config` has moved off its default, plus `extra`.

    THE DERIVATION THE AUTHORING STEP USES, and the reason the maintainer is not
    asked to tick 50 boxes: they built a case they are happy with, so the fields
    they CHANGED are the fields they have an opinion about. `extra` is for the
    one they deliberately set back to the default and still mean — the same
    shape as an overridden threshold beside a measured one.
    """
    default = MeshConfig()
    names = [n for n in ownable_names()
             if not same(_get(config, n), _get(default, n))]
    for name in extra:
        if name not in names:
            names.append(str(name))
    return capture(config, names)


def apply(overlay: FieldOverlay, config=None):
    """`config` with the overlay's fields set; a fresh `MeshConfig` by default.

    With no config it answers user story 1 literally: the case type's fields are
    set and EVERY other field is at its ordinary default, which is what makes the
    overlay sparse rather than partial. Handed a live config it is the operator's
    own — their geometry list and their roles survive, because those are the
    things a case type has no opinion about.
    """
    if config is None:
        config = MeshConfig()
    for name, value in overlay.values.items():
        _set(config, name, value)
    return config


class Deviation:
    """One owned field the operator has moved, and where they moved it to."""

    __slots__ = ("name", "wanted", "actual")

    def __init__(self, name: str, wanted, actual):
        self.name = name
        self.wanted = wanted
        self.actual = actual

    def describe(self) -> str:
        return ("%s: the case type sets %s, this run uses %s"
                % (self.name, _show(self.wanted), _show(self.actual)))

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return "Deviation(name=%r)" % self.name


def deviations(overlay: FieldOverlay, config) -> tuple:
    """The owned fields `config` disagrees with, in declaration order.

    ONLY the owned ones: a field the case type has no opinion about cannot be
    deviated from, which is what keeps "adjust anything you like" (user story
    21) from turning every edit into a downgrade.
    """
    out = []
    for name, wanted in overlay.values.items():
        actual = _get(config, name)
        if not same(wanted, actual):
            out.append(Deviation(name, wanted, actual))
    return tuple(out)


class FieldDiff:
    """One field two case types disagree about. `MISSING` where one is silent."""

    __slots__ = ("name", "left", "right")

    #: What a side holds for a field it does not own. A sentinel rather than
    #: ``None``, because ``None`` is a value a `str` field could hold and
    #: "has no opinion" is not "wants blank".
    MISSING = object()

    def __init__(self, name: str, left, right):
        self.name = name
        self.left = left
        self.right = right

    def _side(self, value) -> str:
        return "no opinion" if value is self.MISSING else _show(value)

    def describe(self) -> str:
        return "%s: %s | %s" % (self.name, self._side(self.left),
                                self._side(self.right))

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return "FieldDiff(name=%r)" % self.name


def diff(left: FieldOverlay, right: FieldOverlay) -> tuple:
    """What differs between two case types' overlays, in declaration order.

    User story 37: "I want to diff two case types, so that I can see what
    actually differs between two problem classes". A field only one of them owns
    IS a difference — one has an opinion and the other leaves it to the default
    — and is reported as such rather than as a value against a blank.
    """
    out = []
    for name in ownable_names():
        in_left, in_right = left.owns(name), right.owns(name)
        if not in_left and not in_right:
            continue
        a = left.values[name] if in_left else FieldDiff.MISSING
        b = right.values[name] if in_right else FieldDiff.MISSING
        if in_left and in_right and same(a, b):
            continue
        out.append(FieldDiff(name, a, b))
    return tuple(out)
