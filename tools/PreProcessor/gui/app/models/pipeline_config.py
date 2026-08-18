from __future__ import annotations
import os
import json
import copy
from dataclasses import dataclass, field

from app.models.project import ProjectModel, _legacy_closed_mode
from app.models.mesh_config import MeshConfig
from app.models.solver_config import SolverConfig
from app.services.project_file_kind import (
    WORKSPACE, classify_project_file, looks_like_workspace,
)

# Bump when the unified pipeline JSON schema changes in a backward-incompatible
# way. Readers tolerate a missing field (treated as version 0/legacy) and warn —
# but do not crash — when the file version is newer than they support.
#
#   v1 -> v2: the single ``cad`` object became a ``cads`` LIST, and an ``stl3d``
#             (immersed-solid) section was added. Before v2 a script could only
#             describe one CAD geometry, so saving a script from a multi-geometry
#             workspace silently dropped every session but the active one, and an
#             immersed-solid case could not be described at all. ``cad`` is still
#             accepted on read and still exposed as a property (the first entry),
#             so v1 scripts and existing call sites keep working.
PIPELINE_FORMAT_VERSION = 2

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

      * ``cads[i]`` -> :class:`ProjectModel`   (surface_resampler input JSON)
      * ``mesh``    -> :class:`MeshConfig`      (HybMesh2D Background_para.dat)
      * ``solver``  -> :class:`SolverConfig`    (getPGrid / unicones input files)
      * ``stl3d``   -> :class:`Stl3dConfig`     (immersed-solid STL -> phi)
      * ``results`` -> contour rendering options (headless PNG / GUI view)

    It is deliberately Qt-free so both the GUI orchestrator and the headless CLI
    runner share exactly this schema.
    """

    name: str = "pipeline"

    # CAD / resample stage — one entry per geometry, because a case routinely has
    # several (an airfoil plus a ground plane, a multi-element wing, a custom
    # domain shape). Each entry either resamples a raw geometry through
    # surface_resampler (segments define the per-edge strategy, exactly like the
    # PreProcessor GUI export), or is skipped and its input_file fed straight to
    # the mesher; resampling is skipped automatically when no segments are given.
    #   [{input_file, output_file, is_closed, global_spline, transform,
    #     segments:[...], skip:bool}, ...]
    cads: list = field(default_factory=list)

    # Mesh stage: a subset of MeshConfig fields (defaults fill the rest). The
    # geometry input is auto-wired to the CAD output unless geom_files is given.
    mesh: dict = field(default_factory=dict)

    # Solver stage: a subset of SolverConfig fields. The STAR-CD inputs are
    # auto-linked from the mesh output unless input_vrt/cel/bnd_file are given.
    # An optional "preset" name (see solver_config.PRESETS) is applied first.
    # "skip": true stops the pipeline after meshing.
    solver: dict = field(default_factory=dict)

    # Immersed-solid (IB) stage: a subset of Stl3dConfig fields (STL path, domain
    # box, resolution, case name). Carried so a script can describe an
    # immersed-solid case; the GUI applies it to the IB panel. The headless runner
    # does not execute this stage yet and says so rather than skipping quietly.
    stl3d: dict = field(default_factory=dict)

    # Results stage: contour options. {variable, cmap, save_png, mesh_overlay}
    results: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # cad <-> cads compatibility
    # ------------------------------------------------------------------ #
    @property
    def cad(self) -> dict:
        """The first CAD entry (``{}`` when there is none).

        Kept as a property so v1-era call sites — and hand-written single-geometry
        scripts — read exactly as before while the storage is a list.
        """
        return self.cads[0] if self.cads else {}

    @cad.setter
    def cad(self, value: dict):
        value = dict(value or {})
        if not self.cads:
            self.cads = [value]
        else:
            self.cads[0] = value

    # ------------------------------------------------------------------ #
    # Units
    # ------------------------------------------------------------------ #
    def unit_warnings(self) -> list:
        """Cross-stage length-unit problems in this script. Never raises.

        The unit rides inside each section's dict (``mesh.length_unit``,
        ``solver.linf``), so a script assembled by hand or by editing two halves can
        state one unit for the geometry and a contradictory ``Linf`` for the solver.
        Nothing downstream would complain: the mesh would be perfect and the Reynolds
        number silently wrong by the ratio between them. A headless run has no Solver
        panel to show the reference Re on, so this is where it gets said.
        """
        from app.services import units
        out = []
        mesh_unit = units.parse(self.mesh.get("length_unit", ""), "")
        if not mesh_unit:
            return out
        mesh_metres = units.metres_per_unit(
            mesh_unit, self.mesh.get("length_unit_metres", 1.0) or 1.0)

        for i, cad in enumerate(self.cads or []):
            cad_unit = units.parse(cad.get("length_unit", ""), "")
            if cad_unit and cad_unit != mesh_unit:
                out.append(
                    f"cads[{i}] is in {units.plural(cad_unit)} but mesh is in "
                    f"{units.plural(mesh_unit)}. The mesher does not convert "
                    f"coordinates, so the geometry would be meshed at the wrong scale.")

        linf = self.solver.get("linf")
        if linf is None:
            return out
        try:
            linf = float(linf)
        except (TypeError, ValueError):
            out.append(f"solver.linf is not a number ({linf!r}).")
            return out
        if linf <= 0:
            out.append(f"solver.linf is {linf:g}; it is metres per grid unit and "
                       f"must be positive (Re = fs_UnitRe x Linf).")
        elif abs(linf - mesh_metres) > 1e-12 * max(1.0, mesh_metres):
            implied = units.unit_for_linf(linf)
            what = (f"a grid in {units.plural(implied)}" if implied
                    else f"1 grid unit = {linf:g} m")
            out.append(
                f"solver.linf = {linf:g} means {what}, but mesh.length_unit is "
                f"{units.name(mesh_unit)} ({mesh_metres:g} m). Re = fs_UnitRe x Linf, "
                f"so the Reynolds number is off by "
                f"{max(linf, mesh_metres) / min(linf, mesh_metres):g}x.")
        return out

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        d = {
            "pipeline_version": PIPELINE_FORMAT_VERSION,
            "name": self.name,
            "cads": copy.deepcopy(self.cads),
            "mesh": copy.deepcopy(self.mesh),
            "solver": copy.deepcopy(self.solver),
            "results": copy.deepcopy(self.results),
        }
        # Only present when actually configured, so a plain CAD->mesh->solver
        # script stays as readable as it was before the section existed.
        if self.stl3d:
            d["stl3d"] = copy.deepcopy(self.stl3d)
        return d

    @staticmethod
    def _migrate(d: dict, from_version: int) -> dict:
        """Upgrade an older pipeline dict to PIPELINE_FORMAT_VERSION.

        Extension point for backward-compatible pipeline-script migration.
        Add an ``if v < N`` block here when the schema changes. A NEWER file is
        left as-is (callers warn it is read-only / best-effort)."""
        v = int(from_version)
        if v >= PIPELINE_FORMAT_VERSION:
            return d
        out = copy.deepcopy(d)
        # v0 -> v1: stamp the version; no structural change.
        if v < 1:
            v = 1
        # v1 -> v2: the single "cad" object becomes the first entry of "cads".
        # A hand-written script may legitimately carry either key, so an already
        # present "cads" wins and "cad" is folded in only when it adds something.
        if v < 2:
            cads = list(out.get("cads") or [])
            cad = out.pop("cad", None)
            if cad and not cads:
                cads = [dict(cad)]
            out["cads"] = cads
            v = 2
        out["pipeline_version"] = PIPELINE_FORMAT_VERSION
        return out

    @classmethod
    def from_dict(cls, d: dict) -> PipelineConfig:
        # Missing version = legacy v0 (explicit, not "current"); migrate older
        # dicts field-by-field before reading them.
        version = int(d.get("pipeline_version", 0))
        if version < PIPELINE_FORMAT_VERSION:
            d = cls._migrate(d, version)
        # A v2+ file normally has "cads"; still accept a bare "cad" so a
        # hand-written single-geometry script does not need the list syntax.
        cads = [dict(c or {}) for c in (d.get("cads") or [])]
        if not cads and d.get("cad"):
            cads = [dict(d["cad"])]
        return cls(
            name=d.get("name", "pipeline"),
            cads=cads,
            mesh=dict(d.get("mesh", {}) or {}),
            solver=dict(d.get("solver", {}) or {}),
            stl3d=dict(d.get("stl3d", {}) or {}),
            results=dict(d.get("results", {}) or {}),
        )

    def save_to_file(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def _looks_like_workspace(d: dict) -> bool:
        """True for a ``.hws`` workspace dict rather than a pipeline script.

        Decided by contents, not by extension, so a renamed file still loads as
        what it actually is. The shape test itself lives in
        ``services/project_file_kind``, shared with the by-path classifier so the
        two cannot drift apart.
        """
        return looks_like_workspace(d)

    @classmethod
    def classify_file(cls, path: str) -> str:
        """What ``path`` actually holds: ``"workspace"``, ``"pipeline"`` or ``""``
        — see :func:`app.services.project_file_kind.classify_project_file`."""
        return classify_project_file(path)

    @classmethod
    def is_workspace_file(cls, path: str) -> bool:
        """True if ``path`` holds a workspace (used for the CLI's notice)."""
        return classify_project_file(path) == WORKSPACE

    @classmethod
    def load_from_file(cls, path: str) -> PipelineConfig:
        """Load a pipeline script, or a ``.hws`` workspace (see
        :meth:`from_workspace_dict`), by looking at what the file actually holds."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Pipeline config not found: {path}")
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if cls._looks_like_workspace(d):
            return cls.from_workspace_dict(d)
        return cls.from_dict(d)

    @classmethod
    def from_workspace_dict(cls, data: dict, name: str = "") -> PipelineConfig:
        """Build a runnable script from a ``.hws`` workspace dict.

        The workspace (local working state, multi-tab) and the pipeline script
        (portable, runnable) describe the same case from different angles. This is
        the bridge, so a case configured interactively can be re-run headlessly
        without re-authoring it: every CAD session becomes a ``cads`` entry, and
        the workspace's ``project`` section supplies mesh / solver / IB.

        View-only workspace state (cached resampled points, selection indices,
        active tab) is intentionally dropped — it is derived, not input.
        """
        sessions = data.get("sessions") or []
        cads = []
        for s in sessions:
            pconf = dict(s.get("project_config") or {})
            # ProjectModel's own keys already ARE the cad-section keys; carry the
            # session's source file over when the config didn't record one.
            if not pconf.get("input_file"):
                pconf["input_file"] = s.get("file_path", "") or ""
            entry = {k: pconf.get(k) for k in
                     ("input_file", "output_file", "closed_mode", "is_closed",
                      "global_spline", "transform")}
            entry["segments"] = list(pconf.get("segments") or [])
            cads.append(entry)

        project = dict(data.get("project") or {})
        solver = dict(project.get("solver_config") or {})
        for k in _SOLVER_DERIVED_KEYS:
            solver.pop(k, None)
        if not name:
            first = next((s.get("display_name") or "" for s in sessions), "")
            name = os.path.splitext(first.lstrip("*"))[0] or "workspace"
        return cls(
            name=name,
            cads=cads,
            mesh=dict(project.get("mesh_config") or {}),
            solver=solver,
            stl3d=dict(project.get("stl3d_config") or {}),
            results={},
        )

    @staticmethod
    def file_version(path: str) -> int:
        """Peek at a file's declared pipeline_version without fully building it.

        A ``.hws`` workspace has no pipeline version and needs no pipeline-axis
        migration, so it reports the current version — otherwise every workspace
        run would print a bogus "migrating from v0" notice."""
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if PipelineConfig._looks_like_workspace(d):
            return PIPELINE_FORMAT_VERSION
        return int(d.get("pipeline_version", 0))

    # ------------------------------------------------------------------ #
    # Stage helpers
    # ------------------------------------------------------------------ #
    def cad_at(self, index: int = 0) -> dict:
        """The CAD entry at ``index``, or ``{}`` when out of range."""
        return self.cads[index] if 0 <= index < len(self.cads) else {}

    def cad_indices(self) -> list:
        """Indices of every CAD entry, for iterating the resample stage."""
        return list(range(len(self.cads)))

    def cad_skip(self, index: int = 0) -> bool:
        """Resampling is skipped when explicitly requested, when there is no
        per-edge segment configuration to drive it, or when no source geometry
        file is given (segments reference a source by index, so with no source
        there is nothing to resample — the mesh stage uses its geom_files)."""
        cad = self.cad_at(index)
        if cad.get("skip"):
            return True
        if not cad.get("segments"):
            return True
        return not bool(cad.get("input_file"))

    def cads_all_skipped(self) -> bool:
        """True when no CAD entry will be resampled (so the chain starts at mesh)."""
        return all(self.cad_skip(i) for i in self.cad_indices()) if self.cads else True

    def solver_skip(self) -> bool:
        return bool(self.solver.get("skip"))

    def resolve_input_file(self, repo_root: str, index: int = 0) -> str:
        """Absolute path to a CAD geometry, resolved against several roots so a
        pipeline file authored with a repo-relative path still works from any cwd."""
        inp = self.cad_at(index).get("input_file", "")
        if not inp:
            return ""
        if os.path.isabs(inp) and os.path.exists(inp):
            return inp
        for base in (os.getcwd(), repo_root, os.path.join(repo_root, "examples")):
            cand = os.path.abspath(os.path.join(base, inp))
            if os.path.exists(cand):
                return cand
        return os.path.abspath(inp)

    def default_cad_output(self, repo_root: str, index: int = 0) -> str:
        """Where a resampled geometry lands when output_file is not given.

        The stem comes from the source file, so several geometries in one script
        cannot collide on a shared default name; only a nameless entry falls back
        to the script name (suffixed by index when there is more than one)."""
        out = self.cad_at(index).get("output_file", "")
        if out:
            return out if os.path.isabs(out) else os.path.abspath(
                os.path.join(repo_root, out))
        inp = self.resolve_input_file(repo_root, index)
        if inp:
            stem = os.path.splitext(os.path.basename(inp))[0]
        else:
            stem = self.name if len(self.cads) <= 1 else f"{self.name}_{index}"
        return os.path.join(repo_root, "results", "resampled", f"{stem}_resampled.dat")

    # ------------------------------------------------------------------ #
    # Converters to the per-stage config models
    # ------------------------------------------------------------------ #
    def build_project_model(self, repo_root: str, output_file: str,
                            index: int = 0) -> ProjectModel:
        """One CAD entry -> ProjectModel ready for ProjectModel.export_config()."""
        cad = self.cad_at(index)
        pm = ProjectModel()
        cfg = {
            "input_file": self.resolve_input_file(repo_root, index),
            "output_file": output_file,
            "closed_mode": cad.get("closed_mode", _legacy_closed_mode(cad)),
            "is_closed": cad.get("is_closed", True),
            "global_spline": cad.get("global_spline", False),
            "transform": cad.get("transform"),
            "segments": cad.get("segments", []),
        }
        pm.load_from_config(cfg)
        return pm

    def build_mesh_config(self, geom_files: str | list | None) -> MeshConfig:
        """Mesh section -> MeshConfig.

        ``geom_files`` (a single path or a list — one per resampled CAD entry)
        becomes the boundary geometry unless the section already declares its own
        ``geom_files``. Order is preserved: the mesher's per-geometry roles and BL
        overrides are keyed by path, so a stable order keeps a script reproducible.
        """
        mc = MeshConfig()
        mesh = dict(self.mesh)
        # geom_files/geom_roles are handled by load_from_dict; take an explicit
        # list if provided, else wire the CAD outputs as the boundaries.
        mc.load_from_dict(mesh)
        if not mc.geom_files and geom_files:
            if isinstance(geom_files, str):
                geom_files = [geom_files]
            seen, ordered = set(), []
            for g in geom_files:
                a = os.path.abspath(g)
                if a not in seen:
                    seen.add(a)
                    ordered.append(a)
            mc.geom_files = ordered
        return mc

    def build_stl3d_config(self, repo_root: str = ""):
        """Immersed-solid section -> Stl3dConfig (defaults when the section is
        absent). Imported lazily so this module stays importable without the IB
        model on a trimmed install.

        ``repo_root`` resolves a RELATIVE ``stl_path`` the same way
        :meth:`resolve_input_file` resolves a relative CAD input. Without it a
        script could only name its STL absolutely: every other section in this
        schema takes a repo-relative path, but the IB stage validated
        ``stl_path`` against the process cwd, so a portable script failed with
        "STL file not found" naming the path it had been given. Callers that have
        no repo (a round-trip test, a config already holding absolute paths) may
        omit it and nothing is rewritten.
        """
        from app.models.stl3d_config import Stl3dConfig
        if not self.stl3d:
            return Stl3dConfig()
        cfg = Stl3dConfig.from_dict(dict(self.stl3d))
        if repo_root and cfg.stl_path and not os.path.isabs(cfg.stl_path):
            cfg.stl_path = os.path.join(repo_root, cfg.stl_path)
        return cfg

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
    @staticmethod
    def cad_section(project_model: ProjectModel) -> dict:
        """One ProjectModel -> a ``cads`` entry."""
        return {
            "input_file": project_model.input_file,
            "output_file": project_model.output_file,
            "closed_mode": project_model.closed_mode,
            "is_closed": project_model.is_closed,
            "global_spline": project_model.global_spline,
            "transform": copy.deepcopy(project_model.transform),
            "segments": [s.to_dict() for s in project_model.segments],
        }

    @classmethod
    def from_configs(cls, name: str, project_model: ProjectModel | list | None,
                     mesh_config: MeshConfig | None,
                     solver_config: SolverConfig | None,
                     results: dict | None = None,
                     stl3d_config=None) -> PipelineConfig:
        """Build a script from live per-stage configs (GUI "Save Pipeline").

        ``project_model`` accepts a LIST of models — one per open CAD session — so
        a multi-geometry workspace round-trips. Passing a single model still works
        and yields a one-entry ``cads``.
        """
        pc = cls(name=name or "pipeline")
        if project_model is not None:
            models = (list(project_model)
                      if isinstance(project_model, (list, tuple))
                      else [project_model])
            pc.cads = [cls.cad_section(pm) for pm in models if pm is not None]
        if mesh_config is not None:
            pc.mesh = mesh_config.to_dict()
        if solver_config is not None:
            solver = solver_config.to_dict()
            for k in _SOLVER_DERIVED_KEYS:
                solver.pop(k, None)
            pc.solver = solver
        if stl3d_config is not None and getattr(stl3d_config, "stl_path", ""):
            # Only emit the section when an STL is actually configured, so a plain
            # CAD->mesh->solver script is not padded with an inert IB block.
            pc.stl3d = stl3d_config.to_dict()
        pc.results = dict(results or {})
        return pc
