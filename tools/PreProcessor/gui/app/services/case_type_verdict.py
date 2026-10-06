"""The VERDICT a case type passes on a finished mesh. Qt-free.

The grading half of the case-type seam (issue #160, parent #158); the artefact
itself — the name, the metric, the thresholds and their advice — is
`services/case_type.py`, and the thresholds are DECLARED there and only there.
This module applies them, which is why the files are one seam rather than one
body of knowledge in several places: every cut is the ~500-line GUI file-length
standard — #161 added `case_type_reference.py` and `case_type_author.py` the
same way — and it is the same one #159 made between `mesh_config.py` (declares)
and `mesh_config_validate.py` (judges). The dependency runs one way.

THE FOUR STATES ARE NOT THREE PLUS AN ERROR. `usable`, `needs attention`,
`unusable`, `not determinable`. The fourth exists because the mesher returns
NEGATIVE — never 0.0 — for anything it could not measure and prints `not
measured`, precisely so that "we did not measure" never reads as "it came out
perfect" (`.claude/rules/mesher-quality.md`). A verdict layer that collapsed an
unmeasured figure into a pass would spend that rule for nothing, so an
unmeasurable figure is `not determinable` and never `usable`.

`EXIT_ERR_INVERTED` (9) IS A HARD `unusable`, BEFORE ANY FIGURE IS READ. The
mesher exports a folded mesh under its ordinary filename and keeps `blSuccess`
true, by design, so that a developer can SEE the fold (ADR-0002). That is right
for the mesher and dangerous for an operator, whose finished case would
otherwise carry a folded mesh that looks entirely normal. This layer is where
the refusal lives, and it does not consult a figure first: non-orthogonality is
blind to a fold that preserves angles, so no published number can be relied on
to notice what the exit code already said.

WORST WINS, AND THE ORDER IS NOT ALPHABETICAL. `unusable` beats `not
determinable` beats `needs attention` beats `usable`: positive evidence of a
defect outranks the absence of evidence about something else, and the absence
outranks a figure that merely crossed a bound — otherwise one unmeasurable
figure among three good ones would be reported as the milder answer.

DEVIATION DOWNGRADES STANDING, IT NEVER WITHHOLDS (#162). The thresholds were
measured on a reference mesh the case type's own config fields produced; an
operator who changes one of those fields has moved the ground under them, so
presenting the verdict unqualified would be a lie. Withholding it would be
worse — it would teach operators not to touch anything, which is the opposite of
user story 21. So the STATE is unchanged and honest, the verdict is MARKED, the
moved fields are NAMED, and the only thing that moves is the log grade: a
deviated `usable` is a WARNING rather than an INFO, because it is a pass with a
caveat and a caveat nobody sees is not one.

ONE RENDERING, TWO HOSTS. `run_verdict` judges and renders; `run_report` is
that function with the judgement dropped. The headless `services/pipeline_runner`
calls the second and the GUI's disposition (#166) the first, so a verdict cannot
be WORDED one way in the window and another in a log file nobody is watching —
there is one rendering and one pass through the thresholds, not two of either. A
host still spells no state, no comparison and no grade of its own; what the GUI
needs the object for is the DISPOSITION, and the one judgement it may act on is
`commit_refusal`, which is spelled here beside the states it reads. The
same arrangement `mesh_shape_stats.format_figures` already holds for the figures
themselves. The GRADE it returns beside the text is used by the GUI only: the
headless `log` callback takes no level (it is `print` in `run_pipeline`), and a
level tag inside the text would not anchor behind the `[Mesh] ` component prefix
either, which is the shape ~20 of this repo's lines already have
(`.claude/rules/gui-seams.md`). Named rather than left as a half-used return.
"""
from __future__ import annotations

# ONE import form for the artefact, under an alias: `judge`'s own parameter is
# named `case_type`, so importing the module under that name would shadow it
# inside the function that needs it most.
from app.services import case_type as case_type_mod
from app.services import case_type_fields
from app.services import case_type_scale
from app.services import mesh_shape_stats
from app.services.logging_setup import get_logger

logger = get_logger(__name__)

