from __future__ import annotations
import re
from dataclasses import dataclass, field

import numpy as np

from app.models.tecplot_index import ZoneInfo, index_for

# ----------------------------------------------------------------------------
# Tecplot FEBLOCK parser for unicones solver output (xtecp_sol_allz.dat.*).
#
# Format (verified against solver output):
#   Title = "..."
#   variables = "x", "y", "`r", "u", "v", "T", "p", "M", "vort", "phi"
#   zone t = "time 0" N=50426 E=99994 ZONETYPE=FETRIANGLE
#         DATAPACKING = BLOCK VARLOCATION = ( [1-2] = NODAL, [3-10] = CELLCENTERED )
#   <block data: all values of var1, then var2, ...; NODAL vars have N values,
#    CELLCENTERED vars have E values>
#   <connectivity: E rows of node indices (3 for FETRIANGLE, 4 for
#    FEQUADRILATERAL), one-based>
#
# FEQUADRILATERAL zones are split into two triangles per quad at load time (the
# rest of the app — matplotlib Triangulation, tripcolor, tricontourf, integral
# areas — is triangle-based), duplicating each cell value onto both triangles.
#
# Transient runs append multiple zones. Zones are parsed lazily: list_zones()
# reads only the headers (R7); from_file() seeks straight to ONE zone's byte
# range (app/models/tecplot_index.py) and materialises just that zone's arrays,
# so animating through the zones does not re-read the whole file per frame.
# ----------------------------------------------------------------------------

# A VARLOCATION entry like "[3-10] = CELLCENTERED" or "[1] = NODAL"
_VARLOC_RE = re.compile(r"\[\s*(\d+)\s*(?:-\s*(\d+))?\s*\]\s*=\s*(\w+)", re.IGNORECASE)


def _parse_varlocation(line: str, n_vars: int) -> list[str]:
    """Return a per-variable location list ("NODAL"/"CELLCENTERED").

    Tecplot defaults unspecified variables to NODAL.
    """
    loc = ["NODAL"] * n_vars
    for m in _VARLOC_RE.finditer(line):
        lo = int(m.group(1))
        hi = int(m.group(2)) if m.group(2) else lo
        kind = m.group(3).upper()
        for i in range(lo, hi + 1):
            if 1 <= i <= n_vars:
                loc[i - 1] = kind
    return loc


