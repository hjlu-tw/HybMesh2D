"""The CHARACTERISTIC LENGTH a case type's geometry-driven sizes are relative to. Qt-free.

The sixth file of the case-type seam (#163, parent #158). `case_type.py` is the
document, `case_type_reference.py` the figures and provenance it holds,
`case_type_fields.py` the sparse config overlay, `case_type_author.py` the step
that produces one and `case_type_verdict.py` the grading. This one makes an
overlay fit a geometry OTHER THAN the one it was authored on: without it a case
type built on a 1 m body hands a 10 mm body the same 0.02 surface size and meshes
it in two cells (#158's user story 22).

**THE RULER IS DERIVED, NEVER TYPED.** A case type names a ROLE and a MEASURE —
"the extent of the geometries bearing `body`" — and the length is read off the
maintainer's drawing when the case type is authored, and off the operator's when
it is applied. Neither end types a number, for the reason a threshold is measured
from a reference mesh rather than invented (#161): a figure somebody typed is a
figure nobody can trace. What the maintainer declares is which curve the sizes
are about, which no measurement can decide for them.

**TWO KINDS OF LENGTH, AND CONFLATING THEM IS THE BUG THIS EXISTS AGAINST.** A
surface size, a far-field radius and a wake length are GEOMETRIC: they say "a
fiftieth of the body", and they scale. The boundary-layer first cell height is
PHYSICAL: it is set by the Reynolds number and the target y+, and scaling it with
the body would amount to claiming that smaller aerofoils have thinner boundary
layers. So it is carried through unscaled, and it is the one value a case type
asks the operator to CONFIRM on every application rather than applying silently
(user story 23) — `Application.apply` refuses until they do, which makes "never
silently" a property of the code rather than a promise in a docstring.

**WHICH LENGTHS EXIST IS DERIVED FROM THE FIELD-SPEC TABLES, NOT LISTED.** A
field is a length exactly when its `FieldSpec.kind` is `sci`, which is already
this repo's declaration of a physical length — it decides the unit suffix and the
decade-stepping spin box, and `field_spec.LENGTH_KINDS` says so. What each of
those lengths MEANS — a size, an x or y coordinate, or a physical quantity — is a
judgement nothing in the tree records, so `LENGTH_KIND` declares it per field. A
`sci` field missing from that map FAILS `tests/test_case_type_scale.py`: a new
length must be classified before it ships, because the default would otherwise be
"scale it", and that is the wrong default for the one field that matters most.

**A COORDINATE IS NOT A SIZE.** `DOMAIN_X_MIN` is a position in the geometry's own
frame, so multiplying it by the scale factor is right only when the body sits at
the origin. Positions map AFFINELY about the characteristic length's own centre —
the centre of the role-bearing geometries, recorded at authoring and re-derived
at application — so a case type authored on a body at the origin still works on a
drawing whose body sits at (500, 500).

**IT USES THE LENGTH-UNIT SYSTEM RATHER THAN DUPLICATING IT.** The geometric
scale factor is a RATIO of two lengths each measured in its own project's grid
units, so the unit cancels and nothing converts. The physical parameter is the
opposite case: `services/units.py` records that `length_unit_metres` IS
metres-per-grid-unit, and a first cell height means a height in METRES, so
carrying it from a case authored in metres to a project drawn in millimetres
multiplies by the ratio of the two unit factors — not a second scaling rule, the
existing one applied where it has always applied. This repo has already lost a
run to the adjacent mistake (a millimetre mesh left at the default `Linf` runs a
thousand times wrong), which is also why the three `length_unit*` fields are NOT
ownable: a case type that imposed its author's unit on the operator's drawing
would relabel their geometry rather than fit it.

**A RULER THAT CANNOT BE READ REFUSES.** No geometry bearing the named role, a
file that will not load, a role-bearing set with no extent — each raises rather
than falling back to the whole drawing or to 1.0: a guessed ruler gives a mesh
that looks right and is the wrong size.
"""
from __future__ import annotations

from app.services import units
from app.services.case_type_fields import FieldOverlay
from app.services.case_type_fields import TOPOLOGY_PREFIX
from app.services.case_type_fields import show_value, apply as apply_overlay
from app.services.case_type_reference import CaseTypeError
from app.services.field_spec import LENGTH_KINDS
from app.services.logging_setup import get_logger

logger = get_logger(__name__)