# `include/ExitCodes.hpp` OWNS this number; this is the Python mirror, and
# `tests/test_case_type_verdict.py` check 1 reads the enum out of that header and
# fails if the two ever disagree. Declared here rather than taken from
# `app/workers/exit_codes.py`, which holds the GUI's own out-of-band sentinels
# (cancel, timeout) and knows nothing about the mesher's codes.
EXIT_ERR_INVERTED = 9

# The four states. STRINGS rather than an enum because they are written into
# logs and (from #166) into a finished case, and a reader six months from now
# should see the word rather than a number.
USABLE = "usable"
NEEDS_ATTENTION = "needs attention"
UNUSABLE = "unusable"
NOT_DETERMINABLE = "not determinable"

#: Worst wins; see the module docstring for why this order and not another.
#: This is also the ONE declaration of the set of states — `STATES` is derived
#: from it, so a fifth state cannot be added to one and missed by the other.
#: `_LEVELS` is the map that could still go stale, which is why check 3 of the
#: gate compares its keys against `STATES` rather than trusting them to match.
_RANK = {USABLE: 0, NEEDS_ATTENTION: 1, NOT_DETERMINABLE: 2, UNUSABLE: 3}
STATES = tuple(_RANK)

# The grade each state is logged at. Held HERE so the GUI and the headless host
# cannot show one verdict two ways; `user_log.log_report` takes the level as an
# argument precisely so the caller owns the grade
# (`.claude/rules/gui-seams.md`), and this is that caller's one answer.
_LEVELS = {USABLE: "INFO", NEEDS_ATTENTION: "WARNING",
           UNUSABLE: "ERROR", NOT_DETERMINABLE: "WARNING"}

#: The grade a DEVIATED verdict may not sit below. It only ever lifts `usable`
#: — every other state is already at least this — which is exactly the
#: "standing downgraded, never withheld" rule: the answer is unchanged, the
#: caveat is audible.
DEVIATED_FLOOR = "WARNING"


class Reason:
    """One figure's contribution to a verdict, and what to do about it.

    Carries the measurement, the bound it crossed and the gap between them, so
    the judgement is checkable rather than opaque (user story 12), plus the case
    type's own advice for that threshold (user stories 13 and 14).

    A reason whose state is `not determinable` has no bound: nothing was
    compared, and `detail` says why instead.
    """

    __slots__ = ("key", "state", "measured", "bound", "bound_name", "advice",
                 "detail")

    def __init__(self, key: str, state: str, measured: float | None = None,
                 bound: float | None = None, bound_name: str = "",
                 advice: str = "", detail: str = ""):
        self.key = key
        self.state = state
        self.measured = measured
        self.bound = bound
        self.bound_name = bound_name
        self.advice = advice
        self.detail = detail

    def describe(self) -> str:
        """One line naming the measurement, the bound and the gap.

        BY HOW MUCH is given twice — the absolute excess and the ratio — because
        the published figures span four orders of magnitude between shipped
        cases (the square's 1.0 against the C-grid's 3147.958), so neither form
        alone tells a reader whether a miss is marginal.
        """
        if self.bound is None or self.measured is None:
            # Two wordings, because a reason with no bound reaches here from two
            # different places: a figure nobody could measure, which must SAY it
            # was not judged, and a run-level fact such as the inverted exit
            # code, which was judged perfectly well without reading a figure.
            if self.state == NOT_DETERMINABLE:
                return "%s could not be judged: %s" % (self.key, self.detail)
            return "%s: %s" % (self.key, self.detail)
        return ("%s %.3f exceeds the %s bound %.3f by %.3f (x%.3f)"
                % (self.key, self.measured, self.bound_name, self.bound,
                   self.measured - self.bound, self.measured / self.bound))

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return "Reason(key=%r, state=%r)" % (self.key, self.state)


