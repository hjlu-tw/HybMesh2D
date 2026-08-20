#!/usr/bin/env python3
"""A live edge edit belongs to the CAD tab it began in.

Architecture backlog candidate 7, ticket 4 (issue #18). This is the ticket that
CHANGES behaviour; #15-#17 were the moves that made it expressible.

THE DEFECT, as it stood. Nothing cancelled a live edit when a CAD tab was
switched or closed — neither ``switch_tab`` nor ``close_tab`` touched the
pending state, and only the dialog's own reject signal ever cancelled — while
the commit path resolved its target through ``active_session()``, i.e. whichever
tab is in front NOW. Two silent consequences:

* **Committing an edit** looked the segment up in the now-active session, failed,
  and fell back to matching by segment **id**. Ids are per-session, so they
  collide across tabs and the fallback — which exists to survive an intervening
  undo — landed the edit on ANOTHER TAB'S edge: an undo entry whose before-state
  came from one geometry and whose after-state came from another. (The issue
  describing this named 10001, ``ProjectModel._next_curve_id``'s starting value.
  Measured, it is worse: ``renumber_segments`` reassigns contiguous 1..N ids
  across both edge kinds, so in practice every tab's Nth edge has id N and the
  collision is not merely possible but systematic. Check 0 asserts the collision
  rather than a particular number, so a renumbering change cannot quietly turn
  this test into one that proves nothing.)
* **Committing a new edge** handed the preconfigured segment to the now-active
  session, so an edge drawn in tab A was added to tab B.

Check 1 reproduces both by putting the app in exactly that state — the front tab
is not the tab the edit began in — and asserting nothing lands on the wrong one.
It reaches that state by moving ``active_idx`` DIRECTLY rather than through
``switch_tab``, on purpose: ``switch_tab`` now ends the edit, so going through it
would test the prompt instead of the binding, and the binding is the half that
still has to hold when some other route changes the front tab. Measured: with the
session binding reverted, this check fails exactly as described (see the commit
message for the injection run).

What else is pinned:

2. SWITCHING TABS MID-EDIT ASKS, and No really aborts — the edit stays live and
   intact on its own tab, and the tab bar goes back (Qt has already moved it by
   the time we are told, so refusing has to undo that or the tab bar shows one
   geometry while the canvas and the live edit belong to another).

3. CLOSING THE OWNING TAB ASKS THE EDIT QUESTION FIRST and the unsaved-changes
   question SECOND. Declining the first aborts the close, so the second is never
   asked. They are two prompts because they ask different things — is this edit
   worth keeping, is this geometry worth saving.

4. BOTH PROMPTS TAKE THEIR ``headless_default``, so a batch run never blocks —
   and a headless close still ends with no live edit, which is the outcome that
   matters: never coming out the other side with an edit pointing at a tab that
   is gone.

5. ``begin`` WHILE AN EDIT IS LIVE ASKS. Yes cancels the live one and begins the
   new one; No refuses the new one, narrates it, and leaves the live one
   untouched. The six ``_edit_in_progress()`` guards fire first and are
   unchanged; this is only for the routes they do not block.

6. ``commit``/``cancel`` WITH NOTHING LIVE IS A NO-OP — no pop-up, no user-log
   line, no exception, no change to the undo stack. Reaching it is a timing
   artefact (a dialog signal arriving after the state was cleared), not
   something the user did.

Run:  python3 tools/PreProcessor/tests/test_edit_session_binding.py
"""
import functools
import os
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

import builtins  # noqa: E402
print = functools.partial(builtins.print, flush=True)
_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >60s — a prompt without a headless default?")
    os._exit(99)


_wd = threading.Timer(60, _watchdog)
_wd.daemon = True
_wd.start()

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import app.utils as utils  # noqa: E402
from app.controller import AppController  # noqa: E402
from app.models.segment import SegmentModel  # noqa: E402

c = AppController()
while len(c.sessions) > 1:
    c.close_tab(len(c.sessions) - 1)
