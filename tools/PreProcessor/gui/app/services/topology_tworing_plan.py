"""The two-ring O-grid's PLAN: what the parameters derive, and the read-out (#199).

Split out of ``topology_tworing.py`` under this repo's ~500-line standard when that
file took the generated far field (#199), for the reason and in the shape
``topology_ogrid_plan.py`` was split out at #198: the derivation and its sentences are
one job, the document builder is another, and the one that grows is the sentences.
Qt-free, mesher-free, canvas-free, like every module in this package.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.topology_counts import MAX_COUNT, ring_advice

#: Below this circularity the read-out says a RING is the wrong construction for this
#: body. :data:`topology_ogrid_plan.RING_ADVICE_BELOW`'s value and its whole argument,
#: imported rather than restated so the two ring families cannot drift apart on what
#: counts as thin. Re-exported here only so this module reads as one unit.
from app.services.topology_ogrid_plan import RING_ADVICE_BELOW

#: The two rows a NAMED far field makes inert (#199). The O-grid's mechanism and
#: its direction: a row is inert because of what the user CONFIGURED, never because
#: of what they typed into it — so naming a far field greys these two, and emptying
#: the name brings them back rather than leaving a stale grey.
INERT_WHEN_BOUND = ("topo_tworing_far_ratio", "topo_tworing_far_aspect")


@dataclass
class Plan:
    """What the parameters derive, and why — the ONE owner, shared with the panel.

    Every number the read-out displays is computed here, so the panel cannot show a
    figure the generated document does not use. ``problem`` is non-empty exactly when
    :func:`build` would refuse, and carries the same sentence.
    """

    problem: str = ""
    #: The edge id a binding refusal is about, so the repair panel (#138) flags that
    #: edge rather than re-parsing the sentence.
    broken_edge: str = ""
    #: Blocks PER RING; the document declares twice this many.
    blocks: int = 0
    wall_counts: tuple[int, ...] = ()
    n_theta: int = 0
    ratio: float = 0.0
    first_cell: float = 0.0
    radius: float = 0.0
    seam_radius: float = 0.0
    far_radius: float = 0.0
    inner: int = 0
    inner_derived: int = 0
    inner_overridden: bool = False
    inner_clamped: bool = False
    outer: int = 0
    outer_derived: int = 0
    outer_overridden: bool = False
    outer_clamped: bool = False
    #: The chord of edge ``ri0`` — the length the mesher distributes the inner ring's
    #: nodes along, and therefore the length ``ds_start`` is solved from.
    inner_chord: float = 0.0
    #: The outer ring's first cell: the inner ring's own LAST interval.
    ds_start: float = 0.0
    body_segs: tuple[int, ...] = ()
    seam_segs: tuple[int, ...] = ()
    far_segs: tuple[int, ...] = ()
    ccw: bool = True
    seam_geom: str = ""
    #: ``4*pi*A/P^2`` of the body, for the one line that says a RING is the wrong
    #: construction for it (#198). The O-grid's measure and the O-grid's threshold.
    circularity: float = 1.0
    #: True when the user NAMED a far-field geometry. False is the generated path and
    #: is not a degraded state; the two are told apart by the stored NAME and never by
    #: whether the lookup found anything, so a name that resolves to nothing is a
    #: refusal rather than a quiet generation (#197's rule, #199's second caller).
    far_bound: bool = True
    #: The generated ellipse, written through by ``topology_genfar.derive``. Unset on
    #: the drawn path, where the far field is a geometry and these mean nothing.
    far_centre: tuple = (0.0, 0.0)
    far_a: float = 0.0
    far_b: float = 0.0
    #: Rows this configuration has made inert (#149). The two generated-far-field
    #: rows, once a far field is NAMED — the C-grid's mechanism and its direction:
    #: a row is inert because of what the user CONFIGURED, never because of what they
    #: typed into it.
    inert_rows: tuple[str, ...] = ()

    def lines(self) -> list:
        """The derivation, RESULT AND WORKING — #137's rule, and the read-out's text."""
        if self.problem:
            return [f"—  {self.problem}"]
        return [
            f"rings: {self.blocks} inner + {self.blocks} outer blocks, "
            f"{self.n_theta} circumferential cells "
            f"(counts {', '.join(str(c) for c in self.wall_counts[:8])}"
            f"{'…' if len(self.wall_counts) > 8 else ''})",
            f"1:1 law: q = 1 + 2π/{self.n_theta} = {self.ratio:.5f}",
            f"inner: {self.inner} nodes over r {self.radius:.4g} → "
            f"{self.seam_radius:.4g}"
            + (" (overridden)" if self.inner_overridden
               else f" (derived from BL_INITIAL_THICKNESS {self.first_cell:.3e})")
            + (f" — CLAMPED at {MAX_COUNT}" if self.inner_clamped else ""),
            f"seam: ds_start {self.ds_start:.6e} — DERIVED, the inner ring's own last "
            f"interval over its {self.inner_chord:.4g} chord, so changing the inner "
            f"count, the seam or the wall height moves it",
            f"outer: {self.outer} nodes over r {self.seam_radius:.4g} → "
            f"{self.far_radius:.4g}"
            + (" (overridden)" if self.outer_overridden
               else " (derived: q from that seam spacing)")
            + (f" — CLAMPED at {MAX_COUNT}" if self.outer_clamped else ""),
            # MORE CORNERS IS A QUALITY KNOB HERE, which it is not on the O-grid —
            # but WHICH way of adding them matters, and the read-out says so because
            # nothing else would. #155's research note measured the RE-SEGMENTING
            # ladder and this family's first draft quoted it for `splits`; the Spec
            # review measured `splits` itself and the two ladders are different. Both
            # are on a 2:1 ellipse at 96 nodes around, unsmoothed, worst wall first
            # cell. Gate: `test_topology_tworing.py` check 24 re-measures both.
            f"corners: {self.blocks} edges per ring. The seam's nodes track the body's "
            f"by ARC LENGTH, so the two rings are normal-opposite only on a circle, "
            f"and the wall's first cell is out by that much before smoothing.",
            "  · cutting the body AND the seam into more SOURCE segments, at the same "
            "points, shrinks it fastest — 7.06% → 1.82% → 0.21% at 4, 8 and 16 "
            "segments per ring, because those corners pair point for point.",
            "  · raising Splits Per Segment helps LESS — 7.06% → 2.67% → 1.03% at the "
            "same 4, 8 and 16 — because a split corner sits at equal arc FRACTION and "
            "inherits the error. Unsmoothed only: the default 20 smoothing sweeps "
            "repair either to 0.000000.",
            f"seam BC: its {self.blocks} edges FOLLOW '{self.seam_geom}' as interfaces "
            f"and export no face, so whatever you labelled those segments reaches "
            f"nothing.",
        ] + self._far_lines() + ring_advice(self.circularity, RING_ADVICE_BELOW)

    def _far_lines(self) -> list:
        """What the OUTER boundary is, and only when it is not a geometry.

        The drawn path says nothing here, because the far-field row already names the
        geometry and a line repeating it would be the read-out's own noise. The
        generated path has to say three things nothing else can: the shape, that its
        corners pair with the SEAM rather than with the body, and the one condition
        it can carry.
        """
        if self.far_bound:
            return []
        return [
            f"far field: GENERATED — one ellipse {2 * self.far_a:.4g} by "
            f"{2 * self.far_b:.4g} about the body's centroid (equivalent radius "
            f"{self.far_radius:.4g}), declared as the curve it is rather than "
            f"written to a file.",
            "  · its corners pair by ARC LENGTH with the SEAM's, not with the "
            "body's: the seam is the outer blocks' inner side, so that is the ring "
            "the outer blocks have to stay normal to.",
            "  · every generated side carries the run's BC_GEOM, so an outer "
            "boundary needing an inlet and an outlet on different parts of it still "
            "has to be drawn.",
        ]