class Verdict:
    """The graded judgement one case type passes on one finished mesh."""

    __slots__ = ("state", "case_type", "reasons", "checked", "deviations")

    def __init__(self, state: str, case_type: case_type_mod.CaseType,
                 reasons: "list[Reason] | None" = None, checked: int = 0,
                 deviations: "tuple | None" = None):
        self.state = state
        self.case_type = case_type
        #: ONLY the reasons that moved the verdict off `usable`. A figure that
        #: met its bound has nothing to say and the headline carries the count.
        self.reasons = list(reasons or [])
        #: How many of the case type's thresholds were actually evaluated. 0
        #: when the verdict was settled before any of them was read, which is a
        #: different thing from a case type that has none.
        self.checked = checked
        #: The owned config fields this run has moved, as
        #: `case_type_fields.Deviation`. Carried on EVERY verdict, including the
        #: ones settled before a figure is read: a folded mesh produced with the
        #: case type's settings changed is still a folded mesh, and which
        #: settings were changed is the first thing anybody asks about it.
        self.deviations = tuple(deviations or ())

    @property
    def deviated(self) -> bool:
        """True when the operator has moved a field the case type owns."""
        return bool(self.deviations)

    @property
    def level(self) -> str:
        """The log grade for this state, so both hosts show it the same way.

        A deviated verdict is floored at `DEVIATED_FLOOR`, which is the whole of
        what "standing downgraded" costs: the state is untouched and the caveat
        becomes audible.
        """
        level = _LEVELS[self.state]
        if self.deviated and level == "INFO":
            return DEVIATED_FLOOR
        return level

    @property
    def headline(self) -> str:
        line = "Verdict: %s%s — case type '%s'" % (
            self.state,
            (", DEVIATED on %d field(s)" % len(self.deviations)
             if self.deviated else ""),
            self.case_type.name)
        if self.checked:
            # `reasons` holds only the ones that MOVED the verdict (see the slot
            # comment), so their count IS the number that were not met; counting
            # by state here would be a second definition of the same invariant.
            line += " (%d of %d thresholds met)" % (
                self.checked - len(self.reasons), self.checked)
        return line

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("Verdict(state=%r, case_type=%r, reasons=%d)"
                % (self.state, self.case_type.name, len(self.reasons)))


def judge_threshold(threshold: case_type_mod.Threshold, summary) -> Reason:
    """One threshold against the published figures. Never raises.

    THE NEGATIVE-MEASUREMENT RULE IS ENFORCED HERE, through
    `ShapeFigures.measured` rather than by testing one figure's sign: the mesher
    writes a set's three figures negative TOGETHER and its count 0 with them
    (`include/CellShape.hpp`: "It is 0 exactly when the three figures are
    negative"), so the SET is the honest unit, and reading one figure's sign
    would accept a set the producer never writes.

    The `unusable` bound is tested before the `attention` one. They can only
    both be crossed when the figure is past the higher of the two, and the
    answer then is the worse state.
    """
    set_name, field = case_type_mod.split_key(threshold.key)
    figures = case_type_mod.figures_for(summary, set_name)
    if figures is None:
        return Reason(threshold.key, NOT_DETERMINABLE, advice=threshold.advice,
                      detail="this run published no layer/bulk split")
    if not figures.measured:
        return Reason(threshold.key, NOT_DETERMINABLE, advice=threshold.advice,
                      detail="the mesher looked and could not measure it")
    value = float(getattr(figures, field))
    if threshold.unusable is not None and value > threshold.unusable:
        return Reason(threshold.key, UNUSABLE, measured=value,
                      bound=threshold.unusable, bound_name="unusable",
                      advice=threshold.advice)
    if threshold.attention is not None and value > threshold.attention:
        return Reason(threshold.key, NEEDS_ATTENTION, measured=value,
                      bound=threshold.attention, bound_name="needs-attention",
                      advice=threshold.advice)
    return Reason(threshold.key, USABLE, measured=value)


def _undeterminable(case_type, key: str, detail: str,
                    deviations: tuple = ()) -> Verdict:
    """A verdict settled before any threshold was read. One shape, four causes.

    Written once because the four short circuits in `judge` differ in nothing
    but the subject and the sentence; four copies of the same three-line
    construction is where one of them acquires a different state by edit.
    """
    return Verdict(NOT_DETERMINABLE, case_type,
                   [Reason(key, NOT_DETERMINABLE, detail=detail)],
                   deviations=deviations)


