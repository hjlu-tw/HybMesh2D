"""Read the solver's recorded probe time-history so the GUI can plot it (#4).

The Unicones solver, when ``probe_points_def_fn`` is set, writes two files into
the case work dir:

* ``probe_data_dist`` (small text index):

      probe_data.gui            # line 1: the binary data filename
      <probeIdx> <distance>     # one line per probe: index + distance from the
      ...                       #   requested point to the sampled cell centre

* ``probe_data.gui`` (raw little-endian float64, row-major): one row per probe
  per output step, ``NCOLS`` columns per row. The columns are the solver's
  Tecplot solution variables, in the same order the macro prints them
  (``x, y, ``r, u, v, T, p, M, vort, phi`` for the 2D eqn6 build) — verified
  against the freestream initial record (rho=1, u=v=0, T=1, M=0.2,
  p = 1/(gamma*M^2) = 17.857).

There is no source for the solver (it ships as a compiled macro), so this
reader is empirical: it trusts the ``NCOLS`` column layout above and the probe
count from ``probe_data_dist``, and bails gracefully if the byte count is not a
whole number of records.
"""
from __future__ import annotations
import os
import numpy as np

# 2D eqn6 Tecplot variable order (see unicones.eqn6.mac:
# variables = "x","y","`r","u","v","T","p","M","vort","phi").
PROBE_VARS = ["x", "y", "rho", "u", "v", "T", "p", "M", "vort", "phi"]
NCOLS = len(PROBE_VARS)

# Display labels (match TecplotResult.VAR_LABELS symbols where sensible).
PROBE_VAR_LABELS = {"rho": "ρ", "T": "T", "p": "p", "M": "M",
                    "vort": "vort", "phi": "φ", "u": "u", "v": "v",
                    "x": "x", "y": "y"}


class ProbeHistory:
    """Parsed probe time-history. ``series`` is a list, one entry per probe, of
    ``dict(idx, dist, x, y, data)`` where ``data`` is an ``(nsteps, NCOLS)``
    float array in ``PROBE_VARS`` column order."""

    def __init__(self, series: list[dict], skip_niter: int = 1):
        self.series = series
        self.skip_niter = max(1, int(skip_niter or 1))

    def __bool__(self) -> bool:
        return bool(self.series)

    def steps(self, i: int) -> np.ndarray:
        """Solver iteration number for each output row of probe ``i`` (row index
        times the probe output skip)."""
        n = len(self.series[i]["data"])
        return np.arange(n, dtype=float) * self.skip_niter

    def column(self, i: int, var: str) -> np.ndarray:
        j = PROBE_VARS.index(var)
        return self.series[i]["data"][:, j]


def dist_index_path(work_dir: str) -> str:
    return os.path.join(work_dir, "probe_data_dist")


def read_probe_history(work_dir: str, skip_niter: int = 1) -> ProbeHistory | None:
    """Read the probe history from ``work_dir`` (the case's ``work`` dir). Returns
    ``None`` when the index/data files are missing or unparseable."""
    idx_path = dist_index_path(work_dir)
    if not os.path.isfile(idx_path):
        return None
    try:
        with open(idx_path, encoding="utf-8", errors="replace") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
    except OSError:
        return None
    if not lines:
        return None
    data_name = lines[0]
    probes: list[tuple[int, float]] = []
    for ln in lines[1:]:
        parts = ln.split()
        if not parts:
            continue
        try:
            pidx = int(parts[0])
            dist = float(parts[1]) if len(parts) > 1 else float("nan")
        except ValueError:
            continue
        probes.append((pidx, dist))
    nprobes = len(probes)
    if nprobes == 0:
        return None

    data_path = os.path.join(work_dir, os.path.basename(data_name))
    if not os.path.isfile(data_path):
        return None
    try:
        raw = np.fromfile(data_path, dtype="<f8")
    except OSError:
        return None
    if raw.size == 0 or raw.size % (NCOLS * nprobes) != 0:
        return None
    nsteps = raw.size // (NCOLS * nprobes)
    # Layout: one record per output step, each record holding the NPROBES probes
    # consecutively (probe i at offset i*NCOLS). So probe i's series is every
    # nprobes-th record.
    block = raw.reshape(nsteps, nprobes, NCOLS)
    series: list[dict] = []
    for k, (pidx, dist) in enumerate(probes):
        data = np.ascontiguousarray(block[:, k, :])
        # x/y are constant per probe (the sampled cell); expose the first row's.
        x = float(data[0, 0]) if nsteps else float("nan")
        y = float(data[0, 1]) if nsteps else float("nan")
        series.append({"idx": pidx, "dist": dist, "x": x, "y": y, "data": data})
    return ProbeHistory(series, skip_niter=skip_niter)