#: How a characteristic length is read off a point set. Four, because the two
#: lengths #158 names ("a chord, a body diameter") are not one measurement: a
#: chord is an axis extent and a diameter is orientation-free, and `diagonal` is
#: the only one no rotation of the body changes.
MEASURES = {
    "extent": "the larger of the x and y extents of the role-bearing geometry",
    "x_extent": "the x extent — a chord, for a body drawn along x",
    "y_extent": "the y extent",
    "diagonal": "the bounding-box diagonal, which no rotation changes",
}

#: The role words a characteristic length may name, and what each selects.
#: `MeshConfig.geom_roles`'s own vocabulary rather than a second one (see
#: `models/mesh_config_geoms.py`), with `body` for the DEFAULT role, which that
#: model spells as the ABSENCE of an entry. #164 gives the operator a panel to
#: assign these; the words do not change when it lands.
ROLES = {
    "body": "the geometries that grow a boundary layer (no role recorded)",
    "farfield": "the outer-domain outline, external flow",
    "wall": "the outer-domain wall, internal flow",
    "nobl": "an obstacle that grows no boundary layer",
    "seed": "a refinement seed",
}

#: What one length field IS. `SIZE` scales with the characteristic length; `X`
#: and `Y` are positions in the geometry frame, mapped affinely about its centre;
#: `PHYSICAL` never scales and is always confirmed.
SIZE, X, Y, PHYSICAL = "size", "x", "y", "physical"

#: Every `sci` field, classified. Checked against the field-spec tables by the
#: gate in BOTH directions, so a length that is added without a judgement here
#: fails rather than defaulting to "scale it".
LENGTH_KIND = {
    "domain_x_min": X,
    "domain_x_max": X,
    "domain_y_min": Y,
    "domain_y_max": Y,
    "surface_mesh_size": SIZE,
    "farfield_mesh_size": SIZE,
    "bl_initial_thickness": PHYSICAL,
    TOPOLOGY_PREFIX + "hgrid_x_min": X,
    TOPOLOGY_PREFIX + "hgrid_x_max": X,
    TOPOLOGY_PREFIX + "hgrid_y_min": Y,
    TOPOLOGY_PREFIX + "hgrid_y_max": Y,
    TOPOLOGY_PREFIX + "hgrid_cell": SIZE,
    TOPOLOGY_PREFIX + "ogrid_cell": SIZE,
    TOPOLOGY_PREFIX + "cgrid_wake_length": SIZE,
    TOPOLOGY_PREFIX + "cgrid_far_radius": SIZE,
    TOPOLOGY_PREFIX + "cgrid_cell": SIZE,
    TOPOLOGY_PREFIX + "cgrid_te_cell": SIZE,
    TOPOLOGY_PREFIX + "tworing_cell": SIZE,
}

#: Why each physical parameter is physical, printed where the operator is asked
#: to confirm it: "confirm this number" with no reason is a dialog people learn
#: to dismiss.
PHYSICAL_WHY = {
    "bl_initial_thickness":
        "the first cell height is set by the Reynolds number and the target y+, "
        "not by how big the body is",
}


def length_fields(*tables) -> dict:
    """Overlay name -> `True` for every field the spec tables declare a LENGTH.

    Reads the tables rather than a list, so this is the same declaration that
    decides the unit suffix on the panel. They are parameters so the gate can
    hand in one carrying a length this build does not have.
    """
    if not tables:
        from app.services import mesh_bl_field_specs, mesh_field_specs
        from app.services import topology_field_specs
        tables = ((mesh_field_specs.MESH_SPECS, ""),
                  (mesh_bl_field_specs.BL_SPECS, ""),
                  (topology_field_specs.TOPOLOGY_SPECS, TOPOLOGY_PREFIX))
    out = {}
    for table, prefix in tables:
        for spec in table:
            name = spec.model_name
            if name and spec.kind in LENGTH_KINDS:
                out[prefix + name] = True
    return out


# ── reading the ruler off a drawing ─────────────────────────────────────────

def role_of(config, path: str) -> str:
    """The role word `path` bears in `config`, `"body"` when it records none."""
    return str((config.role_of(path) or {}).get("role") or "body")


def role_paths(config, role: str) -> list:
    """The geometry files in `config` bearing `role`, in the list's own order."""
    return [p for p in config.geom_files if p and role_of(config, p) == role]


