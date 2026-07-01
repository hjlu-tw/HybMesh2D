"""Configuration model for the STL3d immersed-solid preprocessor.

STL3d (``solver/preprocess/STL3d``) is an interactive console tool: it reads
seven answers from stdin and ray-traces an STL surface against a Cartesian grid,
writing a Tecplot ``phi`` field (0 = fluid, 1 = solid) used by the unicones
immersed-boundary solver. This model captures those answers, serialises them to
the exact ``para.in`` line order the binary expects, and provides STL helpers
(bounding box, ASCII/binary detection) so the GUI can pre-fill the domain.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import os
import re
import struct

import numpy as np

from app.services.stl_loader import load_stl_triangles


def _sanitize_token(s: str) -> str:
    """A whitespace-free token safe to feed STL3d's para.in.

    STL3d reads the STL filename and the case name with ``cin >> token``, which
    splits on whitespace. A space anywhere in either name shifts every later
    answer by one token: Nx/Ny/Nz then read garbage and the binary attempts a
    huge/negative allocation that crashes or hangs. Collapsing unsafe runs to
    '_' keeps each name a single token (dots/dashes are kept for ``*.stl``).
    """
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", (s or "").strip())
    return s or "x"


def detect_stl_ascii(path: str) -> bool:
    """Return True if the STL at ``path`` is ASCII (not binary).

    A binary STL is exactly ``84 + n*50`` bytes (n = triangle count at bytes
    80:84), an identity ASCII files don't satisfy. The check needs the real FILE
    SIZE — the previous version passed only the 84-byte header to the size test,
    so the identity failed for every binary file and binaries were misreported as
    ASCII. STL3d then read them with its ASCII parser, whose ``while(true)`` never
    finds ``endsolid`` on binary bytes and hangs.
    """
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            head = f.read(84)
    except OSError:
        return True
    if len(head) < 84:
        return True               # too small to be a binary STL with triangles
    n = struct.unpack("<I", head[80:84])[0]
    return size != 84 + n * 50


def stl_bounding_box(path: str) -> tuple[float, float, float, float, float, float]:
    """Return (xmin, xmax, ymin, ymax, zmin, zmax) of the STL surface."""
    tris = load_stl_triangles(path)            # (N, 3, 3)
    pts = tris.reshape(-1, 3)
    mn = pts.min(axis=0)
    mx = pts.max(axis=0)
    return (float(mn[0]), float(mx[0]),
            float(mn[1]), float(mx[1]),
            float(mn[2]), float(mx[2]))


def _fmt(v: float) -> str:
    """Format a float for para.in (cin >> double accepts this verbatim)."""
    return f"{v:.10g}"


@dataclass
class Stl3dConfig:
    """All the answers STL3d reads from stdin, plus view/derived helpers."""

    stl_path: str = ""
    ascii: bool = True                 # answer to "in ascii format (y/n)?"
    case_name: str = "phi"             # output case name -> <case>_phi_tec.dat
    xmin: float = 0.0
    xmax: float = 1.0
    ymin: float = 0.0
    ymax: float = 1.0
    zmin: float = 0.0
    zmax: float = 0.0
    nx: int = 128
    ny: int = 128
    nz: int = 2
    all_search: bool = True            # all-element (robust) vs close x-range (fast)
    # OpenMP is a runtime-only, machine-specific concern (neither field goes into
    # para.in). The enable flag and the thread count are kept SEPARATE so that
    # "enabled with 1 thread" stays distinguishable from "disabled" on a config
    # round-trip (a single conflated int loses that distinction).
    omp_enabled: bool = False          # run STL3d under OpenMP (else serial)
    omp_threads: int = field(default_factory=lambda: max(1, os.cpu_count() or 1))

    # ------------------------------------------------------------------ #
    @property
    def domain(self) -> tuple[float, float, float, float, float, float]:
        return (self.xmin, self.xmax, self.ymin, self.ymax, self.zmin, self.zmax)

    @property
    def cell_count(self) -> int:
        return max(self.nx, 0) * max(self.ny, 0) * max(self.nz, 0)

    def spacings(self) -> tuple[float, float, float]:
        """Grid spacings dx, dy, dz (0 for a degenerate / single-cell axis)."""
        def d(lo: float, hi: float, n: int) -> float:
            return (hi - lo) / (n - 1) if n > 1 else 0.0
        return (d(self.xmin, self.xmax, self.nx),
                d(self.ymin, self.ymax, self.ny),
                d(self.zmin, self.zmax, self.nz))

    def fit_to_bbox(self, bbox: tuple[float, float, float, float, float, float],
                    margin: float = 0.10) -> None:
        """Set the domain to the STL bounding box expanded by ``margin`` fraction.

        A degenerate axis (e.g. a planar z=0 STL) is left with zero thickness so
        the quasi-2D case (Nz=2, dz=0) the solver expects is preserved.
        """
        x0, x1, y0, y1, z0, z1 = bbox
        def expand(lo: float, hi: float) -> tuple[float, float]:
            span = hi - lo
            if span <= 0.0:
                return lo, hi          # keep degenerate axes flat
            pad = span * margin
            return lo - pad, hi + pad
        self.xmin, self.xmax = expand(x0, x1)
        self.ymin, self.ymax = expand(y0, y1)
        self.zmin, self.zmax = expand(z0, z1)

    # ------------------------------------------------------------------ #
    def stl_run_basename(self) -> str:
        """Whitespace-safe basename for the STL staged into the run dir + para.in.

        Must match the name written on para.in line 1 (see ``para_in_text``) so the
        binary can open the file it is told to read."""
        return _sanitize_token(os.path.basename(self.stl_path) or "input.stl")

    def para_in_text(self) -> str:
        """Serialise to the exact 6-line stdin order STL3d's main() reads.

        The STL filename and case name are sanitised to single tokens: STL3d
        reads them with ``cin >>`` and a space would misalign every later answer.
        """
        lines = [
            self.stl_run_basename(),
            "y" if self.ascii else "n",
            _sanitize_token(self.case_name or "phi"),
            " ".join(_fmt(v) for v in self.domain),
            f"{int(self.nx)} {int(self.ny)} {int(self.nz)}",
            "y" if self.all_search else "n",
        ]
        return "\n".join(lines) + "\n"

    def output_basenames(self) -> tuple[str, str]:
        """(stl_tec, phi_tec) output filenames STL3d writes for this case.

        Uses the sanitised case name so it matches what the binary (reading the
        case name via ``cin >>``) actually writes."""
        case = _sanitize_token(self.case_name or "phi")
        return f"{case}_stl_tec.dat", f"{case}_phi_tec.dat"

    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        # The OpenMP fields are runtime-only, machine-specific concerns (they never
        # go into para.in); drop them from the serialized form so a saved/exported
        # config can't mislead a reader or CLI into treating a thread count as part
        # of the immersed-solid definition. from_dict tolerates their absence.
        d = asdict(self)
        d.pop("omp_enabled", None)
        d.pop("omp_threads", None)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Stl3dConfig":
        fields = {f for f in cls.__dataclass_fields__}        # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in fields})


def parse_phi_tecplot(path: str) -> tuple[np.ndarray, np.ndarray]:
    """Parse a STL3d ``*_phi_tec.dat`` file.

    Returns (points (N,3) xyz, phi (N,)). The file is a POINT-format Tecplot
    zone: 3 header lines (title / variables / zone) then ``x y z phi`` rows.
    """
    data = np.loadtxt(path, skiprows=3)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    return data[:, :3].astype(np.float64), data[:, 3].astype(np.float64)
