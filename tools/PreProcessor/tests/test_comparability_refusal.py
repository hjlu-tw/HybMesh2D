#!/usr/bin/env python3
"""The two cell-shape figures are NEVER compared, and the record of that refusal
is held against the sentences that enforce it (issue #142, parent #128).

#128's story 5 asks for a machine-readable quality line on the hybrid path "so
that the two paths are comparable and neither is silently unmeasured". The tree
ships the SECOND half and refuses the first: `quad_midline_ratio` measures the
multi-block path's structured quads, `tri_edge_ratio` measures the hybrid path's
exported triangles, and a square reads 1.0 as a quad and sqrt(2) as either of the
triangles it splits into — so the difference between the two figures is a property
of the cell kind rather than of the mesh.

That refusal is enforced in the user's own report: each path's ``Cell shape``
banner row names the OTHER path's metric as not comparable. Prose cannot hold a
sentence in `src/cli.cpp` — #142's acceptance asks for a GREP-VERIFIED anchor, so
that a reword of the banner fails loudly here rather than silently unhooking the
record in `docs/design_notes/mesher.md`.

What this pins down:

  1. The MULTI-BLOCK banner sentence is in `src/cli.cpp`, exactly once, with its
     two halves around the mode constant — read with C++ comments stripped and
     adjacent string literals joined, because the sentence is split across
     literals and the comment two lines below it names both metrics.
  2. The HYBRID banner sentence, the same way. Both, because a warning on one
     report only reaches the reader who already had the other open — which is
     `test_hybrid_shape_surface.py` check 5's subject through the real binary,
     and this file's statically.
  3. The design note carries the record at an anchor that resolves EXACTLY once.
  4. The record QUOTES both sentences verbatim, in its own region. This is the
     grep-verified anchor #142 asks for: changing the banner reddens check 1 or 2,
     changing the quotation reddens this one, and either failure names the other
     file.
  5. `.claude/rules/mesher.md` states the rule and points at the anchor with its
     `Why:` pointer on ONE line, the form `docs/agents/rule-file-style.md` fixes.
  6. THE TWO NAMES NEVER CROSS BETWEEN THE TWO EMITTERS: nothing in the
     `HYBMESH_MB_QUALITY` statement names `tri_edge_ratio` and nothing in the
     `HYBMESH_HYBRID_QUALITY` one names `quad_midline_ratio`.
  7. The sidecar is given TWO labels and not one shared one: `quality.metric` is
     assigned exactly twice, once per name.

Checks 6 and 7 are the "nothing in the tree is changed to make the two
comparable" half. They are static where `test_hybrid_shape_surface.py` checks 3
and 4 are dynamic: this file runs with no build tree, so the rule is guarded on a
machine that has never compiled the mesher.

INJECTIONS — AUTOMATED, unlike the C++ gates next door, because every input here
is text and a copy of the world can be mutated in memory. Each asserts the
mutation is well-formed and really differs, then that the named check fails:

  A. `NOT comparable` reworded to `roughly comparable` in the multi-block banner
     sentence -> check 1 fails, naming the design note.
  B. the hybrid banner sentence deleted -> check 2 fails. Separately from A,
     because the two halves of "a reader of EITHER" are separately reachable.
  C. the note's quotation reworded while `src/cli.cpp` stands -> check 4 fails.
     This is the direction the anchor exists for: the record drifting off the
     sentence it claims to quote.
  D. the anchor removed from the note -> checks 3 and 5 fail together, since the
     rule file's `Why:` pointer then resolves nowhere.
  E. the `Why:` line wrapped between the note's path and the anchor -> check 5
     fails. #59's recurring defect: a pointer split across two lines greps as
     absent.
  F. the hybrid emitter's tokens renamed to `quad_midline_ratio_*` -> check 6
     fails. That is injection A of `test_hybrid_shape_surface.py` seen without a
     binary.
  G. both sidecar labels collapsed to one name -> check 7 fails.
  H. negative control: the unmutated tree passes every check, so the failures
     above are the mutations and not the checker.

BLIND SPOTS, named rather than papered over:

  * This file holds the SENTENCES and the RECORD, never the practice. Two figures
    printed side by side by a future GUI panel, a pipeline summary or a README
    table is the defect the record exists to prevent and would pass every check
    here. What is reachable statically is the mesher's own output; a reader that
    puts them in one row is another gate's subject.
  * Check 6 reads the two emitter statements only. A third surface that merged the
    names — a new exporter, a new line — is outside both spans and invisible here.
  * The banner sentences are matched as TEXT. That a run actually prints them is
    `test_hybrid_shape_surface.py` check 5, which needs the binary; this file
    would pass on a `src/cli.cpp` whose reporter is never called.
  * Nothing here asserts the two figures are RIGHT. Their arithmetic is
    `tests/cpp/test_cell_shape.cpp`'s and their collection
    `tests/cpp/test_hybrid_quality.cpp`'s and `tests/cpp/test_mb_quality.cpp`'s.

Run:  python3 tools/PreProcessor/tests/test_comparability_refusal.py
Needs no build tree: every input is text.
"""
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))

