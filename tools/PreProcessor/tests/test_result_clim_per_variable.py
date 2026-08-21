#!/usr/bin/env python3
"""A manual colour range belongs to ONE variable (issue #24).

USER-REPORTED (2026-08-20): on the Results tab, Auto off → Min/Max → Apply set a
range that was then used for **every** variable, so a pressure range coloured
vorticity — a field that renders as one flat colour or one saturated blob, with
the Min/Max boxes still showing the old numbers as if they belonged to it. The
manual range was ONE unkeyed tuple (``ResultCanvas._clim``), and nothing dropped
or re-keyed it when the variable changed.

The playback lock already had this right: ``_range_lock`` carries
``_range_lock_var`` beside it and is invalidated when the variable moves. The
manual clim is the same fact and is now keyed the same way — a dict from
variable code to (vmin, vmax) — rather than a second pattern.

What is pinned here:
  1. Per-variable memory: a custom range on A does not colour B, and returning to
     A restores A's numbers.
  2. Seed on first use: in Custom mode a variable with no remembered pair is
     seeded from ITS OWN data range and remembered — never from another variable.
  3. Mode stays GLOBAL: one Auto/Custom checkbox with one meaning.
  4. No drift across frames: stepping a transient run re-uses the remembered pair
     instead of re-seeding it from the frame on screen.
  5. Precedence untouched: manual > playback lock > auto data range.
  6. A different result file clears the store rather than colouring a new run with
     the old one's numbers.
  7. The panel's Min/Max boxes follow the range in force through
     ``result_rendered`` — refreshed when the variable moves OR when the canvas
     reports the range was SEEDED (which is how a newly loaded run reaches them
     under an unchanged variable name), and NOT by an unrelated re-render, which
     would wipe a number being typed.
  8. The Auto checkbox IS the mode, in BOTH directions: unticking it used to tell
     the canvas nothing until Apply, leaving the panel in Custom while the canvas
     auto-scaled every frame and the boxes froze.

Every check was verified by injection: writing the manual range to every key
(the reported bug) breaks 1/2/3/4; seeding without remembering breaks 2/4;
dropping the store in ``set_clim_auto`` breaks 3/4; removing the load-time
``reset_clim_store`` breaks 6; the pre-fix panel wiring (refresh only in Auto)
breaks 7, refreshing on every render breaks 7's other half, and keying the
refresh on the variable NAME alone — the first version of this fix — breaks 7's
new-file check while every other check stays green; and restoring
``_on_auto_toggled``'s one-way `and checked` breaks 8.

Blind spot, named rather than papered over: check 5 pins the precedence at the
layer that actually decides it — ``playback_clim`` returns None unless
``_clim_auto`` — so ``render``'s own manual-before-locked ordering is redundant
and reordering it alone is invisible here. Making it observable would require a
state the code cannot reach (a lock reported while a manual range is in force).

Run:  python3 tools/PreProcessor/tests/test_result_clim_per_variable.py
"""
import os
import sys
import tempfile
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >180s", flush=True)
    os._exit(99)


_wd = threading.Timer(180, _watchdog)
_wd.daemon = True
_wd.start()

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.views.result_canvas import ResultCanvasView  # noqa: E402
from app.views.panels.result_panel import ResultControlPanel  # noqa: E402


# --------------------------------------------------------------------------- #
# A unit square split into two triangles, N zones. 'p' grows with the frame and
# is strictly positive; 'u' is symmetric about zero — two variables whose ranges
# cannot be mistaken for each other, which is the whole point of the bug.
#   frame k:  p in [k+1, k+2]      u in [-(k+1), k+1]
# --------------------------------------------------------------------------- #
def write_transient(path, n_zones=5):
    L = ['Title = "test"', 'variables = "x", "y", "p", "u"']
    for k in range(n_zones):
        L += ['zone t = "time 0" N=4 E=2 ZONETYPE=FETRIANGLE',
              ' DATAPACKING = BLOCK VARLOCATION = ( [1-2] = NODAL, [3-4] = CELLCENTERED )',
              '0 1 1 0',                       # x
              '0 0 1 1',                       # y
              f'{k + 1.0} {k + 2.0}',          # p
              f'{-(k + 1.0)} {k + 1.0}',       # u
              '1 2 3', '1 3 4']
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")
    return path


