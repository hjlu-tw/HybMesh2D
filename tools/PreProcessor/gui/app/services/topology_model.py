"""The family REGISTRY and the projection to JSON (issue #134).

Qt-free, and gated as such by ``tests/test_qt_free_seam.py``'s ``services/`` sweep:
the whole template library — declaring a family, deriving its counts, building its
document and writing that document out — is exercisable from a headless process, and
the GUI is one caller of it rather than its home.

THE JSON IS A PROJECTION, NOT A SECOND HOME FOR THE TRUTH. What the user edits, what
the project file carries and what undo restores is the MODEL; the document the
mesher reads is produced from it on the way to the run. Two homes for one fact is the
shape this repo has been bitten by before (a per-segment BC that lived both as a label
and as a map, and exported an all-wall mesh when one was rewritten and the other was
not). Here the model is the only writer and the JSON has no readers but the mesher.

THE MODEL ITSELF IS ``topology_params.py``, next door, and is RE-EXPORTED here
(#159). That file ran out of room for the work coming to it, and the seam taken is
the one this docstring already named: the parameters on one side, the registry and
the projection that read them on the other. ``TopologyModel`` is still imported from
this module by every caller it always was, and the dependency runs ONE WAY — the
registry knows about the model, the model knows about no family.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from app.services import (
    topology_binding, topology_cgrid, topology_hgrid, topology_ogrid,
    topology_ogrid_binding, topology_preflight, topology_tworing,
)
from app.services.mesh_modes import (
    MESH_MODE_MULTIBLOCK, missing_mesh_input,
)
# Re-exported, not re-declared: `from app.services.topology_model import
# TopologyModel` is the import every caller and every gate already writes, and a
# prefactor that re-pointed them would be spending their attention to save a file.
# `FAMILY_NONE` travels with it because `FAMILY_CHOICES` below is built from both.
from app.services.topology_params import (  # noqa: F401
    FAMILY_NONE, TopologyModel,
)


@dataclass(frozen=True)
class Family:
    """One entry of the registry: a name, a label, and the pure function.

    ``build`` takes ``(TopologyModel, BindingContext | None)``. The context is the
    second argument rather than a field of the model because it is not the user's
    configuration — it is what their CAD looks like right now, re-read per run — and
    a family that binds to nothing (the H-grid) ignores it. Keeping it out of the
    model is also what keeps the project file a record of DECISIONS: a context baked
    into it would be a stale copy of the geometry list.
    """

    name: str
    label: str
    build: object          # (TopologyModel, BindingContext | None) -> dict
    #: The parameter attribute prefix this family owns, which is how the
    #: parameters-to-families gate attributes a field-spec row to a family.
    prefix: str
    #: ``(TopologyModel, BindingContext | None) -> tuple[Refusal, ...]`` — can this
    #: family work with the geometry and the roles it has been handed (#165).
    #: Declared with NO DEFAULT, which is the whole enforcement asked for: a
    #: fifth family that writes a build function and forgets its refusal does
    #: not CONSTRUCT, so there is no state in which one is silently exempt.
    #: Beside ``build`` for the reason ``broken`` is beside it — what a family
    #: can fill is the family's decision, so what it cannot is too, and a
    #: shared rule table could hold only what all four agree on, which is
    #: nearly nothing (the O-grid needs a closed loop, the C-grid a sharp
    #: trailing edge, the H-grid a rectangle with four distinct corners).
    preflight: object
    #: ``(TopologyModel, BindingContext) -> tuple[BrokenBinding, ...]``, or None
    #: for a family that binds to nothing (#138). Declared here for the reason
    #: ``build`` is: WHICH edges bind is the family's decision, so which of them
    #: are broken — and which segments a dropdown may offer instead — is the
    #: family's answer too, and the panel asks the registry rather than asking a
    #: family by name. A family with no bindings reports none rather than being
    #: special-cased at the call site.
    broken: object = None
    #: ``((BindingContext field, label, MeshConfig attribute), ...)`` — the
    #: quantities this family reads
    #: from the binding CONTEXT rather than from the model, declared so the
    #: provenance summary can name them (#139). Empty for a family that reads none.
    #:
    #: WHY IT EXISTS. #133 decided that where a template needs a physical quantity
    #: the run already carries, it uses THAT name rather than an alias — so the
    #: O-grid's first cell is `BL_INITIAL_THICKNESS` and not an `ogrid_*` parameter.
    #: The summary derives its rows from the field-spec table by the family's
    #: PREFIX, so without this declaration it silently omitted the one number that
    #: set the radial count. Measured in #139's review, on a summary that looked
    #: complete. Declared rather than inferred, and held in BOTH directions by
    #: `tests/test_topology_param_specs.py` check 11: the set of context fields
    #: named here must EQUAL the set the family's module reads, minus the one
    #: exemption that file states. The context field is carried so that pairing can
    #: be exact rather than a count.
    reads_context: tuple = ()

    @property
    def binds(self) -> bool:
        """True for a family that resolves bindings against the user's CAD.

        Spelled HERE rather than at the panel, which asks it to decide whether to
        build a :class:`~app.services.topology_binding.BindingContext` at all — a
        context is a ``.dat`` and a ``.meta`` parse per geometry, paid on every
        keystroke, and the H-grid needs none. It IS ``broken is not None``, because a
        family that binds is exactly one that can report a broken binding: #138 gives
        ``broken=None`` to "a family that binds to nothing", and a second spelling in
        the panel would be free to disagree with the registry about which those are.
        """
        return self.broken is not None


#: The registry. Adding a family is adding a function and a row here — and a
#: field-spec row per parameter, which the bidirectional gate then requires.
FAMILIES: tuple[Family, ...] = (
    Family(topology_hgrid.FAMILY, "H-grid (rectangular blocks)",
           topology_hgrid.build, "hgrid_", topology_hgrid.preflight),
    Family(topology_ogrid.FAMILY, "O-grid (ring around a drawn body)",
           topology_ogrid.build, "ogrid_", topology_ogrid.preflight,
           broken=topology_ogrid_binding.broken_bindings,
           reads_context=(("first_cell", "First Cell Height "
                           "(BL_INITIAL_THICKNESS)", "bl_initial_thickness"),)),
    Family(topology_cgrid.FAMILY, "C-grid (wake cut around a drawn aerofoil)",
           topology_cgrid.build, "cgrid_", topology_cgrid.preflight,
           broken=topology_cgrid.broken_bindings,
           reads_context=(("first_cell", "First Cell Height "
                           "(BL_INITIAL_THICKNESS)", "bl_initial_thickness"),)),
    Family(topology_tworing.FAMILY,
           "Two-ring O-grid (a ring split at a seam you drew)",
           topology_tworing.build, "tworing_", topology_tworing.preflight,
           broken=topology_tworing.broken_bindings,
           reads_context=(("first_cell", "First Cell Height "
                           "(BL_INITIAL_THICKNESS)", "bl_initial_thickness"),)),
)

#: ``(value, label)`` pairs for the family combo, with "no template" first because it
#: is the state every existing project is in.
FAMILY_CHOICES: list[tuple[str, str]] = (
    [(FAMILY_NONE, "(none — name a topology file)")]
    + [(f.name, f.label) for f in FAMILIES])


def family_for(name: str) -> Family | None:
    """The registry entry called ``name``, or ``None`` for "no template"."""
    for f in FAMILIES:
        if f.name == name:
            return f
    return None


def broken_bindings(model: TopologyModel, ctx=None) -> tuple:
    """Every binding ``model`` holds that ``ctx`` can no longer resolve (#138).

    The registry's own dispatch, so the panel that flags a broken binding asks the
    same object the projection asks and cannot come to a different answer about
    which family is in force. Empty for a family that binds to nothing, for a model
    naming no family, and with no context — none of the three is a broken binding,
    and a caller distinguishing them would be re-deciding what a family is.

    NOT a second reading of :func:`build_document`'s refusal. That one stops at the
    first problem because it answers "can this run?"; this lists every position the
    user would have to repair, because repairing them one refusal at a time is the
    round trip #138 exists to remove.

    Empty for a DETACHED model too, through the same predicate the projection asks
    (#139): nothing resolves a binding on that path, so a flagged edge would name
    an edge of a document no run reads and offer a dropdown that rewrites a
    parameter nothing projects. That is the state #138's review already measured
    once, for a family switched away from rather than detached.
    """
    if not model.names_a_family():
        return ()
    fam = family_for(model.family)
    fn = fam.broken if fam is not None else None
    if fn is None or ctx is None:
        return ()
    return tuple(fn(model, ctx))


def preflight(model: TopologyModel, ctx=None) -> tuple:
    """Every reason ``model``'s family cannot work with ``ctx``'s drawing (#165).

    The registry's own dispatch, so the host that refuses a run and the host that
    shows the refusal ask the same object the projection asks and cannot come to
    different answers about which family is in force — ``broken_bindings``'s rule
    above, for the other question a family answers about a drawing.

    Empty for a model naming no family and for a DETACHED one, through the same
    predicate: nothing on either path is built from a family, so a refusal would
    be about a document no run reads. A hand-written topology file is the
    mesher's to judge, which is what ``EXIT_ERR_TOPOLOGY`` is for.

    NOT a second reading of :func:`build_document`'s refusal. That one stops at
    the first problem because it answers "can this run?"; this lists what the
    operator has to fix and names the curve for each.
    """
    if not model.names_a_family():
        return ()
    fam = family_for(model.family)
    if fam is None:
        return ()
    return topology_preflight.stamp_family(fam.name, fam.preflight(model, ctx))


def preflight_for_config(cfg) -> tuple:
    """:func:`preflight` for a whole ``MeshConfig``, context and all.

    The ONE place that pairs a configuration with the context its family is
    judged against, so the GUI, the headless runner and the case-type host
    cannot build that context differently. A configuration carrying no topology
    model, and one whose family binds to nothing, both cost no file read: the
    context is built only when the registry says the family binds.

    BOTH HALVES ARE ASKED — the MODE and a family named — for the reason
    ``mesh_modes.topology_file`` and ``topology_skeleton.skeleton_for_config``
    ask both of their own: a family named while the mode is hybrid drives
    nothing, the panel hides the whole section, and nothing of what it says
    reaches the run. Refusing a hybrid run over it would be this ticket's own
    worst outcome pointed the other way — a mesh the operator can have, withheld
    over a template nothing reads.
    """
    if cfg is None:
        return ()
    if int(getattr(cfg, "mesh_mode", 0) or 0) != MESH_MODE_MULTIBLOCK:
        return ()
    model = getattr(cfg, "topology", None)
    if model is None or not model.names_a_family():
        return ()
    fam = family_for(model.family)
    ctx = topology_binding.context_for_config(cfg) if (
        fam is not None and fam.binds) else None
    return preflight(model, ctx)


def mesh_preflight(cfg) -> str:
    """Why the mesh stage must not launch for ``cfg``, or ``""`` — ONE question.

    The mode's missing input FIRST and the family's own refusal after it, in that
    order because a configuration with no input at all has nothing for a family
    to judge. Both hosts that launch the mesher call this rather than one of its
    halves: `missing_mesh_input` alone is what they called before #165, and a
    host that kept calling it would be the one that still ships a drawing the
    family cannot fill.
    """
    why = missing_mesh_input(cfg)
    return why if why else topology_preflight.refusal_text(
        preflight_for_config(cfg))


def build_document(model: TopologyModel, ctx=None) -> dict:
    """The topology document ``model`` describes, bound against ``ctx``.

    Raises ``ValueError`` when the model names no family: a caller asking for the
    document of a model that has none has asked a question with no answer, and
    returning an empty document would put that answer in a file the mesher then
    refuses with a message about the document rather than about the request.

    A family that BINDS raises
    :class:`~app.services.topology_binding.BindingError` (a ``ValueError``) when a
    stored segment id is no longer on the geometry, naming the edge. It never falls
    back to the configured default boundary condition: a mesh that runs, exports and
    looks right while carrying the wrong conditions is the one outcome worse than a
    refusal (#137).
    """
    fam = family_for(model.family)
    if fam is None:
        raise ValueError(
            "this configuration names no topology family, so there is no document "
            "to build. Pick a family, or name a topology file by hand.")
    return fam.build(model, ctx)


def document_for(model: TopologyModel, ctx=None) -> str:
    """``model``'s document, as the JSON text to write.

    The two-step walk (:func:`build_document` then :func:`document_text`) behind one
    name, so a caller that wants the TEXT — the case staging, which writes it into
    the folder itself rather than to a path — does not have to know there are two
    steps, in the same way :func:`projection_path` already hides the naming rule.
    """
    return document_text(build_document(model, ctx))


def document_text(doc: dict) -> str:
    """``doc`` as the JSON text to write. Trailing newline, stable key order."""
    return json.dumps(doc, indent=2) + "\n"


def projection_path(config_path: str) -> str:
    """Where the document goes for a mesher config written at ``config_path``.

    Beside the config and named after it, so a case directory holding several
    configs holds one document per config rather than one they overwrite between
    them. Absolute, because the mesher opens ``MESH_TOPOLOGY_FILE`` exactly as
    written and relative to ITS OWN working directory (``src/cli.cpp``:
    ``std::ifstream tin(config.topologyFile)``) — which is not the config's
    directory, and is not the same for the two hosts.
    """
    p = os.path.abspath(config_path)
    stem = os.path.splitext(os.path.basename(p))[0]
    return os.path.join(os.path.dirname(p), f"{stem}_topology.json")


def project(model: TopologyModel, config_path: str, ctx=None) -> str:
    """Write ``model``'s document beside ``config_path``; return its absolute path.

    Nothing is written when the document cannot be built: the refusal propagates and
    the caller is left with no file rather than with a stale one from the last run,
    which would be a mesh cut from a topology the configuration no longer describes.
    """
    text = document_for(model, ctx)
    out = projection_path(config_path)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    return out