c.new_blank_tab()
sess_a, sess_b = c.sessions[0], c.sessions[1]
check(sess_a is not sess_b, "two CAD tabs open")


def _add_circle(sess, cx, cy, r):
    """Add an edge the way the model numbers them, so both tabs' first analytic
    edge really is 10001 — the collision the id fallback matched on."""
    seg_id = sess.project_model._next_curve_id
    sess.project_model._next_curve_id += 1
    seg = SegmentModel(seg_id, -1, -1)
    seg.type = "curve"
    seg.curve_type = "circle"
    seg.curve_mode = "parametric"
    seg.parameters = {"n_points": 50, "cx": cx, "cy": cy, "r": r}
    sess.project_model.segments.append(seg)
    return seg


edge_a = _add_circle(sess_a, 0.0, 0.0, 1.0)
edge_b = _add_circle(sess_b, 9.0, 9.0, 3.0)
check(edge_a.id == edge_b.id,
      f"0. both tabs' first analytic edge has the SAME id ({edge_a.id} vs "
      f"{edge_b.id}) — the collision the id fallback matched on")

# ── Prompt control: answer without a screen ─────────────────────────────────
_answers = []
_asked = []


def _stub_confirm(answer):
    def _c(parent, title, question, detail=None, headless_default=True):
        _asked.append(title)
        return answer
    return _c


_real_confirm = utils.confirm


def _set_confirm(fn):
    """Patch every module that already imported ``confirm`` by name, plus the
    module itself for the call sites that import it inside a function body."""
    utils.confirm = fn
    for mod in list(sys.modules.values()):
        if getattr(mod, "__name__", "").startswith("app.") and \
                getattr(mod, "confirm", None) is not None:
            mod.confirm = fn


def _preview_len(session):
    """How many points the live curve-preview item holds for a session. The
    preview is a canvas item keyed by session_id, so clearing the FRONT tab's
    key leaves the preview drawn on the tab the edit actually belonged to."""
    item = c.main_window.canvas_view._curve_preview_items.get(
        session.session_id)
    xs = item.getData()[0] if item is not None else None
    return 0 if xs is None else len(xs)


# ══ 1: the cross-tab commit ═════════════════════════════════════════════════
c.switch_tab(0)
app.processEvents()
b_before = dict(edge_b.parameters)
depth_b = len(sess_b.command_history._undo_stack)

c._begin_pending_edit(edge_a, is_new=False)
check(c.edge_edit.is_active() and c.edge_edit.owning_session is sess_a,
      "1a the edit began in tab A and says so")
# Through the dialog handler, not the owner directly, so the live PREVIEW is
# really drawn on tab A's canvas item — check 1k needs something to be left
# behind before it can catch a clear aimed at the wrong session.
c._on_pending_dialog_changed({"cx": 5.0}, 50)
app.processEvents()
check(_preview_len(sess_a) > 0,
      f"1a' the live preview really is drawn on tab A "
      f"({_preview_len(sess_a)} points)")

# Put tab B in front WITHOUT going through switch_tab: this is the state the
# binding has to survive on its own.
c.active_idx = 1
check(c.active_session() is sess_b, "1b tab B is now the active session")
c._commit_pending_edge()
app.processEvents()

check(len(sess_b.command_history._undo_stack) == depth_b,
      f"1c committing records NOTHING on tab B "
      f"(got {len(sess_b.command_history._undo_stack) - depth_b})")
check(abs(edge_b.parameters["cx"] - b_before["cx"]) < 1e-12
      and abs(edge_b.parameters["r"] - b_before["r"]) < 1e-12,
      "1d tab B's edge is untouched")
check(len(sess_a.command_history._undo_stack) == 1,
      f"1e the edit landed on tab A, where it began "
      f"(got {len(sess_a.command_history._undo_stack)})")
check(abs(edge_a.parameters["cx"] - 5.0) < 1e-12,
      "1f …with tab A's edge carrying the edit")
