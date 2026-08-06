#!/usr/bin/env python3
"""getPGrid / bDecompose ``para.in`` ↔ binary stdin parity.

Follow-up to the STL3d bug (see ``test_stl3d_case_parity.py``): ``para_in_text()``
had drifted one line out of step with ``stl3d.cpp``, which silently produced an
empty phi field **with exit code 0**. Because that failure was invisible, "the
other Python-writes / C++-reads interfaces are probably fine" was not something to
assume — so both remaining ones are audited here and the result is locked in.

Audit result (2026-08-06): getPGrid and bDecompose are **correct**. This file
exists to keep them that way, and to guard the two specific hazards found while
checking:

  * **getPGrid has a ``#if 0`` block containing a ``cin >> yn48`` prompt.** It is
    compiled out today, which is exactly why the writer's 11 answers line up.
    Re-enabling that block would shift every later answer by one — the same class
    of silent failure as the STL3d bug — so this test fails if it becomes active.
  * **bDecompose ships as a prebuilt binary with no source**, so its stdin order
    cannot be read from code. The reference ``para.in`` in its work directory is
    the only ground truth; the writer is compared against that.

Checks:
 1. getPGrid's live ``cin >>`` sequence (with ``#if 0`` regions removed) matches
    the answers ``generate_getpgrid_para`` writes, one per read, in order.
 2. The ``#if 0`` prompt is still compiled out.
 3. Branch-dependent reads are accounted for: the Patran path is not taken (the
    GUI always answers "y" to starcd), and the mixed/slice pair only exists
    because the writer answers "y" to stifcons.
 4. bDecompose's writer reproduces the shipped reference para.in token for token.
 5. Neither writer emits a line containing whitespace where the binary reads a
    single token with ``cin >>``.

Run:  python3 tools/PreProcessor/tests/test_solver_para_in_parity.py
"""
import os
import re
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

GETPGRID_CPP = os.path.join(_REPO, "solver", "preprocess", "getPGrid",
                            "src", "getPGrid.cpp")
BDECOMPOSE_REF = os.path.join(_REPO, "solver", "preprocess", "bDecompose",
                              "work", "para.in")

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def strip_if_zero(src: str) -> str:
    """Remove ``#if 0 ... #endif`` regions (handles simple nesting)."""
    out, depth, i = [], 0, 0
    for line in src.splitlines(keepends=True):
        s = line.strip()
        if re.match(r"#if\s+0\b", s):
            depth += 1
            continue
        if depth:
            if s.startswith("#if"):
                depth += 1
            elif s.startswith("#endif"):
                depth -= 1
            continue
        out.append(line)
        i += 1
    return "".join(out)


from app.models.solver_config import SolverConfig  # noqa: E402


def writer_lines(method: str, **attrs) -> list:
    cfg = SolverConfig()
    cfg.input_vrt_file = "case.vrt"
    cfg.input_cel_file = "case.cel"
    cfg.input_bnd_file = "case.bnd"
    cfg.output_grid_file = "case.grid"
    cfg.output_bc_file = "case.bc"
    for k, v in attrs.items():
        setattr(cfg, k, v)
    path = tempfile.mktemp(suffix="_para.in")
    try:
        getattr(cfg, method)(path)
        with open(path, encoding="utf-8") as f:
            return f.read().rstrip("\n").split("\n")
    finally:
        if os.path.exists(path):
            os.remove(path)


# ── getPGrid ──────────────────────────────────────────────────────────────
if not os.path.exists(GETPGRID_CPP):
    print(f"SKIP {GETPGRID_CPP} not found (solver sources absent)", flush=True)
