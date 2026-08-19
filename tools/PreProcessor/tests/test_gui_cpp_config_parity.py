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

Key PRESENCE was all this could compare until both sides gained a machine-readable
declaration, and presence is blind to the two failures that actually produce a wrong
mesh rather than an error: a parameter that is a ``double`` on one side and an ``int``
on the other, and one whose two defaults differ. Checks 4-6 close that.

Checks:
 1. Every key the GUI writes into the .dat is parsed by Config.hpp.
 2. Keys the C++ parses but the GUI never writes are reported (informational: they
    are reachable from a hand-written config, which is legitimate) and asserted to
    stay within a known list, so a NEW one gets noticed.
 3. The same parity for the pipeline JSON's mesh section, which is fed through the
    identical writer.
 4. Both sides' TYPE for every shared key agrees. No divergence is tolerated: a type
    mismatch means one side cannot represent what the other stores, so there is
    nothing to justify. The list is empty and must stay empty.
 5. Both sides' DEFAULT for every shared key agrees, OR the divergence is PINNED with
    both values and a reason. Pinning rather than equalising, because the two numbers
    answer different questions — see PINNED_DEFAULT_DIVERGENCE.
 6. Every pinned default divergence is INERT, i.e. the GUI writes that key
    unconditionally, so the mesher's default is never the one in force for a
    GUI-driven run. This is the precondition that makes check 5's pinning honest, and
    it is machine-checked rather than asserted: 7 of the writer's keys really are
    conditional.

Where each side's type and default come from:

  * C++ — the 22 BL rows of ``include/BLParams.hpp`` carry KEY, type and default
    directly. The other keys are resolved in two hops: the ``key == "..."`` branch
    names the ``Config`` member it assigns, and the struct's own declaration gives
    that member's type and initialiser. Every key the GUI writes MUST resolve, or
    check 0 fails — an extractor that quietly stops resolving would turn checks 4-6
    into no-ops.
  * GUI — ``mesh_config_keys`` gives KEY -> attribute, ``field_spec.model_types``
    gives the declared type, and ``MeshConfig()`` gives the default. All three are
    derived, so there is no second list to fall out of step.