# The segment list, the selection and the window title all describe the tab in
# FRONT, so a commit onto a BACKGROUND session must not touch them. The
# observable half of that here is the title's unsaved marker: tab A is now
# dirty, but the window is showing tab B, so the marker must not appear.
check(not c.main_window.windowTitle().startswith("*"),
      f"1i a background commit does not mark the FRONT tab's title dirty "
      f"({c.main_window.windowTitle()!r})")
check(sess_a.is_geometry_modified,
      "1j …while the session that was actually edited IS marked modified")


check(_preview_len(sess_a) == 0,
      f"1k the live preview is cleared on the EDIT's session, not the front "
      f"tab's ({_preview_len(sess_a)} points left on tab A)")

# A NEW edge must not appear in the wrong tab either.
c.active_idx = 0
app.processEvents()
n_b = len(sess_b.project_model.segments)
fresh = SegmentModel(sess_a.project_model._next_curve_id, -1, -1)
fresh.type, fresh.curve_type, fresh.curve_mode = "curve", "circle", "parametric"
fresh.parameters = {"n_points": 50, "cx": 2.0, "cy": 2.0, "r": 0.5}
c._begin_pending_edit(fresh, is_new=True)
c.active_idx = 1
c._commit_pending_edge()
app.processEvents()
check(len(sess_b.project_model.segments) == n_b,
      "1g a new edge drawn in tab A never appears in tab B")
check(fresh in sess_a.project_model.segments,
      "1h …it is added to tab A, where it was drawn")
c.active_idx = 0
sess_a.command_history._undo_stack.clear()

# ══ 2: switching tabs mid-edit asks; No aborts ══════════════════════════════
c.switch_tab(0)
app.processEvents()
a_before = dict(edge_a.parameters)
c._begin_pending_edit(edge_a, is_new=False)
c.edge_edit.update({"cx": 7.0}, 50)

_asked.clear()
_set_confirm(_stub_confirm(False))          # No — keep the edit
c.switch_tab(1)
app.processEvents()
check(len(_asked) == 1, f"2a switching tabs mid-edit asked once ({_asked})")
check(c.active_idx == 0, "2b answering No aborts the switch")
check(c.edge_edit.is_active() and c.edge_edit.owning_session is sess_a,
      "2c …and the edit is still live, on its own tab")
check(abs(edge_a.parameters["cx"] - 7.0) < 1e-12,
      "2d …with its in-progress shape intact")
check(c.main_window.tab_widget.currentIndex() == 0,
      "2e …and the tab bar was put back")

_asked.clear()
_set_confirm(_stub_confirm(True))           # Yes — cancel and switch
c.switch_tab(1)
app.processEvents()
check(len(_asked) == 1, "2f answering Yes asked once")
check(c.active_idx == 1, "2g …and the switch proceeded")
check(not c.edge_edit.is_active(), "2h …with no edit left live")
check(abs(edge_a.parameters["cx"] - a_before["cx"]) < 1e-12,
      "2i …and the edited shape reverted to its pre-edit parameters")

# A NEW edge is dropped rather than reverted.
c.switch_tab(0)
app.processEvents()
n_a = len(sess_a.project_model.segments)
drop = SegmentModel(sess_a.project_model._next_curve_id, -1, -1)
drop.type, drop.curve_type, drop.curve_mode = "curve", "circle", "parametric"
drop.parameters = {"n_points": 50, "cx": 4.0, "cy": 4.0, "r": 0.25}
c._begin_pending_edit(drop, is_new=True)
_set_confirm(_stub_confirm(True))
c.switch_tab(1)
app.processEvents()
check(len(sess_a.project_model.segments) == n_a,
      "2j cancelling a new edge on a tab switch drops it")

# ══ 5: begin while an edit is live ══════════════════════════════════════════
c.switch_tab(0)
app.processEvents()
c._begin_pending_edit(edge_a, is_new=False)
live_seg = c.edge_edit.segment
c.edge_edit.update({"cx": 1.5}, 50)