def _extent(paths, measure: str) -> tuple:
    """`(value, (cx, cy))` for the union bounding box of `paths`.

    Through `geometry_service.load_points_dat`, this repo's one validated
    geometry loader, so a malformed file is NAMED rather than becoming a NaN in
    every size the case type sets. `ValueError`, not that loader's own
    `GeometryLoadError`: it validates shape and finiteness but `np.loadtxt`
    raises FIRST and raises a BARE `ValueError` — a geometry entry pointing at
    JSON arrives as `could not convert string '{' to float64`, this repo's own
    USER-REPORTED defect in another costume, which neither this handler nor the
    hosts' deliberately narrow ones would otherwise catch.
    """
    from app.services.geometry_service import load_points_dat
    box = None
    for path in paths:
        try:
            pts = load_points_dat(path)
        except (ValueError, OSError) as exc:
            raise CaseTypeError(
                "the characteristic length is measured from '%s', which could "
                "not be read: %s" % (path, exc)) from exc
        lo = (float(pts[:, 0].min()), float(pts[:, 1].min()))
        hi = (float(pts[:, 0].max()), float(pts[:, 1].max()))
        box = (lo, hi) if box is None else (
            (min(box[0][0], lo[0]), min(box[0][1], lo[1])),
            (max(box[1][0], hi[0]), max(box[1][1], hi[1])))
    (x0, y0), (x1, y1) = box
    dx, dy = x1 - x0, y1 - y0
    value = {"extent": max(dx, dy), "x_extent": dx, "y_extent": dy,
             "diagonal": (dx * dx + dy * dy) ** 0.5}[measure]
    return value, ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def measure_role(config, role: str, measure: str) -> tuple:
    """`(value, centre)` for `role` in `config`, or raise saying why not.

    The paths are taken as the config holds them, with no base of its own:
    `models/mesh_config_io.py` resolves every geometry token to an absolute path
    as it loads, and a second rule here could only come to disagree with it.
    """
    if role not in ROLES:
        raise CaseTypeError(
            "%r is not a role a geometry can bear; expected one of %s"
            % (role, ", ".join(ROLES)))
    if measure not in MEASURES:
        raise CaseTypeError(
            "%r is not a way to measure a characteristic length; expected one "
            "of %s" % (measure, ", ".join(MEASURES)))
    paths = role_paths(config, role)
    if not paths:
        borne = sorted({role_of(config, p) for p in config.geom_files if p})
        raise CaseTypeError(
            "this case type measures its sizes against the %s, and none of the "
            "%d geometries here is a %s%s. Assign the role before applying it — "
            "a characteristic length cannot be guessed from the rest of the "
            "drawing" % (role, len(config.geom_files), role,
                         (" (found: %s)" % ", ".join(borne)) if borne else ""))
    value, centre = _extent(paths, measure)
    if not (value > 0.0):
        # `not (value > 0.0)` rather than `<= 0.0`, so a NaN — which no
        # comparison is true of — is refused by the same line.
        raise CaseTypeError(
            "the %s geometry (%s) has no %s to measure, so there is nothing to "
            "express this case type's sizes relative to"
            % (role, ", ".join(paths), measure))
    return value, centre


