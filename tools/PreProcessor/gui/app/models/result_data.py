from __future__ import annotations
import re
from dataclasses import dataclass, field

import numpy as np

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
#   <connectivity: E rows of 3 one-based node indices>
#
# Transient runs append multiple zones. Zones are parsed lazily: list_zones()
# scans only the headers (R7); from_file() materialises one zone's arrays.
# ----------------------------------------------------------------------------

_ZONE_RE = re.compile(r"^\s*zone\b", re.IGNORECASE)
_N_RE = re.compile(r"\bN\s*=\s*(\d+)", re.IGNORECASE)
_E_RE = re.compile(r"\bE\s*=\s*(\d+)", re.IGNORECASE)
_ZONETYPE_RE = re.compile(r"ZONETYPE\s*=\s*(\w+)", re.IGNORECASE)
_TITLE_RE = re.compile(r't\s*=\s*"([^"]*)"', re.IGNORECASE)
# A VARLOCATION entry like "[3-10] = CELLCENTERED" or "[1] = NODAL"
_VARLOC_RE = re.compile(r"\[\s*(\d+)\s*(?:-\s*(\d+))?\s*\]\s*=\s*(\w+)", re.IGNORECASE)


def _parse_variables(line: str) -> list[str]:
    """Extract the quoted variable names from a `variables = "x", "y", ...` line."""
    return re.findall(r'"([^"]*)"', line)


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
class ZoneInfo:
    """Header metadata for one zone (no field data loaded)."""
    index: int
    title: str
    n_nodes: int
    n_elems: int
    zonetype: str


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

    # ------------------------------------------------------------------ #
    @staticmethod
    def list_zones(path: str) -> list[ZoneInfo]:
        """Scan only the zone headers — cheap metadata, no field data (R7)."""
        zones: list[ZoneInfo] = []
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if _ZONE_RE.match(line):
                    n = _N_RE.search(line)
                    e = _E_RE.search(line)
                    zt = _ZONETYPE_RE.search(line)
                    title = _TITLE_RE.search(line)
                    zones.append(ZoneInfo(
                        index=len(zones),
                        title=title.group(1) if title else f"zone {len(zones)}",
                        n_nodes=int(n.group(1)) if n else 0,
                        n_elems=int(e.group(1)) if e else 0,
                        zonetype=zt.group(1) if zt else "",
                    ))
        return zones

    @classmethod
    def from_file(cls, path: str, zone: int = -1) -> "TecplotResult":
        """Load a single zone (default: last zone, i.e. most-converged solution).

        Raises ValueError if the file has no zones or the index is out of range.
        """
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        variables: list[str] = []
        zone_starts: list[int] = []   # line index of each "zone ..." header
        for i, line in enumerate(lines):
            if not variables and line.lstrip().lower().startswith("variables"):
                variables = _parse_variables(line)
            if _ZONE_RE.match(line):
                zone_starts.append(i)

        if not variables:
            raise ValueError(f"No 'variables =' line found in {path}")
        if not zone_starts:
            raise ValueError(f"No zones found in {path}")

        if zone < 0:
            zone += len(zone_starts)
        if not (0 <= zone < len(zone_starts)):
            raise ValueError(f"Zone {zone} out of range (file has {len(zone_starts)})")

        header_idx = zone_starts[zone]
        header = lines[header_idx]
        n_nodes = int(_N_RE.search(header).group(1))
        n_elems = int(_E_RE.search(header).group(1))
        zt = _ZONETYPE_RE.search(header)
        title = _TITLE_RE.search(header)
        zinfo = ZoneInfo(zone, title.group(1) if title else f"zone {zone}",
                         n_nodes, n_elems, zt.group(1) if zt else "")

        # The DATAPACKING/VARLOCATION line may be on the header line itself or
        # the following line(s). Find it, then numeric data starts after it.
        data_start = header_idx + 1
        varloc_text = header
        for j in range(header_idx, min(header_idx + 3, len(lines))):
            if "DATAPACKING" in lines[j].upper() or "VARLOCATION" in lines[j].upper():
                varloc_text = lines[j] if j == header_idx else varloc_text + lines[j]
                data_start = j + 1
        loc = _parse_varlocation(varloc_text, len(variables))

        # Numeric region for this zone runs to the next zone header (or EOF).
        data_end = zone_starts[zone + 1] if zone + 1 < len(zone_starts) else len(lines)

        counts = [n_nodes if loc[i] == "NODAL" else n_elems
                  for i in range(len(variables))]
        n_data = sum(counts)

        # Read the whole numeric region as floats (connectivity ints parse as
        # floats fine), then slice: first n_data are field values, the next
        # n_elems*3 are connectivity.
        block = "".join(lines[data_start:data_end])
        tokens = np.fromstring(block, sep=" ")
        expected = n_data + n_elems * 3
        if tokens.size < n_data:
            raise ValueError(
                f"Zone {zone}: expected >= {n_data} data values, got {tokens.size}")

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
            conn = tokens[n_data:expected].astype(np.int64).reshape(n_elems, 3) - 1
        else:
            conn = np.empty((0, 3), dtype=np.int64)

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
            zones=[ZoneInfo(k, "", 0, 0, "") for k in range(len(zone_starts))],
        )

    # ------------------------------------------------------------------ #
    def get_variable_names(self) -> list[str]:
        """All variable names (node + cell), in file order."""
        return list(self.variables)

    def scalar_variables(self) -> list[str]:
        """Variable names that carry a field value (excludes coordinate-only x/y)."""
        coords = set(self.variables[:2])
        return [v for v in self.variables if v not in coords]

    def get_cell_field(self, var: str) -> np.ndarray:
        """Return the cell-centered values for a variable, deriving them from
        node data by averaging if necessary."""
        if var in self.cell_data:
            return self.cell_data[var]
        if var in self.node_data and self.elements.size:
            return self.node_data[var][self.elements].mean(axis=1)
        raise KeyError(f"Unknown variable: {var}")

    def cell_to_node(self, var: str) -> np.ndarray:
        """Average a cell-centered field onto nodes (needed for tricontourf and
        for streamline interpolation via LinearTriInterpolator — R6).

        Returns the node-resident field directly if the variable is already nodal.
        """
        if var in self.node_data:
            return self.node_data[var]
        if var not in self.cell_data:
            raise KeyError(f"Unknown variable: {var}")
        cell_vals = self.cell_data[var]
        n_nodes = self.nodes.shape[0]
        acc = np.zeros(n_nodes)
        cnt = np.zeros(n_nodes)
        # Each element contributes its cell value to its 3 nodes.
        for k in range(self.elements.shape[1]):
            np.add.at(acc, self.elements[:, k], cell_vals)
            np.add.at(cnt, self.elements[:, k], 1.0)
        cnt[cnt == 0] = 1.0
        return acc / cnt