_asked.clear()
_set_confirm(_stub_confirm(False))          # No — refuse the new edit
other = _add_circle(sess_a, -3.0, -3.0, 0.5)
c._begin_pending_edit(other, is_new=False)
check(len(_asked) == 1, "5a begin while an edit is live asked once")
check(c.edge_edit.segment is live_seg,
      "5b answering No leaves the LIVE edit in place")
check(abs(edge_a.parameters["cx"] - 1.5) < 1e-12,
      "5c …untouched, including its in-progress shape")

_asked.clear()
_set_confirm(_stub_confirm(True))           # Yes — cancel then begin
c._begin_pending_edit(other, is_new=False)
check(len(_asked) == 1, "5d answering Yes asked once")
check(c.edge_edit.segment is other,
      "5e …cancelled the live edit and began the new one")
check(abs(edge_a.parameters["cx"] - a_before["cx"]) < 1e-12,
      "5f …and the cancelled edit reverted")
_set_confirm(_stub_confirm(True))
c._cancel_pending_edit()

# ══ 6: commit / cancel with nothing live is a silent no-op ══════════════════
check(not c.edge_edit.is_active(), "6a nothing is live")
depth_a = len(sess_a.command_history._undo_stack)
_logged = []
_real_log = c.log
c.log = lambda m: (_logged.append(m), _real_log(m))[1]
c._commit_pending_edge()
c._cancel_pending_edit()
c._commit_file_edit()
c._cancel_file_edit()
c.log = _real_log
check(_logged == [],
      f"6b commit/cancel with nothing live writes no user-log line ({_logged})")
check(len(sess_a.command_history._undo_stack) == depth_a,
      "6c …and leaves the undo stack unchanged")

# ══ 7: the six _edit_in_progress() guards still block, without prompting ════
# The prompt is for the routes the guards do NOT block; it must not become a
# second guard for the ones they do, or a double-click during a live edit would
# start asking questions instead of being ignored.
c.switch_tab(0)
app.processEvents()
c._begin_pending_edit(edge_a, is_new=False)
live_seg = c.edge_edit.segment
c.edge_edit.update({"cx": 6.25}, 50)
_asked.clear()
_set_confirm(_stub_confirm(True))   # any prompt reached would CHANGE the state

c.handle_canvas_segment_double_clicked(0.0, 0.0)
c.handle_canvas_context_menu(0.0, 0.0)
app.processEvents()

check(_asked == [],
      f"7a a double-click / context menu during a live edit reaches no prompt "
      f"({_asked})")
check(c.edge_edit.segment is live_seg,
      "7b …and the live edit is still the same one")
check(abs(edge_a.parameters["cx"] - 6.25) < 1e-12,
      "7c …with its in-progress shape untouched")

# A canvas handle drag is NOT ignored during a live edit — it is ROUTED to it
# (that is what the create-edit session's cyan handles are for). What must not
# happen is a committed-edge drag starting underneath it, which would snapshot
# a segment nobody is dragging.
c._on_edge_handle_dragged("c", 99.0, 99.0, False)
app.processEvents()
check(abs(edge_a.parameters["cx"] - 99.0) < 1e-12,
      "7d a handle drag is routed to the LIVE edit, not ignored")
check(not c.edge_edit.is_dragging(),
      "7e …and starts no committed-edge drag underneath it")
check(_asked == [], f"7f …still with no prompt ({_asked})")
_set_confirm(_stub_confirm(True))
c._cancel_pending_edit()

# ══ 10: an unusable geometry is refused BEFORE a live edit is put at risk ══
# _begin_file_edit is normally guarded by _edit_in_progress(), so this drives it
# directly. The order matters: the user must not be prompted to throw away a
# live edit for a double-click that then turns out to do nothing.
c.switch_tab(0)
app.processEvents()
c._begin_pending_edit(edge_a, is_new=False)
live_seg = c.edge_edit.segment
_asked.clear()
_set_confirm(_stub_confirm(True))     # would cancel the live edit if reached