_SRC = "src/cli.cpp"
_NOTE = "docs/design_notes/mesher.md"
_RULE = ".claude/rules/mesher.md"

# The anchor the design note's record is found by, and the rule file's `Why:`
# pointer names. One derivation, spelled here and in those two files; check 3
# requires it to resolve EXACTLY once, the rule `docs/agents/rule-file-style.md`
# states for every anchor.
ANCHOR = "THE TWO FIGURES ARE NOT COMPARABLE, BY CONSTRUCTION"
WHY = 'Why: `%s`, "%s".' % (_NOTE, ANCHOR)

# The two banner sentences, each as the pair of halves around the mode constant —
# `<< MESH_MODE_HYBRID <<` in the source, a rendered digit in the design note's
# quotation. Splitting them here rather than pinning one string is what lets the
# SAME constant check both files.
SENTENCES = (
    ("multi-block", "MESH_MODE_HYBRID",
     "1.0 is square, and NOT comparable with MESH_MODE ",
     "'s triangle edge ratio)"),
    ("hybrid", "MESH_MODE_MULTIBLOCK",
     "1.0 is equilateral, and NOT comparable with MESH_MODE ",
     "'s quad midline ratio)"),
)

# The two machine-readable lines, and the flush that ends each emitter. A span is
# read to `mr.str()` rather than to the next `;`, because the multi-block emitter
# is TWO statements: the shape tokens were appended in a second one (#129), and a
# span ending at the first semicolon would not contain the names check 6 is about.
EMITTERS = (
    ("HYBMESH_MB_QUALITY", "quad_midline_ratio", "tri_edge_ratio"),
    ("HYBMESH_HYBRID_QUALITY", "tri_edge_ratio", "quad_midline_ratio"),
)
_FLUSH = "mr.str()"

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


# --- the inputs, as one value -------------------------------------------------
# Every check below is a pure function of this dict, which is what makes the
# injections cheap: mutate a copy, ask the same function.
def read_world():
    out = {}
    for key, rel in (("src", _SRC), ("note", _NOTE), ("rule", _RULE)):
        path = os.path.join(_REPO, rel)
        # A missing file reaches the reader as a named failure rather than as a
        # traceback out of the reader, which would take every other check down.
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                out[key] = fh.read()
        else:
            out[key] = None
    return out


def copy_world(w):
    return dict(w)


# --- C++ text, reduced to what a reader of the OUTPUT sees --------------------
def cpp_code(text):
    """`text` with comments removed and adjacent string literals joined.

    Both halves are load bearing rather than tidiness. The comment two lines under
    the multi-block emitter names BOTH metrics (it explains why the name is in the
    key), so check 6 would pass on a crossed name without the strip. And each
    banner sentence is split across two string literals around the mode constant,
    so it exists as one substring only after the join.
    """
    out = []
    i = 0
    n = len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        out.append(c)
        i += 1
    # `"a" "b"` is one literal in C++ and must read as one here too.
    return re.sub(r'"\s*"', "", "".join(out))


def _span(code, prefix):
    """The emitter statement for `prefix`, from its literal to the flush, or None."""
    start = code.find(prefix)
    if start < 0:
        return None
    end = code.find(_FLUSH, start)
    return code[start:end] if end >= 0 else None


