"""DETACH a generated topology into a hand-maintained file, and re-attach (#139).

The escape hatch the template library needs in order not to be a cage. A user whose
case no family covers presses Detach: the document stops being a PROJECTION of the
model and becomes a plain topology file they maintain, exactly as if they had written
it themselves — which is the path that existed before #134 and still works unchanged.

THE STATE IS ONE FLAG AND THE PATH HAS ONE HOME. ``TopologyModel.detached`` says the
projection is off; ``MeshConfig.mesh_topology_file`` names the file, as it already
does for every hand-written topology. Detaching does not copy the path onto the
topology model and re-attaching does not remember it: two homes for one path is the
failure this whole feature is shaped around, and a stale second copy of a filename is
how a run reads last week's document.

WHAT SURVIVES DETACHING IS PROVENANCE, AND THAT IS WHY THE PARAMETERS ARE KEPT. The
family and every parameter stay on the model and stay in the project file; they drive
nothing (``names_a_family()`` is False, so the funnel does not project, the case
staging does not generate and the canvas draws no skeleton) and they answer the one
question left three months later — where did this file come from. The alternative
the ticket names explicitly is an editable panel whose edits no longer take effect,
i.e. a control that does nothing.

RE-ATTACH DISCARDS THE FILE'S EDITS AND SAYS SO FIRST. It cannot merge them: the
model is the only input to the family function, and a hand-edited document has no
representation in it. What it does NOT do is delete the file — the user's work stays
on disk, it simply stops being read. It DOES clear ``mesh_topology_file``, because a
path left in an input row that the projection then overrides is exactly the control
that does nothing this ticket exists to remove — and worse, it becomes live again the
moment the family combo is set back to "(none)".

Qt-free, like every other module in this package and for the same reason: the whole
transition is exercisable headlessly, and the panel is one caller of it. The panel
supplies the two things only it can — WHERE the file goes (a Save dialog) and the
user's consent to discard — and nothing else.
"""
from __future__ import annotations

import os

from app.services import paths, topology_model
from app.services.topology_field_specs import TOPOLOGY_READONLY, TOPOLOGY_SPECS

#: Where a detached document goes when the user has expressed no preference: under
#: the repo's own ``config/`` tree, never beside the mesh output. ``results/`` is
#: swept by ``clean_results.sh``, and a hand-maintained INPUT that a cleanup script
#: is entitled to delete is not a file anybody can maintain.
DEFAULT_DIR = os.path.join("config", "topology")

#: The one wording of what re-attaching costs, so the dialog, the panel's own
#: read-out and the gate cannot each describe it differently.
REATTACH_QUESTION = "Re-attach this topology to the template?"
REATTACH_WARNING = (
    "Any edits you have made to the topology file will be DISCARDED: from now on "
    "the document is generated from the template parameters again, every time the "
    "mesher runs. The file itself is left on disk — it is simply no longer read.")


def default_path(mesh_config) -> str:
    """An absolute path to suggest for ``mesh_config``'s detached document.

    Named after the case, so a user who detaches two cases does not have to invent
    two names to avoid one overwriting the other. Only a SUGGESTION: the panel puts
    it in a Save dialog and the user decides, which is why nothing here creates the
    directory.
    """
    out = str(getattr(mesh_config, "output_filename", "") or "").strip()
    stem = os.path.splitext(os.path.basename(out))[0] if out else ""
    # `mesh_<case>.vtk` is the auto-generated output name (models/mesh_output_names),
    # so stripping the prefix recovers the case label the user actually recognises.
    if stem.startswith("mesh_"):
        stem = stem[len("mesh_"):]
    # `<stem>_topology.json`, or plain `topology.json` when there is no stem to
    # qualify it — `topology_topology.json` is what naming the fallback "topology"
    # produced, and it reads as a bug rather than as a default.
    name = f"{stem}_topology.json" if stem else "topology.json"
    return os.path.join(paths.repo_root(), DEFAULT_DIR, name)


