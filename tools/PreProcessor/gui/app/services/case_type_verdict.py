"""The VERDICT a case type passes on a finished mesh. Qt-free.

The grading half of the case-type seam (issue #160, parent #158); the artefact
itself — the name, the metric, the thresholds and their advice — is
`services/case_type.py`, and the thresholds are DECLARED there and only there.
This module applies them, which is why the two are one seam in two files rather
than one body of knowledge in two places: the split is the ~500-line GUI
file-length standard, the same cut #159 made between `mesh_config.py` (declares)
and `mesh_config_validate.py` (judges), and the dependency runs one way.

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

ONE RENDERING, TWO HOSTS. `run_report` is the single call the GUI's mesh
controller and `services/pipeline_runner` both make, returning the text AND the
log grade, so a verdict cannot be worded or graded one way in the window and
another in a log file nobody is watching — the same arrangement
`mesh_shape_stats.format_figures` already holds for the figures themselves.
"""
from __future__ import annotations

# ONE import form for the artefact, under an alias: `judge`'s own parameter is
# named `case_type`, so importing the module under that name would shadow it
# inside the function that needs it most.
from app.services import case_type as case_type_mod
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
STATES = (USABLE, NEEDS_ATTENTION, UNUSABLE, NOT_DETERMINABLE)

#: Worst wins; see the module docstring for why this order and not another.
_RANK = {USABLE: 0, NEEDS_ATTENTION: 1, NOT_DETERMINABLE: 2, UNUSABLE: 3}

# The grade each state is logged at. Held HERE so the GUI and the headless host
# cannot show one verdict two ways; `user_log.log_report` takes the level as an
# argument precisely so the caller owns the grade
# (`.claude/rules/gui-seams.md`), and this is that caller's one answer.
_LEVELS = {USABLE: "INFO", NEEDS_ATTENTION: "WARNING",
           UNUSABLE: "ERROR", NOT_DETERMINABLE: "WARNING"}


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

    __slots__ = ("state", "case_type", "reasons", "checked")

    def __init__(self, state: str, case_type: case_type_mod.CaseType,
                 reasons: "list[Reason] | None" = None, checked: int = 0):
        self.state = state
        self.case_type = case_type
        #: ONLY the reasons that moved the verdict off `usable`. A figure that
        #: met its bound has nothing to say and the headline carries the count.
        self.reasons = list(reasons or [])
        #: How many of the case type's thresholds were actually evaluated. 0
        #: when the verdict was settled before any of them was read, which is a
        #: different thing from a case type that has none.
        self.checked = checked

    @property
    def level(self) -> str:
        """The log grade for this state, so both hosts show it the same way."""
        return _LEVELS[self.state]

    @property
    def headline(self) -> str:
        line = "Verdict: %s — case type '%s'" % (self.state, self.case_type.name)
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


def _figures_for(summary, set_name: str):
    """The `ShapeFigures` a key's set names, or ``None`` when it is absent.

    Only a HALF is ever absent, and only on a sidecar from a path that did not
    split — the whole-mesh set is the summary itself.
    """
    if not set_name:
        return summary
    return getattr(summary, set_name, None)


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
    set_name, _, field = threshold.key.rpartition(".")
    figures = _figures_for(summary, set_name)
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


def judge(case_type: case_type_mod.CaseType, summary, exit_code: int = 0) -> Verdict:
    """Grade one mesh: measured figures + the mesher's exit code + thresholds.

    `summary` is a `mesh_shape_stats.ShapeSummary`, or ``None`` when the mesh
    published none. The five short circuits below are ordered by how much they
    know, most certain first, and every one of them is a state the tool can
    genuinely be in rather than a defensive branch.
    """
    if exit_code == EXIT_ERR_INVERTED:
        return Verdict(UNUSABLE, case_type, [Reason(
            "inverted cells", UNUSABLE,
            detail="the mesher exited %d — this mesh holds inverted cells, and "
                   "it was exported under its ordinary name anyway so that the "
                   "fold can be looked at" % EXIT_ERR_INVERTED)])
    if exit_code != 0:
        return Verdict(NOT_DETERMINABLE, case_type, [Reason(
            "the run", NOT_DETERMINABLE,
            detail="the mesher exited %d — there is no finished mesh to judge"
                   % exit_code)])
    if summary is None:
        return Verdict(NOT_DETERMINABLE, case_type, [Reason(
            "the mesh", NOT_DETERMINABLE,
            detail="this mesh publishes no quality figures")])
    if summary.metric != case_type.metric:
        return Verdict(NOT_DETERMINABLE, case_type, [Reason(
            "the metric", NOT_DETERMINABLE,
            detail="this mesh was measured with %s and the case type's "
                   "thresholds are about %s, which are different quantities"
                   % (summary.metric, case_type.metric))])
    if not case_type.thresholds:
        return Verdict(NOT_DETERMINABLE, case_type, [Reason(
            "the case type", NOT_DETERMINABLE,
            detail="case type '%s' carries no thresholds, so it has no opinion "
                   "about this mesh" % case_type.name)])

    reasons = [judge_threshold(th, summary) for th in case_type.thresholds]
    state = max((r.state for r in reasons), key=lambda s: _RANK[s])
    return Verdict(state, case_type, [r for r in reasons if r.state != USABLE],
                   checked=len(reasons))


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
    return lines


def report_text(verdict: Verdict) -> str:
    """`report_lines` as one multi-line string — one graded message, not N."""
    return "\n".join(report_lines(verdict))


def run_report(mesh_path: str, exit_code: int,
               case_type: case_type_mod.CaseType | None = None) -> tuple:
    """`(text, level)` for one finished run. ``("", "INFO")`` when there is none.

    The ONE call both hosts make. It resolves the active case type, reads the
    figures the run published and grades them, so neither host holds a rule of
    its own about any of the three — which is what keeps the GUI's verdict and
    the headless one the same verdict.

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
            return ("No verdict: %s" % exc, "WARNING")
        if case_type is None:
            return ("", "INFO")
    verdict = judge(case_type, mesh_shape_stats.read_shape_summary(mesh_path),
                    exit_code)
    return (report_text(verdict), verdict.level)
