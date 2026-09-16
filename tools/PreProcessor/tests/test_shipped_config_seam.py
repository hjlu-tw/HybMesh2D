#!/usr/bin/env python3
"""ONE helper reads a shipped ``config/*.dat`` and retargets it, and it reads from disk.

There is no production code behind this gate. The thing under test is a SEAM:
``mb_shipped_config.shipped_config`` is the only implementation in this tree of
"read the shipped ``.dat``, repoint its paths at this checkout, retarget its
output at ``@STEM@``, raise by name when a rewrite stops landing", and every gate
that drives one of the five shipped multi-block configs goes through it.

IT WAS THREE COPIES UNTIL #126. ``base_config`` in the C-grid surface gate,
``base_config`` in the O-grid's and ``shipped_config`` in the smoothing gate were
one shape written three times, diverging in what they retargeted and in how they
said a rewrite had stopped landing. #124 put the same RECORD at all three with a
gate under it, because deferring the collapse had to be a visible decision rather
than an undocumented state; #126 collapsed them and this gate changed subject with
them. What it held before — every copy carries a record, the records agree on the
count, each names the others — is gone, because a set of one has nothing to agree
about. What replaced it is the property that makes those checks unnecessary: there
is ONE, and a second is a failure the moment it lands.

The reason the helper must read from DISK is the reason all three copies existed:
a shipped config is documentation a user runs (``./run.sh -conf
config/multiblock_cgrid.dat`` is in ``CLAUDE.md``), so a test that composed an
equivalent one would leave an edit to the shipped file invisible from the gate
that is supposed to be covering it. A collapse ending in a composed config would
have removed the reason for the collapse. Check 2 is that property, and it is
measured rather than argued.

Checks:
 1. THE SET IS DERIVED FROM THE TREE, never listed here, and holds exactly ONE
    member: `mb_shipped_config.py::shipped_config`. Every ``*.py`` under the repo
    (minus `build/`, `results/`, `.git/` and the caches, named in `_SKIP_DIRS`) is
    parsed, and a function counts as a retargeter when it BOTH opens for reading a
    path built by joining `"config"` with a `.dat` name AND emits a string literal
    containing `@STEM@` outside its docstring. The docstring is excluded on
    purpose: this seam's own prose talks about `@STEM@`, and a rule that read prose
    would conjure members out of functions that retarget nothing.
 2. AN EDIT TO A SHIPPED CONFIG IS VISIBLE FROM THE GATE THAT DRIVES IT, measured
    through the REAL accessors — `test_multiblock_cgrid_surface.base_config`,
    `test_multiblock_ogrid_surface.base_config` and the smoothing gate's
    `shipped_config` call for the three configs no other gate runs. A temp
    checkout carries an edited copy of each shipped config, `mb_shipped_config`'s
    `_REPO` is pointed at it, and each accessor must return the EDITED value. A
    composed stand-in is run through the identical assertion as the negative
    control and must fail it — otherwise the check would pass on a helper that had
    stopped reading the file.
 3. THE PER-GATE VARIATION LANDS. `bc_geom`, `thickness` and `topo` each reach the
    text, and the shipped value each replaces is gone from it. This is what the
    collapse had to absorb rather than flatten: the three copies took different
    extra arguments, which is why #115 deferred it as "a refactor across three gate
    files and three owners".
 4. EVERY GUARD RAISES, AND NAMES THE FILE AND THE KEY. Five of them, each driven
    against a mutated config in a temp checkout: a path key whose value stops
    resolving, a path under a key `_MB_PATH_KEYS` does not carry, a missing
    `OUTPUT_FILENAME`, a `MESH_MODE` that is no longer 1, and a retarget the caller
    asked for under a key the config does not have. Four of those were a HAND PROBE
    recorded in a comment (2026-09-11) rather than a check, because editing a
    shipped config under the gate that reads it is a hazard this repo does not ship.
    The `repo=` argument is what removed the hazard: the edit lands in a temp tree.
 5. THE ARGUMENTS REFUSE WHAT THEY CANNOT MEAN — a directory for a key that holds
    no path, an override for a key the retargeting rule owns, a key given twice
    under two arguments, one path for a key the config repeats. A caller that got
    one of these wrong and was answered silently would be testing something other
    than what it wrote.

 injections. Check 1 is verified in-process against a COPY of the seam and its
    three callers in a temp tree, with a SECOND copy added in each spelling of
    `_SPELLINGS`: the plain one, a concatenated literal, an f-string, a method
    reading `self._CONF`, a retargeter nested in a factory, and one naming the
    placeholder through a module constant. Every one of those is a hole this
    derivation was once walked through — four found by #124's Standards review
    WRITING them rather than reading the rule, and the constant found by the SEAM
    ITSELF, which spells the placeholder once as `PLACEHOLDER` and was invisible
    here on the day it landed: the gate reported a tree with no retargeter in it
    and passed its own injections. Each puts a RUNNER beside the copy as the
    negative control, since a rule loose enough to catch them all would catch the
    runner too and report a set several times its real size. Injection 0 is the
    unmutated control and injection 2 deletes the seam, because a set of zero is
    not a set of one. Check 2 carries its own negative control (the composed
    stand-in), and checks 4 and 5 are injections by construction: each is a
    mutation that must raise.

Known blind spots, stated rather than pretended away:

 a. The derivation knows ONE spelling of "read a file": a call to `open()`. A
    second copy reading its config through `pathlib.Path.read_text()`, or through
    a helper in another module that hands back the text, is invisible here and its
    silence would look exactly like today's PASS.
 b. It reads the retarget placeholder as `@STEM@` — as a literal, or as a name
    bound to one in the same module. A copy that named its placeholder something
    else, or imported the seam's `PLACEHOLDER` from here, is a copy this gate does
    not see. Both (a) and (b) are the same trade: a shape narrow enough to have no false positives across
    every `.py` in this tree is a shape a copy can be written just outside of. No
    count of those files is stated here on purpose: it would be one more ungated
    figure in a gate written against ungated figures.
 b2. A module this gate cannot parse is skipped in silence. Guessing at its
    contents would be worse, and a file that will not parse is red elsewhere — but
    if a copy ever lands in one, nothing here says so.
 c. Check 2 proves the gates' accessors read the file. It does NOT prove the
    MESHER then reads what the accessor returned: every caller writes that text to
    a temp `.dat` and runs the binary on it, and nothing here follows it that far.
    The surface gates are what cover that, on their own configs.
 d. Nothing here reads the five shipped configs for MEANING. A config edited into
    something that retargets cleanly and meshes into nonsense passes this gate and
    fails the surface gate that drives it, which is the right place for it.
"""

