"""The ONE way a test drives a shipped ``config/*.dat``: read it, retarget it, run it.

Read from disk and never composed. A shipped config is documentation a user
runs — ``./run.sh -conf config/multiblock_cgrid.dat`` is in ``CLAUDE.md`` — so a
test that rebuilt an equivalent one would leave an edit to the shipped file
invisible from the gate that is supposed to be covering it. That property is what
the three copies this module replaces all existed for, and it is gated
(``test_shipped_config_seam.py`` check 2 edits a config in a temp checkout and
requires each gate's own accessor to show the edit).

THREE COPIES BEFORE #126. ``base_config`` in the C-grid surface gate,
``base_config`` in the O-grid's and ``shipped_config`` in the smoothing gate were
one shape written three times — read the shipped ``.dat``, repoint its paths at
this checkout, retarget its output at ``@STEM@``, raise by name when a rewrite
stops landing — diverging in what they retargeted and in how they said a rewrite
had stopped landing. #124 recorded the duplication at all three; #126 collapsed
it here. The two ``base_config`` names survive as four-line wrappers, because
four other files import them and the per-gate variation (a topology, a BC
geometry, a wall thickness, a geometry directory) belongs to the gate that knows
what it means, not to this signature.

RETARGETED BY KEY, NOT BY A LIST OF NEEDLES. The two ``base_config``s each
carried a list of path substrings and raised when one stopped appearing; the
smoothing gate's copy read the KEY instead, which is the only form that can
retarget a config it was not written for. Keying is what let one function serve
five shipped configs, and the needle lists' guarantee survives as something
stronger: a supplied retarget whose key is not in the file raises, so a caller's
argument can no more go silently inert than a needle could.

A KEY LIST IS STILL A LIST, AND THE SWEEP IS WHAT MAKES THAT PARAGRAPH TRUE.
``_MB_PATH_KEYS`` is as capable of going stale as a needle list: a path added to
one of these configs under a key NOT in it would be left relative, and the run
would read — or for an output, WRITE — the repo's own tree while the caller, seeing
a mesh, reported PASS. So after the rewrite every remaining value is checked for
resolving to a file in this checkout, and one that does is a KEY THIS MODULE DOES
NOT KNOW, raised by name. That, not the keying, is the part a reviewer should
trust.

ALL FIVE GUARDS ARE GATE CHECKS SINCE #126. They used to be a hand probe recorded
in a comment (2026-09-11, four of them), because a check that edits a shipped
config under the gate that reads it is a hazard this repo does not ship. With
``repo=`` the edit happens in a TEMP CHECKOUT instead, so the raises are injected
rather than remembered: a path key that stops resolving, an unknown key carrying a
resolving path, a missing ``OUTPUT_FILENAME``, a ``MESH_MODE`` that is no longer
1, and a supplied retarget whose key is absent.

Known blind spots, stated rather than pretended away:

 a. A ``GEOM_FILE`` line carrying per-geometry ``KEY=VALUE`` BL tokens (the
    feature ``.claude/rules/mesher.md`` describes) has a value that is a path PLUS
    tokens. This module takes the whole remainder as the path, so such a line
    raises as "does not exist" rather than being retargeted. Loud and wrong beats
    quiet and wrong, but it IS wrong: none of the five shipped multi-block configs
    uses one today, and the first that does will land here.
 b. The unknown-key sweep asks whether a value resolves to a file IN THIS
    CHECKOUT. A relative path that happens not to exist — a typo, or an output
    directory that has not been created — resolves to nothing and passes through
    untouched. The ``OUTPUT_FILENAME`` case is covered by name; a second output
    key would not be.
 c. Comment lines are left exactly as shipped, so the repo-relative paths quoted
    in them stay repo-relative. The mesher ignores them; a reader diffing the
    retargeted text against the original will see them agree and should not read
    that as "this path was not retargeted".
"""
from __future__ import annotations   # local python3 is 3.9; CI is 3.11

import os

_HERE = os.path.dirname(os.path.abspath(__file__))
# Rebindable on purpose: `test_shipped_config_seam.py` points it at a temp
# checkout to prove an edited shipped config is visible from the real gates, which
# is the one thing a `repo=` argument threaded through four wrappers could not
# prove — the wrappers do not take one.
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))

# Every key whose value is a path into the checkout. Not a closed list: see the
# sweep above, which is what catches the key that should have been added here.
_MB_PATH_KEYS = ("MESH_TOPOLOGY_FILE", "GEOM_FILE", "DOMAIN_FILE")

# The output stem the caller substitutes. Spelled here once; `run_case` in each
# gate consumes it with `.replace(...)`.
PLACEHOLDER = "@STEM@"

# Keys this module owns outright. A caller asking to override one of these is
# asking for the retargeting rule to be undone, which is never what it means.
_RESERVED = ("OUTPUT_FILENAME", "MESH_MODE")


def _fail(msg):
    raise AssertionError(msg)