# --- checks 1 and 2 -----------------------------------------------------------
def check_banner_sentences(world):
    fails = []
    if world["src"] is None:
        return ["%s is missing, so neither banner sentence can be read." % _SRC]
    code = cpp_code(world["src"])
    for i, (path, const, head, tail) in enumerate(SENTENCES, start=1):
        nh, nt = code.count(head), code.count(tail)
        if nh != 1 or nt != 1:
            fails.append(
                "check %d: the %s path's `Cell shape` sentence does not resolve "
                "exactly once in %s (head %d time(s), tail %d). It is what tells a "
                "user the other path's figure is NOT comparable, and %s quotes it "
                "verbatim at \"%s\". Restore the sentence, or reword BOTH homes in "
                "one change.\n    head: %r\n    tail: %r"
                % (i, path, _SRC, nh, nt, _NOTE, ANCHOR, head, tail))
            continue
        between = code[code.find(head) + len(head):code.find(tail)]
        if const not in between or len(between) > 80:
            fails.append(
                "check %d: the %s path's sentence has its two halves in %s but "
                "`%s` is not what sits between them (%r). The row must name the "
                "OTHER mode, and naming it by constant is what keeps the two rows "
                "from drifting to the same number."
                % (i, path, _SRC, const, between[:80]))
    return fails


# --- check 3 ------------------------------------------------------------------
def check_record_anchor(world):
    if world["note"] is None:
        return ["%s is missing, so #142's record of the refusal has no home." % _NOTE]
    n = world["note"].count(ANCHOR)
    if n == 1:
        return []
    return [
        "check 3: the anchor \"%s\" resolves %d time(s) in %s and exactly 1 is "
        "required. It is what `%s`'s rule points at; an anchor that resolves "
        "twice is as unusable as one that resolves not at all."
        % (ANCHOR, n, _NOTE, _RULE)]


# --- check 4 ------------------------------------------------------------------
def record_region(note):
    """The record's own text: from its anchor to the next top-level lead, or end.

    Scoped rather than file-wide so that quoting the same sentence in a LATER
    entry cannot satisfy this check for the record #142 asks for.
    """
    start = note.find(ANCHOR)
    if start < 0:
        return None
    nxt = note.find("\n**", start + len(ANCHOR))
    return note[start:] if nxt < 0 else note[start:nxt]


def check_record_quotes(world):
    if world["note"] is None:
        return ["%s is missing." % _NOTE]
    region = record_region(world["note"])
    if region is None:
        return ["check 4: no record at \"%s\" in %s, so nothing quotes the banner "
                "sentences (check 3 names the same cause)." % (ANCHOR, _NOTE)]
    fails = []
    for path, _const, head, tail in SENTENCES:
        # The rendered form: the mode CONSTANT in the source is a digit on screen.
        pat = re.compile(re.escape(head) + r"[0-9]" + re.escape(tail))
        if len(pat.findall(region)) != 1:
            fails.append(
                "check 4: the record at \"%s\" in %s does not quote the %s path's "
                "banner sentence verbatim exactly once. Without the quotation the "
                "record is an assertion about %s that nothing holds, which is the "
                "whole of #142's second acceptance criterion.\n    expected: %s0%s"
                % (ANCHOR, _NOTE, path, _SRC, head, tail))
    return fails


# --- check 5 ------------------------------------------------------------------
def check_rule_pointer(world):
    if world["rule"] is None:
        return ["%s is missing, so the rule has no home." % _RULE]
    lines = world["rule"].splitlines()
    hits = [ln for ln in lines if WHY in ln]
    if len(hits) == 1:
        return []
    wrapped = (_NOTE in world["rule"] and ANCHOR in world["rule"])
    return [
        "check 5: `%s` does not carry the rule's pointer on ONE line (%d found%s). "
        "The form is exactly:\n    %s\nA pointer split across two lines greps as "
        "absent, which `docs/agents/rule-file-style.md` records as the recurring "
        "way an anchor is lost."
        % (_RULE, len(hits), "; both halves ARE present, so it has WRAPPED"
           if wrapped and not hits else "", WHY)]


