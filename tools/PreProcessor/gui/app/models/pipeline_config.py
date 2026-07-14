from __future__ import annotations
import os
import json
import copy
from dataclasses import dataclass, field

from app.models.project import ProjectModel
from app.models.mesh_config import MeshConfig
from app.models.solver_config import SolverConfig

# Bump when the unified pipeline JSON schema changes in a backward-incompatible
# way. Readers tolerate a missing field (treated as version 0/legacy) and warn —
# but do not crash — when the file version is newer than they support.
PIPELINE_FORMAT_VERSION = 1

# Solver fields that are *derived at run time* (staged case paths, binary
# locations) rather than authored knobs. SolverConfig.to_dict() dumps the whole
# dataclass, so a script saved after a solve would otherwise bake in absolute
# paths to a specific machine/mesh; on reload the runner would then skip
# auto-linking and point at those stale files. Strip them on save so a saved
# script stays portable and always re-links to the mesh the pipeline produces.
_SOLVER_DERIVED_KEYS = (
    "input_vrt_file", "input_cel_file", "input_bnd_file",
    "work_dir", "output_grid_file", "output_bc_file",
    "getpgrid_binary", "solver_binary", "bdecompose_binary",
)


@dataclass
class PipelineConfig:
    """A single, self-contained description of a full CAD -> mesh -> solver ->
    results run.

    Each section maps 1:1 onto an existing per-stage config model, so this class
    is only a thin, human-writable container + a set of converters:

      * ``cad``     -> :class:`ProjectModel`   (surface_resampler input JSON)
      * ``mesh``    -> :class:`MeshConfig`      (HybMesh2D Background_para.dat)
      * ``solver``  -> :class:`SolverConfig`    (getPGrid / unicones input files)
      * ``results`` -> contour rendering options (headless PNG / GUI view)

    It is deliberately Qt-free so both the GUI orchestrator and the headless CLI
    runner share exactly this schema.
    """

    name: str = "pipeline"

    # CAD / resample stage. Either resample a raw geometry through
    # surface_resampler (segments define the per-edge strategy, exactly like the
    # PreProcessor GUI export), or skip resampling and feed input_file straight to
    # the mesher. Resampling is skipped automatically when no segments are given.
    #   {input_file, output_file, is_closed, global_spline, transform,
    #    segments:[...], skip:bool}
    cad: dict = field(default_factory=dict)

    # Mesh stage: a subset of MeshConfig fields (defaults fill the rest). The
    # geometry input is auto-wired to the CAD output unless geom_files is given.
    mesh: dict = field(default_factory=dict)

    # Solver stage: a subset of SolverConfig fields. The STAR-CD inputs are
    # auto-linked from the mesh output unless input_vrt/cel/bnd_file are given.
    # An optional "preset" name (see solver_config.PRESETS) is applied first.
    # "skip": true stops the pipeline after meshing.
    solver: dict = field(default_factory=dict)

    # Results stage: contour options. {variable, cmap, save_png, mesh_overlay}
    results: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        return {
            "pipeline_version": PIPELINE_FORMAT_VERSION,
            "name": self.name,
            "cad": copy.deepcopy(self.cad),
            "mesh": copy.deepcopy(self.mesh),
            "solver": copy.deepcopy(self.solver),
            "results": copy.deepcopy(self.results),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineConfig":
        return cls(
            name=d.get("name", "pipeline"),
            cad=dict(d.get("cad", {}) or {}),
            mesh=dict(d.get("mesh", {}) or {}),
            solver=dict(d.get("solver", {}) or {}),
            results=dict(d.get("results", {}) or {}),
        )

    def save_to_file(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, path: str) -> "PipelineConfig":
        if not os.path.exists(path):
            raise FileNotFoundError(f"Pipeline config not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return cls.from_dict(d)

    @staticmethod
    def file_version(path: str) -> int:
        """Peek at a file's declared pipeline_version without fully building it."""
        with open(path, "r", encoding="utf-8") as f:
            return int(json.load(f).get("pipeline_version", 0))

    # ------------------------------------------------------------------ #
    # Stage helpers
    # ------------------------------------------------------------------ #
    def cad_skip(self) -> bool:
        """Resampling is skipped when explicitly requested, when there is no
        per-edge segment configuration to drive it, or when no source geometry
        file is given (segments reference a source by index, so with no source
        there is nothing to resample — the mesh stage uses its geom_files)."""
        if self.cad.get("skip"):
            return True
        if not self.cad.get("segments"):
            return True
        return not bool(self.cad.get("input_file"))

    def solver_skip(self) -> bool:
        return bool(self.solver.get("skip"))

    def resolve_input_file(self, repo_root: str) -> str:
        """Absolute path to the CAD geometry, resolved against several roots so a
        pipeline file authored with a repo-relative path still works from any cwd."""
        inp = self.cad.get("input_file", "")
        if not inp:
            return ""
        if os.path.isabs(inp) and os.path.exists(inp):
            return inp
        for base in (os.getcwd(), repo_root, os.path.join(repo_root, "examples")):
            cand = os.path.abspath(os.path.join(base, inp))
            if os.path.exists(cand):
                return cand
        return os.path.abspath(inp)

    def default_cad_output(self, repo_root: str) -> str:
        """Where the resampled geometry lands when output_file is not given."""
        out = self.cad.get("output_file", "")
        if out:
            return out if os.path.isabs(out) else os.path.abspath(
                os.path.join(repo_root, out))
        inp = self.resolve_input_file(repo_root)
        stem = os.path.splitext(os.path.basename(inp or self.name))[0]
        return os.path.join(repo_root, "results", "resampled", f"{stem}_resampled.dat")

    # ------------------------------------------------------------------ #
    # Converters to the per-stage config models
    # ------------------------------------------------------------------ #
    def build_project_model(self, repo_root: str, output_file: str) -> ProjectModel:
        """CAD section -> ProjectModel ready for ProjectModel.export_config()."""
        pm = ProjectModel()
        cfg = {
            "input_file": self.resolve_input_file(repo_root),
            "output_file": output_file,
            "is_closed": self.cad.get("is_closed", True),
            "global_spline": self.cad.get("global_spline", False),
            "transform": self.cad.get("transform"),
            "segments": self.cad.get("segments", []),
        }
        pm.load_from_config(cfg)
        return pm

    def build_mesh_config(self, geom_file: str | None) -> MeshConfig:
        """Mesh section -> MeshConfig. When geom_file is given it becomes the sole
        boundary geometry unless the section already declares its own geom_files."""
        mc = MeshConfig()
        mesh = dict(self.mesh)
        # geom_files/geom_roles are handled by load_from_dict; take an explicit
        # list if provided, else wire the CAD output as the single boundary.
        mc.load_from_dict(mesh)
        if not mc.geom_files and geom_file:
            mc.geom_files = [os.path.abspath(geom_file)]
        return mc

    def build_solver_config(self, repo_root: str) -> SolverConfig:
        """Solver section -> SolverConfig with prebuilt-binary defaults filled and
        an optional workload preset applied first."""
        sc = SolverConfig()
        sc.ensure_default_binaries()
        preset = self.solver.get("preset")
        if preset:
            sc.apply_preset(preset)
        payload = {k: v for k, v in self.solver.items()
                   if k not in ("preset", "skip")}
        sc.load_from_dict(payload)
        if not sc.case_name or sc.case_name == "case":
            sc.case_name = self.name or "case"
        return sc

    # ------------------------------------------------------------------ #
    # Build a PipelineConfig from live per-stage configs (GUI "Save Pipeline").
    # ------------------------------------------------------------------ #
    @classmethod
    def from_configs(cls, name: str, project_model: ProjectModel | None,
                     mesh_config: MeshConfig | None,
                     solver_config: SolverConfig | None,
                     results: dict | None = None) -> "PipelineConfig":
        pc = cls(name=name or "pipeline")
        if project_model is not None:
            pc.cad = {
                "input_file": project_model.input_file,
                "output_file": project_model.output_file,
                "is_closed": project_model.is_closed,
                "global_spline": project_model.global_spline,
                "transform": copy.deepcopy(project_model.transform),
                "segments": [s.to_dict() for s in project_model.segments],
            }
        if mesh_config is not None:
            pc.mesh = mesh_config.to_dict()
        if solver_config is not None:
            solver = solver_config.to_dict()
            for k in _SOLVER_DERIVED_KEYS:
                solver.pop(k, None)
            pc.solver = solver
        pc.results = dict(results or {})
        return pc