def detach(model, mesh_config, path: str, ctx=None) -> str:
    """Write ``model``'s document at ``path`` and stop generating it. Returns ``path``.

    The document is built FIRST and the flag is set LAST, so a family that refuses —
    an O-grid whose binding no longer resolves raises
    :class:`~app.services.topology_binding.BindingError` — leaves the configuration
    exactly as it was. A half-detached case (the projection off and no file to read)
    would be the one state neither panel nor mesher has a message for.

    RETURNS THE STORED SPELLING, not the absolute path it wrote: that is the value
    the caller goes on to show, log and put in the row, and handing back a second
    spelling of one path is how a panel comes to display something the model does
    not hold.

    ``mesh_config.mesh_topology_file`` is written with the path AS GIVEN once it is
    inside the repo, matching what every other stored path in this app does
    (``geom_path_identity.stored_geom_path``'s rule, applied by hand because that
    module's verbs are about the GEOMETRY list): a repo-relative spelling is what
    keeps an exported case package portable, and an absolute one is right for a file
    the user keeps outside the tree.
    """
    text = topology_model.document_for(model, ctx)
    out = os.path.abspath(path)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    mesh_config.mesh_topology_file = _stored(out)
    model.detached = True
    return mesh_config.mesh_topology_file


def reattach(model, mesh_config) -> None:
    """Go back to generating the document from ``model``; forget the file.

    The file is NOT deleted — see the module docstring. ``mesh_topology_file`` is
    cleared because from here on it is an OUTPUT again, and a path sitting in an
    input row that the next projection overwrites is a control that does nothing.
    """
    model.detached = False
    mesh_config.mesh_topology_file = ""


def _stored(abs_path: str) -> str:
    """``abs_path`` as it should be written down: repo-relative when it is inside."""
    root = paths.repo_root()
    try:
        rel = os.path.relpath(abs_path, root)
    except ValueError:                       # different drive on Windows
        return abs_path
    return rel if not rel.startswith(os.pardir) else abs_path


def provenance(model, mesh_config=None) -> list:
    """``(label, value)`` rows describing the template this document came from.

    DERIVED FROM THE FIELD-SPEC TABLE by the family's own declared prefix, never
    hand-listed: a parameter added to a family and its table appears here with no
    edit, which is the same bidirectional property ``test_topology_param_specs.py``
    holds for the panel. The read-outs author no model field and are skipped, since
    a derivation is not something the user chose.

    Empty for a model naming no family — there is no provenance to show, and an
    empty list is what the panel's "nothing to summarise" branch reads.
    """
    fam = topology_model.family_for(getattr(model, "family", ""))
    if fam is None:
        return []
    rows = [("Template", fam.label)]
    for spec in TOPOLOGY_SPECS:
        if spec.attr in TOPOLOGY_READONLY or not spec.model_name:
            continue
        if not spec.model_name.startswith(fam.prefix):
            continue
        rows.append((spec.label, _shown(getattr(model, spec.model_name, ""), spec)))
    # ...and the quantities the family reads from the RUN rather than from the
    # model, which the prefix cannot find because #133 deliberately gave them no
    # alias. `mesh_config` is optional, so a caller with only a model gets the
    # parameters it can actually vouch for rather than a row reading "(none)".
    if mesh_config is not None:
        for _ctx_field, label, attr in getattr(fam, "reads_context", ()):
            rows.append((label, _shown(getattr(mesh_config, attr, ""), None)))
    return rows


def _shown(value, spec=None) -> str:
    """One value, as the summary prints it.

    A row that declares its own text for "no value chosen" is asked for it rather
    than having one invented here: the O-grid's radial override is an int spin box
    whose 0 MEANS "take the derived count" (`special`), and printing a bare `0` in a
    provenance summary shows a sentinel as a number the user picked.
    """
    opts = getattr(spec, "opts", None) or {}
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)) and not value and opts.get("special"):
        return str(opts["special"])
    if isinstance(value, float):
        return f"{value:g}"
    text = str(value)
    if text.strip():
        return text
    return str(opts.get("placeholder") or "(none)")


def summary(model, mesh_config=None) -> str:
    """The whole read-only summary, as one block of text.

    ONE builder, so the panel and the gate read the same sentence and a change to
    the wording cannot make a green gate describe a screen nobody sees.
    """
    rows = provenance(model, mesh_config)
    if not rows:
        return ""
    head = ("This topology is DETACHED: the file below is yours to maintain, and "
            "nothing regenerates it.")
    where = str(getattr(mesh_config, "mesh_topology_file", "") or "").strip()
    lines = [head, f"File: {where or '(none named — the run has no topology)'}",
             "Generated from:"]
    lines += [f"    {label}: {value}" for label, value in rows]
    return "\n".join(lines)
