"""The O-grid family's PLAN: what its parameters derive, and the read-out (#198).

Split out of ``topology_ogrid.py`` when that file reached the 500-line standard and
this ticket's advisory did not fit. The seam is derivation against PRESENTATION
plus the object that carries both: what the family computes is next door, what the
panel SHOWS of it is here, and ``Plan`` itself travels with the read-out because
every one of its fields exists to be displayed.

RE-EXPORTED from ``topology_ogrid``, so ``og.Plan`` and ``og.INERT_WHEN_BOUND`` are
the imports every caller and every gate already write; the dependency runs ONE WAY.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.topology_counts import MAX_COUNT, ring_advice

#: Below this circularity a RING is the wrong construction for the body, and the
#: read-out says so (#198). 4*pi*A/P^2 is 1 for a circle and falls as an outline
#: gets longer and thinner; measured on this repo's own bodies, the shipped circle
#: is 0.9999, the 2:1 ellipse 0.8412, a NACA 0012 0.2468 and the flat plate 0.0307.
#: 0.5 is the one value that puts the two round bodies on one side and the two thin
#: ones on the other, and it is a TASTE boundary rather than a measured one -- which
#: is why what it triggers is a sentence and not a refusal.
RING_ADVICE_BELOW = 0.5


#: The field-spec rows the GENERATED far field owns, which naming a far-field
#: geometry makes inert (#197). The C-grid's own mechanism and its own direction:
#: a row is inert because of what the user CONFIGURED, never because of what they
#: typed into it, so these two grey out on the drawn path and are live otherwise.
INERT_WHEN_BOUND = ("topo_ogrid_far_ratio", "topo_ogrid_far_aspect")


@dataclass
class Plan:
    """What the parameters derive, and why — the ONE owner, shared with the panel.

    Every number the read-out displays is computed here, so the panel cannot show a
    figure the generated document does not use. ``problem`` is non-empty exactly when
    :func:`build` would refuse, and carries the same sentence, so the user reads the
    refusal while typing rather than after pressing Generate.
    """

    problem: str = ""
    #: The edge id a binding refusal is about, so the panel that repairs it (#138)
    #: flags that edge rather than re-parsing the sentence.
    broken_edge: str = ""
    blocks: int = 0
    #: Node count of each wall edge, in ring order.
    wall_counts: tuple[int, ...] = ()
    #: Total circumferential CELLS around the body — the N_theta of the radial law.
    n_theta: int = 0
    #: The geometric ratio that gives unit aspect ratio: 1 + 2*pi/N_theta.
    ratio: float = 0.0
    #: The wall first cell that ratio implies, and the one the run actually asks for.
    first_cell_11: float = 0.0
    first_cell: float = 0.0
    radius: float = 0.0
    far_radius: float = 0.0
    radial_derived: int = 0
    radial: int = 0
    overridden: bool = False
    #: True when the derivation hit ``MAX_COUNT``. A silent clamp on a DISPLAYED
    #: derived count is a number the panel presents as the derivation's answer and
    #: is not; review named it, and the read-out now says so.
    clamped: bool = False
    body_segs: tuple[int, ...] = ()
    far_segs: tuple[int, ...] = ()
    ccw: bool = True
    #: True when the far field is DRAWN and bound rather than GENERATED (#197),
    #: the C-grid's own flag under the C-grid's own name. A drawn one carries each
    #: side's condition off its own CAD segment; a generated one carries the run's
    #: BC_GEOM, because a free corner and a declared curve belong to no geometry.
    far_bound: bool = True
    #: The generated ellipse, empty on the drawn path: centre and the two semi-axes.
    far_centre: tuple[float, float] = (0.0, 0.0)
    far_a: float = 0.0
    far_b: float = 0.0
    #: Field-spec rows this plan's own configuration has made INERT — a control the
    #: panel must grey out because nothing reads it any more (#149). NO LONGER
    #: ALWAYS EMPTY: since #197 this family has two modes, and naming a far-field
    #: geometry stops the two generated-path numbers deciding anything. The
    #: mechanism is the C-grid's and so is the direction — a row is inert because
    #: of what the user configured, never because of what they typed into it.
    inert_rows: tuple[str, ...] = ()
    #: 4*pi*A/P^2 of the body, 1 for a circle. Carried so the read-out can say
    #: when a RING is the wrong construction for the shape it has been given.
    circularity: float = 1.0

    @property
    def aspect(self) -> float:
        """How many times longer than tall the cells at the wall are.

        The number the ticket is written around: a 1e-3 first cell where the 1:1
        criterion implies 0.0327 means about 33, and saying "33x" is what tells the
        user their choice has a cost that no single count will remove.
        """
        if self.first_cell <= 0.0:
            return 0.0
        return self.first_cell_11 / self.first_cell

    def lines(self) -> list:
        """The derivation, as the read-out shows it — RESULT AND WORKING, not result.

        #137's central claim is that displaying the derivation is the single most
        useful thing the panel does, so each line carries the quantity it was computed
        from rather than only its answer.
        """
        if self.problem:
            return [f"—  {self.problem}"]
        return [
            f"ring: {self.blocks} blocks, {self.n_theta} circumferential cells "
            f"(counts {', '.join(str(c) for c in self.wall_counts[:8])}"
            f"{'…' if len(self.wall_counts) > 8 else ''})",
            f"1:1 law: q = 1 + 2π/{self.n_theta} = {self.ratio:.5f}  →  first "
            f"cell {self.first_cell_11:.3e} at r = {self.radius:.4g}",
            f"yours: BL_INITIAL_THICKNESS {self.first_cell:.3e}  →  wall cells "
            f"{self.aspect:.3g}x longer than tall",
            ("far field: DRAWN as bound outline"
             if self.far_bound else
             f"far field: GENERATED — ellipse {2 * self.far_a:.4g} x "
             f"{2 * self.far_b:.4g} about ({self.far_centre[0]:.4g}, "
             f"{self.far_centre[1]:.4g}); its sides carry the run's BC_GEOM"),
            f"radial: {self.radial} nodes"
            + (" (overridden)" if self.overridden
               else f" (derived: q from {self.first_cell:.3e} spans "
                    f"{self.far_radius - self.radius:.4g})")
            + (f" — CLAMPED at {MAX_COUNT}, so the first cell you asked for is "
               f"not reachable at this ratio" if self.clamped else ""),
        ] + ring_advice(self.circularity, RING_ADVICE_BELOW)
