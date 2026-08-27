#!/usr/bin/env python3
"""Which legs of a restarted solve play, as a choice the user makes.

USER-REQUESTED (2026-08-27): "在 results 裡面可以詢問是否把多個結果檔案同時開啟
連續播放，並且可以選擇要把哪些勾選到一起播放" — ask whether to open several
result files as one continuous animation, and let the user tick which ones.

**This reverses half of #43 on purpose.** #43 removed #32's per-load modal
because it "made the common case cost a click and made an unattended run behave
differently from an interactive one". The second half of that is preserved
exactly and is check 1 here: headless asks nothing and plays every leg, so batch
and CI are byte-for-byte what they were. The first half is what the user
overruled, and it is recorded as a reversal rather than re-litigated quietly.

Pinned here, against the real ``ResultCanvasView`` on the offscreen platform and
the real ``LegPickerDialog``:

 1. headless asks NOTHING and yields every leg — #43's surviving guarantee;
 2. a subset really is a subset: the series holds the ticked legs only, and is an
    ordinary ``LegSeries``, so frames, labels and ranges behave as they always do;
 3. the picker is offered only when the solve HAS more than one leg, and on the
    LEG count rather than the frame count — three one-frame legs is an ordinary
    restarted run, and keying on frames would hide the control that had just been
    used (the bug #43 found for 'This leg only', measured at 3 legs x 1 zone);
 4. 'This leg only' still wins while it is ticked, so the two controls have a
    stated precedence rather than a race;
 5. the selection is view state for the loaded result: a new load clears it, and
    the prompt is armed once per LOAD rather than once per rebuild — otherwise
    every 'This leg only' toggle would re-ask it;
 6. cancelling, and ticking nothing, both mean "every leg" — one meaning, and
    the state the view already has for "no restriction";
 7. the dialog's own verbs: All / None, and ``selection()`` returns leg KEYS.

Every check was verified by injecting the defect back and re-running. Three of
them were WEAKER than they read on the first attempt and the injections are what
found it, which is why the reasoning sits beside each: the reset check could not
see its own mechanism (a multi-leg load reassigns the selection regardless, so it
had to be asked on a single-leg load), the frame-count check had a 3-frame
fixture where the property only fails at 1, and the handler check reports as a
crash rather than a FAIL line — so an injection harness that counts FAIL lines
scores it 0 and must read the exit code instead.

**Blind spot, named rather than papered over:** the dialog is never actually
SHOWN here, because tests run offscreen and :func:`ask_legs` returns None when
headless — which is check 1's whole point. So what is gated is the dialog's verbs
(check 7), the filter the answer drives (2, 4) and the control's visibility
(3); that the prompt really appears on an interactive load is not, and cannot be
without a windowed session. The seam is narrow on purpose: ``ask_legs`` is the
only thing between the two.

Run:  python3 tools/PreProcessor/tests/test_result_leg_picker.py
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

from PyQt6.QtWidgets import QApplication                           # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app import utils as utils_mod                                 # noqa: E402
from app.services.case_files import RUN_NOTE_NAME                  # noqa: E402
from app.views.result_canvas import ResultCanvasView               # noqa: E402
from app.views import result_leg_picker as picker                  # noqa: E402

RESULT = "xtecp_sol_allz.dat"
tmp = tempfile.mkdtemp(prefix="hybmesh_leg_picker_")


def write_transient(path, n_zones=2, base=0.0):
    L = ['Title = "t"', 'variables = "x", "y", "p"']
    for k in range(n_zones):
        L += ['zone t = "time 0" N=4 E=2 ZONETYPE=FETRIANGLE',
              ' DATAPACKING = BLOCK VARLOCATION = ( [1-2] = NODAL, '
              '[3] = CELLCENTERED )',
              '0 1 1 0', '0 0 1 1',
              f'{base + k + 1.0} {base + k + 2.0}',
              '1 2 3', '1 3 4']
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")


def build_case(name, n_legs=3, n_zones=2):
    """A case whose solve was restarted, as #26/#30 leave one on disk."""
    root = os.path.join(tmp, name)
    work = os.path.join(root, "work")
    convg = "".join(f"{n}  1e-9  1e-3\n" for n in range(10, 1000, 10))
    for i in range(1, n_legs):
        d = os.path.join(work, f"prev_{i:03d}")
        write_transient(os.path.join(d, f"{RESULT}.prev_{i:03d}"),
                        n_zones=n_zones, base=100.0 * i)
        with open(os.path.join(d, f"unicones.enorm.prev_{i:03d}"), "w") as f:
            f.write(convg)
        with open(os.path.join(d, RUN_NOTE_NAME), "w") as f:
            f.write(f"archive: prev_{i:03d}\narchived_at: 2026-08-2{i} 10:0{i}:00\n"
                    f"run_tag: .gui\nresumed_from: cold start\n"
                    f"zone_dump: binDumpZ.dat.prev_{i:03d}\n"
                    f"convergence_file: unicones.enorm.prev_{i:03d}\n"
                    f"last_iteration: {990 * i}\nconvergence_interval: 10\n")
    write_transient(os.path.join(work, f"{RESULT}.gui"),
                    n_zones=n_zones, base=900.0)
    with open(os.path.join(work, "unicones.enorm.gui"), "w") as f:
        f.write(convg)
    with open(os.path.join(work, "input.in"), "w") as f:
        f.write("   print_convg_per_niter\t10\n")
    return os.path.join(work, f"{RESULT}.gui")