def write_shifted(path):
    """A DIFFERENT run: same mesh, values an order of magnitude away, so a store
    carried over from the previous file is visible as a wrong colour range."""
    L = ['Title = "test"', 'variables = "x", "y", "p", "u"',
         'zone t = "time 0" N=4 E=2 ZONETYPE=FETRIANGLE',
         ' DATAPACKING = BLOCK VARLOCATION = ( [1-2] = NODAL, [3-4] = CELLCENTERED )',
         '0 1 1 0', '0 0 1 1',
         '100.0 200.0', '-100.0 100.0',
         '1 2 3', '1 3 4']
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")
    return path


tmp = tempfile.mkdtemp(prefix="hybmesh_clim_")
multi = write_transient(os.path.join(tmp, "xtecp_sol_allz.dat.gui"), n_zones=5)
other = write_shifted(os.path.join(tmp, "other_run.dat.gui"))


class Applied:
    """Records the clim the canvas actually rendered with, off its own signal —
    the same channel the panel listens on, so the test cannot read a value the
    panel could not."""

    def __init__(self, canvas):
        self.last = None
        self.n = 0
        canvas.result_rendered.connect(self._on)

    def _on(self, info):
        self.last = (info["var"], info["vmin"], info["vmax"])
        self.n += 1

    @property
    def rng(self):
        return None if self.last is None else (self.last[1], self.last[2])

    @property
    def var(self):
        return None if self.last is None else self.last[0]


def pick_var(v, code):
    """Switch the displayed variable the way the user does — through the combo,
    so `_on_control_changed` runs and the canvas re-renders."""
    idx = v.var_combo.findData(code)
    assert idx >= 0, code
    v.var_combo.setCurrentIndex(idx)


v = ResultCanvasView()
seen = Applied(v)
v.load_result_path(multi)
v.show_frame(0)
pick_var(v, "p")

# ── 1. per-variable memory ────────────────────────────────────────────────
check(v._clim_auto and seen.rng == (1.0, 2.0),
      f"1. (precondition) Auto colours 'p' by its own data range ({seen.rng})")

v.set_clim(-10.0, 10.0)
check(not v._clim_auto and seen.rng == (-10.0, 10.0),
      f"1. Apply switches to Custom and renders the typed range ({seen.rng})")

pick_var(v, "u")
check(seen.var == "u" and seen.rng == (-1.0, 1.0),
      f"1. switching to 'u' colours it by ITS OWN range, not 'p''s (-10, 10) — "
      f"the reported bug ({seen.rng})")

v.set_clim(-3.0, 4.0)
check(seen.rng == (-3.0, 4.0),
      f"1. 'u' takes its own custom range ({seen.rng})")

pick_var(v, "p")
check(seen.rng == (-10.0, 10.0),
      f"1. coming back to 'p' restores ITS custom numbers — no re-typing to flip "
      f"between variables during a review ({seen.rng})")
pick_var(v, "u")
check(seen.rng == (-3.0, 4.0),
      f"1. ...and both are remembered at once ({seen.rng})")

# ── 2. seed on first use, from the variable's own data ────────────────────
check(v._clim_by_var == {"p": (-10.0, 10.0), "u": (-3.0, 4.0)},
      f"2. the store is keyed by variable, mirroring _range_lock_var "
      f"({v._clim_by_var})")

v._clim_by_var.pop("u")          # 'u' as a variable never seen in Custom mode
v.render()
check(v._clim_by_var.get("u") == (-1.0, 1.0) and seen.rng == (-1.0, 1.0),
      f"2. a variable with no remembered pair is SEEDED from its own data range "
      f"and remembered, so Custom mode never inherits another variable's numbers "
      f"({v._clim_by_var.get('u')})")

# ── 3. the mode is global, the numbers are not ────────────────────────────
v.set_clim_auto(True)
check(v._clim_auto and seen.rng == (-1.0, 1.0),
      "3. Auto is one checkbox with one meaning — turning it on applies to "
      "whatever is displayed")
