#!/usr/bin/env python3
"""`visualize_dat.py` is handed a MESH: what it says (issue #58).

A path is not a kind. `tools/scripts/visualize_dat.py` handed every path it was
given straight to ``np.loadtxt``, so pointing it at a mesh this repo had just
produced ended in an unhandled traceback whose last line was

    ValueError: could not convert string 'HybMesh2D' to float64 at row 0, column 1.

``HybMesh2D`` is the provenance banner on line 2 of a legacy-VTK header. The
message named neither the file, nor that the file was a mesh, nor the tool that
draws one. This repo has already diagnosed and fixed that exact failure class
once — ``main.py case.hws`` ran ``np.loadtxt`` over JSON and reported
``could not convert string '{' to float64`` (USER-REPORTED 2026-08-13), fixed by
``services/project_file_kind.py``: classify by CONTENT and dispatch. #58 is the
second instance, in the one tool that rule was never applied to.

What this pins down:

  1. A REAL legacy-VTK mesh, meshed here by the real binary, is named as a mesh:
     the message carries the path, says it is a mesh and not a geometry, and
     points at ``view_mesh_vtk.py``. No traceback. The same bytes renamed to
     ``.dat`` get the same answer, because the classification is by CONTENT —
     which is the whole rule, and the half an ``endswith(".vtk")`` would fake.
  2. A genuinely malformed geometry ``.dat`` still reports where the parse
     failed — numpy's ``row``/``column`` is the one useful thing the old message
     had, and a fix that loses it trades one blind error for another. Also the
     files that PARSE and still are not geometries: a one-column ``.dat`` and an
     empty one. ``np.loadtxt`` collapses both to a 1-D array, so the parse
     succeeded and the ORIGINAL failure reappeared one step later, as an
     ``IndexError`` inside ``ax.plot`` naming no file — found by the #58 review,
     after the first fix was already green. ``ndmin=2`` plus a shape check closes
     it, and the one-POINT geometry it has to be told apart from is checked too.
  3. A real geometry ``.dat`` still plots, including one whose first line is a
     ``#`` comment — the VTK check reads the first line, and `#` alone must not
     be enough to condemn a file.
  4. The same check guards the ``--config`` path. `plot_element` swallowed both
     of its loads with a bare ``except``, so a mesh named as an element's
     ``output_file`` or ``input_file`` drew an empty figure and said nothing.
  5. The tool still imports with PyQt6 unavailable. The fix must not reach into
     ``app.services`` for the classifier: this script's dependencies are numpy
     and matplotlib, and #58 rules the GUI package out by name.
  6. No bare ``except:`` survives in the file. Two did, inside
     ``get_seg_endpoints`` — a function whose last caller was deleted on
     2026-05-19 (``f4abc5a``) and which then sat dead for three and a half
     months, carrying the file's only three ``eval()`` calls over
     config-supplied strings. Deleted rather than repaired: fixing the exception
     handling of dead code implies the code is live. The repo-wide standard that
     would have caught it is gated by ``test_silent_exceptions.py``, which walks
     the GUI package only, so nothing reached this file; check 6 is that reach.

Check 1 uses a mesh **produced here**, per the ticket's own acceptance ("a real
VTK file this repo produces, not a constructed fixture"): ``MESH_MODE 1`` on
``examples/topology/square_block.json``, which uses Gmsh nowhere and takes about
a second. No ``.vtk`` is tracked in git (``results/`` is ignored), so there is
nothing to point at instead.

INJECTIONS (A-F on the first pass, G-I after the review), run 2026-09-03
against this file, each reverted after. They are
recorded rather than executed: every one needs the tool patched and re-run in a
subprocess with the mesher behind it, which is minutes in ``run_all.sh`` to
re-prove something that does not change on its own.

  A. ``looks_like_legacy_vtk`` returns ``path.endswith(".vtk")``
       -> FAILS "classification is by CONTENT". This is the injection that
          matters: every other check in group 1 still passed, because the ticket's
          own reproduction happens to have the right extension.
  B. the VTK branch is dead (``if False:``)
       -> FAILS 5 checks across groups 1 and 4.
  C. numpy's ``{e}`` dropped from the malformed-geometry message
       -> FAILS "keeping numpy's row/column".
  D. the message points at ``some_other_tool.py``
       -> FAILS "pointing at the tool that draws one".
  E. ``plot_element`` swallows its ``output_file`` load again
       -> FAILS both group-4 report checks.
  F. the classifier is imported from ``app.services.project_file_kind``
       -> FAILS "pulls in no part of the GUI package".
  G. the ``(N, >=2)`` shape check is dead (``if False:``)
       -> FAILS both parses-but-isn't checks.
  H. ``ndmin=2`` dropped from the ``np.loadtxt`` call
       -> FAILS those two AND the one-POINT check, which is the point: without
          ``ndmin`` the one-column file and the one-point geometry are the same
          1-D array, so no shape check can separate them and refusing one
          refuses the other.
  I. one ``except OSError:`` turned back into a bare ``except:``
       -> FAILS check 6, naming the line number.

Two checks were WEAKER than they read, and only the injections showed it. "saying
it is a mesh" was ``"mesh" in out.lower()`` — satisfied by the banner ``HybMesh2D``
inside numpy's own message, so injection B passed it while deleting the feature.
And group 4's first check did not name the FIELD, so injection E passed it on the
*other* element's warning. Both are tightened above.

WHAT THE INJECTIONS DID NOT FIND, and the review did: the first fix guarded the
PARSE and not the SHAPE, so ``visualize_dat.py one_column.dat`` still ended in a
traceback naming no file — this ticket's exact complaint, moved from
``np.loadtxt`` to ``ax.plot`` three lines later. Every injection above mutates
the new code, so none of them could reach a path the new code never touched.
That is the standing limit of injection as evidence, and the reason group 2 now
carries three more checks.

BLIND SPOTS, named rather than papered over:

  * Only the legacy-VTK kind is recognised. A ``.vrt``/``.cel``/``.bnd`` handed
    to this tool still reaches ``np.loadtxt`` — but those are columns of numbers,
    so they parse, and the failure is a wrong picture rather than a wrong
    message. #58 scopes every other kind out.
  * Nothing here renders. The checks read the process's exit code and stderr;
    that the figure is correct is not this file's claim.

Run:  python3 tools/PreProcessor/tests/test_visualize_dat_kind.py
Check 1 self-skips if ./build/HybMesh2D has not been built.
"""
import json
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_SCRIPTS = os.path.join(_REPO, "tools", "scripts")
_VIS = os.path.join(_SCRIPTS, "visualize_dat.py")
_TOPOLOGY = os.path.join(_REPO, "examples", "topology", "square_block.json")
sys.path.insert(0, _HERE)
from mesher_bin import mesher_env as _mesher_env  # noqa: E402