live = build_case("case", n_legs=3)

# ── 1. headless asks nothing and plays every leg (#43's surviving half) ────
_asked = []
_real = utils_mod.confirm


def fake_confirm(*a, **k):
    _asked.append((a, k))
    return False


utils_mod.confirm = fake_confirm
check(picker.ask_legs(None, ["a", "b", "c"], "a") is None,
      "1. ask_legs returns None — 'every leg' — when headless, so an unattended "
      "run never blocks on the prompt and is unchanged from #43")

v = ResultCanvasView()
v.load_result_path(live)
check(_asked == [] and v._series is not None and v._series.n_files == 3,
      f"1. ...and a headless load still plays the whole solve without asking "
      f"({_asked}, {v._series.n_files if v._series else None} files)")
utils_mod.confirm = _real

# ── 3. offered on the LEG count, not the frame count ──────────────────────
check(not v.pick_legs_btn.isHidden(),
      f"3. the leg picker is offered for a restarted solve "
      f"({v.pick_legs_btn.isHidden()})")
one = build_case("solo", n_legs=1)
v1 = ResultCanvasView()
v1.load_result_path(one)
check(v1.pick_legs_btn.isHidden(),
      f"3. ...and NOT for a solve that was never restarted "
      f"({v1.pick_legs_btn.isHidden()})")
# EVERY leg one frame, not just the live one: with the archives still holding
# two zones each the series has 5 frames, so a check written against that
# fixture passes even when the button IS keyed on the frame count (measured —
# the injection came back green).
flat = build_case("flat", n_legs=3, n_zones=1)
vz = ResultCanvasView()
vz.load_result_path(flat)
check(vz._frame_count() == 3 and not vz.pick_legs_btn.isHidden(),
      f"3. ...and it is keyed on LEGS, not frames: a solve of one-frame legs "
      f"still offers it, where keying on the frame count would hide the control "
      f"that had just been used ({vz._frame_count()} frames, "
      f"hidden={vz.pick_legs_btn.isHidden()})")

# ...and it must STAY offered once the user has restricted, which is the shape
# of the bug #43 found for 'This leg only': restricting to one one-frame leg
# leaves a ONE-frame series, so a control keyed on the frame count hides itself
# the moment it is used and the escape closes behind the user. Asking it before
# restricting proves nothing — that fixture has 3 frames either way (measured:
# the injection came back green).
vz.one_leg_cb.setChecked(True)
check(vz._frame_count() == 1 and not vz.pick_legs_btn.isHidden(),
      f"3. ...and it stays offered after restricting to a single one-frame leg, "
      f"where a control keyed on the frame count would hide itself the moment it "
      f"was used ({vz._frame_count()} frame, hidden={vz.pick_legs_btn.isHidden()})")