import ast
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, _HERE)

import mb_shipped_config  # noqa: E402
from mb_shipped_config import shipped_config  # noqa: E402

# Directories with no first-party source in them. `results/` and `build/` hold
# generated trees that can be large; the rest are caches.
_SKIP_DIRS = {".git", "build", "__pycache__", ".ruff_cache", "node_modules",
              "results", ".venv", "venv"}

_PLACEHOLDER = "@STEM@"
_SEAM = "mb_shipped_config.py::shipped_config"

failures = []


def check(msg, cond, sink=None, quiet=False):
    """Record one check. `sink` collects for an injected run; `quiet` prints only
    what went red, because an injection's own PASS lines are noise about a tree
    that does not exist."""
    if not (quiet and cond):
        # An injected check that goes red is this gate WORKING, so it is never
        # printed as FAIL: a run whose only FAIL lines are expected ones is how a
        # harness comes to be read by counting them.
        print(("PASS " if cond else ("FAIL " if sink is None else "RED  ")) + msg)
    if not cond:
        (failures if sink is None else sink).append(msg)


# ── 1. deriving the set ────────────────────────────────────────────────────

def _is_config_dat_join(node):
    """``os.path.join(..., "config", ..., "<something>.dat")`` in any arrangement.

    Matched by the constants anywhere inside the expression rather than by their
    positions, so a whole filename literal and a ``name + ".dat"`` both count.
    """
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "join"):
        return False
    consts = [n.value for n in ast.walk(node)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    return "config" in consts and any(c.endswith(".dat") for c in consts)


def _config_dat_names(nodes):
    """Names bound to such a path, module-level or inside the function."""
    out = set()
    for node in nodes:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Assign) and _is_config_dat_join(sub.value):
                out.update(t.id for t in sub.targets if isinstance(t, ast.Name))
    return out


def _mode_of(call):
    if len(call.args) > 1 and isinstance(call.args[1], ast.Constant):
        return str(call.args[1].value)
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return "r"


