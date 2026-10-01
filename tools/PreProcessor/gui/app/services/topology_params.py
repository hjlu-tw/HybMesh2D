"""The topology template's PARAMETERS: one object holding every family's.

Split off ``topology_model.py`` when that file ran out of room for the work
coming to it (#159), along the seam its own docstring already named: this module
is the MODEL, and ``topology_model`` beside it is the family REGISTRY and the
PROJECTION to JSON. Nothing moved but the text —
``from app.services.topology_model import TopologyModel`` is still the import,
because that module re-exports the name, so every caller is untouched.

Qt-free, and gated as such by ``tests/test_qt_free_seam.py``'s ``services/``
sweep. It imports nothing from this package at all, which is what keeps the
direction one-way: the registry knows about the model, the model knows about no
family.

WHY THE PARAMETERS OF EVERY FAMILY LIVE ON ONE OBJECT rather than in a per-family
dict: the field-spec machinery reads and writes a model by ATTRIBUTE
(``field_widgets.read_specs`` does ``setattr(cfg, spec.model_name, ...)``), so a
parameter that is a dict entry cannot be declared as a field-spec row — and the
bidirectional gate #134 asks for is exactly "every parameter a family reads has
a row, and every row is read by a family", which is a comparison over attribute
names. A family prefixes its own parameters (``hgrid_*``), so two families cannot
collide and the gate can attribute a row to a family by its prefix.
"""
from __future__ import annotations

from dataclasses import dataclass, fields