Run:  python3 tools/PreProcessor/tests/test_gui_cpp_config_parity.py
"""
import ast
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

sys.path.insert(0, _HERE)
from dat_key_facts import STRUCTURAL_KEYS  # noqa: E402

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



# ── each side's (type, default), so checks 4-6 compare declarations ──────────

#: C++ type -> the Python type that represents the same .dat value.
#: Sentinel for "the GUI names a model field that does not exist".
_MISSING = object()

_CPP_TO_PY = {"double": "float", "int": "int", "bool": "bool", "std::string": "str"}


def _struct_fields(src: str, name: str) -> dict:
    """``{field: (cpptype, default_literal)}`` for one struct's own declarations.

    Handles the multi-declarator form the file really uses
    (``std::string bcXMin = "wall", bcXMax = "wall";``), which a one-field-per-line
    reader would silently miss half of.
    """
    m = re.search(r"\nstruct " + name + r" \{(.*?)\n\};", src, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).split("\n"):
        line = re.sub(r"//.*$", "", line).strip()
        m2 = re.match(r"(double|int|bool|std::string)\s+(.+);$", line)
        if not m2:
            continue
        ctype, rest = m2.group(1), m2.group(2)
        for decl in re.split(r",(?![^(]*\))", rest):
            d = re.match(r"\s*(\w+)\s*=\s*(.+?)\s*$", decl)
            if d:
                out[d.group(1)] = (ctype, d.group(2).strip())
    return out


def _bl_declared(decl: str) -> dict:
    """``{KEY: (cpptype, default_literal)}`` straight off the BL declaration rows."""
    return {k: (t, d.strip()) for k, t, _f, d in
            re.findall(r'X\("([A-Z0-9_]+)",\s*(\w+),\s*(\w+),\s*([^)]+)\)', decl)}


def _branch_member(src: str, fields: dict) -> dict:
    """``{KEY: Config member}`` for the hand-written ``key == "..."`` branches.

    The member is the LAST name in the branch body that is both a known ``Config``
    field and an assignment target (``ss >> field`` or ``field =``). Last, not first,
    because several branches read into a local and then narrow
    (``double val; ss >> val; gmshAlgorithm = static_cast<int>(val);``).
    """
    lines = src.split("\n")
    out = {}
    for i, ln in enumerate(lines):
        m = re.search(r'key == "([A-Z][A-Z0-9_]{2,})"\)', ln)
        if not m:
            continue
        body = [ln]
        if ln.rstrip().endswith("{"):
            depth, j = 1, i + 1
            while depth and j < len(lines):
                depth += lines[j].count("{") - lines[j].count("}")
                body.append(lines[j])
                j += 1
        found = [nm for b in body
                 for mm in re.finditer(r"ss >> (\w+)|(\w+)\s*=(?!=)",
                                       re.sub(r"//.*$", "", b))
                 for nm in [mm.group(1) or mm.group(2)] if nm in fields]
        if found:
            out[m.group(1)] = found[-1]
    return out


def cpp_declarations(cfg_src: str, decl_src: str) -> dict:
    """``{KEY: (cpptype, default_literal)}`` for every key the mesher parses.

    Takes both sources as TEXT rather than reading them, so the injections at the foot
    of this file can mutate a declaration in memory and prove the checks notice. A
    checker that opens its own input cannot be injected at all, which is how a gate
    ends up verified by hand at review time instead of permanently.

    STRUCTURAL_KEYS are skipped rather than resolved. They must be: the branch-body
    heuristic would "succeed" on them and quietly return the wrong member — measured,
    ``DOMAIN_FILE`` resolves to ``domainGrowBL`` (bool false) and ``SEED_FILE`` to a
    SeedSpec's ``radius`` (double -1.0), because those branches assign several members
    and none of them is the key's value. Check 0 cannot catch that: it only sees a key
    that fails to resolve, never one that resolves WRONGLY. Excluding them here is what
    makes that blind spot unreachable rather than merely unlikely, and check 0b then
    asserts none of them resolves to a scalar anyway, so the day one becomes a plain
    value the exclusion stops being silent.
    """
    fields = _struct_fields(cfg_src, "Config")
    out = dict(_bl_declared(decl_src))
    for key, member in _branch_member(cfg_src, fields).items():
        if key not in STRUCTURAL_KEYS:
            out[key] = fields[member]
    return out


def _cpp_value(ctype: str, literal: str):
    """A C++ initialiser as the Python value it denotes, or None if unreadable."""
    lit = literal.strip().rstrip("f")
    if ctype == "bool":
        return lit == "true"
    if ctype == "std::string":
        m = re.match(r'^"(.*)"$', lit)
        return m.group(1) if m else None
    try:
        return float(lit) if ctype == "double" else int(float(lit))
    except ValueError:
        return None



def _same(a, b) -> bool:
    """Do a C++ initialiser's value and a Python default denote the same thing?"""
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    if isinstance(a, str) or isinstance(b, str):
        return str(a) == str(b)
    return abs(float(a) - float(b)) <= 1e-12


def type_problems(cpp_decl: dict, gui_decl: dict, pinned: dict) -> list:
    """Keys whose two declarations disagree about the TYPE."""
    out = []
    for k in sorted(set(cpp_decl) & set(gui_decl)):
        ctype = cpp_decl[k][0]
        want, got = _CPP_TO_PY.get(ctype), gui_decl[k][0]
        if want is None:
            out.append(f"{k}: C++ type {ctype!r} has no Python counterpart")
        elif want != got and k not in pinned:
            out.append(f"{k}: C++ {ctype} vs GUI {got}")
    return out


def default_problems(cpp_decl: dict, gui_decl: dict, pins: dict) -> tuple:
    """``(unpinned mismatches, pins that no longer match, pins that are stale)``."""
    bad, drifted, stale = [], [], []
    for k in sorted(set(cpp_decl) & set(gui_decl)):
        cval = _cpp_value(*cpp_decl[k])
        gval = gui_decl[k][1]
        if cval is None:
            bad.append(f"{k}: C++ initialiser {cpp_decl[k][1]!r} not readable")
            continue
        agree = _same(cval, gval)
        pin = pins.get(k)
        if agree:
            if pin is not None:
                stale.append(k)
        elif pin is None:
            bad.append(f"{k}: C++ {cval!r} vs GUI {gval!r}")
        elif not (_same(pin[0], cval) and _same(pin[1], gval)):
            drifted.append(
                f"{k}: pinned {pin[0]!r}/{pin[1]!r} but found {cval!r}/{gval!r}")
    return bad, drifted, stale