def judge(case_type: case_type_mod.CaseType, summary, exit_code: int = 0,
          deviations: "tuple | None" = None) -> Verdict:
    """Grade one mesh: measured figures + the mesher's exit code + thresholds.

    `summary` is a `mesh_shape_stats.ShapeSummary`, or ``None`` when the mesh
    published none. The five short circuits below are ordered by how much they
    know, most certain first, and every one of them is a state the tool can
    genuinely be in rather than a defensive branch.

    `deviations` is what `case_type_fields.deviations` returned for this run.
    It does not change the STATE — see the module docstring — so it is attached
    to whatever verdict the figures and the exit code produce, on every path.
    """
    deviations = tuple(deviations or ())
    if exit_code == EXIT_ERR_INVERTED:
        return Verdict(UNUSABLE, case_type, [Reason(
            "inverted cells", UNUSABLE,
            detail="the mesher exited %d — this mesh holds inverted cells, and "
                   "it was exported under its ordinary name anyway so that the "
                   "fold can be looked at" % EXIT_ERR_INVERTED)],
            deviations=deviations)
    if exit_code != 0:
        return _undeterminable(
            case_type, "the run",
            "the mesher exited %d — there is no finished mesh to judge"
            % exit_code, deviations)
    if summary is None:
        return _undeterminable(case_type, "the mesh",
                               "this mesh publishes no quality figures",
                               deviations)
    if summary.metric != case_type.metric:
        return _undeterminable(
            case_type, "the metric",
            "this mesh was measured with %s and the case type's thresholds are "
            "about %s, which are different quantities"
            % (summary.metric, case_type.metric), deviations)
    if not case_type.thresholds:
        return _undeterminable(
            case_type, "the case type",
            "case type '%s' carries no thresholds, so it has no opinion about "
            "this mesh" % case_type.name, deviations)

    reasons = [judge_threshold(th, summary) for th in case_type.thresholds]
    state = max((r.state for r in reasons), key=lambda s: _RANK[s])
    return Verdict(state, case_type, [r for r in reasons if r.state != USABLE],
                   checked=len(reasons), deviations=deviations)


def report_lines(verdict: Verdict) -> list:
    """The verdict as the lines both hosts show.

    ONE rendering, like `mesh_shape_stats.format_figures`: the GUI log and the
    headless log quote the same words, so a user cannot be told two things about
    one mesh.
    """
    lines = [verdict.headline]
    for reason in verdict.reasons:
        lines.append("  " + reason.describe())
        if reason.advice:
            lines.append("    try: " + reason.advice)
    if verdict.deviated:
        # NAMED, not counted: user story 20 is "I want to see which fields I
        # deviated on, so that I can put one back if I want the verdict's full
        # standing", and a count tells the operator a number they cannot act on.
        lines.append("  deviated: the thresholds were measured on a mesh these "
                     "settings produced, and %d of them %s moved"
                     % (len(verdict.deviations),
                        "has" if len(verdict.deviations) == 1 else "have"))
        for dev in verdict.deviations:
            lines.append("    " + dev.describe())
    if verdict.case_type.source:
        # WHICH FILE JUDGED, when it came from one. `CaseType.source` is kept
        # for traceability — "a verdict a user questions must be traceable to
        # the file that issued it" — and a field nobody prints cannot do that.
        # It also records which case type a run used, which the interim
        # environment-variable channel otherwise leaves nowhere.
        lines.append("  from " + verdict.case_type.source)
    return lines


def report_text(verdict: Verdict) -> str:
    """`report_lines` as one multi-line string — one graded message, not N."""
    return "\n".join(report_lines(verdict))