class _BareFileSeg:
    type = "file"
    id = 99
    start_index = 0
    end_index = 1


c._begin_file_edit(_BareFileSeg())
app.processEvents()
check(_asked == [],
      f"10a a geometry with no usable edge never reaches the prompt ({_asked})")
check(c.edge_edit.segment is live_seg,
      "10b …so the live edit survives a double-click that does nothing")
_set_confirm(_stub_confirm(True))
c._cancel_pending_edit()

# ══ 3 + 4: closing the owning tab ═══════════════════════════════════════════
c.switch_tab(0)
app.processEvents()
sess_a.is_geometry_modified = True
c._begin_pending_edit(edge_a, is_new=False)
_asked.clear()
_set_confirm(_stub_confirm(False))          # No to the FIRST prompt
n_sessions = len(c.sessions)
c.close_tab(0)
app.processEvents()
check(_asked == ["Edit in progress"],
      f"3a the edit question is asked FIRST and alone ({_asked})")
check(len(c.sessions) == n_sessions, "3b …declining it aborts the close")
check(c.edge_edit.is_active(), "3c …and the edit is still live")

_asked.clear()
_set_confirm(_stub_confirm(True))           # Yes to both
c.close_tab(0)
app.processEvents()
check(_asked == ["Edit in progress", "Unsaved Changes"],
      f"3d both questions, in that order ({_asked})")
check(len(c.sessions) == n_sessions - 1, "3e …and the tab closed")
check(not c.edge_edit.is_active(),
      "3f a completed close leaves no live edit")
# Vacuous as first written: it read `... or s is not sess_a`, and sess_a is the
# tab that was just CLOSED, so the disjunct was true for every surviving session
# and the check could not fail. Assert the real thing — the close recorded
# nothing anywhere that is still open.
_surviving = [(s.display_name, len(s.command_history._undo_stack))
              for s in c.sessions]
check(all(n == 0 for _name, n in _surviving),
      f"3g the close recorded no undo entry on any surviving session "
      f"({_surviving})")
check(sess_a not in c.sessions, "3h …and the closed session really is gone")

def _gone(dlg):
    """True when a dialog is off screen — including when Qt has already
    destroyed its C++ side, which ``isVisible()`` raises on rather than
    answering."""
    try:
        return not dlg.isVisible()
    except RuntimeError:
        return True


# ══ 8: no ORPHANED DIALOG on an ending the dialog did not initiate ═════════
# Rebuild a two-tab state: the close block above consumed one.
while len(c.sessions) < 2:
    c.new_blank_tab()
sess_a = c.sessions[0]
edge_a = _add_circle(sess_a, 0.0, 0.0, 1.0)
a_before = dict(edge_a.parameters)

# The dialog tears itself down through finished -> deleteLater, which fires only
# when it closes ITSELF. Every other ending — a tab switch, a tab close, a second
# edit beginning — used to leave the window on screen with its Apply and Cancel
# pointing at an owner that had forgotten the edit.
c.switch_tab(0)
app.processEvents()
c._begin_pending_edit(edge_a, is_new=False)
dlg = c.edge_edit.dialog
check(dlg is not None and not _gone(dlg),
      "8a the modeless dialog is up while the edit is live")
_set_confirm(_stub_confirm(True))
c.switch_tab(1)
app.processEvents()
check(_gone(dlg),
      "8b a tab switch that cancels the edit closes its dialog")

c.switch_tab(0)
app.processEvents()
c._begin_pending_edit(edge_a, is_new=False)
dlg = c.edge_edit.dialog
sess_a.is_geometry_modified = True
_set_confirm(_stub_confirm(True))
n_before = len(c.sessions)
c.close_tab(0)
app.processEvents()
check(len(c.sessions) == n_before - 1 and _gone(dlg),
      "8c closing the owning tab closes its dialog too")

