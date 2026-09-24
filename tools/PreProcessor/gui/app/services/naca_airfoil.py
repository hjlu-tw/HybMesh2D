"""The NACA 4-digit aerofoil: the camber/thickness law, in ONE place.

The CAD stage draws this shape and the resampler re-generates it from the same
parameters, so there are two hosts and the law is written twice — once here and
once in ``tools/PreProcessor/include/NacaAirfoil.hpp``. That is not a second
owner by preference. A Python module cannot be read by a C++ binary, and the
converse is worse: the canvas preview runs on every drag of a control point and
must work in a checkout with no build tree at all (every mesher gate in this
repo self-skips when ``build/`` is empty). What makes the pair behave as one is
``tests/test_naca_airfoil_parity.py``, which DRIVES both — the preview through
``GeometryService`` and the law through the real ``surface_resampler`` — and
compares the coordinates numerically. A source scan would not do: #135's own
finding was that a claim about a shared funnel was true in the source while the
edit never reached it.

Everything in here is therefore written to be mirrored literally: powers are
spelled as repeated multiplication rather than ``**`` so both hosts evaluate the
same expression, and the two endpoints that must be exact are ASSIGNED rather
than computed (see ``_snap``).

Qt-free and stdlib-only, so a headless gate, the resampler-side fixtures and the
GUI all reach it the same way.

THE SHAPE, and the two points it is split at:

    upper   trailing edge -> leading edge   (the +y surface)
    lower   leading edge  -> trailing edge  (the -y surface)
    te      lower TE      -> upper TE       (the base of a BLUNT trailing edge)
    full    the closed loop: upper + lower (+ te when blunt)

A SHARP trailing edge has no ``te`` part — the two surfaces meet at one point —
and asking for one is refused rather than answered with a zero-length segment
(:class:`NacaError`). That is the decision #147 asked to be made and stated: a
blunt trailing edge is PRODUCED here, correctly, with its base as a real third
segment; it is the C-grid TEMPLATE (#148) that refuses one, because its four
blocks meet at a single declared corner that a blunt edge does not have.
"""
from __future__ import annotations

import math

#: The parts an aerofoil can be asked for. ``full`` is the whole closed loop;
#: the others are the pieces the CAD stage creates it as, so a topology template
#: can bind to the upper surface, the lower surface or the trailing-edge base by
#: the ordinary stable segment id and needs no new resolution rule.
PARTS = ("full", "upper", "lower", "te")

#: The trailing-edge coefficient. The classic NACA report's value is -0.1015,
#: which leaves the surface OPEN at x = 1 by 0.0021*t of chord (a blunt, and
#: physically real, trailing edge). -0.1036 is the closed variant: the five
#: coefficients then sum to zero, so y(1) is zero and the two surfaces meet.
_TE_COEFF_SHARP = -0.1036
_TE_COEFF_BLUNT = -0.1015

#: Per-parameter defaults. Mirrored by ``shape_spec.DEFAULTS["naca4"]``; kept
#: here as well because the resampler-side and headless callers read this module
#: without importing the GUI's model layer.
DEFAULTS = {
    "designation": "0012",
    "chord": 1.0,
    "x_le": 0.0,
    "y_le": 0.0,
    "alpha_deg": 0.0,
    "sharp_te": True,
    "part": "full",
}


class NacaError(ValueError):
    """A NACA aerofoil could not be generated, with the reason named.

    Raised rather than returning an empty list so the message reaches the user
    log instead of an edge silently failing to draw.
    """


def parse_designation(text) -> tuple[float, float, float]:
    """``"2412"`` -> ``(m, p, t)`` as FRACTIONS of chord: 0.02, 0.4, 0.12.

    The four digits are max camber in per cent, its chordwise position in
    tenths, and thickness in per cent. Anything else is a :class:`NacaError`
    naming what was given.
    """
    s = str(text).strip().upper()
    if s.startswith("NACA"):
        s = s[4:].strip()
    if len(s) != 4 or not s.isdigit():
        raise NacaError(
            "NACA designation %r is not four digits (e.g. 0012 or 2412)." % text)
    m = int(s[0]) / 100.0
    p = int(s[1]) / 10.0
    t = int(s[2:]) / 100.0
    if t <= 0.0:
        raise NacaError(
            "NACA designation %r has zero thickness; the last two digits are "
            "thickness in per cent of chord." % text)
    # A cambered section needs its camber position: '2012' puts maximum camber
    # at x = 0, where the two-branch law divides by p*p.
    if m > 0.0 and p <= 0.0:
        raise NacaError(
            "NACA designation %r has camber (first digit %s) but places it at "
            "x = 0 (second digit 0); a cambered section needs 1-9 there."
            % (text, s[0]))
    return m, p, t


