"""Which legs of a restarted solve are playing, and the controls that say so.

Split out of ``result_playback_mixin`` when that file passed the GUI length
budget — the same split, for the same reason, that ``result_scale_lock_mixin``
already is: the transport, the colour scale and the leg selection are three
concerns that happen to share one toolbar row.

A restarted solve is several files (#32) and every leg of it plays as one
animation by default. Two controls narrow that, and their PRECEDENCE is stated
rather than raced, the way #24's colour ranges are:

* **"This leg only"** (#43) restricts to the file that was opened, and wins
  while it is ticked;
* **"Legs…"** (USER-REQUESTED 2026-08-27) picks an arbitrary subset, and is what
  the load-time prompt writes its answer into.

Both are OFF for every load and neither is persisted: a solve must not inherit
another's ticks. Unticking "This leg only" restores the subset rather than the
whole solve, so the override does not destroy the answer it overrode.

Both are shown on the LEG count and never on the frame count. Three one-frame
legs is an ordinary restarted run, and a control keyed on frames hides itself
the moment it is used — the escape closing behind the user, which is the bug #43
found for "This leg only" and which the picker would have repeated.
"""
from __future__ import annotations

from app.views.result_leg_picker import ask_legs


class ResultLegSelectMixin:
    """The leg-selection controls' behaviour. The widgets themselves are built
    with the rest of the transport row, which is where they are laid out."""

    def _on_one_leg_toggled(self, _on=None):
        """Rebuild the series with / without the other legs.

        The landing frame is the last frame of the leg the user OPENED, which is
        where the load put them too — so the control moves the surrounding
        animation and not the picture in front of them.
        """
        if getattr(self, "_result_path", ""):
            self.reload_legs()

    def _on_pick_legs(self):
        """Reopen the leg picker and rebuild the series from the answer.

        Pre-ticked with the CURRENT selection rather than with everything, so
        reopening the dialog shows what is playing instead of silently proposing
        to undo the last answer. Cancel returns None, which means "every leg" —
        the same meaning it has at load time.
        """
        legs = self._legs
        if legs is None or len(legs) < 2:
            return
        current = getattr(self, "_leg_selection", None)
        self._leg_selection = ask_legs(self, legs.legs,
                                       getattr(self, "_result_path", ""),
                                       legs.warnings, preselect=current)
        if getattr(self, "_result_path", ""):
            self.reload_legs()

    def _one_leg_only(self) -> bool:
        cb = getattr(self, "one_leg_cb", None)
        return bool(cb.isChecked()) if cb is not None else False

    def _legs_tip(self) -> str:
        """How far each leg of this solve got, for the two widgets that name a leg.

        The frame read-out and the frame selector both say WHICH leg a frame
        belongs to, so the count belongs beside them rather than in a log line the
        user has to scroll back to (#43). "" for a solve with one leg: there is
        nothing to distinguish.
        """
        legs = self._legs
        if not legs or len(legs) < 2:
            return ""
        rows = []
        for leg in legs.legs:
            if not leg.span.known:
                rows.append(f"{leg.key}: how far it got is not recorded")
                continue
            # Both caveats, the same two the restart chooser's tooltip carries:
            # #43 unified the ARITHMETIC so the two windows cannot disagree about
            # a number, and reporting that number with different confidence in
            # each window would put the disagreement back one level up.
            how = "recorded" if leg.span.recorded else "recomputed"
            rows.append(f"{leg.key}: reached iteration {leg.span.end} ({how})")
        return ("This solve's legs, oldest first:\n" + "\n".join(rows)
                + "\nAn upper bound: a run interrupted part-way through a print "
                  "interval got no further than this.")