# --- check 6 ------------------------------------------------------------------
def check_names_do_not_cross(world):
    if world["src"] is None:
        return ["%s is missing." % _SRC]
    code = cpp_code(world["src"])
    fails = []
    for prefix, own, other in EMITTERS:
        span = _span(code, prefix)
        if span is None:
            fails.append(
                "check 6: no `%s` emitter in %s, or none that reaches its `%s` "
                "flush. Each path's machine-readable line is what a script greps; "
                "a missing one is #128's story 5's SECOND half undone."
                % (prefix, _SRC, _FLUSH))
            continue
        if span.count(own + "_") < 4:
            fails.append(
                "check 6: the `%s` emitter does not carry four `%s_*` tokens. The "
                "metric's name lives in the KEY (there is no `shape_metric=` token: "
                "every token on these lines is `key=<float>` and one shared parser "
                "floats all of them)." % (prefix, own))
        if other in span:
            fails.append(
                "check 6: the `%s` emitter names `%s`, the OTHER path's metric. The "
                "two figures measure different quantities on different populations "
                "and are never merged, never compared and never given one shared "
                "label — see %s, \"%s\"." % (prefix, other, _NOTE, ANCHOR))
    return fails


# --- check 7 ------------------------------------------------------------------
def check_two_sidecar_labels(world):
    if world["src"] is None:
        return ["%s is missing." % _SRC]
    code = cpp_code(world["src"])
    found = re.findall(r'quality\.metric\s*=\s*"([A-Za-z0-9_]+)"', code)
    want = sorted(name for _p, name, _o in EMITTERS)
    if sorted(found) == want:
        return []
    return [
        "check 7: `quality.metric` is assigned %r in %s and %r is required — one "
        "label per path, two labels. The sidecar's `metric` is the only place the "
        "quantity is NAMED as a string rather than spelled into a key, so one "
        "shared label there would make two different numbers answer to one name "
        "for every later reader." % (found, _SRC, want)]


# --- run ----------------------------------------------------------------------
world = read_world()


def run(fn, label):
    fails = fn(world)
    check(not fails, label)
    for f in fails:
        print("      " + f.replace("\n", "\n      "), flush=True)


run(check_banner_sentences,
    "checks 1+2. both `Cell shape` banner sentences are in %s, once each, naming the "
    "OTHER mode by constant" % _SRC)
run(check_record_anchor,
    "check 3. the refusal's record resolves exactly once in %s, at \"%s\"" % (_NOTE, ANCHOR))
run(check_record_quotes,
    "check 4. that record QUOTES both banner sentences verbatim — the grep-verified "
    "anchor, so a reword of either home fails loudly")
run(check_rule_pointer,
    "check 5. `%s` carries the rule's `Why:` pointer on ONE line" % _RULE)
run(check_names_do_not_cross,
    "check 6. neither machine-line emitter names the other path's metric")
run(check_two_sidecar_labels,
    "check 7. the sidecar is given TWO metric labels, one per path, never one shared")


# --- injections ---------------------------------------------------------------
# Each mutates a COPY of the inputs, asserts the mutation is well-formed and really
# differs, then asserts the check fails — an injection that merely corrupts its
# input looks identical to the check working.
inj = copy_world(world)
inj["src"] = world["src"].replace("and NOT comparable with ", "and roughly comparable with ", 1)
check(inj["src"] != world["src"] and "1.0 is square" in inj["src"],
      "injection A. injection is well-formed: the multi-block sentence really changed and "
      "the row it lives on is still there")
f = check_banner_sentences(inj)
check(len(f) == 1 and "multi-block" in f[0] and _NOTE in f[0],
      "injection A. check 1 fails on a REWORDED banner sentence and names the design note "
      "that quotes it, so the reader is sent to both homes rather than one")

inj = copy_world(world)
_hy = SENTENCES[1]
# Deleted from the RAW source, which is where an author would delete it: the head
# above exists only AFTER the literals are joined — `"…NOT comparable "` and
# `"with MESH_MODE "` are two literals around the mode constant, and mutating the
# joined form would be injecting into `cpp_code` rather than into `src/cli.cpp`.
inj["src"] = world["src"].replace("1.0 is equilateral, and NOT comparable ", "", 1)
check(inj["src"] != world["src"] and _hy[2] not in cpp_code(inj["src"])
      and SENTENCES[0][2] in cpp_code(inj["src"]),
      "injection B. injection is well-formed: the hybrid sentence's head is gone from the "
      "joined source text and the multi-block one still stands")
