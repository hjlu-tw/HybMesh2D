#!/usr/bin/env python3
"""Three helpers read a shipped ``config/*.dat`` and retarget it; each must say so.

There is no production code behind this gate. The thing under test is a
DUPLICATION and the record of it: ``base_config`` in the C-grid surface gate,
``base_config`` in the O-grid's and ``shipped_config`` in the smoothing gate are
one shape written three times — read the shipped ``.dat`` from disk, repoint its
paths at this checkout, retarget its output at ``@STEM@``, raise by name when a
rewrite stops landing. Reading the file from disk rather than composing an
equivalent one is deliberate and each of the three docstrings already argued it:
a shipped config is documentation a user runs, so an edit to it has to be visible
from a gate.

What TWO of the three never said, until #124, is that the other two exist. The
record was written ONCE, at ``shipped_config``, by #114's review; #115's Out of
Scope then asserted the duplication was "already recorded as residue at the
code", which was true of one copy in three and false of the shape. A record kept
at one of N copies is the same defect as no record: the copy a reader opens is
the one that stays silent.

This gate does not collapse the three — that is a separate ticket, and the
record is what makes deferring it a decision. It holds the record instead.

Checks:
 1. THE SET IS DERIVED FROM THE TREE, never listed here. Every ``*.py`` under the
    repo (minus `build/`, `results/`, `.git/` and the caches — the two generated
    trees and the caches, named in `_SKIP_DIRS`) is parsed, and a function counts as
    a retargeter when it BOTH opens for reading a path built by joining `"config"`
    with a `.dat` name AND emits a string literal containing `@STEM@` outside its
    docstring. The docstring is excluded on purpose: the record itself talks about
    `@STEM@`, and a rule that read prose would make any of these records enough to
    conjure a fourth member out of a function that retargets nothing.
 2. Every member carries the record: the anchor `SHIPPED-CONFIG RETARGETER, ONE OF
    <n>` in its own docstring, exactly once. A copy added without one FAILS — which
    is the whole point, because the record is what a reader of a fourth copy needs
    and the author of it is the last person who will think to write it.
 3. Every record's stated count equals the size of the derived set. Add a fourth
    copy and three records go red at once, naming the file that arrived.
 4. Every record names the OTHER members, spelled `<file>.py::<function>`, exactly
    and no more: a member that stops existing has to be un-named, and one that
    arrives has to be named, in all of them.

 injections. Every check is verified in-process against a mutated COPY of the real
    three files in a temp tree: the record deleted, the count bent, a name dropped,
    a fourth copy added with a record and a fourth added without one. Each asserts
    the mutated input still PARSES, still differs from the original, and is still
    seen as a retargeter by check 1's derivation — a mutation that merely destroyed
    the shape would make the check "fail" for the wrong reason and prove nothing.
    What each injection asserts is the SET of checks that went red and not merely
    that one did, so a mutation reddening the wrong check is a failure here rather
    than a pass with a misleading label. The two fourth-copy injections are the
    ones acceptance is about: with a record, three records go red for the count and
    for the name they are missing; without one, four do. Injections 6a-6d are a
    different question — not whether the record is right but whether the
    derivation SEES a copy at all — so each writes a fourth copy in a spelling
    that once slipped past (a concatenated literal, an f-string, a method reading
    `self._CONF`, a retargeter nested in a factory) and puts a RUNNER beside it as
    the negative control, since a rule loose enough to catch all four would catch
    the runner too and report a set twice its real size.

Deliberately NOT given a `--sync`: the count is one word of a record whose other
sentences — which copy does what extra, what collapsing would cost — have to be
written by whoever adds the fourth copy. A sync that quietly bumped `3` to `4` in
three files would leave three records describing a set of four as if nothing had
been added, which is the failure this gate exists for, automated.

Known blind spots, stated rather than pretended away:

 a. The derivation knows ONE spelling of "read a file": a call to `open()`. A
    fourth copy reading its config through `pathlib.Path.read_text()`, or through
    a helper in another module that hands back the text, is invisible here and its
    silence would look exactly like today's PASS.
 b. It reads the retarget placeholder as the literal `@STEM@`. A copy that named
    its placeholder something else is a fourth copy this gate does not see. Both
    (a) and (b) are the same trade: a shape narrow enough to have no false
    positives across every `.py` in this tree is a shape a copy can be written
    just outside of. No count of those files is stated here on purpose: it would
    be one more ungated figure in a gate written against ungated figures.
    THREE MORE HOLES OF THAT KIND WERE LIVE AND ARE NOW CLOSED, and how they were
    found is the point: #124's Standards review WROTE four fourth copies and ran
    them through the derivation instead of reading it. `"@STEM@" + ".vtk"` and an
    f-string both went unseen, because the first rule asked whether the literal
    carried MORE than the placeholder rather than where it sat; `open(self._CONF)`
    went unseen because only a bare Name counted as a binding; and a retargeter
    nested in a factory was counted TWICE, itself and its container, which
    corrupts the one figure every record states. All four are injections 6a-6d
    now, with the runner beside each as the negative control.
 b2. A module this gate cannot parse is skipped in silence. Guessing at its
    contents would be worse, and a file that will not parse is red elsewhere — but
    if a copy ever lands in one, nothing here says so.
 c. Nothing here checks that a record's PROSE is true — that the cost it states
    is the real cost, or that the extra each copy carries is still that extra. It
    checks the set, the count and the names, which are the parts that go stale on
    their own. The rest is a claim a reviewer has to read.
"""