__all__ = ["FAMILY_NONE", "TopologyModel"]

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

    # DETACHED: the family and every parameter below are still here, and NONE of
    # them drives the run any more (#139). The document stopped being a projection
    # and became a plain file the user maintains, named by
    # `MeshConfig.mesh_topology_file` — which is the ONE home for that path, so
    # this is a flag and never a second copy of it. What the family and the
    # parameters are for once this is set is PROVENANCE: "where did this file come
    # from", which is the only useful thing left three months later, and the reason
    # detaching does not simply clear them.
    detached: bool = False

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

    # ── O-grid (#137) ────────────────────────────────────────────────────────
    # The two geometries are named rather than positional, and the BOUND SEGMENTS
    # are stored as the CAD segment's stable ids rather than as positions in a
    # list: inserting, deleting or reordering a segment shifts every positional
    # binding after it with no error at all, which is the same failure class that
    # once exported an entire mesh as `wall`. Blank adopts what the geometry has
    # now; once captured the list is the binding of record and a missing id is a
    # refusal. See services/topology_binding.py.
    ogrid_body_geom: str = ""
    ogrid_body_segs: str = ""
    ogrid_far_geom: str = ""
    ogrid_far_segs: str = ""
    ogrid_splits: int = 1
    ogrid_cell: float = 0.05
    # 0 = take the derived count. Not a magic blank: the row is an int spin box, so
    # "no override" has to be a value, and any count below the mesher's own floor of
    # 2 cannot be one the user means.
    ogrid_radial_count: int = 0

    # ── C-grid (#148, #149) ──────────────────────────────────────────────────
    # ONE bound geometry is REQUIRED, the aerofoil, stored as stable segment ids
    # by the rule the O-grid's rows above state.
    cgrid_body_geom: str = ""
    cgrid_body_segs: str = ""
    # The far field is OPTIONALLY DRAWN (#149), the way the O-grid's always is.
    # BLANK IS THE DEFAULT AND IS NOT A DEGRADED STATE: the far field is then
    # GENERATED from the two lengths below as six free corners, which is what
    # #148's own demo asks for and what makes those six sides carry the run's
    # BC_GEOM rather than conditions of their own. Naming a geometry cut into six
    # segments binds the six sides to it instead, at which point the outlet
    # halves can carry an `outlet` of their own and the two lengths below decide
    # nothing — which the read-out says rather than leaving them to look live.
    cgrid_far_geom: str = ""
    cgrid_far_segs: str = ""
    # The two physical lengths the GENERATED far field is placed from: how far
    # downstream the outlet plane is from the trailing edge, and how far out the D
    # reaches. The defaults are the shipped hand-written C-grid's own figures for a
    # unit chord, so "accept the defaults and generate" reproduces its corners
    # exactly.
    cgrid_wake_length: float = 19.0
    cgrid_far_radius: float = 10.0
    cgrid_cell: float = 0.02
    # The cell length at the trailing edge — the one spacing the whole document
    # clusters to, because the wake shear layer continues the boundary layer and
    # the far field's nose sides have to track the body's own distribution.
    cgrid_te_cell: float = 0.005
    # 0 = take the derived count, by the rule `ogrid_radial_count` above states.
    cgrid_wake_count: int = 0
    cgrid_radial_count: int = 0

    # ── Two-ring O-grid (#155) ───────────────────────────────────────────────
    # THREE bound geometries, by the rule the O-grid's rows above state: stable
    # segment ids, blank adopting whatever the geometry has now. The middle one
    # is the SEAM, and it is the user's — a template writes no geometry (#133,
    # #150), and a `follows` edge needs a real geometry with a segment id and a
    # polyline rather than a generated corner. Normally made with CAD ▸ Offset
    # Geometry… (#152), which pairs segment-for-segment with the body by
    # construction; a hand-drawn one is equally legal and is checked, not assumed.
    tworing_body_geom: str = ""
    tworing_body_segs: str = ""
    tworing_seam_geom: str = ""
    tworing_seam_segs: str = ""
    tworing_far_geom: str = ""
    tworing_far_segs: str = ""
    tworing_splits: int = 1
    tworing_cell: float = 0.05
    # TWO radial counts, not one: splitting the ring is pointless if a single
    # number still governs both sides of the seam. 0 = take the derived count, by
    # the rule `ogrid_radial_count` above states. The inner one's derivation is
    # the O-grid's, from BL_INITIAL_THICKNESS; the outer one's starts from the
    # interval the inner ring finished on, which is the derived `ds_start`.
    tworing_radial_inner: int = 0
    tworing_radial_outer: int = 0

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

    def has_family(self) -> bool:
        """True when a family is NAMED here, whether or not it still drives the run.

        The one spelling of ``bool(self.family)``, which the two predicates below are
        both built on and which the panel asks to decide whether there is any
        provenance to show. It was inline at three sites and named in #139's own
        blind-spot list before review took the list at its word.
        """
        return bool(self.family)

    def is_detached(self) -> bool:
        """True for a family that has been DETACHED from its document (#139).

        Not the inverse of :meth:`names_a_family`, which is also True for a
        configuration that never had a template: this is what makes the panel show a
        provenance summary rather than an empty template section, and the three
        states (no family / attached / detached) need all three predicates to be
        told apart.
        """
        return self.has_family() and self.detached

    def names_a_family(self) -> bool:
        """True when a TEMPLATE drives this configuration.

        The ONE owner of that question, because three call sites now ask it and two
        of them used to spell it themselves, inverted: the funnel decides whether to
        PROJECT a document, the case staging decides whether to GENERATE one, and
        `mesh_topology_file` is an output rather than an input exactly when this is
        true. Two spellings of one predicate is how the projection and the staging
        drift into disagreeing about what a template case is.

        Deliberately NOT :meth:`is_configured`, which is a different question one
        line up: a user who has typed parameters but not yet picked a family has
        configured something (so the project file must carry it) while naming no
        family (so there is no document to build).

        FALSE ONCE DETACHED, which is how one flag turns the whole feature off in
        every place at once (#139): the funnel stops projecting, the case staging
        stops generating, the canvas overlay stops drawing a model the run no
        longer reads, and `mesh_topology_file` goes back to being an INPUT. The
        family is still named — `names_a_family` is not :meth:`has_family` and
        must not be re-spelled as one — because the panel still shows where the
        file came from. That is the whole difference between "no template" and
        "a template that has been detached".
        """
        return self.has_family() and not self.detached

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