f = check_banner_sentences(inj)
check(len(f) == 1 and "hybrid" in f[0],
      "injection B. check 2 fails on it ALONE — the two rows are separately guarded, which "
      "is what \"a reader of EITHER report\" needs")

inj = copy_world(world)
inj["note"] = world["note"].replace("1.0 is square, and NOT comparable",
                                    "1.0 is square, and not comparable", 1)
check(inj["note"] != world["note"] and ANCHOR in inj["note"],
      "injection C. injection is well-formed: only the QUOTATION moved, by one letter's "
      "case, and the record is still anchored")
f = check_record_quotes(inj)
check(len(f) == 1 and "multi-block" in f[0] and _SRC in f[0],
      "injection C. check 4 fails when the record drifts off the sentence it claims to "
      "quote — the direction the anchor exists for, and one a human diff reads as noise")

inj = copy_world(world)
inj["note"] = world["note"].replace(ANCHOR, "THE TWO FIGURES ARE DIFFERENT", 1)
check(ANCHOR not in inj["note"] and "1.0 is square" in inj["note"],
      "injection D. injection is well-formed: the anchor is gone while the record's text "
      "stays, which is exactly how a retitling loses one")
check(len(check_record_anchor(inj)) == 1 and len(check_record_quotes(inj)) == 1,
      "injection D. checks 3 and 4 both fail: the rule file's pointer now resolves nowhere, "
      "and the record it points at cannot be located to read its quotations")

inj = copy_world(world)
inj["rule"] = world["rule"].replace(WHY, WHY.replace('`, "', '`,\n  "'), 1)
check(inj["rule"] != world["rule"] and ANCHOR in inj["rule"] and _NOTE in inj["rule"],
      "injection E. injection is well-formed: both halves of the pointer are still in the "
      "rule file, on two lines")
f = check_rule_pointer(inj)
check(len(f) == 1 and "WRAPPED" in f[0],
      "injection E. check 5 fails on a WRAPPED pointer and says so, rather than reporting it "
      "as absent — #59's recurring defect, named in the failure a reader gets")

inj = copy_world(world)
inj["src"] = world["src"].replace(" tri_edge_ratio_", " quad_midline_ratio_")
check(inj["src"] != world["src"] and "HYBMESH_HYBRID_QUALITY" in inj["src"],
      "injection F. injection is well-formed: the hybrid line still exists and now emits the "
      "other path's metric name")
f = check_names_do_not_cross(inj)
check(any("HYBMESH_HYBRID_QUALITY" in m and "quad_midline_ratio" in m for m in f),
      "injection F. check 6 fails when one line emits the other's name — the same defect "
      "`test_hybrid_shape_surface.py` injection A needs a rebuilt binary to see")

inj = copy_world(world)
inj["src"] = world["src"].replace('quality.metric = "tri_edge_ratio"',
                                  'quality.metric = "cell_shape"', 1)
check(inj["src"] != world["src"] and 'quality.metric = "quad_midline_ratio"' in inj["src"],
      "injection G. injection is well-formed: one sidecar label was relabelled and the other "
      "stands")
f = check_two_sidecar_labels(inj)
check(len(f) == 1 and "cell_shape" in f[0],
      "injection G. check 7 fails when a sidecar label stops naming its own quantity, and "
      "prints what it found rather than only what it wanted")

check(not any(fn(world) for fn in (check_banner_sentences, check_record_anchor,
                                   check_record_quotes, check_rule_pointer,
                                   check_names_do_not_cross, check_two_sidecar_labels)),
      "injection H. negative control: the real, unmutated tree passes every check, so the "
      "failures above are the mutations and not the checker")

print(("\nRESULT: " + ("ALL PASS" if not _FAILS else "%d FAIL" % len(_FAILS))), flush=True)
sys.exit(1 if _FAILS else 0)