class CharacteristicLength:
    """The ruler a case type's geometry-driven sizes are expressed against.

    `role` and `measure` are the maintainer's DECLARATION; `value` and `centre`
    are what it measured on the authoring drawing, and `unit_metres` what one of
    its grid units was worth — what a later application needs to put its own
    measurement into proportion.
    """

    __slots__ = ("role", "measure", "value", "centre", "unit_metres")

    def __init__(self, role: str, measure: str, value: float,
                 centre=(0.0, 0.0), unit_metres: float = 1.0):
        if role not in ROLES:
            raise CaseTypeError(
                "characteristic length names role %r, which is not one a "
                "geometry can bear; expected one of %s"
                % (role, ", ".join(ROLES)))
        if measure not in MEASURES:
            raise CaseTypeError(
                "characteristic length names measure %r; expected one of %s"
                % (measure, ", ".join(MEASURES)))
        try:
            value = float(value)
            centre = (float(centre[0]), float(centre[1]))
            unit_metres = float(unit_metres)
        except (TypeError, ValueError, IndexError, KeyError) as exc:
            raise CaseTypeError(
                "characteristic length carries a value, centre or unit that is "
                "not a number: %s" % exc) from exc
        if not (value > 0.0):
            raise CaseTypeError(
                "characteristic length is %r; a ruler of zero or less divides "
                "every size by nothing" % value)
        if not (unit_metres > 0.0):
            raise CaseTypeError(
                "characteristic length records %r metres per grid unit, which "
                "no drawing has" % unit_metres)
        self.role, self.measure = role, measure
        self.value, self.centre, self.unit_metres = value, centre, unit_metres

    def describe(self) -> str:
        return ("%s of the %s = %.6g (%.6g m), centred (%.6g, %.6g)"
                % (self.measure, self.role, self.value,
                   self.value * self.unit_metres,
                   self.centre[0], self.centre[1]))

    @classmethod
    def from_dict(cls, raw) -> "CharacteristicLength | None":
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise CaseTypeError(
                "`characteristic_length` must be an object naming the role and "
                "measure its sizes are relative to, got %r" % (raw,))
        unknown = set(raw) - {"role", "measure", "value", "centre",
                              "unit_metres"}
        if unknown:
            raise CaseTypeError("unknown key(s) in characteristic length: %s"
                                % ", ".join(sorted(unknown)))
        for required in ("role", "measure", "value"):
            if required not in raw:
                raise CaseTypeError(
                    "characteristic length is missing %r" % required)
        return cls(role=str(raw["role"]), measure=str(raw["measure"]),
                   value=raw["value"], centre=raw.get("centre", (0.0, 0.0)),
                   unit_metres=raw.get("unit_metres", 1.0))

    def to_dict(self) -> dict:
        return {"role": self.role, "measure": self.measure,
                "value": self.value, "centre": list(self.centre),
                "unit_metres": self.unit_metres}

    @classmethod
    def derive(cls, config, role: str,
               measure: str = "extent") -> "CharacteristicLength":
        """Read the ruler off a drawing. The ONLY way one is ever created."""
        value, centre = measure_role(config, role, measure)
        return cls(role, measure, value, centre,
                   units.metres_per_unit(config.length_unit,
                                         config.length_unit_metres))

    def scale_for(self, config) -> "Scale":
        """The `Scale` that fits this case type to `config`'s own drawing."""
        value, centre = measure_role(config, self.role, self.measure)
        return Scale(value / self.value, self.centre, centre,
                     self.unit_metres / units.metres_per_unit(
                         config.length_unit, config.length_unit_metres))

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return "CharacteristicLength(role=%r, value=%r)" % (self.role,
                                                            self.value)


class Scale:
    """How one case type's numbers become this drawing's numbers.

    `factor` is a ratio of two lengths each measured in its OWN project's grid
    units, so it carries no unit; `unit_ratio` is the separate conversion a
    PHYSICAL quantity needs when the two projects declare different units, and
    is 1.0 whenever they agree — which is why "carried through unscaled" is
    literally true in the ordinary case.
    """

    __slots__ = ("factor", "ref_centre", "centre", "unit_ratio")

    def __init__(self, factor: float = 1.0, ref_centre=(0.0, 0.0),
                 centre=(0.0, 0.0), unit_ratio: float = 1.0):
        self.factor = float(factor)
        self.ref_centre = (float(ref_centre[0]), float(ref_centre[1]))
        self.centre = (float(centre[0]), float(centre[1]))
        self.unit_ratio = float(unit_ratio)

    def size(self, value: float) -> float:
        return float(value) * self.factor

    def coord(self, value: float, axis: int) -> float:
        return (self.centre[axis]
                + (float(value) - self.ref_centre[axis]) * self.factor)

    def physical(self, value: float) -> float:
        """The same length in metres, spelled in THIS drawing's grid units."""
        return float(value) * self.unit_ratio

    def map(self, name: str, value):
        """`value` as this drawing wants it, by what kind of length `name` is."""
        kind = LENGTH_KIND.get(name)
        if kind in (X, Y):
            return self.coord(value, 0 if kind == X else 1)
        if kind == SIZE:
            return self.size(value)
        return self.physical(value) if kind == PHYSICAL else value

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return "Scale(%r, unit_ratio=%r)" % (self.factor, self.unit_ratio)


class Confirmation:
    """One physical parameter the operator must answer for before it applies."""

    __slots__ = ("name", "offered", "metres", "why")

    def __init__(self, name: str, offered: float, metres: float, why: str):
        self.name, self.offered = name, float(offered)
        self.metres, self.why = float(metres), why

    def describe(self) -> str:
        return ("%s = %s (%.6g m) — %s. Confirm it for your own flow."
                % (self.name, show_value(self.offered), self.metres, self.why))


