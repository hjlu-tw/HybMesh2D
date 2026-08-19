"""The immersed-solid (STL3d) panel's field TABLE — all 15 ``Stl3dConfig`` fields.

The smallest of the three, and the one with the two genuinely irregular fields, so it
is where the ``read``/``write``-on-the-spec escape hatch earns its place:

* **``ascii``** is edited by a THREE-item combo (Auto-detect / ASCII / Binary) behind a
  bool. Auto-detect resolves to ASCII here and is set concretely by the controller once
  an STL is loaded, so the mapping is not symmetric and cannot be a choice list.
* **``all_search``** is a two-item combo whose values ARE the bool, so it is an ordinary
  ``choice`` — listed here only to say why the first one is not.

``group`` names the ``_build_*`` section. Three groups build their widgets without form
rows because the layout puts several on one line: the domain bounds go two per row
(min, max) and Nx/Ny/Nz share a row under a single stacked label — side by side with a
label, three ~83px spin boxes overflow the fixed 360px sidebar and the right one is
clipped away.
"""
from __future__ import annotations

from app.services.field_spec import FieldSpec

_BOUND = dict(lo=-1e9, hi=1e9, dec=6, width=90)

STL3D_SPECS: tuple[FieldSpec, ...] = (
    # ── STL Input ────────────────────────────────────────────────────────────
    # Read-only: the path is set by the Browse button / the CAD stager, never typed.
    FieldSpec("stl_path", "text", "STL File",
              "STL surface file to mark against the Cartesian grid",
              group="input", opts=dict(readonly=True)),
    FieldSpec("ascii_combo", "choice", "Encoding",
              "STL encoding. Auto-detect reads the file header.",
              model="ascii", group="input",
              opts=dict(choices=[(True, "Auto-detect"), (True, "ASCII"),
                                 (False, "Binary")]),
              # Three items, one bool: Auto-detect and ASCII both mean ascii=True, so
              # the mapping is not one-to-one and the pair is declared here rather
              # than being smoothed into a choice list that cannot express it.
              read=lambda w: w.currentText() != "Binary",
              write=lambda w, v: w.setCurrentText("ASCII" if v else "Binary")),
    FieldSpec("case_name", "text", "Case Name",
              "Output case name -> <case>_phi_tec.dat / <case>_stl_tec.dat",
              group="input", opts=dict(fallback="phi")),

    # ── Cartesian Domain ─────────────────────────────────────────────────────
    # model=None: the Auto-Domain padding, an argument to a button rather than a
    # field of the config.
    FieldSpec("margin_spin", "narrow", "margin %",
              "Padding around the STL bounding box, in % of extent",
              model=None, group="margin", opts=dict(lo=0.0, hi=100.0, dec=1)),
    FieldSpec("xmin", "narrow", "X min", "Domain x min", group="bounds", opts=dict(_BOUND)),
    FieldSpec("xmax", "narrow", "X max", "Domain x max", group="bounds", opts=dict(_BOUND)),
    FieldSpec("ymin", "narrow", "Y min", "Domain y min", group="bounds", opts=dict(_BOUND)),
    FieldSpec("ymax", "narrow", "Y max", "Domain y max", group="bounds", opts=dict(_BOUND)),
    FieldSpec("zmin", "narrow", "Z min", "Domain z min", group="bounds", opts=dict(_BOUND)),
    FieldSpec("zmax", "narrow", "Z max", "Domain z max", group="bounds", opts=dict(_BOUND)),

    # ── Grid Resolution ──────────────────────────────────────────────────────
    FieldSpec("nx", "int", "Nx", "Number of grid points in x",
              group="res", opts=dict(lo=2, hi=4096)),
    FieldSpec("ny", "int", "Ny", "Number of grid points in y",
              group="res", opts=dict(lo=2, hi=4096)),
    # nz may be 1: a quasi-2D case uses 2, and a degenerate z extent is legal.
    FieldSpec("nz", "int", "Nz",
              "Number of grid points in z (use 2 for a quasi-2D / planar case)",
              group="res", opts=dict(lo=1, hi=4096)),
    FieldSpec("derived_lbl", "label", "", "", model=None, group="res_readout",
              opts=dict(style="color:#8892b0; font-size:11px;")),
    FieldSpec("warn_lbl", "label", "", "", model=None, group="res_readout",
              opts=dict(style="color:#eab308; font-size:11px;", hidden=True)),

    # ── Search Method ────────────────────────────────────────────────────────
    FieldSpec("search_combo", "choice", "Method",
              "Ray-tracing element search. All-elements never misses a triangle but "
              "scales with surface size; close x-range is faster on uniform meshes.",
              model="all_search", group="search",
              opts=dict(choices=[(True, "All elements (robust, slower)"),
                                 (False, "Close x-range (faster, may miss large "
                                         "elements)")])),

    # ── Parallel (OpenMP) ────────────────────────────────────────────────────
    FieldSpec("omp_cb", "bool", "Enable OpenMP",
              "Off = single-threaded (default). On = parallel ray tracing across the "
              "chosen number of threads. Biggest gains on heavy STLs / all-element "
              "search.",
              model="omp_enabled", group="omp_enable",
              opts=dict(text="Enable OpenMP")),
    # Seeded from the model, whose own default is max(1, os.cpu_count() or 1) — the
    # panel used to repeat that expression.
    FieldSpec("threads_spin", "int", "Threads",
              "OMP_NUM_THREADS used when OpenMP is enabled",
              model="omp_threads", group="omp", opts=dict(lo=1, hi=256, width=70)),
)

#: The IB panel authors every field of its model through the table, so there is no
#: residue. That is also the only reason ``stl3d_ctrl`` may assign the model wholesale
#: (see check 10 of tests/test_panel_model_sync.py, which self-destructs if this grows).
STL3D_EXTRA_AUTHORED = frozenset()