@dataclass
class TecplotResult:
    """One materialised zone of a Tecplot FEBLOCK solver result."""

    variables: list[str] = field(default_factory=list)
    nodes: np.ndarray = field(default_factory=lambda: np.empty((0, 2)))   # (N, 2)
    elements: np.ndarray = field(default_factory=lambda: np.empty((0, 3), dtype=int))  # (E, 3) 0-based
    cell_data: dict = field(default_factory=dict)   # {var: (E,)}
    node_data: dict = field(default_factory=dict)   # {var: (N,)}
    zone: ZoneInfo | None = None
    zones: list = field(default_factory=list)       # all ZoneInfo in the file
    #: Bytes of the single token buffer the field arrays are VIEWS into (0 when this
    #: result was not parsed from a file). The cache accounting needs it: one slice
    #: being referenced keeps the whole buffer — connectivity region included —
    #: resident, and that region is covered by no field array.
    raw_nbytes: int = 0

    # ------------------------------------------------------------------ #
    @staticmethod
    def list_zones(path: str) -> list[ZoneInfo]:
        """Scan only the zone headers — cheap metadata, no field data (R7)."""
        return list(index_for(path).zones)

    @classmethod
    def from_file(cls, path: str, zone: int = -1, index=None) -> TecplotResult:
        """Load a single zone (default: last zone, i.e. most-converged solution).

        Only that zone's byte range is read (see ``tecplot_index``), so the cost
        is proportional to one zone rather than to the whole transient history.

        ``index`` lets a caller that already holds an index for this file read THROUGH
        it, so its zone list and the data it gets back describe the same snapshot of the
        file (see ``ResultSeries``). Omitted, the shared cache is asked as before.

        Raises ValueError if the file has no zones or the index is out of range.
        """
        idx = index if index is not None else index_for(path)
        variables = idx.variables
        n_zones = len(idx.zones)

        if not variables:
            raise ValueError(f"No 'variables =' line found in {path}")
        if not n_zones:
            raise ValueError(f"No zones found in {path}")

        if zone < 0:
            zone += n_zones
        if not (0 <= zone < n_zones):
            raise ValueError(f"Zone {zone} out of range (file has {n_zones})")

        # Zone-local lines: line 0 IS this zone's header, and the slice already
        # ends where the next zone begins.
        lines = idx.read_zone_lines(zone)
        zinfo = idx.zones[zone]
        n_nodes, n_elems = zinfo.n_nodes, zinfo.n_elems

        # The DATAPACKING/VARLOCATION line may be on the header line itself or
        # the following line(s). Find it, then numeric data starts after it.
        data_start = 1
        varloc_text = lines[0]
        for j in range(0, min(3, len(lines))):
            if "DATAPACKING" in lines[j].upper() or "VARLOCATION" in lines[j].upper():
                varloc_text = lines[j] if j == 0 else varloc_text + lines[j]
                data_start = j + 1
        loc = _parse_varlocation(varloc_text, len(variables))

        data_end = len(lines)

        counts = [n_nodes if loc[i] == "NODAL" else n_elems
                  for i in range(len(variables))]
        n_data = sum(counts)

        # Read the whole numeric region as floats (connectivity ints parse as
        # floats fine), then slice: first n_data are field values, the rest are
        # the connectivity (npe node indices per element).
        block = "".join(lines[data_start:data_end])
        tokens = np.fromstring(block, sep=" ")
        if tokens.size < n_data:
            raise ValueError(
                f"Zone {zone}: expected >= {n_data} data values, got {tokens.size}")

        # Nodes-per-element from ZONETYPE (FETRIANGLE=3, FEQUADRILATERAL=4);
        # fall back to inferring it from the trailing connectivity token count.
        zt_name = zinfo.zonetype.upper()
        if "QUAD" in zt_name:
            npe = 4
        elif "TRI" in zt_name:
            npe = 3
        else:
            avail = tokens.size - n_data
            npe = 4 if (n_elems > 0 and avail >= n_elems * 4) else 3
        expected = n_data + n_elems * npe

        data_part = tokens[:n_data]
        node_data: dict = {}
        cell_data: dict = {}
        offset = 0
        for i, var in enumerate(variables):
            seg = data_part[offset:offset + counts[i]]
            offset += counts[i]
            if loc[i] == "NODAL":
                node_data[var] = seg
            else:
                cell_data[var] = seg

        # Connectivity (one-based -> zero-based). If absent (shared connectivity
        # in a transient run), leave empty; caller may reuse a prior zone's.
        if tokens.size >= expected:
            conn = tokens[n_data:expected].astype(np.int64).reshape(n_elems, npe) - 1
        else:
            conn = np.empty((0, npe), dtype=np.int64)

        # Split quads into two triangles [n0,n1,n2] + [n0,n2,n3] and duplicate
        # each cell-centered value so it stays 1:1 with its triangle. The two
        # triangles tile the quad, so area-weighted integrals are unchanged.
        if npe == 4 and conn.size:
            conn = np.vstack([conn[:, [0, 1, 2]], conn[:, [0, 2, 3]]])
            for k in list(cell_data):
                cell_data[k] = np.tile(cell_data[k], 2)

        # Nodes come from the first two NODAL variables (x, y).
        nodal_vars = [v for i, v in enumerate(variables) if loc[i] == "NODAL"]
        if len(nodal_vars) >= 2:
            nodes = np.column_stack([node_data[nodal_vars[0]], node_data[nodal_vars[1]]])
        else:
            nodes = np.empty((n_nodes, 2))

        return cls(
            variables=variables,
            nodes=nodes,
            elements=conn,
            cell_data=cell_data,
            node_data=node_data,
            zone=zinfo,
            zones=list(idx.zones),
            raw_nbytes=int(tokens.nbytes),
        )

    # ------------------------------------------------------------------ #
    def get_variable_names(self) -> list[str]:
        """All variable names (node + cell), in file order."""
        return list(self.variables)

    # Ratio of specific heats used by the derived-field formulas (air).
    GAMMA = 1.4
    # Post-processing quantities derived from the raw solver output (#11). Only
    # those whose inputs are present are actually offered (see scalar_variables).
    DERIVED = ("|V|", "Cp", "s", "p0", "T0")

    # Human-readable labels for the variable selector (#6): the raw Tecplot codes
    # are cryptic (`r, vort, phi…), so map each to "code — description". Keyed by
    # the exact variable string; unknown codes fall back to the code itself.
    VAR_LABELS = {
        "`r": "ρ — density", "r": "ρ — density", "rho": "ρ — density",
        "u": "u — x-velocity", "v": "v — y-velocity", "w": "w — z-velocity",
        "T": "T — temperature", "p": "p — pressure", "M": "M — Mach number",
        "vort": "vorticity", "phi": "φ — solid marker (IBM)",
        "|V|": "|V| — velocity magnitude",
        "Cp": "Cp — pressure coefficient",
        "s": "s — entropy (rel. freestream)",
        "p0": "p₀ — total pressure", "T0": "T₀ — total temperature",
    }

    def variable_label(self, code: str) -> str:
        """Readable label for a variable code (#6), e.g. 'p' -> 'p — pressure'."""
        return self.VAR_LABELS.get(code, code)

    def variable_short_label(self, code: str) -> str:
        """Symbol-only label for a RAW solver field: the descriptive '— …' suffix
        is dropped since users already know their own fields, e.g. 'p' -> 'p',
        '`r' -> 'ρ'. Derived quantities keep the full label via variable_label()."""
        return self.VAR_LABELS.get(code, code).split(" — ")[0]

    def base_scalar_variables(self) -> list[str]:
        """Raw (non-derived) field variables, in file order (excludes x/y)."""
        return list(self.variables[2:])

    def derived_scalar_variables(self) -> list[str]:
        """Derived post-processing quantities available for this result (#11)."""
        base = self.base_scalar_variables()
        return [d for d in self._derived_available() if d not in base]

    def scalar_variables(self) -> list[str]:
        """Variable names that carry a field value. The first two variables are
        the x/y coordinates (Tecplot convention), so exclude them by position —
        excluding by name would also drop a distinct later field variable that
        happens to share a coordinate's name. Derived post-processing quantities
        (#11) are appended after the raw fields."""
        return self.base_scalar_variables() + self.derived_scalar_variables()

    # ------------------------------------------------------------------ #
    # Derived fields (#11): velocity magnitude, Cp, entropy, total p / T.
    # Cf and y+ are intentionally NOT here — they are wall-line quantities
    # that need wall-shear / wall-distance data the Tecplot output does not
    # carry (a solver-side addition), so faking them would mislead.
    # ------------------------------------------------------------------ #
    def _density_field(self):
        for name in ("`r", "r", "rho"):
            if name in self.cell_data or name in self.node_data:
                return self._base_cell_field(name)
        return None

    def _field_or_none(self, name: str):
        if name in self.cell_data or name in self.node_data:
            return self._base_cell_field(name)
        return None

    def _derived_available(self) -> list[str]:
        u, v = self._field_or_none("u"), self._field_or_none("v")
        rho, p = self._density_field(), self._field_or_none("p")
        T, M = self._field_or_none("T"), self._field_or_none("M")
        out: list[str] = []
        if u is not None and v is not None:
            out.append("|V|")
        if p is not None and rho is not None:
            out += ["Cp", "s"]
        if p is not None and M is not None:
            out.append("p0")
        if T is not None and M is not None:
            out.append("T0")
        return out

    def _compute_derived(self, var: str) -> np.ndarray:
        g = self.GAMMA
        u, v = self._field_or_none("u"), self._field_or_none("v")
        rho, p = self._density_field(), self._field_or_none("p")
        T, M = self._field_or_none("T"), self._field_or_none("M")
        if var == "|V|":
            return np.sqrt(u * u + v * v)
        if var == "p0":     # isentropic total (stagnation) pressure
            return p * np.power(1.0 + 0.5 * (g - 1.0) * M * M, g / (g - 1.0))
        if var == "T0":     # total (stagnation) temperature
            return T * (1.0 + 0.5 * (g - 1.0) * M * M)
        if var == "s":      # entropy, referenced to the freestream (~0 far away)
            p_inf = float(np.median(p))
            rho_inf = float(np.median(rho))
            with np.errstate(divide="ignore", invalid="ignore"):
                s = (np.log(np.maximum(p, 1e-30) / max(p_inf, 1e-30))
                     - g * np.log(np.maximum(rho, 1e-30) / max(rho_inf, 1e-30)))
            return np.nan_to_num(s)
        if var == "Cp":     # pressure coefficient with field-estimated freestream
            p_inf = float(np.median(p))
            rho_inf = float(np.median(rho))
            vmag = np.sqrt(u * u + v * v) if (u is not None and v is not None) else None
            v_inf = float(np.median(vmag)) if vmag is not None else 1.0
            q = 0.5 * max(rho_inf, 1e-30) * max(v_inf, 1e-9) ** 2
            return (p - p_inf) / max(q, 1e-30)
        raise KeyError(f"Unknown derived variable: {var}")

    def _base_cell_field(self, var: str) -> np.ndarray:
        """Cell-centered values for a RAW variable (no derived dispatch)."""
        if var in self.cell_data:
            return self.cell_data[var]
        if var in self.node_data and self.elements.size:
            return self.node_data[var][self.elements].mean(axis=1)
        raise KeyError(f"Unknown variable: {var}")

    def get_cell_field(self, var: str) -> np.ndarray:
        """Return the cell-centered values for a variable, deriving them from
        node data by averaging if necessary. Derived quantities (#11) are
        computed on demand.

        A RAW field carried by the file always wins over a same-named derived
        code: a Tecplot result may already ship its own 's'/'p0'/'T0'/'Cp', and
        the stored field must not be silently shadowed by our recompute."""
        if var in self.cell_data or (var in self.node_data and self.elements.size):
            return self._base_cell_field(var)
        if var in self.DERIVED:
            return self._compute_derived(var)
        return self._base_cell_field(var)

    # ------------------------------------------------------------------ #
    # Wall / perimeter extraction (#11): trace the mesh boundary so a field
    # quantity (e.g. Cp) can be plotted ALONG the geometry surface vs arc length.
    # ------------------------------------------------------------------ #
    def boundary_loops(self) -> list[list[int]]:
        """Ordered boundary loops of the triangulation, as lists of node indices.
        A boundary edge belongs to exactly one triangle; those edges are chained
        into closed loops (the geometry surface + the far-field outer boundary)."""
        from collections import defaultdict
        elems = self.elements
        if elems.size == 0:
            return []
        edge_count: dict = defaultdict(int)
        for tri in elems:
            for a, b in ((int(tri[0]), int(tri[1])),
                         (int(tri[1]), int(tri[2])),
                         (int(tri[2]), int(tri[0]))):
                edge_count[(a, b) if a < b else (b, a)] += 1
        adj: dict = defaultdict(list)
        for (a, b), c in edge_count.items():
            if c == 1:                       # boundary edge (single incident tri)
                adj[a].append(b)
                adj[b].append(a)
        remaining = set(adj.keys())
        used: set = set()
        loops: list[list[int]] = []
        while remaining:
            start = next(iter(remaining))
            loop = [start]
            prev, cur = None, start
            while True:
                nxt = None
                for n in adj[cur]:
                    e = (cur, n) if cur < n else (n, cur)
                    if e in used:
                        continue
                    if n != prev or len(adj[cur]) == 1:
                        nxt = n
                        break
                if nxt is None:
                    break
                used.add((cur, nxt) if cur < nxt else (nxt, cur))
                if nxt == start:
                    break
                loop.append(nxt)
                prev, cur = cur, nxt
            for n in loop:
                remaining.discard(n)
            if len(loop) >= 3:
                loops.append(loop)
        return loops

    def geometry_boundary_loops(self) -> list[list[int]]:
        """Boundary loops that are the geometry surface(s) — i.e. every loop
        except the far-field outer boundary (the one spanning the full extent)."""
        loops = self.boundary_loops()
        if len(loops) <= 1 or self.nodes.size == 0:
            return loops
        gmin, gmax = self.nodes.min(axis=0), self.nodes.max(axis=0)

        def is_outer(loop):
            pts = self.nodes[loop]
            return (np.allclose(pts.min(axis=0), gmin, atol=1e-6) and
                    np.allclose(pts.max(axis=0), gmax, atol=1e-6))

        inner = [l for l in loops if not is_outer(l)]
        return inner if inner else loops

    # Sampling a field along a surface loop lives in services/surface_source +
    # services/surface_sample: "the surface" is no longer implicitly this mesh's
    # boundary (it can be a φ iso-line, the analytic solid or the CAD outline),
    # and s = 0 is a stated rule rather than wherever the loop tracer started.
    # ``geometry_boundary_loops`` above is still the mesh-boundary source.

    def cell_to_node(self, var: str) -> np.ndarray:
        """Average a cell-centered field onto nodes (needed for tricontourf and
        for streamline interpolation via LinearTriInterpolator — R6).

        Returns the node-resident field directly if the variable is already
        nodal; derived quantities are computed in cell space then averaged.
        """
        if var in self.node_data:
            return self.node_data[var]
        cell_vals = self.get_cell_field(var)   # handles raw + derived
        n_nodes = self.nodes.shape[0]
        acc = np.zeros(n_nodes)
        cnt = np.zeros(n_nodes)
        # Each element contributes its cell value to its 3 nodes.
        for k in range(self.elements.shape[1]):
            np.add.at(acc, self.elements[:, k], cell_vals)
            np.add.at(cnt, self.elements[:, k], 1.0)
        cnt[cnt == 0] = 1.0
        return acc / cnt