def half_thickness(x: float, t: float, sharp_te: bool = True) -> float:
    """The 4-digit thickness law: half the section thickness at chord fraction x."""
    a4 = _TE_COEFF_SHARP if sharp_te else _TE_COEFF_BLUNT
    xx = x * x
    return 5.0 * t * (0.2969 * math.sqrt(x if x > 0.0 else 0.0)
                      - 0.1260 * x - 0.3516 * xx + 0.2843 * xx * x
                      + a4 * xx * xx)


def camber(x: float, m: float, p: float) -> tuple[float, float]:
    """The mean line and its slope at chord fraction x -> ``(yc, dyc_dx)``.

    Symmetric sections (m == 0) are flat, and are taken by the first branch so
    the cambered formulae never divide by a zero p.
    """
    if m <= 0.0 or p <= 0.0 or p >= 1.0:
        return 0.0, 0.0
    if x < p:
        return (m / (p * p) * (2.0 * p * x - x * x),
                2.0 * m / (p * p) * (p - x))
    q = 1.0 - p
    return (m / (q * q) * ((1.0 - 2.0 * p) + 2.0 * p * x - x * x),
            2.0 * m / (q * q) * (p - x))


def surface_point(x: float, m: float, p: float, t: float,
                  sharp_te: bool, upper: bool) -> tuple[float, float]:
    """One point of the upper or lower surface at chord fraction x, unit chord."""
    yt = half_thickness(x, t, sharp_te)
    yc, dyc = camber(x, m, p)
    theta = math.atan(dyc)
    st = math.sin(theta)
    ct = math.cos(theta)
    if upper:
        return (x - yt * st, yc + yt * ct)
    return (x + yt * st, yc - yt * ct)


def _cosine_x(k: int, n: int, from_te: bool) -> float:
    """Chord fraction of sample k of n, cosine-spaced so the samples crowd at
    the leading and trailing edges — where the surface actually turns.

    ``from_te`` runs 1 -> 0 (the upper surface's direction), otherwise 0 -> 1.
    Both ends are exact: ``cos(0)`` is 1.0 and ``cos(pi)`` is -1.0 in IEEE
    double, so the first and last x are exactly 1 and 0 with no snapping.
    """
    c = math.cos(math.pi * k / (n - 1))
    return 0.5 * (1.0 + c) if from_te else 0.5 * (1.0 - c)


def _surface(n: int, m: float, p: float, t: float, sharp_te: bool,
             upper: bool) -> list:
    """``n`` points along one surface, in that surface's own direction."""
    pts = [surface_point(_cosine_x(k, n, upper), m, p, t, sharp_te, upper)
           for k in range(n)]
    return _snap(pts, m, p, t, sharp_te, upper)


def _snap(pts: list, m: float, p: float, t: float, sharp_te: bool,
          upper: bool) -> list:
    """Pin the two ends of a surface onto the points they are DEFINED to be.

    The leading edge is (0, 0) for every 4-digit section (both the thickness and
    the camber vanish there), and a sharp trailing edge is (1, 0) because the
    five thickness coefficients sum to zero. Neither comes out exactly from the
    arithmetic — the coefficients are decimal literals, so the sum is ~1e-17 —
    and "exactly" is the whole point: it is where the upper surface meets the
    lower one, and a block corner sits there.
    """
    le = (0.0, 0.0)
    te = (1.0, 0.0) if sharp_te else _blunt_te(m, p, t, upper)
    if upper:                                  # TE -> LE
        pts[0], pts[-1] = te, le
    else:                                      # LE -> TE
        pts[0], pts[-1] = le, te
    return pts


def _blunt_te(m: float, p: float, t: float, upper: bool) -> tuple[float, float]:
    """The trailing-edge point of one surface when the section is left OPEN."""
    return surface_point(1.0, m, p, t, False, upper)


def airfoil_points(designation="0012", n: int = 100, part: str = "full",
                   chord: float = 1.0, x_le: float = 0.0, y_le: float = 0.0,
                   alpha_deg: float = 0.0, sharp_te: bool = True) -> list:
    """The requested PART of a NACA 4-digit aerofoil as ``[(x, y), ...]``.

    ``n`` is the number of points on the part (for ``full``, of the closed loop).
    ``alpha_deg`` is the angle of attack: the section is rotated by MINUS alpha
    about its leading edge, so a positive alpha pitches the nose up against a
    flow running along +x. ``chord`` scales, ``(x_le, y_le)`` places the leading
    edge.

    Raises :class:`NacaError` for an unusable designation, an unknown part, a
    non-positive chord, or a ``te`` part on a section whose trailing edge is
    sharp (there is no such segment — see the module docstring).
    """
    m, p, t = parse_designation(designation)
    part = str(part or "full").lower()
    if part not in PARTS:
        raise NacaError("Unknown aerofoil part %r; expected one of %s."
                        % (part, ", ".join(PARTS)))
    chord = float(chord)
    if chord <= 0.0:
        raise NacaError("Aerofoil chord must be positive (got %g)." % chord)
    n = max(2, int(n))
    sharp_te = bool(sharp_te)

    if part == "te":
        if sharp_te:
            raise NacaError(
                "This aerofoil has a SHARP trailing edge, so it has no "
                "trailing-edge segment: the upper and lower surfaces meet at "
                "one point. Turn the sharp trailing edge off to give it a "
                "blunt base.")
        lo = _blunt_te(m, p, t, upper=False)
        up = _blunt_te(m, p, t, upper=True)
        local = [(lo[0] + (up[0] - lo[0]) * k / (n - 1),
                  lo[1] + (up[1] - lo[1]) * k / (n - 1)) for k in range(n)]
    elif part == "upper":
        local = _surface(n, m, p, t, sharp_te, upper=True)
    elif part == "lower":
        local = _surface(n, m, p, t, sharp_te, upper=False)
    else:
        local = _full_loop(n, m, p, t, sharp_te)
    return [_place(x, y, chord, x_le, y_le, alpha_deg) for x, y in local]