pick_var(v, "p")
check(v._clim_auto and seen.rng == (1.0, 2.0),
      f"3. ...and stays on across a variable switch, rather than becoming a "
      f"second hidden per-variable mode ({seen.rng})")
check(v._clim_by_var.get("p") == (-10.0, 10.0),
      "3. Auto does not forget the custom numbers; Custom brings them back")
v.set_clim_auto(False)
check(seen.rng == (-10.0, 10.0),
      f"3. back to Custom, 'p''s own remembered range renders again ({seen.rng})")

# With nothing displayed there is no variable to own a range, so Apply is a
# no-op rather than a mode flip with no numbers behind it (found in review: the
# first version set `_clim_auto = False` before discovering it had no key).
blank = ResultCanvasView()
blank.set_clim(-1.0, 1.0)
check(blank._clim_auto and blank._clim_by_var == {},
      f"3. set_clim with no variable displayed changes NOTHING — it does not "
      f"half-apply ({blank._clim_auto}, {blank._clim_by_var})")

# ── 4. no drift across frames ─────────────────────────────────────────────
# 'p' grows with the frame, so a range re-seeded per frame would MOVE. That is
# the failure this check exists for: the manual range must be the user's number
# on every frame of the run.
ranges = []
for k in range(5):
    v.show_frame(k)
    ranges.append(seen.rng)
check(ranges == [(-10.0, 10.0)] * 5,
      f"4. stepping every frame keeps the SAME manual range — no re-seed, no "
      f"drift ({ranges})")

v._clim_by_var.pop("p")
v.show_frame(2)
first = seen.rng
v.show_frame(3)
check(first == (3.0, 4.0) and seen.rng == (3.0, 4.0),
      f"4. a seed is paid ONCE, on the frame it happened on, and then holds — "
      f"playback must not re-seed every frame ({first} then {seen.rng})")

# ── 5. precedence: manual > lock > auto ───────────────────────────────────
pick_var(v, "p")
v.set_clim_auto(True)
v.lock_scale_cb.setChecked(True)
check(v.playback_clim() == (1.0, 6.0) and seen.rng == (1.0, 6.0),
      f"5. with Auto on, 'Lock scale' pins the run-wide range ({seen.rng})")
v.set_clim(0.0, 0.5)
check(v.playback_clim() is None and seen.rng == (0.0, 0.5),
      f"5. a manual range still WINS over the lock — keying it by variable did "
      f"not change the precedence ({seen.rng})")
v.set_clim_auto(True)
check(v.playback_clim() == (1.0, 6.0) and seen.rng == (1.0, 6.0),
      f"5. ...and the lock takes over again when Auto returns ({seen.rng})")
v.lock_scale_cb.setChecked(False)

# ── 6. a new file starts clean ────────────────────────────────────────────
v.set_clim(-10.0, 10.0)
check(v._clim_by_var,
      "6. (precondition) the store holds this run's numbers")
v.load_result_path(other)
# The load ends in a render, so Custom mode legitimately re-seeds the variable it
# shows from the NEW file's data — what must not survive is any pair from the old
# run. (Clearing is checked by that absence rather than by an empty dict, which
# would only hold if nothing were ever drawn.)
check((-10.0, 10.0) not in v._clim_by_var.values(),
      f"6. loading a different result file clears the store — a new run must not "
      f"be coloured with the old one's numbers ({v._clim_by_var})")
pick_var(v, "p")
check(seen.rng == (100.0, 200.0) and v._clim_by_var["p"] == (100.0, 200.0),
      f"6. ...so the new run seeds from its own data ({seen.rng})")
v.clear()
check(v._clim_by_var == {},
      "6. Clear drops the store with the result")

# ── 7. the panel's Min/Max boxes follow the variable ──────────────────────
v2 = ResultCanvasView()
panel = ResultControlPanel()
panel.bind(v2)
v2.load_result_path(multi)
v2.show_frame(0)
pick_var(v2, "p")
check(panel.auto_cb.isChecked()
      and (panel.vmin.value(), panel.vmax.value()) == (1.0, 2.0),
      f"7. (precondition) in Auto the boxes report the range in force "
      f"({panel.vmin.value()}, {panel.vmax.value()})")