def _reads_shipped_config(fn, names):
    for sub in ast.walk(fn):
        if not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                and sub.func.id == "open" and sub.args):
            continue
        arg = sub.args[0]
        bound = ((isinstance(arg, ast.Name) and arg.id in names)
                 or (isinstance(arg, ast.Attribute) and arg.attr in names))
        if bound or _is_config_dat_join(arg):
            if "w" not in _mode_of(sub) and "a" not in _mode_of(sub):
                return True
    return False


def _needles_of(node):
    """The first argument of every `<x>.replace(...)` call under `node`."""
    out = set()
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "replace" and sub.args):
            out.add(id(sub.args[0]))
    return out


def _placeholder_names(nodes):
    """Names bound to a string carrying `@STEM@` — the seam's own `PLACEHOLDER`.

    Added because the seam FAILED this derivation when it landed: #126 spelled the
    placeholder once, as a module constant, and a rule that read only literals saw
    a tree with no retargeter in it at all. Naming the thing is the form a shared
    helper is most likely to use, so it was also the hole most likely to be walked
    through by the next copy.
    """
    out = set()
    for node in nodes:
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Constant)
                    and isinstance(sub.value.value, str)
                    and _PLACEHOLDER in sub.value.value):
                out.update(t.id for t in sub.targets if isinstance(t, ast.Name))
    return out


def _emits_placeholder(fn, ph_names=frozenset()):
    """A `@STEM@` the function WRITES, the docstring excluded.

    A retargeter WRITES the placeholder into the text it returns; a runner
    CONSUMES it with `.replace("@STEM@", stem)`. The two are told apart by the
    POSITION of the placeholder — a `.replace()` needle is the consuming form and
    nothing else is — rather than by the literal carrying more than the
    placeholder, which was this function's first rule and let a copy spelling it
    `"@STEM@" + ".vtk"` through. F-strings are read the same way, since a
    `JoinedStr` is never a `.replace()` needle, and so is a NAME bound to the
    placeholder: `PLACEHOLDER` in a needle position is still a runner.
    """
    body = fn.body[1:] if ast.get_docstring(fn) else fn.body
    for node in body:
        needles = _needles_of(node)
        for sub in ast.walk(node):
            if isinstance(sub, ast.JoinedStr):
                parts = [v.value for v in sub.values
                         if isinstance(v, ast.Constant) and isinstance(v.value, str)]
                if any(_PLACEHOLDER in v for v in parts):
                    return True
            if (isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                    and _PLACEHOLDER in sub.value and id(sub) not in needles):
                return True
            named = ((isinstance(sub, ast.Name) and sub.id in ph_names)
                     or (isinstance(sub, ast.Attribute) and sub.attr in ph_names))
            if named and id(sub) not in needles:
                return True
    return False


def retargeters(roots):
    """Every shipped-config retargeter under `roots`, as sorted dicts."""
    found = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
            for name in sorted(filenames):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    with open(path, encoding="utf-8") as f:
                        src = f.read()
                    tree = ast.parse(src)
                except (OSError, SyntaxError, ValueError):
                    # Not this gate's business: a file that will not parse is a
                    # lint failure elsewhere, and guessing at its contents here
                    # would be worse than leaving it out.
                    continue
                top = [s for s in tree.body if not isinstance(s, ast.FunctionDef)]
                mod_names = _config_dat_names(top)
                ph_names = _placeholder_names(top)
                matched = []
                for node in ast.walk(tree):
                    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    names = mod_names | _config_dat_names(node.body)
                    here = ph_names | _placeholder_names(node.body)
                    if (_reads_shipped_config(node, names)
                            and _emits_placeholder(node, here)):
                        matched.append(node)
                # ATTRIBUTED TO THE INNERMOST FUNCTION THAT CARRIES THE SHAPE. A
                # retargeter defined inside a factory matches twice — once itself
                # and once through its container, which contains its code — and
                # counting both would make the derived SIZE wrong, which is the one
                # number this gate is about. A container that matches on its OWN
                # statements (it reads the config, the inner function emits) has no
                # matching descendant and is kept.
                for node in matched:
                    if any(other is not node and other in ast.walk(node)
                           for other in matched):
                        continue
                    found.append({
                        "path": path,
                        "file": name,
                        "func": node.name,
                        "line": node.lineno,
                    })
    return sorted(found, key=lambda h: (h["file"], h["func"]))


