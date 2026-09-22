"""One declaration per template parameter (issue #134, parent #133).

Qt-free, like the two mesh tables beside it and for the same reason: the panel is
one consumer of this table and the bidirectional gate
(``tests/test_topology_param_specs.py``) is another, and that gate must run in a
headless process.

WHY THIS IS A THIRD TABLE AND NOT ROWS IN ``MESH_SPECS``. The mesh table's rows
author fields of ``MeshConfig`` and carry the ``.dat``/``Config.hpp`` KEY that
``tests/test_gui_cpp_config_parity.py`` compares against the C++ in both
directions. A template parameter authors a field of :class:`TopologyModel` and has
NO C++ counterpart — the mesher never sees a far-field radius or a block count, it
sees the document they produced. Putting these rows in ``MESH_SPECS`` would either
give them a key the C++ does not have (failing the parity gate) or make "a row with
no key" mean two different things in one table.

``key=""`` here is therefore the normal case rather than the exception it is next
door, and it is why these parameters need their own bidirectional gate: the
existing field-spec gates compare a table against the mesher's keys, and there is
nothing on the other side of that comparison to compare these to. What they are
compared against instead is the FAMILY FUNCTIONS — every parameter a family reads
has a row here, and every row here is read by a family — which is the pair of
silent failures this table exists to remove, one in each direction: a control that
does nothing, and a parameter the user cannot reach.

``group`` is the builder section that lays a row out, exactly as in the mesh table.
All rows are ``modes=(MESH_MODE_MULTIBLOCK,)``: a topology is what the multi-block
path fills, and the hybrid path has nothing to do with one.
"""
from __future__ import annotations

from app.services.field_spec import FieldSpec
from app.services.mesh_modes import MESH_MODE_MULTIBLOCK
from app.services.topology_model import FAMILY_CHOICES

_MB = (MESH_MODE_MULTIBLOCK,)

#: The section every row below is laid out in.
GROUP = "topology"

TOPOLOGY_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec("topo_family", "choice", "Template",
              "Which topology family to generate. '(none)' is the path that "
              "existed before templates: name a topology document by hand in the "
              "Topology File row above. Picking a family makes that row a "
              "PROJECTION of the parameters below — the document is written on the "
              "way to the mesher rather than maintained by you.",
              model="family", group=GROUP, modes=_MB,
              opts=dict(choices=list(FAMILY_CHOICES), fallback="")),

    # ── H-grid ───────────────────────────────────────────────────────────────
    FieldSpec("topo_hgrid_x_min", "sci", "X Min",
              "Left edge of the rectangular domain the blocks divide.",
              model="hgrid_x_min", group=GROUP, modes=_MB,
              opts=dict(lo=-1e9, hi=1e9)),
    FieldSpec("topo_hgrid_x_max", "sci", "X Max",
              "Right edge of the rectangular domain the blocks divide.",
              model="hgrid_x_max", group=GROUP, modes=_MB,
              opts=dict(lo=-1e9, hi=1e9)),
    FieldSpec("topo_hgrid_y_min", "sci", "Y Min",
              "Bottom edge of the domain. When 'Cluster To Floor' is on, this is "
              "the wall the grid clusters toward.",
              model="hgrid_y_min", group=GROUP, modes=_MB,
              opts=dict(lo=-1e9, hi=1e9)),
    FieldSpec("topo_hgrid_y_max", "sci", "Y Max",
              "Top edge of the domain.",
              model="hgrid_y_max", group=GROUP, modes=_MB,
              opts=dict(lo=-1e9, hi=1e9)),
    FieldSpec("topo_hgrid_nx", "int", "Blocks in X",
              "How many blocks across. The blocks divide the range equally; the "
              "node count of each column is derived from the target cell size and "
              "shown below, where it can be overridden.",
              model="hgrid_nx", group=GROUP, modes=_MB,
              opts=dict(lo=1, hi=64)),
    FieldSpec("topo_hgrid_ny", "int", "Blocks in Y",
              "How many blocks up. Same division and the same derivation as "
              "Blocks in X.",
              model="hgrid_ny", group=GROUP, modes=_MB,
              opts=dict(lo=1, hi=64)),
    FieldSpec("topo_hgrid_cell", "sci", "Target Cell Size",
              "The cell edge length to aim for. It is the PHYSICAL quantity you "
              "have; the node counts it implies are derived and displayed rather "
              "than asked for, because converting one into the other in your head "
              "is the step this template exists to remove.",
              model="hgrid_cell", group=GROUP, modes=_MB,
              opts=dict(lo=1e-12, hi=1e9)),
    FieldSpec("topo_hgrid_wall_bottom", "bool", "Cluster To Floor",
              "Cluster the grid toward Y Min, the way a flat plate or a duct floor "
              "wants. The first cell height is the run's BL_INITIAL_THICKNESS — the "
              "same field the hybrid path uses, not an alias, because it is the "
              "same physical quantity. Off leaves the vertical spacing uniform.",
              model="hgrid_wall_bottom", group=GROUP, modes=_MB,
              opts=dict(text="cluster the first cell toward Y Min")),
    FieldSpec("topo_hgrid_counts_derived", "label", "Derived Counts",
              "The node count each column and row gets from the target cell size "
              "above. Shown as you type, so the relationship between a cell size "
              "and the count it implies is visible rather than hidden.",
              model=None, group=GROUP, modes=_MB),
    FieldSpec("topo_hgrid_counts_x", "text", "Override X Counts",
              "Comma-separated node counts, one per column, overriding the derived "
              "value at that position. Leave an entry blank to keep the derived "
              "one. The derivation is a default, not a cage.",
              model="hgrid_counts_x", group=GROUP, modes=_MB,
              opts=dict(placeholder="(derived)")),
    FieldSpec("topo_hgrid_counts_y", "text", "Override Y Counts",
              "Comma-separated node counts, one per row. Same rule as the X "
              "overrides.",
              model="hgrid_counts_y", group=GROUP, modes=_MB,
              opts=dict(placeholder="(derived)")),
)

#: Rows that author no model field, declared rather than inferred: the derived-count
#: read-out displays a number the family function computed and writes nothing back.
#: Named here so the bidirectional gate can hold "every OTHER row is read by a
#: family" without a read-out counting as an unread parameter.
TOPOLOGY_READONLY = ("topo_hgrid_counts_derived",)