import ast
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))

# Directories with no first-party source in them. `results/` and `build/` hold
# generated trees that can be large; the rest are caches.
_SKIP_DIRS = {".git", "build", "__pycache__", ".ruff_cache", "node_modules",
              "results", ".venv", "venv"}

_ANCHOR = "SHIPPED-CONFIG RETARGETER, ONE OF "
_PLACEHOLDER = "@STEM@"

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
    positions, so the C-grid's whole filename literal and the smoothing gate's
    ``name + ".dat"`` both count.
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


def _emits_placeholder(fn):
    """A `@STEM@`-bearing literal in the CODE, the docstring excluded.

    A retargeter WRITES the placeholder into the text it returns; a runner
    CONSUMES it with `.replace("@STEM@", stem)`. The two are told apart by the
    POSITION of the literal — a `.replace()` needle is the consuming form and
    nothing else is — rather than by the literal carrying more than the
    placeholder, which was this function's first rule and let a copy spelling it
    `"@STEM@" + ".vtk"` through. F-strings are read the same way, since a
    `JoinedStr` is never a `.replace()` needle.
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
                mod_names = _config_dat_names(
                    [s for s in tree.body if not isinstance(s, ast.FunctionDef)])
                matched = []
                for node in ast.walk(tree):
                    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    names = mod_names | _config_dat_names(node.body)
                    if _reads_shipped_config(node, names) and _emits_placeholder(node):
                        matched.append(node)
                # ATTRIBUTED TO THE INNERMOST FUNCTION THAT CARRIES THE SHAPE. A
                # retargeter defined inside a factory matches twice — once itself
                # and once through its container, which contains its code — and
                # counting both would make the derived SIZE wrong, which is the one
                # number every record states. A container that matches on its OWN
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
                        "doc": ast.get_docstring(node) or "",
                    })
    return sorted(found, key=lambda h: (h["file"], h["func"]))


# ── 2-4. the record each one has to carry ──────────────────────────────────

def stated_count(doc):
    """The `<n>` of the record's anchor, or None when the anchor is absent.

    Read off the anchor rather than by searching the record for a numeral, so a
    figure that appears in the prose for another reason cannot be taken for this
    one. An anchor appearing twice returns None as well: two of them is two
    claims, and there is no principled way to pick.
    """
    if doc.count(_ANCHOR) != 1:
        return None
    tail = doc.split(_ANCHOR, 1)[1].lstrip()
    digits = ""
    for ch in tail:
        if not ch.isdigit():
            break
        digits += ch
    return int(digits) if digits else None


def named_members(doc):
    """Every `<file>.py::<function>` the record names."""
    out = set()
    for token in doc.replace("`", " ").replace(",", " ").split():
        token = token.strip(".;:()[]'\"")
        if "::" in token and token.split("::")[0].endswith(".py"):
            out.add(token)
    return out


def _spell(hit):
    return "%s::%s" % (hit["file"], hit["func"])


def run_checks(roots, sink=None, prefix="", quiet=False):
    """The four checks over `roots`. Returns the numbers that went red."""
    red = []

    def one(number, msg, cond, detail=None):
        check("%s%d. %s" % (prefix, number, msg), cond, sink=sink, quiet=quiet)
        if not cond:
            red.append(number)
            if detail:
                print("       " + detail)

    hits = retargeters(roots)
    one(1, "the tree holds at least one shipped-config retargeter", len(hits) > 0)
    if not hits:
        return red
    if not quiet:
        print("     derived: " + ", ".join(
            "%s:%d %s" % (h["file"], h["line"], h["func"]) for h in hits))

    for hit in hits:
        where = "%s::%s (%s:%d)" % (hit["file"], hit["func"], hit["path"], hit["line"])
        has = hit["doc"].count(_ANCHOR) == 1
        one(2, "%s carries the record anchor exactly once" % where, has,
            "write `%s%d` into its docstring, naming the other %d"
            % (_ANCHOR, len(hits), len(hits) - 1))
        if not has:
            continue
        said = stated_count(hit["doc"])
        one(3, "%s states the set's real size (%d)" % (where, len(hits)),
            said == len(hits),
            "it says %r; the tree holds %d: %s"
            % (said, len(hits), ", ".join(_spell(h) for h in hits)))
        want = {_spell(h) for h in hits if _spell(h) != _spell(hit)}
        got = named_members(hit["doc"])
        one(4, "%s names exactly the other members" % where, got == want,
            "missing: %s   unexpected: %s"
            % (sorted(want - got) or "none", sorted(got - want) or "none"))
    return red


# ── injections ─────────────────────────────────────────────────────────────
#
# A FOURTH COPY, written to look as right as a fourth copy ever looks: it reads a
# shipped config, retargets it, and carries a record naming the three that were
# there before it. Only the COUNT gives it away, which is why the count is checked
# separately from the names.
_FOURTH = '''"""A fourth gate that drives a shipped config."""
import os

_REPO = "/nowhere"
_CONF = os.path.join(_REPO, "config", "multiblock_hgrid.dat")


def fourth_config():
    """The shipped config, retargeted at a temp output stem.

    %s3. The other three are `test_multiblock_cgrid_surface.py::base_config`,
    `test_multiblock_ogrid_surface.py::base_config` and
    `test_multiblock_smooth_surface.py::shipped_config`.
    """
    with open(_CONF, encoding="utf-8") as f:
        text = f.read()
    return text.replace("results/meshes/x.vtk", "@ST" "EM@.vtk")
''' % _ANCHOR


# FOUR SPELLINGS OF ONE FOURTH COPY, each of which a reasonable author could
# write and three of which the first version of `_emits_placeholder` missed —
# found by the Standards review of #124 rather than by this gate. They are
# injected as SHAPES, not as records: what each asserts is that the derivation
# SEES a fourth copy written that way, because a copy it cannot see needs no
# record, and the gate then stays green while the set it reports is wrong.
_SPELLINGS = {
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
# POSITION rather than its length: a runner CONSUMES the placeholder and
# retargets nothing. Every file holding a retargeter holds one of these beside
# it, so a rule that counted them would not fail loudly — it would report a set
# twice the real size, with every record in it "wrong".
_RUNNER = (
    "import os\n\n\n"
    "def run(tmp, name, text):\n"
    '    conf = os.path.join(tmp, name + ".dat")\n'
    '    with open(conf, "w", encoding="utf-8") as f:\n'
    '        f.write(text.replace("@ST" "EM@", os.path.join(tmp, name)))\n'
    "    return conf\n")


_SOURCES = ("test_multiblock_cgrid_surface.py",
            "test_multiblock_ogrid_surface.py",
            "test_multiblock_smooth_surface.py")


def _copy_tree(tmp):
    root = os.path.join(tmp, "tree")
    os.makedirs(root, exist_ok=True)
    for name in _SOURCES:
        shutil.copyfile(os.path.join(_HERE, name), os.path.join(root, name))
    return root


def _mutate(root, name, old, new):
    """Rewrite one copy, asserting the edit landed and left a parsable file."""
    path = os.path.join(root, name)
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if src.count(old) != 1:
        raise AssertionError("injection setup: %r appears %d times in %s"
                             % (old[:40], src.count(old), name))
    out = src.replace(old, new)
    ast.parse(out)
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)
    return src != out


def _injection(label, root, expect_red, expect_size):
    """Re-derive over the mutated tree and require exactly those checks to fail.

    The size assertion comes first and is not a formality: a mutation that
    destroyed the shape instead of the record would make every check below "fail"
    while proving nothing about the check it is labelled for.
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
        # 1. the record deleted from one copy.
        root = _copy_tree(tmp + "/a")
        changed = _mutate(root, "test_multiblock_ogrid_surface.py",
                          _ANCHOR + "3", "SHIPPED-CONFIG RETARGETER (unstated)")
        check("injection 1: the deletion changed the file", changed)
        _injection("1", root, [2], 3)

        # 2. the count bent on one copy.
        root = _copy_tree(tmp + "/b")
        changed = _mutate(root, "test_multiblock_cgrid_surface.py",
                          _ANCHOR + "3", _ANCHOR + "4")
        check("injection 2: the bend changed the file", changed)
        _injection("2", root, [3], 3)

        # 3. one named member dropped from a record.
        root = _copy_tree(tmp + "/c")
        changed = _mutate(root, "test_multiblock_smooth_surface.py",
                          "`test_multiblock_ogrid_surface.py::base_config`",
                          "the O-grid's")
        check("injection 3: the drop changed the file", changed)
        _injection("3", root, [4], 3)

        # 4. a fourth copy that carries a record naming the other three.
        root = _copy_tree(tmp + "/d")
        with open(os.path.join(root, "test_fourth_surface.py"), "w",
                  encoding="utf-8") as f:
            f.write(_FOURTH)
        _injection("4", root, [3, 4], 4)

        # 5. a fourth copy with no record at all.
        root = _copy_tree(tmp + "/e")
        with open(os.path.join(root, "test_fourth_surface.py"), "w",
                  encoding="utf-8") as f:
            f.write(_FOURTH.replace(_ANCHOR + "3", "A fourth, silently"))
        _injection("5", root, [2, 3, 4], 4)

        # 6. the same fourth copy in four other spellings, each beside the runner
        #    that must NOT be counted as a fifth.
        for i, (label, src) in enumerate(sorted(_SPELLINGS.items())):
            tag = "6" + chr(ord("a") + i)
            root = _copy_tree("%s/f%d" % (tmp, i))
            for name, text in (("test_fourth_%s.py" % label, src),
                               ("test_fourth_runner.py", _RUNNER)):
                with open(os.path.join(root, name), "w", encoding="utf-8") as f:
                    f.write(text)
            hits = retargeters([root])
            check("injection %s: a fourth copy spelled `%s` is SEEN and the runner "
                  "beside it is not (got %s)"
                  % (tag, label, sorted(_spell(h) for h in hits)),
                  len(hits) == 4 and not any(h["func"] == "run" for h in hits))
            _injection(tag, root, [2, 3, 4], 4)


def main() -> int:
    run_checks([_REPO])
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
