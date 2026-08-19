#!/usr/bin/env python3
"""GUI ↔ C++ configuration parity (finding N13's real gate).

The GUI writes a ``Background_para.dat`` and HybMesh2D parses it key by key. Those
two lists are maintained in different languages, in different files, by hand:

  * writer — ``tools/PreProcessor/gui/app/models/mesh_config_io.py``
  * reader — ``include/Config.hpp`` (``key == "..."`` branches) plus
    ``include/BLParams.hpp`` (the ``X("KEY", type, field, default)`` declaration
    the boundary-layer parsers are generated from — those 22 keys have no
    ``key ==`` branch of their own any more, and reading only the branches would
    have reported all 22 as silently ignored)

Nothing enforced that they agree. A key the GUI writes but the C++ does not parse
is the worst kind of bug in a pre-processor: the user sets a value, the GUI saves
it, the mesher silently ignores it, and the mesh is not the one that was asked
for — with no error anywhere. That is exactly what happened before (finding R2:
the C++ read per-segment ``auto_split``/``split_threshold`` the GUI never wrote).

This test is deliberately **static** — it parses both sources as text and needs no
compiled binary — so it can gate every push, including on a runner with no C++
toolchain.

Checks:
 1. Every key the GUI writes into the .dat is parsed by Config.hpp.
 2. Keys the C++ parses but the GUI never writes are reported (informational: they
    are reachable from a hand-written config, which is legitimate) and asserted to
    stay within a known list, so a NEW one gets noticed.
 3. The same parity for the pipeline JSON's mesh section, which is fed through the
    identical writer.

Run:  python3 tools/PreProcessor/tests/test_gui_cpp_config_parity.py
"""
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

WRITER = os.path.join(_GUI, "app", "models", "mesh_config_io.py")
READER = os.path.join(_REPO, "include", "Config.hpp")
BL_DECL = os.path.join(_REPO, "include", "BLParams.hpp")

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def gui_written_keys() -> set:
    """Keys the GUI emits into a Background_para.dat.

    Matched from the writer's f-string lines (``f"BL_LAYERS {cfg.bl_layers}"``),
    which is the single place the .dat is produced.
    """
    src = open(WRITER, encoding="utf-8").read()
    # A written line always starts with the KEY followed by a space, inside a
    # (possibly f-prefixed) double-quoted string.
    return set(re.findall(r'f?"([A-Z][A-Z0-9_]{2,}) ', src))


def cpp_parsed_keys() -> set:
    """Every .dat key the mesher parses, from BOTH places it can be declared.

    A hand-written ``key == "..."`` branch in Config.hpp, or a row of the
    boundary-layer declaration in BLParams.hpp — whose 22 keys are parsed by a
    branch GENERATED from that row, so there is no literal to grep for. Missing
    the second source would report all 22 as silently ignored, which is the
    opposite of the truth: they are the keys that can no longer BE missed.
    """
    src = open(READER, encoding="utf-8").read()
    keys = set(re.findall(r'key == "([A-Z][A-Z0-9_]{2,})"', src))
    decl = open(BL_DECL, encoding="utf-8").read()
    declared = set(re.findall(r'X\("([A-Z][A-Z0-9_]{2,})"', decl))
    assert len(declared) >= 20, (
        f"only {len(declared)} rows found in {BL_DECL} — this regex no longer "
        "matches the declaration, which would make check 1 pass for the wrong "
        "reason")
    return keys | declared


# Keys the C++ accepts that the GUI intentionally does not write as standalone
# lines. Each entry below was checked against both sources — the list is not a
# place to silence a finding, it is a record of why that key is fine. A NEW
# C++-only key fails the test so it gets the same scrutiny.
KNOWN_CPP_ONLY = {
    # GLOBAL seed fallbacks for a hand-written config. The GUI instead emits its
    # per-seed values as positional tokens on the SEED_FILE line
    # (`SEED_FILE <path> [size|auto] [radius] <mode>` — mesh_config_io.py:296),
    # which Config.hpp parses into each SeedSpec's own size/radius. Verified: the
    # GUI's Seed Size / Seed Radius fields DO reach the mesher, via that line.
    "SEED_SIZE", "SEED_RADIUS", "SEED_MODE",
    # Performance knob with no GUI control (thread count for Gmsh).
    "GMSH_NUM_THREADS",
    # Opt-in BL front smoothing: deliberately not exposed in the GUI (see the
    # arc/cylinder teardrop fix — it is a diagnostic escape hatch, not a setting).
    "BL_FRONT_SMOOTHING_ITERS",
}

if not os.path.exists(READER):
    print(f"SKIP {READER} not found (C++ sources absent)", flush=True)
    sys.exit(0)

written = gui_written_keys()
parsed = cpp_parsed_keys()

check(len(written) >= 40,
      f"0. the writer was parsed ({len(written)} keys found — a big drop means "
      "this test's regex no longer matches the writer)")
check(len(parsed) >= 40,
      f"0. Config.hpp was parsed ({len(parsed)} keys found)")

# ── 1. nothing the GUI writes may be silently ignored ─────────────────────
ignored = sorted(written - parsed)
check(not ignored,
      "1. every GUI-written key is parsed by Config.hpp"
      + (f" — SILENTLY IGNORED: {ignored}" if ignored else ""))

# ── 2. C++-only keys stay within the reviewed list ────────────────────────
cpp_only = sorted(parsed - written)
unexpected = sorted(set(cpp_only) - KNOWN_CPP_ONLY)
print(f"     ({len(cpp_only)} keys are C++-only; "
      f"{len(set(cpp_only) & KNOWN_CPP_ONLY)} of them are on the known list)",
      flush=True)
check(not unexpected,
      "2. no NEW C++-only key appeared (add it to KNOWN_CPP_ONLY with a reason, "
      "or write it from the GUI)"
      + (f" — new: {unexpected}" if unexpected else ""))

# ── 3. the same writer backs the pipeline JSON's mesh section ─────────────
from app.models.mesh_config import MeshConfig  # noqa: E402
from app.models.pipeline_config import PipelineConfig  # noqa: E402

pc = PipelineConfig(name="parity", mesh={"bl_layers": 4})
mc = pc.build_mesh_config(["/tmp/x.dat"])
check(isinstance(mc, MeshConfig) and mc.bl_layers == 4,
      "3. the pipeline mesh section builds the same MeshConfig the writer emits")

# A round-trip proves the writer/reader pair inside the GUI agrees with itself,
# so any parity break above is genuinely a GUI-vs-C++ issue, not a GUI bug.
import tempfile  # noqa: E402

with tempfile.NamedTemporaryFile("w", suffix="_parity.dat", delete=False) as tf:
    dat = tf.name
try:
    mc.bl_layers = 9
    mc.save_to_file(dat)
    with open(dat, encoding="utf-8") as f:
        keys_on_disk = {ln.split()[0] for ln in f
                        if ln.strip() and not ln.lstrip().startswith("#")
                        and len(ln.split()) >= 2}
    missing = sorted(k for k in keys_on_disk
                     if re.fullmatch(r"[A-Z][A-Z0-9_]{2,}", k) and k not in parsed)
    check(not missing,
          "3. every key in an actually-written .dat is parsed by Config.hpp"
          + (f" — IGNORED: {missing}" if missing else ""))
    back = MeshConfig()
    back.load_from_file(dat)
    check(back.bl_layers == 9, "3. the .dat round-trips through the GUI reader")
finally:
    if os.path.exists(dat):
        os.remove(dat)

if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    sys.exit(1)
print("\nRESULT: ALL PASS", flush=True)
sys.exit(0)
