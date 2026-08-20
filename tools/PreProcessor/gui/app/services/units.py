"""Length units for the model, and the one place they turn into numbers.

There was no unit system: every length field was a bare number, and nothing recorded
what those numbers meant. That is not a cosmetic gap, because the solver *is*
dimensional. From the UNICONES manual:

    fs_UnitRe:  Freestream unit Reynolds number **per meter**
    Linf:       Length scale used to normalize grid coordinates (**in meter**),
                input 1 if dimensional in meters

and its own sample input reads ``Linf 0.0254  //to convert mesh to meter`` — a grid
authored in inches. So ``Linf`` is not a free parameter: it is exactly *how many metres
one grid unit is*, and Re is ``fs_UnitRe × Linf``. Mesh a millimetre geometry with the
default ``Linf = 1`` and the Reynolds number is wrong by 1000× while every mesh picture
looks perfect. That is the bug class this module exists to close.

**What converts numbers and what does not.** Only two things convert:

* ``Linf``, derived from the declared unit (:func:`metres_per_unit`).
* Coordinates at *import*, when the file's unit differs from the model's.

Everything else — mesh sizes, BL thickness, domain bounds, spacings — is expressed in
the model unit and stays untouched, because the mesher only ever compares those lengths
against each other. Labelling them is worth doing; rescaling them would be a
gratuitous risk. Changing the declared unit therefore never silently rewrites geometry:
that is what :func:`convert_points` is for, called explicitly.

**Custom units are first-class**, not an escape hatch. A unit-chord aerofoil grid
(coordinates 0…1, chord 25.4 mm) is not metres, millimetres or inches — it is a grid
whose unit happens to be 0.0254 m. Supporting that keeps "``Linf`` is derived from the
unit" true for *every* project, so the derivation never has to be switched off for
correctness — only for backward compatibility with configs written before this existed.
"""
from __future__ import annotations

#: Unit code -> (display name, metres per unit, symbol, plural).
#: Factors are exact: the imperial ones are definitions, not measurements.
#: The plural is stored rather than formed by adding "s", because two of the six are
#: irregular ("inches", "feet") and a message reading "a grid in inchs" undermines the
#: authority of the warning it appears in.
#: Adding a unit is one row; nothing else in the codebase enumerates units.
_UNITS: dict[str, tuple[str, float, str, str]] = {
    "m":  ("meter", 1.0, "m", "meters"),
    "cm": ("centimeter", 1.0e-2, "cm", "centimeters"),
    "mm": ("millimeter", 1.0e-3, "mm", "millimeters"),
    "um": ("micrometer", 1.0e-6, "µm", "micrometers"),
    "in": ("inch", 0.0254, "in", "inches"),
    "ft": ("foot", 0.3048, "ft", "feet"),
}

#: Code for a user-defined unit; its factor is carried alongside, not looked up here.
CUSTOM = "custom"

#: The unit a project starts in. SI, and it makes ``Linf = 1`` — which is both the
#: solver's default and what every pre-existing config already implies, so adopting
#: this module changes no existing result.
DEFAULT_UNIT = "m"

#: Spelling variants seen in files and typed by people. Deliberately conservative:
#: "u" alone is not accepted for micro, because a stray letter must not silently
#: become a 1e-6 factor.
_ALIASES = {
    "meter": "m", "meters": "m", "metre": "m", "metres": "m",
    "centimeter": "cm", "centimeters": "cm", "centimetre": "cm", "centimetres": "cm",
    "millimeter": "mm", "millimeters": "mm", "millimetre": "mm", "millimetres": "mm",
    "micrometer": "um", "micrometre": "um", "micron": "um", "microns": "um",
    "µm": "um", "μm": "um",
    "inch": "in", "inches": "in", '"': "in",
    "foot": "ft", "feet": "ft", "'": "ft",
}


