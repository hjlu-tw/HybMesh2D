"""The pipeline's stage set, declared once instead of once per host.

Qt-free by construction: this module imports nothing but the standard library,
so the headless runner does not acquire a GUI dependency to learn its own stage
list. (``test_qt_free_seam.py`` sweeps every ``services/*.py`` as a deny-list,
so that property is already gated and is not re-checked here.)

WHY THIS EXISTS. The four stages are implemented twice — ``pipeline_runner.py``
runs them blocking and linear, ``pipeline_ctrl.py`` chains the same four on
QThread ``finished_signal`` — and until this module there was nothing that knew
the set. Each host named its own stages, ordered them, and decided by comment
what each handed to the next. Two things followed, both measured on ``84e186a``:

* **An artefact could be produced for nobody.** ``pipeline_runner`` carried the
  comment *"before meshing, because the solver stage links the phi field it
  produces"* while ``_run_solver`` took no phi argument at all, so the
  immersed-solid stage's output reached the solve only by coincidence — and did
  not. That was candidate 6a; the gate it left behind watches one artefact
  crossing one seam and cannot see the next one.
* **The stage count was hand-written and already wrong.** ``Stage 1/3`` …
  ``Stage 3/3`` appeared at 8 sites across the two hosts while four stages
  existed, because the immersed-solid stage was logged outside the numbering in
  both. The denominator was a literal where the plan is a variable. Nobody typed
  the wrong number; there was no number to derive.

WHAT THIS IS, AND IS NOT. It is DATA — a tuple of frozen records. It is
deliberately not a ``Stage`` base class the hosts subclass: the one thing that
legitimately differs between them is how they WAIT (``subprocess.wait`` versus a
``finished_signal``), and a hierarchy would have to host that difference, so it
would either force one waiting model onto the other or leave a base class whose
only shared member is a name. The hosts keep their own bodies and stay adapters.

The declaration is meant to be load-bearing rather than decorative: both hosts
build their run plan and their ``Stage i/N`` labels from it, so a run with an
immersed solid says 1/4 and a run without one says 1/3. A table nobody reads is
documentation with a test attached, and it goes stale exactly the way the prose
comments did.

Gated by ``tests/test_pipeline_stages.py``.
"""
from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# The artefact vocabulary. A stage consumes and produces these names; the gate
# asserts the graph closes, which is candidate 6a's defect stated as a static
# property rather than as something a reader has to notice.
# --------------------------------------------------------------------------- #
CAD = "cad"          # resampled .dat geometry, one per `cads` entry
PHI = "phi"          # immersed-solid phi field (Tecplot, from STL3d)
VTK = "vtk"          # generated mesh (+ the sibling STAR-CD .vrt/.cel/.bnd)
RESULT = "result"    # solver Tecplot result

#: Artefacts that end the pipeline: produced, and legitimately consumed by no
#: later stage. A flag rather than a special case in the gate, so a future
#: terminal artefact costs an entry here and not a test edit.
TERMINAL = (RESULT,)


@dataclass(frozen=True)
class Stage:
    """One pipeline stage, and where it is implemented in each host.

    ``runner_fn`` / ``gui_fn`` are names rather than callables on purpose: this
    module must not import either host (the GUI one is a Qt mixin, and importing
    it here would undo the Qt-free property this whole file depends on). The
    gate resolves them by AST, which is what turns "a stage exists in one host
    only" from a review finding into a build failure.
    """

    key: str
    title: str                     # human-readable, as it appears in the log
    consumes: tuple[str, ...]
    produces: tuple[str, ...]
    optional: bool                 # False = always in the plan, never skippable
    runner_fn: str                 # services/pipeline_runner.py
    gui_fn: str                    # controllers/pipeline_ctrl.py


#: The stage set, in run order. This tuple is the single declaration; adding,
#: removing or reordering a stage is an edit here and nowhere else.
#:
#: The immersed solid sits BEFORE the mesh in both hosts. That is not a
#: preference: the solver stage reads the phi field this stage traces, so the
#: ordering is the artefact dependency below, now written as data rather than as
#: a comment that was false for as long as it took anyone to check it.
STAGES: tuple[Stage, ...] = (
    Stage(
        key="resample",
        title="CAD resample",
        consumes=(),
        produces=(CAD,),
        # Optional: an entry may feed its raw geometry straight to the mesher,
        # and a mesh built from existing .dat files has no CAD stage at all.
        optional=True,
        runner_fn="_run_resample",
        gui_fn="_pipe_resample",
    ),
    Stage(
        key="stl3d",
        title="immersed solid",
        consumes=(),
        produces=(PHI,),
        optional=True,
        runner_fn="_run_stl3d",
        gui_fn="_pipe_stl3d",
    ),
    Stage(
        key="mesh",
        title="mesh generation",
        # Consumes the resampled geometry when there is one. `optional=True` on
        # the resample stage is what covers the other case (mesh straight from
        # configured geom_files); this declares the dependency, not a demand.
        consumes=(CAD,),
        produces=(VTK,),
        optional=False,
        runner_fn="_run_mesh",
        gui_fn="_pipe_mesh",
    ),
    Stage(
        key="solver",
        title="solver",
        consumes=(VTK, PHI),
        produces=(RESULT,),
        optional=True,
        runner_fn="_run_solver",
        gui_fn="_pipe_solver",
    ),
)


def by_key(key: str) -> Stage:
    """The declared stage with this key. Raises ``KeyError`` if there is none."""
    for s in STAGES:
        if s.key == key:
            return s
    raise KeyError(f"no pipeline stage named {key!r}")


def plan(active: dict) -> tuple[Stage, ...]:
    """The stages that will actually run, in order.

    ``active`` maps a stage key to whether the caller will run it. A
    non-optional stage is in the plan whatever ``active`` says — asking about
    one is allowed and its answer ignored — so a caller cannot drop the mesh by
    forgetting a key. An optional stage absent from ``active`` does not run.

    An UNKNOWN key raises. Ignoring one would reintroduce this candidate's own
    defect by a new route and without a wrong number being typed anywhere:
    measured before the check existed, ``plan({"resamlpe": True, ...})`` returned
    ``(stl3d, mesh, solver)`` — a misspelt key silently drops an optional stage
    from the plan, so every label after it is numbered against the wrong total.
    ``by_key`` already refuses a bad key; this is the same rule for the plural.

    The point of computing this is the label: the count has to follow what will
    execute, which is the fact the two hand-written ``/3`` denominators got
    wrong.
    """
    unknown = sorted(set(active) - {s.key for s in STAGES})
    if unknown:
        raise KeyError(f"unknown pipeline stage(s): {', '.join(unknown)}")
    return tuple(s for s in STAGES
                 if not s.optional or bool(active.get(s.key, False)))


def label(stage: Stage, steps: tuple[Stage, ...]) -> str:
    """``Stage 2/4: immersed solid`` — numbered against the PLAN, not the set.

    A stage that is not in ``steps`` is not running, so it gets its title with
    no number rather than a position it does not occupy; the hosts use that for
    their "skipped" lines.
    """
    if stage not in steps:
        return stage.title
    return f"Stage {steps.index(stage) + 1}/{len(steps)}: {stage.title}"


def label_for(key: str, steps: tuple) -> str:
    """``label(by_key(key), steps)`` — the form both hosts actually want.

    Exists so the two hosts do not each carry the same two-call adapter: they
    differ in where ``steps`` comes from (a local in the blocking runner, an
    attribute set at the top of the GUI's chain) and in nothing else.
    """
    return label(by_key(key), steps)