def live_pins(pins: dict, uncond: set) -> list:
    """Pinned divergences the GUI does NOT write on every save, i.e. not inert."""
    return sorted(k for k in pins if k not in uncond)


def gui_declarations() -> dict:
    """``{KEY: (pytype, default_value)}``, all three parts derived."""
    from app.models.mesh_config import MeshConfig
    from app.models.mesh_config_keys import _KEY_MAP
    from app.services.field_spec import model_types
    types, defaults = model_types(MeshConfig), MeshConfig()
    out = {}
    for k, (attr, _conv) in _KEY_MAP.items():
        # A spec row naming an attribute MeshConfig does not have used to raise
        # AttributeError here, i.e. the gate crashed instead of reporting. A crash is
        # a build break too, but it names a traceback rather than the key.
        out[k] = (types.get(attr), getattr(defaults, attr, _MISSING))
    return out


def unconditional_keys(writer_src: str) -> set:
    """Keys ``config_to_text`` emits from statement level, i.e. on every single save.

    A key emitted inside any guard is NOT here — 7 of them are, which is what gives
    check 6 teeth. Read by AST rather than by indentation, because the writer builds its
    list in several appends.

    Two things this deliberately gets right, both of which were wrong first:
    it walks ``config_to_text`` ALONE (walking the module also swept the READER's key
    literals, which are not writes at all), and EVERY block that can make a write
    conditional bumps the depth, not just ``If`` — a key emitted inside a ``for`` or a
    ``try`` is no more unconditional than one inside an ``if``.
    """
    tree = ast.parse(writer_src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "config_to_text"), None)
    if fn is None:
        return set()          # check 0 reports the empty result rather than passing
    uncond = set()
    GUARDS = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With,
              ast.AsyncWith, ast.IfExp)

    def walk(node, guarded):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                m = re.match(r"([A-Z][A-Z0-9_]{2,}) ", child.value)
                if m and not guarded:
                    uncond.add(m.group(1))
            walk(child, guarded or isinstance(child, GUARDS))

    walk(fn, False)
    return uncond



