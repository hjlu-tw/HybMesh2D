#!/usr/bin/env python3
"""Transient result playback: frame indexing, the frame cache, and the transport.

A transient solver run appends one zone per dumped step, so the Results view is a
movie that was only ever shown one frame at a time. Adding Play / Prev / Next is
only half the job — two things decide whether the animation is usable at all:

 1. **Loading a frame must cost one frame.** ``from_file`` used to ``readlines()``
    the WHOLE file and rescan it for zone headers, so every step of a 113 MB run
    re-read 113 MB. It now seeks to the zone's byte range (``tecplot_index``).
    This test pins the parse to be IDENTICAL to a whole-file scan — a faster
    loader that reads a different array is not a faster loader.

 2. **The colour scale must be the user's choice.** Auto-scaling each frame to
    its own min/max repaints the same colours onto a changing range, so a field
    that doubles looks unchanged — ticking "Lock scale" pins the range over ALL
    frames instead. USER-REQUESTED (2026-08-12): that lock is OFF by default,
    because "Auto (fit to data)" must fit the data on screen, i.e. the current
    frame. Neither ever overrides a range the user typed in by hand.

What is pinned here:
  1. Index: zone count/offsets, and a byte-range parse == whole-file parse.
  2. Series: frames cached and served, global range spans every frame, and the
     cache honours its byte cap instead of growing without bound.
  3. Transport: hidden for a steady (1-zone) result, wraps at both ends, Play
     toggles, First/Last jump to an end, and leaving the page stops the timer.
  4. The colour lock is opt-in, applies in auto mode, is dropped when the
     variable changes, and NEVER overrides a manual range.
  5. Stepping keeps the pinned probes (frames of one run share their mesh).

Run:  python3 tools/PreProcessor/tests/test_result_playback.py
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

import numpy as np  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.models.result_data import TecplotResult  # noqa: E402
from app.models.result_series import ResultSeries  # noqa: E402
from app.models import tecplot_index  # noqa: E402
from app.views.result_canvas import ResultCanvasView  # noqa: E402


# --------------------------------------------------------------------------- #
# A unit square split into two triangles, written as N zones whose cell field
# GROWS with the frame — so a per-frame colour scale and a global one differ.
# --------------------------------------------------------------------------- #
def write_transient(path, n_zones=5, title="time 0", offset=0.0,
                    distinct_titles=False):
    """``offset`` shifts every field value, so two generations of the same file are
    distinguishable — which is how a frame served from a stale cache is caught.
    ``distinct_titles`` gives each zone its own title (the solver does not, but the
    label path indexes the zone list only in that case)."""
    L = ['Title = "test"', 'variables = "x", "y", "p", "u"']
    for k in range(n_zones):
        t = f"{title} {k}" if distinct_titles else title
        L += [f'zone t = "{t}" N=4 E=2 ZONETYPE=FETRIANGLE',
              ' DATAPACKING = BLOCK VARLOCATION = ( [1-2] = NODAL, [3-4] = CELLCENTERED )',
              '0 1 1 0',                       # x
              '0 0 1 1',                       # y
              f'{k + 1.0 + offset} {k + 2.0 + offset}',   # p: frame-dependent
              f'{-(k + 1.0 + offset)} {k + 1.0 + offset}',  # u: symmetric about 0
              '1 2 3', '1 3 4']
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")
    return path


def whole_file_parse(path, zone):
    """Reference parse: find the zone by scanning every line, as before."""
    with open(path) as f:
        lines = f.readlines()
    starts = [i for i, ln in enumerate(lines) if ln.lstrip().lower().startswith("zone")]
    if zone < 0:
        zone += len(starts)
    end = starts[zone + 1] if zone + 1 < len(starts) else len(lines)
    body = lines[starts[zone] + 2:end]
    toks = np.fromstring("".join(body), sep=" ")
    return toks


tmp = tempfile.mkdtemp(prefix="hybmesh_playback_")
multi = write_transient(os.path.join(tmp, "xtecp_sol_allz.dat.gui"), n_zones=5)
single = write_transient(os.path.join(tmp, "steady.dat"), n_zones=1)

# ── 1. the byte index ─────────────────────────────────────────────────────
idx = tecplot_index.index_for(multi)
check(len(idx.zones) == 5 and idx.variables == ["x", "y", "p", "u"],
      "1. the index finds every zone and the variables line in one scan")
check(idx.offsets == sorted(idx.offsets) and idx.offsets[0] > 0
      and idx.zone_byte_range(4)[1] == idx.size,
      "1. zone offsets ascend and the last zone runs to EOF")
check([z.n_nodes for z in idx.zones] == [4] * 5
      and [z.n_elems for z in idx.zones] == [2] * 5,
      "1. each zone header yields its own N/E")

same = True
for k in list(range(5)) + [-1]:
    r = TecplotResult.from_file(multi, zone=k)
    ref = whole_file_parse(multi, k)
    got = np.concatenate([r.node_data["x"], r.node_data["y"],
                          r.cell_data["p"], r.cell_data["u"],
                          (r.elements[:2] + 1).astype(float).ravel()])
    same = same and np.array_equal(got, ref)
check(same,
      "1. a byte-range parse reproduces the whole-file parse EXACTLY for every "
      "zone, including the negative (last-zone) index")

bad = False
try:
    TecplotResult.from_file(multi, zone=99)
except ValueError:
    bad = True
check(bad, "1. an out-of-range zone still raises ValueError, not an IndexError")

# The index is cached, and a rewritten file invalidates it rather than serving
# a stale offset table (the solver appends zones while a run is going).
first = tecplot_index.index_for(multi)
check(tecplot_index.index_for(multi) is first,
      "1. a repeated index_for() is served from cache (the point of the index)")
grown = os.path.join(tmp, "grown.dat")
write_transient(grown, n_zones=2)
i2 = tecplot_index.index_for(grown)
write_transient(grown, n_zones=4)
os.utime(grown, (0, 0))          # force a distinct stamp on a fast filesystem
i3 = tecplot_index.index_for(grown)
check(len(i2.zones) == 2 and len(i3.zones) == 4 and i3 is not i2,
      "1. a file that gained zones is re-indexed, not served stale")

# ── 2. the series: cache + global range ───────────────────────────────────
s = ResultSeries(multi)
check(s.n_frames == 5, "2. the series exposes one frame per zone")
f2a = s.frame(2)
f2b = s.frame(2)
check(f2a is f2b, "2. a revisited frame comes from the cache (playback loops)")
check(s.frame_label(0) == "Frame 1 / 5",
      f"2. frames are labelled by POSITION — every zone the solver writes carries "
      f"the same title, so the position is the only honest id ({s.frame_label(0)})")

rng = s.global_range("p")
check(rng == (1.0, 6.0),
      f"2. the global range spans EVERY frame (p goes 1..6 over the run), not "
      f"just the one on screen ({rng})")
check(s.has_global_range("p") and not s.has_global_range("u"),
      "2. the range is cached per variable, so the scan is paid once")
per_frame = s.frame(0).get_cell_field("p")
check(float(per_frame.max()) == 2.0 and rng[1] == 6.0,
      "2. ... and it genuinely differs from the frame's own max, which is what "
      "made the colours jump")

tiny = ResultSeries(multi, max_bytes=1)
for k in range(5):
    tiny.frame(k)
check(tiny.cached_frames() == 1,
      f"2. the cache obeys its BYTE cap (a long run must not fill memory) but "
      f"always keeps the frame on screen ({tiny.cached_frames()})")

# ── 3. the transport ──────────────────────────────────────────────────────
v = ResultCanvasView()
v.load_result_path(single)
check(v._frame_count() == 1
      and not any(w.isVisibleTo(v) for w in v._playback_widgets),
      "3. a steady (1-zone) result hides the whole transport — there is nothing "
      "to animate")
v.start_playback()
check(not v._playing, "3. Play on a single-frame result is a no-op, not a spin")

v.load_result_path(multi)
check(v._frame_count() == 5
      and all(w.isVisibleTo(v) for w in v._playback_widgets),
      "3. a transient result shows the transport")
check(v._frame == 4,
      "3. loading still lands on the LAST frame (the most-converged solution), "
      "as it did before playback existed")

# ── 3b. Loop is opt-in: off by default, and it governs BOTH the animation
#        and the step buttons ────────────────────────────────────────────────
check(not v.loop_cb.isChecked(),
      "3b. Loop is OFF by default — a run plays through once, it does not "
      "start repeating at you")
check(not v.next_btn.isEnabled() and v.prev_btn.isEnabled(),
      "3b. parked on the last frame, Next is greyed out and Prev is not — an "
      "end of the run is a visible boundary, not a click that does nothing")
v.step_frame(1)
check(v._frame == 4,
      "3b. Next at the last frame stays put instead of wrapping to the first")
v.show_frame(0)
check(not v.prev_btn.isEnabled() and v.next_btn.isEnabled(),
      "3b. ... and symmetrically at the first frame")
v.step_frame(-1)
check(v._frame == 0, "3b. Prev at the first frame stays put")

v.loop_cb.setChecked(True)
check(v.prev_btn.isEnabled() and v.next_btn.isEnabled(),
      "3b. ticking Loop re-enables the step button parked at an end")
v.step_frame(-1)
check(v._frame == 4, "3b. with Loop on, Prev wraps back to the last frame")
v.step_frame(1)
check(v._frame == 0, "3b. ... and Next wraps forward to the first")

v.loop_cb.setChecked(False)
v.show_frame(3)
v.start_playback()
for _ in range(4):                      # drive the timer's slot directly
    v._advance_frame()
check(v._frame == 4 and not v._playing,
      f"3b. a non-looping run STOPS on the last frame rather than starting over "
      f"(frame {v._frame + 1}, playing={v._playing})")
v.start_playback()
check(v._playing and v._frame == 0,
      "3b. Play at the end of a finished run rewinds and plays it again, rather "
      "than starting with nowhere to go")
v.stop_playback()

v.loop_cb.setChecked(True)
v.show_frame(4)
v._advance_frame()
check(v._frame == 0,
      "3b. with Loop on the animation wraps past the end and keeps going")
v.loop_cb.setChecked(False)

# ── 3c. First / Last: one click to either end of the run ──────────────────
v.show_frame(2)
v.go_to_end(1)
check(v._frame == 4, "3c. Last jumps straight to the final frame")
check(not v.last_btn.isEnabled() and v.first_btn.isEnabled(),
      "3c. ... and greys itself out there, like the step buttons do")
v.go_to_end(-1)
check(v._frame == 0, "3c. First jumps straight back to frame 1")
check(not v.first_btn.isEnabled() and v.last_btn.isEnabled(),
      "3c. ... symmetrically at the other end")
v.loop_cb.setChecked(True)
check(not v.first_btn.isEnabled(),
      "3c. Loop does not re-enable First on the first frame: a jump to an end "
      "has one meaning, and there is no far end to wrap to")
v.loop_cb.setChecked(False)
v.show_frame(2)
v.start_playback()
v.go_to_end(1)
check(v._frame == 4 and not v._playing,
      "3c. jumping to an end pauses the animation, like Prev/Next do")
v.show_frame(2)          # leave room to step in both directions below

v.show_frame(2)
check(v._frame == 2 and v.zone_combo.currentIndex() == 2,
      "3. the zone selector follows the frame (one source of truth on screen)")
check(v.frame_label.text() == "Frame 3 / 5",
      f"3. the frame read-out names the position ({v.frame_label.text()!r})")

v.start_playback()
check(v._playing and v._play_timer.isActive() and "Pause" in v.play_btn.text(),
      "3. Play starts the timer and the button offers Pause")
v.toggle_playback()
check(not v._playing and not v._play_timer.isActive()
      and "Play" in v.play_btn.text(),
      "3. the same button pauses (one-key play/pause)")
v.show()
app.processEvents()          # Qt only delivers a hide event to a shown widget
v.start_playback()
v.hide()
app.processEvents()
check(not v._playing and not v._play_timer.isActive(),
      "3. leaving the Results page stops the animation — a hidden canvas must "
      "not keep loading frames against the run the user switched to watch")
v.show()

# ── 4. the colour lock (opt-in) ───────────────────────────────────────────
v.select_variable("p")
v.set_clim_auto(True)
check(not v.lock_scale_cb.isChecked(),
      "4. 'Lock scale' is OFF by default — Auto (fit to data) fits the data on "
      "SCREEN, which is the frame being shown")
v.step_frame(1)
check(v.playback_clim() is None,
      f"4. so stepping pins nothing and each frame keeps its own range "
      f"({v.playback_clim()})")

v.lock_scale_cb.setChecked(True)
check(v.playback_clim() == (1.0, 6.0),
      f"4. ticking the box pins the run-wide range immediately — no need to "
      f"step first to see the colours settle ({v.playback_clim()})")
v.step_frame(-1)
check(v.playback_clim() == (1.0, 6.0),
      f"4. ... and stepping keeps it, so a frame's colours mean the same thing "
      f"in every frame ({v.playback_clim()})")
v.select_variable("u")
check(v.playback_clim() is None,
      "4. switching variables drops the lock — 'u' must not be coloured with "
      "'p''s range")
v.step_frame(1)
check(v.playback_clim() == (-5.0, 5.0),
      f"4. ... and the next step pins the NEW variable's own run-wide range "
      f"({v.playback_clim()})")
v.lock_scale_cb.setChecked(False)
check(v.playback_clim() is None,
      "4. unticking hands the scale straight back to the current frame")
v.lock_scale_cb.setChecked(True)
v.set_clim(0.0, 1.0)
check(v.playback_clim() is None and v.manual_clim() == (0.0, 1.0),
      "4. a manual colour range wins over the lock — locking fixes AUTO-scaling, "
      "it does not overrule an explicit choice")
v.set_clim_auto(True)
check(v.playback_clim() == (-5.0, 5.0),
      "4. going back to auto restores the pinned range without a rescan")

# ── 5. overlays survive a step ────────────────────────────────────────────
v.select_variable("p")
v.show_frame(0)
v._probes = [{"x": 0.5, "y": 0.5, "vals": {"p": 1.0}}]
v._extrema = [{"which": "max", "var": "p", "x": 1.0, "y": 1.0, "value": 2.0}]
tri_before = v._triang
v.step_frame(1)
check(v._triang is tri_before,
      "5. the triangulation is REUSED across frames of one run (same mesh), "
      "which is most of what makes a step fast")
check(len(v._probes) == 1 and len(v._extrema) == 1,
      "5. probes and marked extrema survive a step — they mark geometry, and the "
      "geometry did not move")
check(v._node_cache == {} or "p" not in v._node_cache
      or float(np.max(v._node_cache["p"])) != 2.0,
      "5. ... but the field caches are dropped, because the VALUES did change")

v.clear()
check(v._series is None and v._frame_count() == 0
      and not any(w.isVisibleTo(v) for w in v._playback_widgets),
      "5. Clear tears the transport down with the result")

# ── 6. the zone combo is a transport control too ──────────────────────────
# Picking a frame from the dropdown is the most obvious way to compare two steps, and
# it used to render them WITHOUT the pinned scale: the lock was applied by step_frame
# and start_playback, not by show_frame, which every route shares. So the same two
# frames looked different depending on how you got to them — and someone comparing
# frames by hand (the likeliest user) got exactly the per-frame auto-scaling the lock
# exists to remove. A FRESH view is essential here: once any other control has run,
# the lock is already in place and the bug is invisible.
v2 = ResultCanvasView()
# Tick the lock BEFORE the load: with no series attached there is nothing to
# scan, so the precondition below still holds and the combo is the first control
# that could pin anything.
v2.lock_scale_cb.setChecked(True)
v2.load_result_path(multi)
v2.select_variable("p")
v2.set_clim_auto(True)
check(v2.playback_clim() is None,
      "6. (precondition) a freshly loaded run has nothing pinned yet")
v2.zone_combo.setCurrentIndex(1)
check(v2._frame == 1,
      f"6. picking a zone by hand moves the frame counter ({v2._frame})")
check(v2.playback_clim() == (1.0, 6.0),
      f"6. ...and pins the run-wide colour scale, like Prev/Next do "
      f"({v2.playback_clim()})")
v2.zone_combo.setCurrentIndex(0)
_via_combo = v2.playback_clim()
v2.step_frame(1)
check(v2.playback_clim() == _via_combo == (1.0, 6.0),
      f"6. the two routes to a frame agree about its colours — the property that was "
      f"broken ({v2.playback_clim()} vs {_via_combo})")
v2.clear()

# ── 7. one series speaks for ONE file ─────────────────────────────────────
# The frame COUNT/labels came from an index snapshotted in __init__ while the frame
# DATA came from whatever from_file re-resolved, so a run rewritten under an open
# Results tab (a re-run into the same case dir, or a headless run_pipeline.sh) mixed
# two solutions: cached indices replayed the OLD file, uncached ones read the NEW one,
# under a colour scale pinned to the old range. Read as physics, that is a wrong answer
# presented as a converged one.
churn = os.path.join(tmp, "rerun.dat.gui")
write_transient(churn, n_zones=5)
s2 = ResultSeries(churn)
check(s2.n_frames == 5 and float(s2.frame(0).get_cell_field("p").max()) == 2.0,
      "7. (precondition) five frames, frame 1's p peaking at 2")
check(s2.global_range("p") == (1.0, 6.0),
      "7. (precondition) and a pinned range over the whole run")

write_transient(churn, n_zones=3, offset=100.0)      # the re-run: fewer, different
os.utime(churn, (0, 0))                              # a distinct stamp on any fs
check(s2.n_frames == 3,
      f"7. the frame count follows the file that is on disk NOW ({s2.n_frames})")
check(s2.frame_label(0) == "Frame 1 / 3",
      f"7. ...so does the read-out ({s2.frame_label(0)!r})")
check(float(s2.frame(0).get_cell_field("p").max()) == 102.0,
      f"7. a frame index still sitting in the LRU is re-read from the NEW file "
      f"instead of replaying the previous run "
      f"({float(s2.frame(0).get_cell_field('p').max())})")
check(not s2.has_global_range("p"),
      "7. the range pinned to the old run is dropped, not kept over new data")
check(s2.global_range("p") == (101.0, 104.0),
      f"7. ...and rescans to the new run's own range ({s2.global_range('p')})")

# The transport's frame index can outlive a file that shrank under it; a LABEL must
# never be the thing that raises (it is called from the UI refresh, not a load path).
titled = os.path.join(tmp, "titled.dat")
write_transient(titled, n_zones=4, distinct_titles=True)
s3 = ResultSeries(titled)
check("time 0 2" in s3.frame_label(2),
      f"7. a file whose zones DO differ still shows the title ({s3.frame_label(2)!r})")
write_transient(titled, n_zones=2, distinct_titles=True)
os.utime(titled, (0, 0))
try:
    stale_label = s3.frame_label(3)
except IndexError:
    stale_label = "<IndexError>"
check(stale_label == "Frame 4 / 2",
      f"7. and a label for a now-out-of-range frame degrades instead of raising "
      f"({stale_label!r})")

# ── 8. the byte cap counts what a frame really holds ──────────────────────
# from_file parses ONE token buffer and hands out slices, so caching any one field array
# keeps the whole buffer — including the element-connectivity region, which no field
# array covers. Charging only the slices under-reported every frame, so the 512 MB cap
# really admitted ~1.25x that: a machine sized to the bound swaps instead of evicting.
from app.models.result_series import _frame_nbytes  # noqa: E402

r0 = TecplotResult.from_file(multi, zone=0)
check(r0.raw_nbytes > 0,
      f"8. a parsed frame records the size of the buffer it was sliced from "
      f"({r0.raw_nbytes})")
_slices = sum(a.nbytes for d in (r0.cell_data, r0.node_data) for a in d.values())
_counted = _frame_nbytes(r0)
check(_counted >= r0.raw_nbytes + r0.nodes.nbytes + r0.elements.nbytes,
      f"8. the accounting includes that shared buffer ({_counted} >= "
      f"{r0.raw_nbytes + r0.nodes.nbytes + r0.elements.nbytes})")
check(_counted > _slices + r0.nodes.nbytes + r0.elements.nbytes,
      f"8. ...which is strictly more than the slices alone — the connectivity region is "
      f"the part that used to be invisible ({_counted} vs "
      f"{_slices + r0.nodes.nbytes + r0.elements.nbytes})")
check(_frame_nbytes(TecplotResult()) == 0,
      "8. a result not parsed from a file still measures as empty, not as a crash")

# ── 9. the index cache is LRU, not FIFO ───────────────────────────────────
# A cache hit did not re-insert the key, so eviction was by INSERTION order: the index
# for the file being animated is the oldest entry and the fifth distinct path evicted it,
# putting the next frame back to a whole-file rescan.
tecplot_index.clear_index_cache()
lru_paths = [write_transient(os.path.join(tmp, f"lru{i}.dat"), n_zones=2)
             for i in range(tecplot_index._CACHE_MAX)]
for p in lru_paths:
    tecplot_index.index_for(p)
oldest = tecplot_index.index_for(lru_paths[0])       # USE it: now the most recent
tecplot_index.index_for(write_transient(os.path.join(tmp, "lru_extra.dat"), n_zones=2))
check(tecplot_index.index_for(lru_paths[0]) is oldest,
      "9. an entry that is still being used survives eviction (LRU), instead of being "
      "dropped for being the first one inserted")
check(len(tecplot_index._CACHE) <= tecplot_index._CACHE_MAX,
      f"9. ...and the cache still obeys its size ({len(tecplot_index._CACHE)})")

# invalidate() is the escape hatch for a change the (mtime, size) stamp cannot see, so
# it must force a rebuild rather than re-ask the shared cache — which would hand back
# the very index it was told to discard.
inv = ResultSeries(multi)
before = inv._files[0].index
inv.frame(0)
inv.invalidate()
check(inv._files[0].index is not before and inv.n_frames == 5 and inv.cached_frames() == 0,
      "9. invalidate() rebuilds the index and drops the frames even when the file looks "
      "unchanged (a rewrite inside one mtime tick at the same size)")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
