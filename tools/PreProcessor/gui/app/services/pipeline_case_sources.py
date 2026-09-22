"""What a SCRIPTED solver case carries into its own ``grid/cad/``.

The headless twin of ``solver_ctrl._case_source_files`` /
``_case_generated_files``: given a :class:`~app.models.pipeline_config.PipelineConfig`
it answers the one question ``services/case_sources.py`` needs answered before it
can stage anything — *which files did this run actually read, and which does it
have to reconstruct?* — so a case run from a pipeline script describes itself the
way a case run from the GUI does.

Split out of ``pipeline_runner`` (#103), which owns the stage SEQUENCING and the
subprocess plumbing; collecting a case's provenance is neither, and it is the
half with rules of its own — per-body sources, the per-MODE topology, the
generated parameter file, and the deliberate refusal to fail a solve over any of
them. Rules: ``.claude/rules/pipeline-case.md``; why:
``docs/design_notes/pipeline.md``.
"""
from __future__ import annotations
import os

from app.models.pipeline_config import PipelineConfig
from app.services import case_sources
from app.services.logging_setup import get_logger

_log = get_logger(__name__)


def case_sources_for(pcfg: PipelineConfig, repo: str, geoms: list | str | None,
                     vtk: str) -> tuple[list, list]:
    """``(sources, generated)`` for staging a scripted case's grid/cad/.

    The same things per body the GUI stages — the imported source and the
    resampled ``.dat`` the mesher read, plus the immersed STL, the mesh
    provenance sidecar and the mesh parameter file. Nothing is filtered by
    whether the resample ran: a skipped CAD entry still points at a geometry the
    mesh was cut from, and the staging service drops whatever does not exist on
    disk.
    """
    out: list = []
    for i in pcfg.cad_indices():
        out.append(pcfg.resolve_input_file(repo, i))
        out.append(pcfg.default_cad_output(repo, i))
    stl = (pcfg.stl3d or {}).get("stl_path", "")
    if stl:
        out.append(stl if os.path.isabs(stl) else os.path.join(repo, stl))
    out.extend(case_sources.mesh_provenance_paths(vtk))

    generated: list = []
    try:
        mc = pcfg.build_mesh_config(geoms)
        mc.output_filename = vtk or mc.output_filename
        # The block topology a MESH_MODE 1 run filled: an input of this run and
        # not a preference, so it is staged like the CAD rather than only quoted
        # by the generated parameter file. Repo-relative in a script, hence repo.
        # That is the HAND-WRITTEN document, which exists on disk to be copied; a
        # TEMPLATE's has no file, and is generated below beside the parameter file
        # that names it (#135).
        out.extend(case_sources.mesh_input_paths(mc, repo))
        generated.extend(case_sources.mesh_config_generated(
            mc, pcfg.name or "case"))
    except Exception:
        # Staging the geometry is worth having even when the settings cannot be
        # rebuilt; failing the solver run over it is not. Both the topology and
        # the parameter file are lost together, because both are read off the
        # MeshConfig this block builds.
        _log.warning("could not rebuild the mesh config, so neither it nor the "
                     "block topology reaches the case's cad/ folder",
                     exc_info=True)
    return [p for p in out if p], generated