def commit_refusal(verdict: "Verdict | None") -> str:
    """Why this mesh may NOT be written into a case, or ``""`` when it may.

    ONLY `unusable` refuses (#166). `not determinable` does not: an unmeasured
    figure is the absence of evidence, and refusing on it would mean a case type
    whose metric this mesh does not publish could never commit anything — while
    `needs attention` is by construction a mesh the operator is allowed to keep.
    A run with NO case type in play (`verdict is None`) has nobody to refuse.

    THE REFUSAL IS SPELLED HERE and nowhere else, for the reason the states are:
    `.claude/rules/gui-handoff.md` holds the hosts to "neither may spell a
    verdict state, a threshold comparison or a grade of its own", and the
    disposition that acts on this answer is a host like any other. It returns a
    SENTENCE rather than a bool so that "says why" (user story 17) cannot be
    satisfied by a caller inventing its own wording.
    """
    if verdict is None or verdict.state != UNUSABLE:
        return ""
    lines = ["This mesh is %s, so it was not written into the case."
             % verdict.state]
    for reason in verdict.reasons:
        lines.append("  " + reason.describe())
        if reason.advice:
            lines.append("    try: " + reason.advice)
    return "\n".join(lines)


def run_verdict(mesh_path: str, exit_code: int,
                case_type: case_type_mod.CaseType | None = None,
                config=None) -> tuple:
    """`(verdict, text, level)` for one finished run — the whole of what this
    layer can say about it, judged ONCE.

    The verdict OBJECT is returned beside its rendering because a run has two
    readers with different needs and only one judgement to go round: the log
    wants the text and the grade, and the disposition that follows (#166) wants
    the case type that issued it, the state it reached and the reasons, to
    freeze into the case. Judging a second time to get them would be a second
    answer about one mesh, and the first thing to diverge would be the one
    nobody is looking at.

    `verdict` is ``None`` on both paths that produce no judgement — no case type
    in play, and a named case type that will not load — which is exactly the
    condition `commit_refusal` reads as "nobody to refuse".

    It resolves the active case type, reads the figures the run published,
    works out which of the case type's own fields this run moved and grades the
    lot, so neither host holds a rule of its own about any of the four — which
    is what keeps the GUI's verdict and the headless one the same verdict.

    `config` is the `MeshConfig` the run used. Passed by the host because only
    the host has it; ``None`` means nobody could say, and the deviation report
    is then EMPTY rather than invented — a verdict that silently claimed no
    deviation because nothing looked would be the one lie this layer exists
    against.

    A case type that was NAMED and will not load comes back as a message rather
    than as silence: the operator asked for a judgement and must be told why
    there is none.
    """
    if case_type is None:
        try:
            case_type = case_type_mod.active_case_type()
        except case_type_mod.CaseTypeError as exc:
            logger.warning("case type named by %s did not load: %s",
                           case_type_mod.CASE_TYPE_ENV, exc, exc_info=True)
            return (None, "No verdict: %s" % exc, "WARNING")
        if case_type is None:
            return (None, "", "INFO")
    # Against the FITTED overlay, not the authored one (#163): the value a case
    # type has an opinion about on THIS drawing is the one its characteristic
    # length scaled to. Comparing against the authored number would mark every
    # geometric field of every rescaled run as deviated.
    moved, why_not = (), ""
    if config is not None:
        wanted, _scale, why_not = case_type_scale.fit(case_type, config)
        moved = case_type_fields.deviations(wanted, config)
    verdict = judge(case_type, mesh_shape_stats.read_shape_summary(mesh_path),
                    exit_code, moved)
    text = report_text(verdict)
    if why_not:
        # SAID, not only logged. The comparison below it was made against
        # numbers nothing fitted to this geometry, and a deviation list computed
        # on the wrong ground is this file's own failure mode: a plausible wrong
        # answer rather than an error.
        text += ("\n  The case type's characteristic length could not be "
                 "measured on this case (%s), so its fields were compared as "
                 "AUTHORED rather than fitted to this geometry." % why_not)
    return (verdict, text, verdict.level)


def run_report(mesh_path: str, exit_code: int,
               case_type: case_type_mod.CaseType | None = None,
               config=None) -> tuple:
    """`(text, level)` for one finished run. ``("", "INFO")`` when there is none.

    The ONE call the headless host makes, and the SAME rendering the GUI's
    disposition shows — it is `run_verdict` with the judgement dropped, not a
    second path through the thresholds, so a verdict cannot be worded one way in
    the window and another in a log file nobody is watching.
    """
    _verdict, text, level = run_verdict(mesh_path, exit_code, case_type, config)
    return (text, level)