# …and a second edit beginning must not leave the first one's window behind.
c.switch_tab(0)
app.processEvents()
tab = c.sessions[0]
e1 = _add_circle(tab, 0.0, 0.0, 1.0)
e2 = _add_circle(tab, 5.0, 0.0, 1.0)
c._begin_pending_edit(e1, is_new=False)
first = c.edge_edit.dialog
_set_confirm(_stub_confirm(True))
c._begin_pending_edit(e2, is_new=False)
app.processEvents()
second = c.edge_edit.dialog
check(_gone(first),
      "8d beginning a second edit closes the first one's dialog")
check(second is not None and second is not first and not _gone(second)
      and c.edge_edit.segment is e2,
      "8e …and the new edit has its own, live")
# The re-emitted `rejected` from that close lands on an idle owner. That is the
# silent no-op by construction — it must not take the NEW edit down with it.
check(c.edge_edit.is_active(),
      "8f …and the closing dialog's re-emitted reject did not cancel it")
_set_confirm(_stub_confirm(True))
c._cancel_pending_edit()
app.processEvents()

# ══ 9: the routes that DISCARD a session end the edit unconditionally ═══════
# Not the prompt: opening a tab or replacing the workspace is not abortable in
# the way a switch or a close is. What must hold is that no live edit survives
# pointing at a background or discarded session.
c.switch_tab(0)
app.processEvents()
c._begin_pending_edit(c.sessions[0].project_model.segments[0], is_new=False)
check(c.edge_edit.is_active(), "9a an edit is live before opening a new tab")
c.new_blank_tab()
app.processEvents()
check(not c.edge_edit.is_active(),
      "9b opening a new tab ends it rather than leaving it on a background tab")

c.switch_tab(0)
app.processEvents()
c._begin_pending_edit(c.sessions[0].project_model.segments[0], is_new=False)
live_dialog = c.edge_edit.dialog
c.reset_all_state(new_blank=True)
app.processEvents()
check(not c.edge_edit.is_active() and _gone(live_dialog),
      "9c a full state reset ends it, dialog and all")

# ══ 9d: loading a workspace ends an edit whose session it discards ═════════
import json  # noqa: E402
import tempfile  # noqa: E402

c.switch_tab(0)
app.processEvents()
_ws_seg = _add_circle(c.sessions[0], 2.0, 2.0, 1.0)
_ws = json.dumps(c.workspace_dict())
with tempfile.NamedTemporaryFile("w", suffix=".hws", delete=False) as fh:
    fh.write(_ws)
    _ws_path = fh.name
c._begin_pending_edit(_ws_seg, is_new=False)
_ws_dialog = c.edge_edit.dialog
check(c.edge_edit.is_active(), "9d an edit is live before the workspace load")
_set_confirm(_stub_confirm(True))
c._read_workspace_file(_ws_path)
app.processEvents()
check(not c.edge_edit.is_active() and _gone(_ws_dialog),
      "9e loading a workspace ends it — its session is discarded")
os.unlink(_ws_path)
while len(c.sessions) < 2:
    c.new_blank_tab()
sess_a = c.sessions[0]
edge_a = _add_circle(sess_a, 0.0, 0.0, 1.0)

# Headless defaults: with the real confirm restored, nothing blocks.
_set_confirm(_real_confirm)
c.new_blank_tab()
tail = c.sessions[-1]
tail_edge = _add_circle(tail, 1.0, 1.0, 1.0)
c.switch_tab(len(c.sessions) - 1)
app.processEvents()
c._begin_pending_edit(tail_edge, is_new=False)
check(c.edge_edit.is_active(), "4a an edit is live for the headless close")
c.close_tab(len(c.sessions) - 1)
app.processEvents()
check(not c.edge_edit.is_active(),
      "4b a HEADLESS close takes the default, ends the edit and never blocks")

print()
_wd.cancel()
if _FAILS:
    print(f"RESULT: {len(_FAILS)} FAILED")
    for f in _FAILS:
        print("  - " + f)
    os._exit(1)
print("RESULT: ALL PASS")
os._exit(0)
