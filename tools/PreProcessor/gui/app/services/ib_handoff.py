"""Hand the immersed-solid stage's phi field to the solver stage.

STL3d writes a **Tecplot** phi field (3 header lines, then ``x y z phi`` rows).
The solver never reads that file: its initial-condition DLL reads a
**headerless** ``phi.dat`` out of the work dir, with the STL3d grid spec
(origin, spacing, cell counts) baked into the DLL source so it can map the field
onto its own cells. So *producing* a phi field is not the same as *wiring one
up*, and the gap between the two is where a whole IB run used to disappear:

* the headless pipeline ran STL3d, collected ``out["phi"]`` and passed it
  nowhere — ``_run_solver`` built its SolverConfig from the script alone, so a
  script declaring ``immersed_solid`` without naming a phi file ran on whatever
  ``work/phi.dat`` a PREVIOUS run had left in the reused case directory (see
  :func:`solver_case.report_stale_ibm_artifacts`): the previous geometry's
  solid, converging to a believable answer for the wrong shape;
* the GUI's Run All had no IB stage at all, so it did the same.

The conversion and the wiring lived in ``stl3d_ctrl.send_stl3d_to_solver``, a Qt
controller method no headless runner can call. They live here instead, so both
hosts hand off identically and neither can drift from the other.
"""
from __future__ import annotations
import os

from app.models.solver_config import SolverConfig
from app.models.stl3d_config import Stl3dConfig
from app.services.dll_templates import render_phi_field_init
from app.services.solver_case import sanitize_case_name

# How many lines of Tecplot header sit in front of the x y z phi rows.
# ``stl3d_config.parse_phi_tecplot`` reads the same file with
# ``np.loadtxt(skiprows=3)``; the DLL reads it with no header at all, so the two
# have to agree on this number.
PHI_HEADER_LINES = 3


class IbHandoffError(RuntimeError):
    """The phi field could not be wired into the solver config."""


def _noop(*_a, **_k):
    pass


def _case(cfg: Stl3dConfig) -> str:
    return sanitize_case_name(cfg.case_name, default="phi")


def _phi_dat_path(phi_tec: str, cfg: Stl3dConfig) -> str:
    """The headerless phi the DLL reads, beside the Tecplot field it came from."""
    return os.path.join(os.path.dirname(phi_tec), f"{_case(cfg)}_phi.dat")


def _init_dll_path(repo: str, cfg: Stl3dConfig) -> str:
    """The generated init-condition DLL source (compiled by ``solver_case``)."""
    return os.path.join(repo, "results", "solver", "dll_src",
                        f"ibm_init_{_case(cfg)}.cc")


def _strip_phi_header(phi_tec: str, phi_dat: str) -> int:
    """Write the Tecplot field out headerless. Returns the row count written."""
    rows = 0
    with open(phi_tec) as fin, open(phi_dat, "w") as fout:
        for n, line in enumerate(fin):
            if n >= PHI_HEADER_LINES:
                fout.write(line)
                rows += 1
    return rows


def _write_init_dll(cfg: Stl3dConfig, repo: str) -> str:
    """Render the init DLL for THIS field's grid and return the source path."""
    dll_cc = _init_dll_path(repo, cfg)
    dx, dy, dz = cfg.spacings()
    src = render_phi_field_init(
        xmin=cfg.xmin, ymin=cfg.ymin, zmin=cfg.zmin,
        dx=dx, dy=dy, dz=dz, nx=cfg.nx, ny=cfg.ny, nz=cfg.nz)
    try:
        os.makedirs(os.path.dirname(dll_cc), exist_ok=True)
        with open(dll_cc, "w") as f:
            f.write(src)
    except OSError as e:
        raise IbHandoffError(f"failed to write init DLL source: {e}") from e
    return dll_cc


def link_phi_to_solver(sc: SolverConfig, phi_tec: str, cfg: Stl3dConfig,
                       repo: str, log=_noop, replace: bool = True) -> dict:
    """Wire an STL3d phi result into ``sc``. Returns the paths it produced.

    Writes the headerless ``<case>_phi.dat`` and, when it supplies them, the
    grid-matched init DLL source, then points the solver config at both.

    **The phi field and the init DLL are ONE fact**, so this takes over BOTH or
    NEITHER. The DLL carries this stage's origin, spacing and cell counts, so it
    can only read the field this stage traced; pairing a caller's phi with our
    DLL — or ours with the caller's — hands the solve a field read on the wrong
    grid, which is a wrong answer rather than an error.

    What this does NOT decide is **whether the solve has an immersed solid at
    all**. ``immersed_solid`` stays the caller's to declare, for the same reason
    the motion preset (``stationary_solid`` / ``rigid_moving_body`` /
    ``motion_dll``) is left alone: a script that says ``immersed_solid: false``
    has exactly as much standing as one that configured a moving body, and a
    stage may not overrule it. ``send_stl3d_to_solver`` turns it on itself,
    because a button labelled "Send to Solver" is allowed an opinion a pipeline
    stage is not.

    ``replace`` is the difference between the two callers, and it is not a
    style choice. The GUI hands off a field the user just computed *now*, so it
    must overwrite the paths of an earlier run; the headless runner is
    auto-linking a scripted case, so an explicitly-named path wins and only
    blanks are filled — the same rule ``_run_solver`` already applies to the
    ``.vrt`` / ``.cel`` / ``.bnd`` inputs. Either way what it settled on is
    logged, so the file the solve reads is never a guess.
    """
    if not phi_tec or not os.path.exists(phi_tec):
        raise IbHandoffError(
            f"no phi field to hand to the solver: {phi_tec or '(none)'}")

    phi_dat = _phi_dat_path(phi_tec, cfg)

    try:
        rows = _strip_phi_header(phi_tec, phi_dat)
    except OSError as e:
        raise IbHandoffError(f"failed to write phi data: {e}") from e
    if not rows:
        raise IbHandoffError(
            f"phi field {os.path.basename(phi_tec)} has no data rows "
            f"(only {PHI_HEADER_LINES} header lines were expected)")

    if replace or not (sc.ibm_phi_file or sc.init_cond_dll):
        dll_cc = _write_init_dll(cfg, repo)
        sc.ibm_phi_file = phi_dat
        sc.init_cond_dll = dll_cc
        log(f"[IB] solver reads phi from {os.path.basename(phi_dat)} "
            f"({rows:,} cells), init DLL {os.path.basename(dll_cc)}")
        return {"phi_dat": phi_dat, "init_dll": dll_cc, "rows": rows}

    # Explicit wins — but the field this stage just traced must not vanish from
    # the transcript. A script that names one phi and a stage that computes
    # another is exactly what the log has to be able to tell apart.
    named = [n for n in (f"phi field {sc.ibm_phi_file}" if sc.ibm_phi_file else "",
                         f"init DLL {sc.init_cond_dll}" if sc.init_cond_dll else "")
             if n]
    log("[IB] keeping the immersed-solid inputs this run was given: "
        + ", ".join(named))
    log(f"[IB] the field this stage traced is at {phi_dat} ({rows:,} cells) "
        "and is NOT what the solve reads.")
    if not (sc.ibm_phi_file and sc.init_cond_dll):
        missing = "init DLL" if sc.ibm_phi_file else "phi field"
        log(f"[WARNING] the immersed solid has no {missing}. The DLL is what "
            "reads phi.dat and this stage's DLL is baked for its own grid, so "
            f"neither input was substituted. Name a matching {missing}, or "
            "clear the other one so the IB stage supplies both.")
    return {"phi_dat": phi_dat, "init_dll": "", "rows": rows}