def _full_loop(n: int, m: float, p: float, t: float, sharp_te: bool) -> list:
    """The closed loop, TE -> LE -> TE, whose first and last point coincide.

    The budget is split evenly between the two surfaces; a blunt section spends
    ``_TE_LOOP_POINTS`` more across its base so the gap survives the closed-loop
    seam weld the resampler applies (it pulls the last point onto the first when
    they are within a fraction of the local spacing — on a blunt section that
    would close the very gap this shape exists to keep).
    """
    per_side = max(2, (n + 1) // 2)
    up = _surface(per_side, m, p, t, sharp_te, upper=True)
    lo = _surface(per_side, m, p, t, sharp_te, upper=False)
    loop = up + lo[1:]                    # the leading edge is shared, not repeated
    if sharp_te:
        loop.append(up[0])                # close exactly on the trailing edge
        return loop
    lo_te, up_te = lo[-1], up[0]
    k_max = _TE_LOOP_POINTS
    loop += [(lo_te[0] + (up_te[0] - lo_te[0]) * k / k_max,
              lo_te[1] + (up_te[1] - lo_te[1]) * k / k_max)
             for k in range(1, k_max + 1)]
    return loop


#: Points spent on the base of a blunt trailing edge inside the ``full`` loop.
#: Small on purpose — the base is a straight line a few thousandths of a chord
#: long — but never 1, or the closing edge is a single jump the seam weld reads
#: as an accidental gap.
_TE_LOOP_POINTS = 4


def _place(x: float, y: float, chord: float, x_le: float, y_le: float,
           alpha_deg: float) -> tuple[float, float]:
    """Unit-chord (x, y) -> world, scaled, pitched by -alpha, LE at (x_le, y_le)."""
    a = -float(alpha_deg) * math.pi / 180.0
    ca = math.cos(a)
    sa = math.sin(a)
    return (x_le + chord * (x * ca - y * sa),
            y_le + chord * (x * sa + y * ca))


def params_points(params: dict, n: int) -> list:
    """``airfoil_points`` from a segment's ``parameters`` dict, defaults applied.

    The one entry point both hosts' shape code uses, so "which key means what"
    is answered once.
    """
    p = params or {}
    return airfoil_points(
        designation=p.get("designation", DEFAULTS["designation"]),
        n=n,
        part=p.get("part", DEFAULTS["part"]),
        chord=float(p.get("chord", DEFAULTS["chord"])),
        x_le=float(p.get("x_le", DEFAULTS["x_le"])),
        y_le=float(p.get("y_le", DEFAULTS["y_le"])),
        alpha_deg=float(p.get("alpha_deg", DEFAULTS["alpha_deg"])),
        sharp_te=bool(p.get("sharp_te", DEFAULTS["sharp_te"])),
    )


def segment_parts(sharp_te: bool) -> tuple:
    """The parts a DRAWN aerofoil is created as — the segmentation itself.

    Two for a sharp section (split at the trailing edge and at the leading
    edge), three for a blunt one (its base is a segment of its own). This is
    what "arrives already segmented" means, and it is the only place that
    decides it.
    """
    return ("upper", "lower") if sharp_te else ("upper", "lower", "te")


def part_node_counts(n: int, parts) -> dict:
    """How the drawn section's node budget is split across its parts.

    The two surfaces share it; the trailing-edge base does NOT take a share of
    it, because it is a straight line a few thousandths of a chord long and a
    proportional split would give it one point. It gets ``TE_PART_POINTS``,
    which is enough for the mesher to see a base rather than a corner cut.
    """
    parts = tuple(parts)
    surfaces = [q for q in parts if q in ("upper", "lower")]
    per = max(2, int(n) // max(1, len(surfaces))) if surfaces else 2
    return {q: (TE_PART_POINTS if q == "te" else per) for q in parts}


#: Nodes on a blunt trailing edge's own segment.
TE_PART_POINTS = 5


def part_label(part: str) -> str:
    """How a part is named to the user (the edge list, the log)."""
    return {"upper": "upper surface", "lower": "lower surface",
            "te": "trailing edge", "full": "aerofoil"}.get(part, part)