def shipped_config(name, paths=None, dirs=None, overrides=None, repo=None):
    """``config/<name>.dat``, read from disk and retargeted at this checkout.

    Every path key is repointed at an absolute path, ``OUTPUT_FILENAME`` at
    ``@STEM@``, and anything that cannot be done is an ``AssertionError`` naming
    the file, the key and the value.

    The per-gate variation rides on three arguments, each keyed by CONFIG KEY:

      ``paths``      one exact path for a key that appears exactly once, e.g.
                     ``{"MESH_TOPOLOGY_FILE": <a mutated topology in a tmp dir>}``.
      ``dirs``       a directory to resolve a path key's basenames under, for a
                     key that may appear more than once, e.g.
                     ``{"GEOM_FILE": <a dir of generated geometries>}``.
      ``overrides``  a whole value for a non-path key, e.g. ``{"BC_GEOM": "inlet"}``
                     or ``{"BL_INITIAL_THICKNESS": "1e-3"}``.

    ``repo`` is where ``config/`` and every relative value resolve; it defaults to
    this checkout.
    """
    repo = repo or _REPO
    paths = dict(paths or {})
    dirs = dict(dirs or {})
    overrides = dict(overrides or {})

    for key in sorted(set(dirs) - set(_MB_PATH_KEYS)):
        _fail("dirs=%r: %s is not a path key (%s), so there is no path under it "
              "to resolve. Use overrides= for a value, or add the key to "
              "_MB_PATH_KEYS." % (dirs, key, ", ".join(_MB_PATH_KEYS)))
    for key in sorted(set(paths) - set(_MB_PATH_KEYS)):
        _fail("paths=%r: %s is not a path key (%s). Use overrides= for a value "
              "that is not a path." % (paths, key, ", ".join(_MB_PATH_KEYS)))
    for key in sorted(set(paths) & set(dirs)):
        _fail("%s is given in BOTH paths= and dirs=, which are two answers to one "
              "question. Give one." % key)
    for key in sorted(set(overrides) & (set(_MB_PATH_KEYS) | set(_RESERVED))):
        _fail("overrides=%r: %s is retargeted by this function, so overriding its "
              "value would undo the retarget. Use paths= or dirs= for a path; "
              "OUTPUT_FILENAME and MESH_MODE are not the caller's to set."
              % (overrides, key))

    path = os.path.join(repo, "config", name + ".dat")
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    seen = {key: 0 for key in list(paths) + list(dirs) + list(overrides)}
    out, hit = [], {"MESH_MODE": False, "OUTPUT_FILENAME": False}
    for ln in lines:
        parts = ln.split()
        key = parts[0] if parts else ""
        val = ln[len(key):].strip()
        if key in _MB_PATH_KEYS:
            if key in paths:
                target = paths[key]
            elif key in dirs:
                target = os.path.join(dirs[key], os.path.basename(val))
            else:
                target = os.path.join(repo, val)
            if key in seen:
                seen[key] += 1
            if not os.path.exists(target):
                _fail("%s: %s %r retargets to %r, which does not exist, so this "
                      "test cannot drive the shipped config. Either the config "
                      "moved the file or the caller's retarget is wrong."
                      % (path, key, val, target))
            ln = key + " " + target
        elif key == "OUTPUT_FILENAME":
            hit[key] = True
            ext = os.path.splitext(val)[1]
            if not ext:
                _fail("%s: %s %r has no extension, so this test cannot retarget "
                      "it at a temp stem and still know what the mesher wrote."
                      % (path, key, val))
            ln = key + " " + PLACEHOLDER + ext
        elif key == "MESH_MODE":
            hit[key] = (val == "1")
        elif key in overrides:
            seen[key] += 1
            ln = key + " " + str(overrides[key])
        elif key and not key.startswith("#") and val and os.path.isfile(
                os.path.join(repo, val)):
            # A PATH UNDER A KEY THIS MODULE DOES NOT KNOW. Left alone it would
            # stay repo-relative, the mesher would read the repo's own file and,
            # for an output, write into the repo's `results/`. Caught by what the
            # value IS rather than by what the key is called, so `_MB_PATH_KEYS`
            # cannot go stale in silence.
            _fail("%s: %s %r resolves to a file in this checkout but %s is not in "
                  "_MB_PATH_KEYS, so the run would read (or write) the repo's own "
                  "tree. Add it there." % (path, key, val, key))
        out.append(ln)

    # EVERY SUPPLIED RETARGET MUST LAND. This is the needle lists' guarantee, kept:
    # a caller that names a key the config no longer has would otherwise get the
    # shipped value back and report PASS on a run that tested nothing it meant to.
    for key in sorted(k for k, n in seen.items() if n == 0):
        _fail("%s has no %s line, so the retarget asked for under that key would "
              "not land. Either the config moved it or the caller is wrong."
              % (path, key))
    for key in sorted(k for k in paths if seen[k] > 1):
        _fail("%s has %d %s lines and paths= gives ONE path for that key, which "
              "would point them all at the same file. Use dirs= instead."
              % (path, seen[key], key))
    if not hit["MESH_MODE"]:
        _fail("%s is no longer a MESH_MODE 1 config, so this test cannot drive it "
              "as one." % path)
    if not hit["OUTPUT_FILENAME"]:
        _fail("%s no longer declares OUTPUT_FILENAME, so this test cannot retarget "
              "its output away from the repo." % path)
    return "\n".join(out) + "\n"