def _spell(hit):
    return "%s::%s" % (hit["file"], hit["func"])


def run_checks(roots, sink=None, prefix="", quiet=False):
    """Check 1 over `roots`. Returns the numbers that went red."""
    red = []

    def one(number, msg, cond, detail=None):
        check("%s%d. %s" % (prefix, number, msg), cond, sink=sink, quiet=quiet)
        if not cond:
            red.append(number)
            if detail:
                print("       " + detail)

    hits = retargeters(roots)
    if not quiet:
        print("     derived: " + ", ".join(
            "%s:%d %s" % (h["file"], h["line"], h["func"]) for h in hits))
    one(1, "the tree holds exactly ONE shipped-config retargeter, and it is `%s`"
        % _SEAM,
        [_spell(h) for h in hits] == [_SEAM],
        "derived %s. A second copy is what #126 collapsed; call "
        "`mb_shipped_config.shipped_config` instead, passing the per-gate "
        "variation as `paths=` / `dirs=` / `overrides=`."
        % (sorted(_spell(h) for h in hits) or "nothing"))
    return red


# ── 2-5. the seam's own behaviour, against a temp checkout ─────────────────

_PROBE = "hybmesh_seam_probe"


def _checkout(tmp, names, edit=None):
    """A tiny checkout holding `names`' configs and every file they point at.

    Edited in a COPY rather than in the repo: a gate that rewrites a shipped
    config under the gate that reads it is a hazard this repo does not ship, and
    it is the reason four of check 4's guards were a hand probe before #126.
    """
    root = os.path.join(tmp, "checkout")
    os.makedirs(os.path.join(root, "config"), exist_ok=True)
    for name in names:
        rel = os.path.join("config", name + ".dat")
        shutil.copyfile(os.path.join(_REPO, rel), os.path.join(root, rel))
        with open(os.path.join(root, rel), encoding="utf-8") as f:
            text = f.read()
        for line in text.splitlines():
            parts = line.split()
            if parts and parts[0] in mb_shipped_config._MB_PATH_KEYS:
                val = line[len(parts[0]):].strip()
                dst = os.path.join(root, val)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.isfile(os.path.join(_REPO, val)):
                    shutil.copyfile(os.path.join(_REPO, val), dst)
        if edit is not None:
            old, new = edit
            if text.count(old) != 1:
                raise AssertionError("checkout setup: %r appears %d times in %s"
                                     % (old, text.count(old), rel))
            with open(os.path.join(root, rel), "w", encoding="utf-8") as f:
                f.write(text.replace(old, new))
    return root


class _Repo:
    """Point the seam at a temp checkout for the duration of a block.

    The seam reads `_REPO` at call time for exactly this: the two `base_config`
    wrappers take no `repo=` argument, so pointing the MODULE is the only way to
    ask the REAL accessors what they would do with an edited shipped file.
    """

    def __init__(self, root):
        self.root = root

    def __enter__(self):
        self.saved = mb_shipped_config._REPO
        mb_shipped_config._REPO = self.root
        return self.root

    def __exit__(self, *exc):
        mb_shipped_config._REPO = self.saved
        return False


def _raises(fn):
    """The AssertionError `fn` raises, or None. Any other exception propagates."""
    try:
        fn()
    except AssertionError as exc:
        return str(exc)
    return None


def _composed(name, **kw):
    """The NEGATIVE CONTROL for check 2: a retargeter that does not read the file.

    This is what the collapse must not have ended in, spelled out so the check
    that forbids it is measured against something rather than asserted. It is
    plausible — it returns a runnable MESH_MODE 1 config — and it is blind to
    every edit anyone makes to the shipped file.
    """
    return ("MESH_MODE 1\nBC_GEOM wall\nEXPORT_VTK 1\n"
            "OUTPUT_FILENAME " + _PLACEHOLDER + ".vtk\n")