vz.one_leg_cb.setChecked(False)

# ── 2. a subset is a subset, and an ordinary LegSeries ────────────────────
v._leg_selection = {"prev_001", "latest"}
v.reload_legs()
check(v._series is not None and v._series.n_files == 2,
      f"2. only the ticked legs are played "
      f"({v._series.n_files if v._series else None} files)")
check(v._frame_count() == 4 and v.zone_combo.count() == 4,
      f"2. ...and the frame list, the selector and the transport all follow — a "
      f"subset is an ordinary LegSeries, not a second code path "
      f"({v._frame_count()}, {v.zone_combo.count()})")

# ── 4. 'This leg only' still wins ─────────────────────────────────────────
v.one_leg_cb.setChecked(True)
check(v._series.n_files == 1,
      f"4. 'This leg only' overrides a subset while it is ticked — a stated "
      f"precedence rather than a race between two controls "
      f"({v._series.n_files})")
v.one_leg_cb.setChecked(False)
check(v._series.n_files == 2,
      f"4. ...and unticking it restores the subset rather than the whole solve, "
      f"so the override does not destroy the answer it overrode "
      f"({v._series.n_files})")

# The button's handler exists and is reachable: headless it answers None, so
# invoking it returns the view to the whole solve. Without the handler this is
# an AttributeError, which is the failure.
v._on_pick_legs()
check(v._series.n_files == 3 and getattr(v, "_leg_selection", "x") is None,
      f"4. the 'Legs…' handler rebuilds from the answer — headless that is None, "
      f"i.e. every leg, the same meaning a cancel has "
      f"({v._series.n_files}, {getattr(v, '_leg_selection', 'x')})")
v._leg_selection = {"prev_001", "latest"}
v.reload_legs()

# ── 5. the selection is view state for the RESULT that is loaded ──────────
# Loading a SINGLE-leg result, deliberately: _resolve_legs returns before the
# prompt for those, so this is the only route on which the reset is what clears
# the subset. On a multi-leg load ask_legs reassigns it regardless, and a check
# written that way passes with the reset deleted (measured).
v.load_result_path(one)
check(getattr(v, "_leg_selection", "unset") is None,
      f"5. a new load clears the subset — it is view state for the result being "
      f"loaded, like the clim store, so a solve never inherits another's ticks, "
      f"including on a load that never reaches the prompt "
      f"({getattr(v, '_leg_selection', 'unset')})")
v.load_result_path(live)
check(v._series.n_files == 3,
      f"5. ...and the solve reopens whole ({v._series.n_files})")
v._ask_legs_pending = True
v._leg_selection = {"latest"}
v.reload_legs()
check(v._ask_legs_pending is False,
      "5. ...and the prompt is armed once per LOAD, not per rebuild: a "
      "'This leg only' toggle must not re-ask it")

# ── 6/7. the dialog's own verbs ───────────────────────────────────────────
legs = v._legs.legs
dlg = picker.LegPickerDialog(None, legs, live)
check(dlg.selection() == {leg.key for leg in legs},
      f"7. the dialog opens with every leg ticked ({dlg.selection()})")
dlg._set_all(False)
check(dlg.selection() == set(),
      f"7. ...'None' clears them ({dlg.selection()})")
dlg._set_all(True)
check(dlg.selection() == {leg.key for leg in legs},
      f"7. ...and 'All' puts them back ({dlg.selection()})")
check(all(isinstance(k, str) and k for k in dlg.selection()),
      f"7. ...returning leg KEYS, which is what _resolve_legs filters on "
      f"({dlg.selection()})")

print()
if _FAILS:
    print(f"{len(_FAILS)} FAILED:")
    for m in _FAILS:
        print("  - " + m)
print(f"{len(_FAILS)} failure(s)" if _FAILS else "all checks passed")
os._exit(1 if _FAILS else 0)