def unit_codes() -> list:
    """Selectable unit codes, coarsest first, with ``custom`` last.

    Ordered by physical size rather than alphabetically, so a unit dropdown reads
    like a ruler instead of like a hash table.
    """
    return sorted(_UNITS, key=lambda c: -_UNITS[c][1]) + [CUSTOM]


def is_known(unit: str) -> bool:
    return unit in _UNITS or unit == CUSTOM


def parse(text: str, default: str = DEFAULT_UNIT) -> str:
    """Best-effort unit code from user or file text; ``default`` when unrecognised.

    Never raises and never guesses beyond the alias table: an unknown word falls back
    rather than being mapped to something plausible, because a wrong unit is worse
    than an unset one.
    """
    if not text:
        return default
    key = str(text).strip()
    if key in _UNITS or key == CUSTOM:
        return key
    low = key.lower()
    if low in _UNITS or low == CUSTOM:
        return low
    return _ALIASES.get(low, default)


def symbol(unit: str, custom_name: str = "") -> str:
    """Short symbol for a label, e.g. ``mm``. Custom units show their own name."""
    if unit == CUSTOM:
        return custom_name or "unit"
    entry = _UNITS.get(unit)
    return entry[2] if entry else str(unit)


def name(unit: str, custom_name: str = "") -> str:
    """Full English name, for messages that read as prose."""
    if unit == CUSTOM:
        return custom_name or "custom unit"
    entry = _UNITS.get(unit)
    return entry[0] if entry else str(unit)


def plural(unit: str, custom_name: str = "") -> str:
    """Plural name — "inches", not "inchs"."""
    if unit == CUSTOM:
        return f"{custom_name} units" if custom_name else "custom units"
    entry = _UNITS.get(unit)
    return entry[3] if entry else str(unit)


def metres_per_unit(unit: str, custom_metres: float = 1.0) -> float:
    """How many metres one model unit is — i.e. the solver's ``Linf``.

    An unknown code yields 1.0 rather than raising: a mislabelled project should
    still run as if dimensionless, not fail to open.
    """
    if unit == CUSTOM:
        try:
            v = float(custom_metres)
        except (TypeError, ValueError):
            return 1.0
        return v if v > 0 else 1.0
    entry = _UNITS.get(unit)
    return entry[1] if entry else 1.0


#: ``Linf`` is metres-per-grid-unit, so this is the same number under the name the
#: solver uses. Two names for one quantity is normally a smell; here it documents the
#: bridge between the GUI's vocabulary and the solver's.
linf_for = metres_per_unit


def unit_for_linf(linf: float, rel_tol: float = 1e-6):
    """The unit code whose factor is ``linf``, or None.

    Used to interpret a config written before units existed: ``Linf = 0.0254`` says
    "this grid is in inches" as plainly as a unit field would, so the mismatch can be
    reported concretely instead of as a vague "check your units".
    """
    try:
        v = float(linf)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    for code, (_n, factor, _s, _p) in _UNITS.items():
        if abs(v - factor) <= rel_tol * factor:
            return code
    return None


def convert(value: float, frm: str, to: str,
            frm_metres: float = 1.0, to_metres: float = 1.0) -> float:
    """Convert one length between units.

    Identical units short-circuit, so a no-op conversion cannot introduce
    floating-point drift into a value the user typed.
    """
    if frm == to and not (frm == CUSTOM and frm_metres != to_metres):
        return value
    f = metres_per_unit(frm, frm_metres) / metres_per_unit(to, to_metres)
    return value * f


def scale_factor(frm: str, to: str,
                 frm_metres: float = 1.0, to_metres: float = 1.0) -> float:
    """The multiplier taking a length from ``frm`` to ``to``."""
    if frm == to and not (frm == CUSTOM and frm_metres != to_metres):
        return 1.0
    return metres_per_unit(frm, frm_metres) / metres_per_unit(to, to_metres)