class Application:
    """A case type fitted to one drawing, and what it still needs answered.

    Produced by `plan`. Nothing is written until `apply`, and `apply` REFUSES
    while any physical parameter is unconfirmed — user story 23 made structural,
    rather than a dialog somebody can forget to show.
    """

    __slots__ = ("case_type", "scale", "values", "confirmations")

    def __init__(self, case_type, scale: Scale, values: dict,
                 confirmations: tuple):
        self.case_type, self.scale = case_type, scale
        self.values, self.confirmations = values, confirmations

    def describe(self) -> list:
        """One line per owned field: what the case type said, what this run gets."""
        out = []
        for name, value in self.values.items():
            was = show_value(self.case_type.fields.values[name])
            by = ("unit" if LENGTH_KIND.get(name) == PHYSICAL
                  else "%.6g" % self.scale.factor)
            now = show_value(value)
            out.append("%s = %s%s" % (name, now, "" if was == now
                                      else "   <- %s x %s" % (was, by)))
        return out

    def unconfirmed(self, confirmed=None) -> tuple:
        answered = set(confirmed or ())
        return tuple(c for c in self.confirmations if c.name not in answered)

    def apply(self, config=None, confirmed=None):
        """`config` with the fitted overlay set, or raise while one is unanswered.

        `confirmed` maps a physical parameter's name to the value the operator
        actually wants — the offered one to accept it, their own to correct it,
        so confirming and adjusting are one act rather than a button people
        learn to click.
        """
        missing = self.unconfirmed(confirmed)
        if missing:
            raise CaseTypeError(
                "this case type carries %d physical parameter(s) that must be "
                "confirmed before it is applied, because they are set by "
                "physics rather than by the size of the body: %s"
                % (len(missing), "; ".join(c.describe() for c in missing)))
        values = dict(self.values)
        asked = {c.name for c in self.confirmations}
        for name, value in dict(confirmed or {}).items():
            if name not in asked:
                # Refused rather than taken as a general override: confirming is
                # ANSWERING a question that was asked, and a confirmed geometric
                # size would be an edit wearing a confirmation's name.
                raise CaseTypeError(
                    "%r is not a physical parameter this case type asks about; "
                    "it asks about %s"
                    % (name, ", ".join(sorted(asked)) or "none"))
            values[name] = value
        return apply_overlay(FieldOverlay(values), config)


def plan(case_type, config) -> Application:
    """Fit `case_type` to the drawing `config` holds.

    `config` is the OPERATOR's own: their geometry list and the roles on it are
    what the ruler is read from, and what the returned `Application` leaves
    untouched. A case type declaring no characteristic length (every one
    authored before #163) fits at 1:1 — and still asks for its physical
    parameters, that question being about physics rather than scale.
    """
    scale = (Scale() if case_type.characteristic is None
             else case_type.characteristic.scale_for(config))
    values, confirmations = {}, []
    unit = units.metres_per_unit(config.length_unit, config.length_unit_metres)
    for name, value in case_type.fields.values.items():
        fitted = scale.map(name, value)
        values[name] = fitted
        if LENGTH_KIND.get(name) == PHYSICAL:
            confirmations.append(Confirmation(
                name, fitted, fitted * unit,
                PHYSICAL_WHY.get(name, "it is fixed by physics, not by the "
                                       "size of the body")))
    return Application(case_type, scale, values, tuple(confirmations))


def fitted_fields(case_type, config) -> FieldOverlay:
    """What the case type wants ON THIS DRAWING — the fair deviation ground.

    A deviation is "the operator moved a field the case type had an opinion
    about", and since #163 the value it has an opinion about is the FITTED one.
    Comparing against the authored number instead would mark every geometric
    field of every rescaled run as deviated, which is the opposite of what the
    marking means.

    Falls back to the authored overlay when the ruler cannot be read off this
    drawing: no ruler means nothing was scaled, so the authored numbers ARE what
    the case type wants. Logged rather than swallowed — the same refusal is a
    hard one at `plan`.
    """
    if case_type.characteristic is None:
        return case_type.fields
    try:
        return FieldOverlay(plan(case_type, config).values)
    except CaseTypeError as exc:
        logger.debug("case type %r could not measure its characteristic length "
                     "on this drawing, so its fields are compared as authored: "
                     "%s", case_type.name, exc, exc_info=True)
        return case_type.fields