panel.auto_cb.setChecked(False)          # -> Custom, box revealed
panel.vmin.setValue(-10.0); panel.vmax.setValue(10.0)
panel.apply_btn.click()
check((panel.vmin.value(), panel.vmax.value()) == (-10.0, 10.0),
      "7. Apply leaves the typed numbers alone")

pick_var(v2, "u")
check((panel.vmin.value(), panel.vmax.value()) == (-1.0, 1.0),
      f"7. switching variable refreshes the boxes to the range actually in force "
      f"for the field on screen — they must not keep describing 'p' "
      f"({panel.vmin.value()}, {panel.vmax.value()})")
pick_var(v2, "p")
check((panel.vmin.value(), panel.vmax.value()) == (-10.0, 10.0),
      f"7. ...and back, so what the boxes say is always what is rendering "
      f"({panel.vmin.value()}, {panel.vmax.value()})")

# A render triggered by something OTHER than the variable must not rewrite the
# boxes: in Custom mode they are an INPUT the user may be halfway through typing.
panel.vmin.setValue(-99.0)
v2.render()
check(panel.vmin.value() == -99.0,
      f"7. an unrelated re-render does not overwrite a half-typed number "
      f"({panel.vmin.value()})")

# ...but a NEW FILE is not an unrelated render, even though the variable NAME did
# not move: the store was cleared, so the range on screen is a fresh seed and the
# boxes would otherwise sit there showing the previous run's numbers — verbatim
# the symptom this whole change exists to kill. Found in review of the first fix,
# which keyed the refresh on the variable name alone; the canvas now reports
# `clim_seeded`, i.e. "this range is NOT one the user typed".
pick_var(v2, "p")
panel.vmin.setValue(-10.0); panel.vmax.setValue(10.0)
panel.apply_btn.click()
v2.load_result_path(other)
pick_var(v2, "p")
check((panel.vmin.value(), panel.vmax.value()) == (100.0, 200.0),
      f"7. loading a DIFFERENT run refreshes the boxes too, though the variable "
      f"name is the same — a cleared store means the range is a fresh seed "
      f"({panel.vmin.value()}, {panel.vmax.value()})")
check(not panel.auto_cb.isChecked(),
      "7. ...and the MODE is still Custom: only the numbers were reset")

# ── 8. the Auto checkbox IS the mode, in both directions ──────────────────
# Unticking used to tell the canvas nothing until Apply, so the panel showed the
# Custom box while the canvas kept auto-scaling each frame to its own min/max —
# and the boxes, no longer refreshed by the Auto branch, froze on the frame the
# untick happened on. Found in review; it is issue #24's own symptom (boxes
# describing a range that is not on screen) reached by the other route, and it
# needs a MULTI-frame run to show, which is why it is its own section.
v3 = ResultCanvasView()
p3 = ResultControlPanel()
p3.bind(v3)
v3.load_result_path(multi)
v3.show_frame(0)
pick_var(v3, "p")
p3.auto_cb.setChecked(False)
check(not v3._clim_auto,
      "8. unticking Auto moves the CANVAS out of auto too — the checkbox and "
      "_clim_auto are one fact, not two that agree by luck")
seed = (p3.vmin.value(), p3.vmax.value())
check(seed == (1.0, 2.0),
      f"8. ...seeded from the frame on screen, so nothing JUMPS at the moment of "
      f"unticking ({seed})")
for k in range(5):
    v3.show_frame(k)
check(v3.manual_clim() == (1.0, 2.0)
      and (p3.vmin.value(), p3.vmax.value()) == (1.0, 2.0),
      f"8. ...and stepping the whole run keeps that range, with the boxes still "
      f"describing what is on screen ({v3.manual_clim()}, "
      f"{(p3.vmin.value(), p3.vmax.value())})")
p3.auto_cb.setChecked(True)
check(v3._clim_auto,
      "8. re-ticking hands the scale back to the data (the direction that always "
      "worked)")

print("-" * 60)
if _FAILS:
    print(f"FAILED {len(_FAILS)}:")
    for m in _FAILS:
        print("  - " + m)
    _wd.cancel()
    os._exit(1)
print("OK  all checks passed")
_wd.cancel()
os._exit(0)