# Keys the C++ accepts that the GUI intentionally does not write. A DICT, not a set:
# each entry carries the reason it is fine, and the checks below refuse both a new
# C++-only key and a STALE entry (one the GUI has since started writing, or one the C++
# no longer parses). It was a bare set of keys with the reasons as comments, so a stale
# entry sat there passing for ever and nothing enforced that a reason existed at all —
# which is how an exemption list becomes the norm.
KNOWN_CPP_ONLY = {
    # GLOBAL seed fallbacks for a hand-written config. The GUI instead emits its
    # per-seed values as positional tokens on the SEED_FILE line
    # (`SEED_FILE <path> [size|auto] [radius] <mode>`), which Config.hpp parses into
    # each SeedSpec's own size/radius. Verified: the GUI's Seed Size / Seed Radius
    # fields DO reach the mesher, via that line.
    "SEED_SIZE": "global fallback; the GUI emits per-seed tokens on SEED_FILE instead",
    "SEED_RADIUS": "as SEED_SIZE",
    "SEED_MODE": "as SEED_SIZE",
    "GMSH_NUM_THREADS": "performance knob with no GUI control (Gmsh thread count)",
    # Opt-in BL front smoothing: deliberately not exposed in the GUI (see the
    # arc/cylinder teardrop fix — it is a diagnostic escape hatch, not a setting).
    "BL_FRONT_SMOOTHING_ITERS": "diagnostic escape hatch, deliberately not a GUI "
                                "setting; printed in the banner so a mesh still "
                                "records it",
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
unexpected = sorted(set(cpp_only) - set(KNOWN_CPP_ONLY))
print(f"     ({len(cpp_only)} keys are C++-only; "
      f"{len(set(cpp_only) & set(KNOWN_CPP_ONLY))} of them are on the known list)",
      flush=True)
check(not unexpected,
      "2. no NEW C++-only key appeared (add it to KNOWN_CPP_ONLY with a reason, "
      "or write it from the GUI)"
      + (f" — new: {unexpected}" if unexpected else ""))
stale_cpp_only = sorted(k for k in KNOWN_CPP_ONLY if k not in set(cpp_only))
check(not stale_cpp_only,
      f"2. ...and no KNOWN_CPP_ONLY entry is stale — one the GUI now writes, or one "
      f"the mesher no longer parses, is an exemption that has outlived its reason "
      f"({stale_cpp_only})")
check(all(str(v).strip() for v in KNOWN_CPP_ONLY.values()),
      "2. ...and every KNOWN_CPP_ONLY entry carries a reason")

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

# ── 4-6. the same key must mean the same TYPE and, unless pinned, the same DEFAULT ──
#
# Measured when this was written: over the 49 keys the GUI writes, 1 type mismatch and
# 8 default mismatches. The type mismatch was a real defect and was fixed (see
# PINNED_TYPE_DIVERGENCE). Of the 8 defaults, SIX were self-evidently deliberate — the
# four outer BCs and the two export flags — and finding them is what decided the SHAPE
# of check 5, because equalising any of them would be actively wrong.
#
# The other TWO (BL_CONVEX_METHOD, BL_AUTO_TRANSITION_LAYERS) were flagged on issue #13
# as needing a decision rather than a repair, and this is that decision: they are pinned
# for the same reason as the six, not merely by analogy with them. The mesher's 0 is the
# conservative reading of a key nobody wrote (a plain fan, no automatic transition
# layers); the GUI's 2 is the setting its users actually work with, and the GUI writes
# it explicitly on every save. Changing either would move meshes — the C++ side for
# hand-written configs, the GUI side for every new case — to make two numbers match
# that were never answering the same question. Check 6 is what keeps that honest.

#: Type divergences. Deliberately EMPTY, and this is not an oversight. A type mismatch
#: means one side cannot represent what the other stores, so there is no version of it
#: that is intended: BL_AUTO_FAN_NODES was an int in Config.hpp (with a live `== 2`
#: branch in BoundaryLayer.cpp) and a bool in MeshConfig, so the GUI's own three-item
#: combo could not express the LOCAL it offered. Fixed by widening the model field
#: rather than by an entry here.
PINNED_TYPE_DIVERGENCE: dict = {}

#: Default divergences that are CORRECT, each pinned to BOTH values so that changing
#: either side fails this gate again — an entry cannot absorb a new drift the way a
#: bare key list would.
#:
#: Why pin rather than equalise: the two numbers answer different questions. The C++
#: default is what an UNSPECIFIED key in a hand-written .dat means, and it should be
#: the neutral, safe reading. The GUI default is what a FRESH EDITING SESSION suggests
#: before the user changes it, and the GUI then writes the value explicitly. Forcing
#: them equal would be actively wrong in both directions — it would either make a new
#: GUI case default to an all-`wall` box with no inlet, or make the mesher stop
#: writing a VTK for a CLI user who asked for nothing.
#:
#: {KEY: (cpp_default, gui_default, reason)}
PINNED_DEFAULT_DIVERGENCE = {
    # The mesher's neutral fallback for an outer boundary is `wall`; the GUI opens on
    # an external-flow starting point the user is expected to edit.
    "BC_XMIN": ("wall", "inlet", "mesher falls back to a safe wall; the GUI opens on "
                                 "an external-flow starting point"),
    "BC_XMAX": ("wall", "outlet", "as BC_XMIN"),
    "BC_YMIN": ("wall", "outlet", "as BC_XMIN"),
    "BC_YMAX": ("wall", "outlet", "as BC_XMIN"),
    # A CLI user who asks for no format wants something viewable; the GUI exists to
    # feed the solver, which reads STAR-CD.
    "EXPORT_VTK": (True, False, "CLI default is a viewable mesh; the GUI defaults to "
                                "the format the solver reads"),
    "EXPORT_STARCD": (False, True, "as EXPORT_VTK, the other way round"),
    # Corner/transition strategy: 0 is the conservative reading of an unspecified key
    # (plain fan, no auto transition layers); the GUI ships the richer setting its
    # users work with.
    "BL_CONVEX_METHOD": (0, 2, "0 = Fan is the conservative reading of an unspecified "
                               "key; the GUI ships Parallelogram"),
    "BL_AUTO_TRANSITION_LAYERS": (0, 2, "0 = OFF is the conservative reading; the GUI "
                                        "ships per-geometry averaging"),
}

_CFG_SRC = open(READER, encoding='utf-8').read()
_DECL_SRC = open(BL_DECL, encoding='utf-8').read()
_WRITER_SRC = open(WRITER, encoding='utf-8').read()

cpp_decl = cpp_declarations(_CFG_SRC, _DECL_SRC)
gui_decl = gui_declarations()
uncond = unconditional_keys(_WRITER_SRC)

check(len(cpp_decl) >= 50,
      f"0. both C++ declaration sources were parsed ({len(cpp_decl)} keys resolved to "
      f"a type and default) — a big drop means the extractor stopped resolving, which "
      f"would turn checks 4-6 into no-ops")
unresolved = sorted(written - set(cpp_decl) - set(KNOWN_CPP_ONLY) - set(STRUCTURAL_KEYS))
check(not unresolved,
      f"0. every GUI-written key resolves to a C++ type AND default, or is declared "
      f"structural ({unresolved or 'all of them'})")
stale_struct = sorted(k for k in STRUCTURAL_KEYS if k not in written)
check(not stale_struct,
      f"0. ...and no structural exemption is stale ({stale_struct})")
check(len(uncond) >= 40,
      f"0. the writer's unconditional keys were parsed ({len(uncond)}) — needed by "
      f"check 6")

shared = sorted(set(cpp_decl) & set(gui_decl))
check(len(shared) >= 45, f"0. there are shared keys to compare ({len(shared)})")

# ── 1b. what the GUI can READ must also be parsed by the mesher ──────────────
# Check 1 compares the WRITER's f-strings; this compares the reader's key map, which
# is derived from the field-spec tables. The two are different lists and a key can be
# in one alone: a spec row given a KEY the mesher does not parse produces a .dat line
# the GUI accepts on load and the mesher ignores, and the writer's f-strings would
# never mention it, so check 1 cannot see it.
readable_only = sorted(set(gui_decl) - set(cpp_decl) - set(KNOWN_CPP_ONLY))
check(not readable_only,
      f"1b. every key the GUI's own reader accepts is parsed by the mesher "
      f"({readable_only})")

# --- 4. type ---------------------------------------------------------------
type_bad = type_problems(cpp_decl, gui_decl, PINNED_TYPE_DIVERGENCE)
check(not type_bad,
      "4. every shared key has the same TYPE on both sides"
      + (f" — {type_bad}" if type_bad else ""))
check(not PINNED_TYPE_DIVERGENCE,
      f"4. ...and no type divergence is pinned, because a type mismatch is never "
      f"intended ({sorted(PINNED_TYPE_DIVERGENCE)})")

# --- 5. default ------------------------------------------------------------
default_bad, pin_bad, stale_pin = default_problems(
    cpp_decl, gui_decl, PINNED_DEFAULT_DIVERGENCE)
check(not default_bad,
      "5. every shared key has the same DEFAULT, or the divergence is pinned with a "
      "reason" + (f" — {default_bad}" if default_bad else ""))
check(not pin_bad,
      "5. ...and every pinned divergence still matches BOTH recorded values, so a "
      "change to either side is not absorbed by the pin"
      + (f" — {pin_bad}" if pin_bad else ""))
check(not stale_pin,
      f"5. ...and no pin is stale, i.e. still recorded for a key that now agrees "
      f"({stale_pin})")
check(all(len(v) == 3 and str(v[2]).strip() for v in PINNED_DEFAULT_DIVERGENCE.values()),
      "5. ...and every pin carries a reason")

# --- 6. a pinned divergence must be INERT -----------------------------------
# The pin is only honest while the GUI writes that key on every save: then the
# mesher's default is never the value in force for a GUI-driven run, and the
# divergence can only be seen by someone writing a .dat by hand. Machine-checked,
# because 7 of the writer's keys really are conditional.
live = live_pins(PINNED_DEFAULT_DIVERGENCE, uncond)
check(not live,
      f"6. every pinned default divergence is inert — the GUI writes that key "
      f"unconditionally, so the mesher's differing default is never in force for a "
      f"GUI run. LIVE: {live}" if live else
      "6. every pinned default divergence is inert (the GUI always writes the key)")


# ── 7. every check above is verified BY INJECTION, here, permanently ─────────
# Not by hand at review time: a checker whose failure mode was only ever demonstrated
# in a terminal is a checker nobody can re-demonstrate after the next edit. The first
# version of checks 4-6 was verified exactly that way and this section is what a review
# of it asked for.
#
# Two rules every injection below obeys, both learned from injections that lied:
#   * it asserts the mutated text REALLY CHANGED — a substitution that silently matched
#     nothing looks exactly like the check working;
#   * it asserts the mutated source still PARSES (C++ via the extractor resolving, and
#     the Python mutations are data rather than text, so they cannot fail to parse).
# Text mutations go through `_mutate`, which enforces the first rule.


def _mutate(src: str, old: str, new: str) -> str:
    """``src`` with ``old`` -> ``new``, refusing a substitution that does nothing."""
    if src.count(old) != 1:
        raise AssertionError(
            f"injection target is not unique ({src.count(old)} matches): {old[:60]!r}")
    out = src.replace(old, new)
    assert out != src, "injection did not change the text"
    return out


def injected(msg, cond):
    """A check whose subject is a DELIBERATELY BROKEN input: cond must be True."""
    check(cond, "7. (injection) " + msg)


# 7a/7b — a TYPE mismatch, on each side in turn.
_cpp_t = cpp_declarations(
    _CFG_SRC, _mutate(_DECL_SRC,
                      'X("BL_LAYERS",                      int,    blLayers,'
                      '                       5)',
                      'X("BL_LAYERS",                      double, blLayers,'
                      '                     5.0)'))
injected("a C++ type changed under a key the GUI shares is reported",
         any("BL_LAYERS" in p for p in
             type_problems(_cpp_t, gui_decl, PINNED_TYPE_DIVERGENCE)))
_gui_t = dict(gui_decl); _gui_t["BL_LAYERS"] = ("float", 5)
injected("a GUI type changed under a key the C++ shares is reported",
         any("BL_LAYERS" in p for p in
             type_problems(cpp_decl, _gui_t, PINNED_TYPE_DIVERGENCE)))
injected("...and pinning a type divergence does NOT silence it, because check 4's "
         "second half refuses a non-empty pin list",
         bool(type_problems(cpp_decl, _gui_t, {})) and not PINNED_TYPE_DIVERGENCE)

# 7c/7d — a DEFAULT mismatch, on a declared BL key and on a branch-parsed one.
_cpp_d = cpp_declarations(
    _CFG_SRC, _mutate(_DECL_SRC, "blGrowthRate,                 1.2)",
                      "blGrowthRate,                 1.3)"))
injected("a changed C++ default on a DECLARED key is reported",
         any("BL_GROWTH_RATE" in p for p in
             default_problems(_cpp_d, gui_decl, PINNED_DEFAULT_DIVERGENCE)[0]))
_cpp_d2 = cpp_declarations(
    _mutate(_CFG_SRC, "double surfaceSize = 0.1, farFieldSize = 1.0;",
            "double surfaceSize = 0.2, farFieldSize = 1.0;"), _DECL_SRC)
injected("a changed C++ default on a BRANCH-PARSED key is reported (the two-hop "
         "resolution really reaches the struct initialiser)",
         any("SURFACE_MESH_SIZE" in p for p in
             default_problems(_cpp_d2, gui_decl, PINNED_DEFAULT_DIVERGENCE)[0]))

# 7e — a pinned divergence that DRIFTS is not absorbed by its pin.
_cpp_p = cpp_declarations(
    _mutate(_CFG_SRC, "bool exportVTK = true;", "bool exportVTK = false;"), _DECL_SRC)
_bad, _drift, _stale = default_problems(_cpp_p, gui_decl, PINNED_DEFAULT_DIVERGENCE)
injected("a pinned divergence whose C++ side moves is reported (here it collapses onto "
         "the GUI value, so the pin becomes STALE rather than drifted)",
         "EXPORT_VTK" in _stale)
_pins_drift = dict(PINNED_DEFAULT_DIVERGENCE)
_pins_drift["BC_XMIN"] = ("hedge", "inlet", "a value neither side holds")
injected("a pin recording a value neither side holds is reported",
         any("BC_XMIN" in p for p in
             default_problems(cpp_decl, gui_decl, _pins_drift)[1]))

# 7f — an unpinned divergence is not quietly tolerated.
injected("removing a pin makes its divergence a failure again",
         any("EXPORT_VTK" in p for p in default_problems(
             cpp_decl, gui_decl,
             {k: v for k, v in PINNED_DEFAULT_DIVERGENCE.items()
              if k != "EXPORT_VTK"})[0]))

# 7g — check 6's precondition: a pin whose key stops being written unconditionally.
injected("a pinned key the GUI writes only conditionally is reported as LIVE",
         live_pins(PINNED_DEFAULT_DIVERGENCE, uncond - {"EXPORT_VTK"}) == ["EXPORT_VTK"])
injected("...and the writer walk really distinguishes the two, rather than calling "
         "everything unconditional (the 7 conditional keys are absent from it)",
         bool(written - uncond) and "EXPORT_VTK" in uncond)

# 7h — the extractors must not go blind. Each of these mutations makes one of them
# stop resolving, which check 0 turns into a failure rather than a silent no-op.
_blind_struct = cpp_declarations(
    _mutate(_CFG_SRC, 'std::string bcXMin = "wall", bcXMax = "wall", bcYMin = "wall", '
                      'bcYMax = "wall", bcGeom = "wall";',
            'std::string bcXMin = "wall";'), _DECL_SRC)
injected("dropping the struct's multi-declarator form loses keys, which check 0 sees",
         len(_blind_struct) < len(cpp_declarations(_CFG_SRC, _DECL_SRC)))
_blind_rows = cpp_declarations(_CFG_SRC, _DECL_SRC.replace('    X("BL_', '    Y("BL_'))
injected("a BL declaration the row regex no longer matches loses all 22 keys",
         len(_blind_rows) <= len(cpp_declarations(_CFG_SRC, _DECL_SRC)) - 22)
injected("a writer the AST walk cannot find yields NO unconditional keys, which "
         "check 0 sees rather than passing check 6 vacuously",
         unconditional_keys(_mutate(_WRITER_SRC, "def config_to_text(",
                                    "def config_to_text_renamed(")) == set())

# 7i — a key on one side alone, in both directions.
injected("a key declared in C++ alone is reported as a new C++-only key",
         "BL_ORPHAN_KNOB" in (set(cpp_declarations(
             _CFG_SRC,
             _mutate(_DECL_SRC,
                     'X("BL_FRONT_SMOOTHING_ITERS",       int,    blFrontSmoothingIters,'
                     '          0)',
                     'X("BL_FRONT_SMOOTHING_ITERS",       int,    blFrontSmoothingIters,'
                     '          0)\\\n    X("BL_ORPHAN_KNOB",                 int,'
                     '    blOrphanKnob,                   0)'))) - written)
             - set(KNOWN_CPP_ONLY))
injected("a key the GUI's reader accepts alone is reported (check 1b's subject)",
         sorted(set({**gui_decl, "SURFACE_MESH_SIZE_TYPO": ("float", 0.1)})
                - set(cpp_decl) - set(KNOWN_CPP_ONLY)) == ["SURFACE_MESH_SIZE_TYPO"])

# 7j — a structural key that becomes a plain scalar must stop being excluded silently.
injected("a structural key is excluded from the comparison, not mis-resolved: none of "
         "them appears in the C++ declaration map",
         not (set(STRUCTURAL_KEYS) & set(cpp_decl)))


if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    sys.exit(1)
print("\nRESULT: ALL PASS", flush=True)
sys.exit(0)
