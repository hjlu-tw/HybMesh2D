"""Configuration model for the STL3d immersed-solid preprocessor.

STL3d (``solver/preprocess/STL3d``) is an interactive console tool: it reads
seven answers from stdin and ray-traces an STL surface against a Cartesian grid,
writing a Tecplot ``phi`` field (0 = fluid, 1 = solid) used by the unicones
immersed-boundary solver. This model captures those answers, serialises them to
the exact ``para.in`` line order the binary expects, and provides STL helpers
(bounding box, ASCII/binary detection) so the GUI can pre-fill the domain.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import os

import numpy as np

from app.services.stl_loader import load_stl_triangles, _is_binary_stl


def detect_stl_ascii(path: str) -> bool:
    """Return True if the STL at ``path`` is ASCII (not binary)."""
    try:
        with open(path, "rb") as f:
            head = f.read(84)
    except OSError:
        return True
    return not _is_binary_stl(head if len(head) >= 84 else head + b"\0" * 84)


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
    def para_in_text(self) -> str:
        """Serialise to the exact 6-line stdin order STL3d's main() reads."""
        stl_base = os.path.basename(self.stl_path) or "input.stl"
        lines = [
            stl_base,
            "y" if self.ascii else "n",
            self.case_name or "phi",
            " ".join(_fmt(v) for v in self.domain),
            f"{int(self.nx)} {int(self.ny)} {int(self.nz)}",
            "y" if self.all_search else "n",
        ]
        return "\n".join(lines) + "\n"

    def output_basenames(self) -> tuple[str, str]:
        """(stl_tec, phi_tec) output filenames STL3d writes for this case."""
        case = self.case_name or "phi"
        return f"{case}_stl_tec.dat", f"{case}_phi_tec.dat"

    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        return asdict(self)

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
