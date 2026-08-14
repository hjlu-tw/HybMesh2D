"""One edge's point-distribution settings, and the resampler contract for them.

Qt-free on purpose. These rules used to live inside the controller, reading
thirteen sidebar spin boxes by name and writing straight into
``SegmentModel.parameters`` — so none of them could be exercised without a
QApplication, and the sidebar could not be given an interface without dragging
the contract into a widget.

The contract is NOT "copy the fields into a dict". Three rules make the
``parameters`` dict mean what the resampler reads:

* **A spacing of zero means "this end is unspecified" and must be OMITTED**, not
  written as 0.0. The resampler distinguishes a one-sided distribution from a
  two-sided blend by which keys are PRESENT, so a written zero makes
  ``readPositiveSpacing`` see a present-but-invalid value on both ends.
* **Presence of a spacing key IS the mode.** There is deliberately no separate
  mode flag in ``parameters``, which is what lets a config written by hand or by
  an older build round-trip. ``from_parameters`` recovers the mode the same way.
* **Two sources for one quantity drift apart.** In tanh's By-End-Spacing mode the
  resampler solves the clustering from the spacing, so ``intensity`` must not
  also be written — and when the spacing is left at zero the spec falls back to
  intensity rather than emitting neither.

``spacing_start`` carries tanh's single symmetric field because tanh clusters
both ends equally; either key restores it, since an older or hand-written config
may carry ``spacing_end`` instead.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DistributionSpec:
    """The distribution form's state for ONE strategy, independent of widgets."""

    strategy: str
    n_points: int = 50
    # uniform: "By Spacing"; tanh/geometric: "By End Spacing".
    by_spacing: bool = False
    spacing: float = 0.0          # uniform, By Spacing
    intensity: float = 2.0        # tanh, By Intensity
    spacing_ends: float = 0.0     # tanh, By End Spacing (symmetric)
    sensitivity: float = 1.5      # curvature
    ratio: float = 1.2            # geometric, By Growth Ratio
    ratio_end: float = 1.0        # geometric, By Growth Ratio
    spacing_start: float = 0.0    # geometric, By End Spacing
    spacing_end: float = 0.0      # geometric, By End Spacing

    # ── model → resampler ────────────────────────────────────────────────
    def to_parameters(self) -> dict:
        """The ``SegmentModel.parameters`` dict this spec means.

        Returns a fresh dict: the caller replaces the segment's parameters
        wholesale, so a key this strategy does not use cannot survive a strategy
        change.
        """
        p: dict = {}
        if self.strategy == "uniform":
            if self.by_spacing:
                p["spacing"] = float(self.spacing)
            else:
                p["n_points"] = int(self.n_points)
            return p

        if self.strategy == "tanh":
            p["n_points"] = int(self.n_points)
            ds = float(self.spacing_ends)
            if self.by_spacing and ds > 0.0:
                p["spacing_start"] = ds       # symmetric; spacing_end stays absent
            else:
                p["intensity"] = float(self.intensity)
            return p

        if self.strategy == "cosine":
            p["n_points"] = int(self.n_points)
            return p

        if self.strategy == "curvature":
            p["n_points"] = int(self.n_points)
            p["sensitivity"] = float(self.sensitivity)
            return p

        if self.strategy == "geometric":
            p["n_points"] = int(self.n_points)
            if self.by_spacing:
                for key, value in (("spacing_start", self.spacing_start),
                                   ("spacing_end", self.spacing_end)):
                    if float(value) > 0.0:
                        p[key] = float(value)
            else:
                p["ratio"] = float(self.ratio)
                if float(self.ratio_end) != 1.0:
                    p["ratio_end"] = float(self.ratio_end)
            return p

        return p

    # ── resampler → model ────────────────────────────────────────────────
    @classmethod
    def from_parameters(cls, strategy: str, parameters: dict | None) -> "DistributionSpec":
        """Recover the form state a ``parameters`` dict implies.

        Absent keys fall back to the field defaults, so a segment carrying only
        ``n_points`` still populates every mode's fields with something sane
        rather than zeroing the ones it does not mention.
        """
        p = parameters or {}
        spec = cls(strategy=strategy)
        spec.n_points = int(p.get("n_points", spec.n_points))

        if strategy == "uniform":
            spec.by_spacing = "spacing" in p
            spec.spacing = float(p.get("spacing", spec.spacing))
        elif strategy == "tanh":
            spec.by_spacing = "spacing_start" in p or "spacing_end" in p
            spec.intensity = float(p.get("intensity", spec.intensity))
            spec.spacing_ends = float(
                p.get("spacing_start") or p.get("spacing_end") or 0.0)
        elif strategy == "curvature":
            spec.sensitivity = float(p.get("sensitivity", spec.sensitivity))
        elif strategy == "geometric":
            spec.by_spacing = "spacing_start" in p or "spacing_end" in p
            spec.ratio = float(p.get("ratio", spec.ratio))
            spec.ratio_end = float(p.get("ratio_end", spec.ratio_end))
            spec.spacing_start = float(p.get("spacing_start", spec.spacing_start))
            spec.spacing_end = float(p.get("spacing_end", spec.spacing_end))
        return spec