def behaviour_checks():
    import test_multiblock_cgrid_surface as cgrid
    import test_multiblock_ogrid_surface as ogrid
    import test_multiblock_smooth_surface as smooth

    # ── 2. the edit is visible from the gate that drives the config ─────────
    #
    # ACCESSORS, NOT A RE-IMPLEMENTATION OF THEM: what each gate actually calls is
    # what is called here, so a gate that stopped going through the seam would be
    # red on its own line rather than on a claim about the seam.
    accessors = [
        ("multiblock_cgrid", "test_multiblock_cgrid_surface.py::base_config",
         cgrid.base_config),
        ("multiblock_ogrid", "test_multiblock_ogrid_surface.py::base_config",
         ogrid.base_config),
        ("multiblock_square", "test_multiblock_smooth_surface.py drives it directly",
         lambda: smooth.shipped_config("multiblock_square")),
        ("multiblock_cavity", "test_multiblock_smooth_surface.py drives it directly",
         lambda: smooth.shipped_config("multiblock_cavity")),
        ("multiblock_hgrid", "test_multiblock_smooth_surface.py drives it directly",
         lambda: smooth.shipped_config("multiblock_hgrid")),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        for i, (name, who, fn) in enumerate(accessors):
            root = _checkout(os.path.join(tmp, "e%d" % i), [name],
                             edit=("\nBC_GEOM ", "\nBC_GEOM " + _PROBE + " # "))
            with _Repo(root):
                text = fn()
            check("2. an edit to config/%s.dat reaches %s" % (name, who),
                  _PROBE in text)
        # THE NEGATIVE CONTROL. Same checkout, same assertion, a composed helper:
        # it must FAIL, or check 2 above is passing on something it cannot see.
        root = _checkout(os.path.join(tmp, "neg"), ["multiblock_square"],
                         edit=("\nBC_GEOM ", "\nBC_GEOM " + _PROBE + " # "))
        with _Repo(root):
            composed = _composed("multiblock_square")
        check("2. ...and a COMPOSED helper fails that same assertion, so the check "
              "is measuring the read rather than asserting it",
              _PROBE not in composed)

        # ── 3. the per-gate variation lands ────────────────────────────────
        text = cgrid.base_config(bc_geom="inlet")
        check("3. the C-grid's `bc_geom` reaches BC_GEOM, and the shipped value is "
              "gone", "\nBC_GEOM inlet\n" in text and "\nBC_GEOM wall\n" not in text)
        text = ogrid.base_config(thickness="1e-3")
        check("3. the O-grid's `thickness` reaches BL_INITIAL_THICKNESS, and the "
              "shipped value is gone",
              "\nBL_INITIAL_THICKNESS 1e-3\n" in text
              and "\nBL_INITIAL_THICKNESS 0.001\n" not in text)
        topo = os.path.join(tmp, "some_topology.json")
        with open(topo, "w", encoding="utf-8") as f:
            f.write("{}\n")
        for label, fn in (("C-grid", cgrid.base_config), ("O-grid", ogrid.base_config)):
            text = fn(topo=topo)
            check("3. the %s's `topo` reaches MESH_TOPOLOGY_FILE" % label,
                  ("\nMESH_TOPOLOGY_FILE " + topo + "\n") in text
                  and "examples/topology" not in
                  [ln.split()[1] for ln in text.splitlines()
                   if ln.startswith("MESH_TOPOLOGY_FILE")][0])
        text = ogrid.base_config()
        check("3. ...and the shipped output is retargeted at the placeholder in "
              "every case",
              ("\nOUTPUT_FILENAME " + _PLACEHOLDER + ".vtk\n") in text
              and "results/meshes" not in
              [ln for ln in text.splitlines()
               if ln.startswith("OUTPUT_FILENAME")][0])

        # ── 4. every guard raises, naming the file and the key ─────────────
        guards = [
            ("a path key whose value stops resolving",
             ("\nMESH_TOPOLOGY_FILE examples/topology/square_block.json\n",
              "\nMESH_TOPOLOGY_FILE examples/topology/gone.json\n"),
             ("MESH_TOPOLOGY_FILE", "gone.json"), {}),
            ("a path under a key _MB_PATH_KEYS does not carry",
             ("\nBC_GEOM wall\n",
              "\nBC_GEOM_FILE examples/topology/square_block.json\n"),
             ("BC_GEOM_FILE", "_MB_PATH_KEYS"), {}),
            ("a missing OUTPUT_FILENAME",
             ("\nOUTPUT_FILENAME", "\n# OUTPUT_FILENAME"),
             ("OUTPUT_FILENAME", "multiblock_square.dat"), {}),
            ("a MESH_MODE that is no longer 1",
             ("\nMESH_MODE 1\n", "\nMESH_MODE 0\n"),
             ("MESH_MODE 1", "multiblock_square.dat"), {}),
            ("a retarget asked for under a key the config does not have",
             None, ("NO_SUCH_KEY", "multiblock_square.dat"),
             {"overrides": {"NO_SUCH_KEY": "x"}}),
        ]
        for i, (label, edit, needles, kw) in enumerate(guards):
            root = _checkout(os.path.join(tmp, "g%d" % i), ["multiblock_square"],
                             edit=edit)
            with _Repo(root):
                msg = _raises(lambda: shipped_config("multiblock_square", **kw))
            ok = msg is not None and all(n in msg for n in needles)
            check("4. %s raises, naming %s" % (label, " and ".join(needles)), ok)
            if not ok:
                print("       got: %r" % msg)

        # ── 5. the arguments refuse what they cannot mean ──────────────────
        refusals = [
            ("a directory for a key that holds no path",
             {"dirs": {"BC_GEOM": tmp}}, ("BC_GEOM", "_MB_PATH_KEYS")),
            ("an override for a key the retargeting rule owns",
             {"overrides": {"OUTPUT_FILENAME": "x.vtk"}},
             ("OUTPUT_FILENAME", "undo the retarget")),
            ("an override for a PATH key",
             {"overrides": {"GEOM_FILE": "x.dat"}},
             ("GEOM_FILE", "undo the retarget")),
            ("one key given under two arguments",
             {"paths": {"MESH_TOPOLOGY_FILE": topo},
              "dirs": {"MESH_TOPOLOGY_FILE": tmp}},
             ("MESH_TOPOLOGY_FILE", "two answers to one")),
            ("one path for a key the config repeats",
             {"paths": {"GEOM_FILE": topo}}, ("GEOM_FILE", "dirs=")),
        ]
        for label, kw, needles in refusals:
            name = ("multiblock_ogrid" if "GEOM_FILE" in str(kw)
                    else "multiblock_square")
            msg = _raises(lambda: shipped_config(name, **kw))
            ok = msg is not None and all(n in msg for n in needles)
            check("5. %s is refused, naming %s" % (label, " and ".join(needles)), ok)
            if not ok:
                print("       got: %r" % msg)


# ── injections ─────────────────────────────────────────────────────────────
#
# A SECOND COPY, written the way a second copy always arrives: a gate that needs
# one more thing than the seam offers and writes twenty lines instead of an
# argument. Five spellings, four of which the first version of `_emits_placeholder`
# missed — found by the Standards review of #124 WRITING them rather than by
# reading the rule. They are injected as SHAPES: what each asserts is that the
# derivation SEES the copy, because a copy it cannot see leaves this gate green
# while the set it reports is wrong.
_SPELLINGS = {
    "plain": (
        "import os\n"
        '_CONF = os.path.join("/r", "config", "x.dat")\n\n\n'
        "def second_config():\n"
        '    with open(_CONF, encoding="utf-8") as f:\n'
        "        t = f.read()\n"
        '    return t.replace("out.vtk", "@ST" "EM@.vtk")\n'),
    "concat": (
        "import os\n"
        '_CONF = os.path.join("/r", "config", "x.dat")\n\n\n'
        "def concat_config():\n"
        '    with open(_CONF, encoding="utf-8") as f:\n'
        "        t = f.read()\n"
        '    return t.replace("out.vtk", "@ST" "EM@" + ".vtk")\n'),
    "fstring": (
        "import os\n"
        '_CONF = os.path.join("/r", "config", "x.dat")\n\n\n'
        'def fstring_config(ext=".vtk"):\n'
        '    with open(_CONF, encoding="utf-8") as f:\n'
        "        t = f.read()\n"
        '    return t.replace("out.vtk", f"@ST" f"EM@{ext}")\n'),
    "method": (
        "import os\n\n\n"
        "class Gate:\n"
        '    _CONF = os.path.join("/r", "config", "x.dat")\n\n'
        "    def cfg(self):\n"
        '        with open(self._CONF, encoding="utf-8") as f:\n'
        "            t = f.read()\n"
        '        return t.replace("out.vtk", "@ST" "EM@.vtk")\n'),
    "constant": (
        "import os\n"
        '_CONF = os.path.join("/r", "config", "x.dat")\n'
        '_PH = "@ST" "EM@"\n\n\n'
        "def constant_config():\n"
        '    with open(_CONF, encoding="utf-8") as f:\n'
        "        t = f.read()\n"
        '    return t.replace("out.vtk", _PH + ".vtk")\n'),
    "nested": (
        "import os\n"
        '_CONF = os.path.join("/r", "config", "x.dat")\n\n\n'
        "def factory():\n"
        "    def inner_config():\n"
        '        with open(_CONF, encoding="utf-8") as f:\n'
        "            t = f.read()\n"
        '        return t.replace("out.vtk", "@ST" "EM@.vtk")\n'
        "    return inner_config\n"),
}

# THE NEGATIVE CONTROL, and the reason `_emits_placeholder` reads the literal's
# POSITION rather than its length: a runner CONSUMES the placeholder and retargets
# nothing. Every gate that drives a shipped config holds one of these, so a rule
# that counted them would not fail loudly — it would report a set several times the
# real size, with the seam "duplicated" by its own callers.
_RUNNER = (
    "import os\n\n\n"
    "def run(tmp, name, text):\n"
    '    conf = os.path.join(tmp, name + ".dat")\n'
    '    with open(conf, "w", encoding="utf-8") as f:\n'
    '        f.write(text.replace("@ST" "EM@", os.path.join(tmp, name)))\n'
    "    return conf\n")

# The seam and its three callers, copied into each injected tree so that what is
# derived there is the real set plus the mutation, not a tree of fixtures.
_SOURCES = ("mb_shipped_config.py",
            "test_multiblock_cgrid_surface.py",
            "test_multiblock_ogrid_surface.py",
            "test_multiblock_smooth_surface.py")


def _copy_tree(tmp):
    root = os.path.join(tmp, "tree")
    os.makedirs(root, exist_ok=True)
    for name in _SOURCES:
        shutil.copyfile(os.path.join(_HERE, name), os.path.join(root, name))
    return root


def _injection(label, root, expect_red, expect_size):
    """Re-derive over the mutated tree and require exactly those checks to fail.

    The size assertion comes first and is not a formality: a mutation that
    destroyed the shape instead of duplicating it would make the check below
    "fail" while proving nothing about the check it is labelled for.
    """
    hits = retargeters([root])
    check("injection %s: the mutation left the shape intact (%d retargeter(s), "
          "got %d)" % (label, expect_size, len(hits)), len(hits) == expect_size)
    sink = []
    red = set(run_checks([root], sink=sink, prefix="  (injected) ", quiet=True))
    check("injection %s: checks %s go red, and only those (got %s)"
          % (label, sorted(expect_red), sorted(red)), red == set(expect_red))
    return red


def injections():
    with tempfile.TemporaryDirectory() as tmp:
        # 0. the unmutated copy of the real sources derives the seam and nothing
        #    else — the control every injection below is measured against.
        root = _copy_tree(os.path.join(tmp, "base"))
        hits = retargeters([root])
        check("injection 0: the seam's own three callers add NO retargeter (got %s)"
              % sorted(_spell(h) for h in hits),
              [_spell(h) for h in hits] == [_SEAM])

        # 1. a second copy, in five spellings, each beside the runner that must
        #    NOT be counted as a third.
        for i, (label, src) in enumerate(sorted(_SPELLINGS.items())):
            tag = "1" + chr(ord("a") + i)
            root = _copy_tree(os.path.join(tmp, "s%d" % i))
            for name, text in (("test_second_%s.py" % label, src),
                               ("test_second_runner.py", _RUNNER)):
                with open(os.path.join(root, name), "w", encoding="utf-8") as f:
                    f.write(text)
            hits = retargeters([root])
            check("injection %s: a second copy spelled `%s` is SEEN and the runner "
                  "beside it is not (got %s)"
                  % (tag, label, sorted(_spell(h) for h in hits)),
                  len(hits) == 2 and not any(h["func"] == "run" for h in hits))
            _injection(tag, root, [1], 2)

        # 2. the seam DELETED from the tree, which is the other way check 1 can be
        #    wrong: a set of zero is not a set of one, and a gate that only counted
        #    "more than one" would call an empty tree clean.
        root = _copy_tree(os.path.join(tmp, "gone"))
        os.remove(os.path.join(root, "mb_shipped_config.py"))
        _injection("2", root, [1], 0)


def main() -> int:
    run_checks([_REPO])
    behaviour_checks()
    injections()
    print("-" * 60)
    if failures:
        print("FAILED %d check(s):" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