else:
    raw = open(GETPGRID_CPP, encoding="utf-8", errors="replace").read()
    main_src = raw[raw.index("main() {"):]

    # 2. The disabled prompt must stay disabled.
    check("cin >> yn48" not in strip_if_zero(main_src),
          "2. getPGrid's `cin >> yn48` prompt is still compiled out (#if 0) — "
          "re-enabling it shifts every later answer by one")
    check("yn48" in main_src,
          "2. (sanity: the yn48 block is still present in the file, just disabled)")

    live = strip_if_zero(main_src)
    # Reads up to and including the output bc filename; anything after belongs to
    # the geometry loop, not the answer file. The \b matters: a plain substring
    # search for "cin >> fn_bc" also matches "cin >> fn_bcflags" and would cut the
    # sequence short at the third read.
    _end = re.search(r"cin\s*>>\s*fn_bc\b", live)
    check(_end is not None, "1. found getPGrid's final answer-file read (fn_bc)")
    upto = live[:_end.end()] if _end else live
    reads = [m.strip() for m in re.findall(r"cin\s*>>\s*([A-Za-z_][A-Za-z0-9_]*)", upto)]
    print(f"     getPGrid live reads: {reads}", flush=True)

    # 3. The Patran branch is not taken: the writer always answers "y" to starcd,
    #    so fn_neutral is never read.
    check("fn_neutral" in reads,
          "3. (sanity: the Patran else-branch read exists in the source)")
    on_path = [r for r in reads if r != "fn_neutral"]

    lines = writer_lines("generate_getpgrid_para", is_3d=False,
                         reorient_mesh=True, mixed_mesh=False,
                         slice_to_simplex=False)
    check(len(on_path) == len(lines),
          f"1. one answer per live read ({len(lines)} lines vs {len(on_path)} reads: "
          f"{on_path})")

    if len(on_path) == len(lines):
        # Spot-check the positions that actually carry data (filenames), since a
        # shift would put a y/n answer where a filename belongs.
        want = {"fn_vtx": "case.vrt", "fn_cel": "case.cel",
                "fn_bcflags": "case.bnd", "fn_out": "case.grid",
                "fn_bc": "case.bc"}
        wrong = [(name, lines[i], want[name])
                 for i, name in enumerate(on_path)
                 if name in want and lines[i] != want[name]]
        check(not wrong,
              "1. every filename answer lands on the read that expects it"
              + (f" (read/got/want: {wrong})" if wrong else ""))
        # And the y/n slots must actually be y/n.
        bad_yn = [(name, lines[i]) for i, name in enumerate(on_path)
                  if name not in want and lines[i] not in ("y", "n")]
        check(not bad_yn,
              "1. every y/n slot holds y or n"
              + (f" (read/got: {bad_yn})" if bad_yn else ""))

    # 3. The mixed/slice pair is conditional on the stifcons answer, which the
    #    writer hardcodes to "y" — so both reads are on the path.
    check("write_stifcons_files" in live and "cin >> mixedf" in live,
          "3. the mixed/slice reads are guarded by the stifcons answer")
    stif_idx = on_path.index("yn_stif") if "yn_stif" in on_path else -1
    check(stif_idx >= 0 and lines[stif_idx] == "y",
          "3. ...and the writer answers 'y' there, so those two reads happen")

# ── bDecompose ────────────────────────────────────────────────────────────
if not os.path.exists(BDECOMPOSE_REF):
    print(f"SKIP {BDECOMPOSE_REF} not found", flush=True)
else:
    ref = [ln for ln in open(BDECOMPOSE_REF, encoding="utf-8").read().split("\n")
           if ln.strip()]
    got = writer_lines("generate_bdecompose_para",
                       output_grid_file="mesh_cartesian.grid",
                       output_bc_file="mesh_cartesian.bc",
                       num_partitions=4)
    got = [ln for ln in got if ln.strip()]
    check(got == ref,
          "4. the bDecompose writer reproduces the shipped reference para.in"
          + (f"\n     got: {got}\n     ref: {ref}" if got != ref else ""))

# ── 5. no whitespace inside a single-token answer ─────────────────────────
for method, kwargs in (("generate_getpgrid_para", {}),
                       ("generate_bdecompose_para", {})):
    lines = writer_lines(method, **kwargs)
    # The domain-style multi-number lines belong to STL3d, not these two writers:
    # every line here answers a single `cin >> token` read.
    multi = [ln for ln in lines if len(ln.split()) != 1]
    check(not multi,
          f"5. {method} emits single-token lines only"
          + (f" (multi-token: {multi})" if multi else ""))

if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    sys.exit(1)
print("\nRESULT: ALL PASS", flush=True)
sys.exit(0)