def convert_points(points, frm: str, to: str,
                   frm_metres: float = 1.0, to_metres: float = 1.0):
    """Scale an ``(N, 2)`` coordinate array between units.

    Returns the input object unchanged when the factor is exactly 1, so an import in
    the model's own unit is not silently copied — callers can rely on identity to know
    nothing happened.
    """
    f = scale_factor(frm, to, frm_metres, to_metres)
    if f == 1.0 or points is None:
        return points
    import numpy as np
    return np.asarray(points, dtype=float) * f


# ── plausibility ──────────────────────────────────────────────────────────
#: A GROSS-ERROR NET ONLY, and worth being blunt about its limits: a 4.5 m car body
#: mistakenly declared as metres when the file was millimetres reads as 4500 m, which
#: is inside any band wide enough not to reject real work (aircraft, ships, atmospheric
#: domains). So this catches nothing subtler than ~10⁵x — a model 1e7 m or 1e-9 m
#: across, i.e. an outright wrong unit or a corrupt file.
#:
#: The real defence against a plausible-looking wrong unit is not a threshold at all:
#: it is showing the resulting reference Reynolds number (fs_UnitRe x Linf) on the
#: Solver panel. An engineer recognises Re = 5.8e3 or Re = 5.8e6 for their own case
#: instantly, where the same error hidden inside Linf is invisible. Guessing at size
#: bands would only add false confidence on top of that read-out.
PLAUSIBLE_MIN_M = 1.0e-8
PLAUSIBLE_MAX_M = 1.0e6


def physical_extent(extent: float, unit: str, custom_metres: float = 1.0) -> float:
    """A model extent expressed in metres."""
    return float(extent) * metres_per_unit(unit, custom_metres)


def implausible(extent: float, unit: str, custom_metres: float = 1.0) -> bool:
    """True when the declared unit makes the model absurdly large or small.

    Zero and non-finite extents are NOT implausible — an empty or degenerate
    geometry is a different problem, and reporting it as a unit error would send
    people to the wrong dialog.
    """
    try:
        e = float(extent)
    except (TypeError, ValueError):
        return False
    if not (e > 0) or e != e or e in (float("inf"), float("-inf")):
        return False
    metres = physical_extent(e, unit, custom_metres)
    return not (PLAUSIBLE_MIN_M <= metres <= PLAUSIBLE_MAX_M)


def plausible_alternatives(extent: float, unit: str,
                           custom_metres: float = 1.0) -> list:
    """Unit codes that would put ``extent`` inside the plausible band.

    Offered as candidates, never applied. The check knows the declared unit is
    suspicious; it does not know the right answer, and pretending otherwise is how a
    tool ends up rescaling someone's geometry behind their back.
    """
    try:
        e = float(extent)
    except (TypeError, ValueError):
        return []
    if not (e > 0):
        return []
    out = [code for code in _UNITS
           if code != unit and PLAUSIBLE_MIN_M <= e * _UNITS[code][1] <= PLAUSIBLE_MAX_M]
    return sorted(out, key=lambda c: -_UNITS[c][1])


def format_length(value: float, unit: str, custom_name: str = "",
                  digits: int = 6) -> str:
    """A length with its unit, for a read-out."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if v != v:
        return "—"
    return f"{v:.{digits}g} {symbol(unit, custom_name)}"


def label(text: str, unit: str, custom_name: str = "") -> str:
    """Append the unit to a field label: ``label("Surface size:", "mm")``.

    Keeps a trailing colon where it belongs — ``"Surface size (mm):"`` — because a
    form whose labels end in different characters looks broken.
    """
    sym = symbol(unit, custom_name)
    if text.endswith(":"):
        return f"{text[:-1]} ({sym}):"
    return f"{text} ({sym})"


def describe(unit: str, custom_metres: float = 1.0, custom_name: str = "") -> str:
    """One line naming the unit and its metre factor, for logs and tooltips."""
    m = metres_per_unit(unit, custom_metres)
    return f"{name(unit, custom_name)} (1 {symbol(unit, custom_name)} = {m:g} m)"