failures = []
skipped = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run_vis(*args):
    """visualize_dat.py under Agg, so nothing tries to open a window."""
    env = dict(os.environ, MPLBACKEND="Agg")
    p = subprocess.run([sys.executable, _VIS, *args], cwd=_REPO, env=env,
                       capture_output=True, text=True, timeout=180)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def make_real_vtk(tmp):
    """Mesh ``square_block.json`` with the real binary; return the .vtk path."""
    conf = os.path.join(tmp, "mb.dat")
    stem = os.path.join(tmp, "square")
    with open(conf, "w", encoding="utf-8") as f:
        f.write("MESH_MODE 1\n"
                f"MESH_TOPOLOGY_FILE {_TOPOLOGY}\n"
                "MB_SPLIT_QUADS 1\n"
                "EXPORT_VTK 1\n"
                "EXPORT_STARCD 0\n"
                "BC_GEOM wall\n"
                f"OUTPUT_FILENAME {stem}.vtk\n")
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=300)
    vtk = stem + ".vtk"
    if p.returncode != 0 or not os.path.exists(vtk):
        return None
    return vtk


def main():
    with tempfile.TemporaryDirectory() as tmp:
        vtk = None
        # ── 1. a real mesh, named as a mesh ────────────────────────────────
        if not os.path.exists(_BIN):
            skipped.append("1. real-VTK checks (no ./build/HybMesh2D)")
        else:
            vtk = make_real_vtk(tmp)
            if vtk is None:
                skipped.append("1. real-VTK checks (the mesher did not run)")
            else:
                first = open(vtk, encoding="utf-8").readline()
                check("1. the mesh this repo just produced really is legacy VTK",
                      first.startswith("# vtk DataFile Version"))
                rc, out = run_vis(vtk)
                check("1. handing it to visualize_dat.py fails, rather than "
                      "drawing something", rc != 0)
                check("1. ...naming the file", vtk in out)
                # Deliberately NOT `"mesh" in out.lower()`: the banner numpy
                # chokes on is `HybMesh2D`, so that phrasing was satisfied by
                # the very message this ticket is replacing.
                check("1. ...saying it is a mesh, not a geometry",
                      "VTK" in out and "not a geometry" in out)
                check("1. ...and pointing at the tool that draws one",
                      "view_mesh_vtk.py" in out)
                check("1. ...with no traceback, which names a numpy internal "
                      "instead of the user's mistake",
                      "Traceback (most recent call last)" not in out)
                # The rule is CONTENT, not extension: the same bytes under a
                # .dat name are the realistic case (someone renamed a mesh, or
                # a config points at the wrong output), and an `endswith(.vtk)`
                # check would sail past it back into the numpy traceback.
                renamed = os.path.join(tmp, "renamed_mesh.dat")
                with open(vtk, "rb") as src, open(renamed, "wb") as dst:
                    dst.write(src.read())
                rc, out = run_vis(renamed)
                check("1. a mesh named .dat is still recognised as a mesh — the "
                      "classification is by CONTENT, never by extension",
                      rc != 0 and "renamed_mesh.dat" in out
                      and "view_mesh_vtk.py" in out)

        # ── 2. a malformed geometry stays diagnosable ──────────────────────
        bad = os.path.join(tmp, "bad_geometry.dat")
        with open(bad, "w", encoding="utf-8") as f:
            f.write("0.0 0.0\n0.1 0.2\nnot-a-number 0.3\n0.4 0.5\n")
        rc, out = run_vis(bad)
        check("2. a malformed geometry .dat still fails", rc != 0)
        check("2. ...naming the file", "bad_geometry.dat" in out)
        check("2. ...and keeping numpy's row/column, the one useful thing the "
              "old message had", "row 2" in out and "column 1" in out)
        check("2. ...without a traceback",
              "Traceback (most recent call last)" not in out)
        # A file that PARSES and still is not a geometry. Found by the #58
        # review: `np.loadtxt` collapses a one-column file to a 1-D array, so
        # the parse succeeded and `ax.plot(pts[:, 1])` died one step later with
        # an IndexError naming no file -- the ticket's own failure, one remove
        # further in. `ndmin=2` plus a shape check is what closes it.
        for name, body in (("one_column.dat", "0.1\n0.2\n0.3\n"),
                           ("empty.dat", "")):
            thin = os.path.join(tmp, name)
            with open(thin, "w", encoding="utf-8") as f:
                f.write(body)
            rc, out = run_vis(thin)
            check(f"2. {name} parses but is not a geometry, and is REFUSED by "
                  f"name rather than crashing in ax.plot",
                  rc != 0 and name in out
                  and "Traceback (most recent call last)" not in out)
        # ...and the one-POINT geometry that `ndmin=2` disambiguates it from
        # must still draw. Without ndmin both are 1-D and indistinguishable.
        one_point = os.path.join(tmp, "one_point.dat")
        with open(one_point, "w", encoding="utf-8") as f:
            f.write("0.1 0.2\n")
        rc, out = run_vis(one_point)
        check("2. a one-POINT geometry still plots — the shape check must not "
              "swallow the case it has to be told apart from", rc == 0)

        # ── 3. a real geometry still plots ─────────────────────────────────
        good = os.path.join(tmp, "good.dat")
        with open(good, "w", encoding="utf-8") as f:
            f.write("# a leading comment, which numpy skips\n")
            f.write("\n".join(f"{i * 0.1} {i * 0.1 * i}" for i in range(20)))
            f.write("\n")
        rc, out = run_vis(good)
        check("3. a geometry .dat whose first line is a # comment still plots — "
              "'#' alone is not a VTK header", rc == 0)

        # ── 4. the --config path gets the same answer ──────────────────────
        # Reusing group 1's mesh rather than meshing again: it is the same bytes
        # and the mesher is the slowest thing here.
        if vtk is None:
            skipped.append("4. --config checks (no mesh to point an element at)")
        else:
            cfg = os.path.join(tmp, "cfg.json")
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump({"elements": [
                    {"output_file": vtk, "segments": []},
                    {"output_file": good, "input_file": vtk, "segments": []},
                ]}, f)
            rc, out = run_vis("--config", cfg)
            # Naming the FIELD, because the second element below names the
            # same mesh as its input_file: without this the check passes on the
            # other element's warning.
            check("4. an element whose output_file is a mesh is REPORTED, "
                  "not silently skipped",
                  "output_file" in out and vtk in out
                  and "view_mesh_vtk.py" in out)
            check("4. ...and so is one whose input_file is",
                  out.count("view_mesh_vtk.py") >= 2)
            check("4. ...without a traceback",
                  "Traceback (most recent call last)" not in out)
            # DELIBERATE asymmetry with group 1: a positional mesh is the whole
            # request and exits 1, while one bad element among several is a
            # warning — the other elements still draw. Pinned because it is a
            # decision, and an unpinned decision reads as an oversight.
            check("4. ...and the run still SUCCEEDS: one bad element does not "
                  "throw away the elements that are fine", rc == 0)

        # ── 5. no PyQt6, no GUI package ────────────────────────────────────
        prog = (
            "import sys\n"
            "class _Block:\n"
            "    def find_module(self, name, path=None):\n"
            "        return self.find_spec(name, path)\n"
            "    def find_spec(self, name, path=None, target=None):\n"
            "        if name == 'PyQt6' or name.startswith('PyQt6.'):\n"
            "            raise ImportError('PyQt6 blocked by test')\n"
            "        return None\n"
            "sys.meta_path.insert(0, _Block())\n"
            f"sys.path.insert(0, {_SCRIPTS!r})\n"
            "import visualize_dat\n"
            "assert not [m for m in sys.modules if m == 'app' "
            "or m.startswith('app.')], 'the GUI package was imported'\n"
            "print('IMPORT OK')\n"
        )
        p = subprocess.run([sys.executable, "-c", prog], cwd=_REPO,
                           env=dict(os.environ, MPLBACKEND="Agg"),
                           capture_output=True, text=True, timeout=180)
        check("5. visualize_dat.py imports with PyQt6 unavailable, and pulls in "
              "no part of the GUI package",
              p.returncode == 0 and "IMPORT OK" in (p.stdout or ""))
        if p.returncode != 0:
            print("    | " + (p.stderr or "").strip().replace("\n", "\n    | "))

        # ── 6. the residue cannot come back ────────────────────────────────
        # `never except Exception: pass` is a repo-wide standard, but its gate
        # (test_silent_exceptions.py) walks the GUI package only, so this script
        # is outside it -- which is how two bare `except:` survived here inside
        # a function whose last caller was deleted on 2026-05-19 (f4abc5a). The
        # function is gone; this is the cheap check that neither comes back.
        src = open(_VIS, encoding="utf-8").read()
        bare = [i + 1 for i, ln in enumerate(src.splitlines())
                if ln.strip().startswith("except:")]
        check("6. no bare `except:` in visualize_dat.py — the repo standard's "
              "own gate does not reach tools/scripts/, so this is the only "
              "thing that does" + (f" — found at lines {bare}" if bare else ""),
              not bare)

    for s in skipped:
        print("SKIP " + s)
    print("\nRESULT: " + ("ALL PASS" if not failures
                          else f"{len(failures)} FAILURE(S)"))
    for f in failures:
        print("  - " + f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
