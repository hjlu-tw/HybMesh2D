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

    FieldSpec("topo_detached", "bool", "Detached",
              "Whether the template still generates the document (#139). A row "
              "rather than a flag the panel keeps for itself, because THIS is what "
              "carries the state through the machinery every other template "
              "parameter uses: the panel->model sync, the project file, undo and "
              "the projection. It is READ-ONLY — detaching writes a file and "
              "re-attaching discards one, and neither is something a checkbox "
              "should be able to do by being clicked; the Detach / Re-attach "
              "buttons at the foot of this section are the controls.",
              model="detached", group=GROUP, modes=_MB,
              opts=dict(text="detached — the Topology File above is maintained by "
                             "hand", readonly=True)),

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

    # ── O-grid (#137) ────────────────────────────────────────────────────────
    FieldSpec("topo_ogrid_body_geom", "path", "Body Geometry",
              "The closed body the ring wraps. One of the geometries this mesh "
              "loads — the template writes none of its own, so the walls follow "
              "the shape you drew and their boundary conditions are read off its "
              "own segments.",
              model="ogrid_body_geom", group=GROUP, modes=_MB,
              opts=dict(caption="Select body geometry",
                        filter="Geometry (*.dat);;All files (*)")),
    FieldSpec("topo_ogrid_body_segs", "text", "Bound Body Segments",
              "READ-ONLY: which edges bind is the template's decision, not yours. "
              "Captured when you name the geometry above, as the CAD segment's "
              "STABLE IDs — never as positions in a list, because inserting, "
              "deleting or reordering a segment shifts every positional binding "
              "after it with no error at all. An id the geometry no longer has, or "
              "an order it does not run them in, REFUSES the run with the edge "
              "named rather than falling back to the default boundary condition.",
              model="ogrid_body_segs", group=GROUP, modes=_MB,
              opts=dict(placeholder="(all of the body's segments)", readonly=True)),
    FieldSpec("topo_ogrid_far_geom", "path", "Far-Field Geometry",
              "The outer outline. Its segments pair ONE TO ONE with the body's, so "
              "segment it the same way you segmented the body; its own per-segment "
              "conditions reach the export the same way the body's do.",
              model="ogrid_far_geom", group=GROUP, modes=_MB,
              opts=dict(caption="Select far-field geometry",
                        filter="Geometry (*.dat);;All files (*)")),
    FieldSpec("topo_ogrid_far_segs", "text", "Bound Far Segments",
              "The far field's bound segment ids. Same rule as the body's.",
              model="ogrid_far_segs", group=GROUP, modes=_MB,
              opts=dict(placeholder="(all of the far field's segments)", readonly=True)),
    FieldSpec("topo_ogrid_splits", "int", "Splits Per Segment",
              "How many equal-arc blocks each source segment becomes. A bound edge "
              "declares ONE segment — that is how its boundary condition is read "
              "off the geometry — so the block ring refines your segments and never "
              "cuts across them. A body drawn as a single segment needs at least 2 "
              "here.",
              model="ogrid_splits", group=GROUP, modes=_MB,
              opts=dict(lo=1, hi=64)),
    FieldSpec("topo_ogrid_cell", "sci", "Target Cell Edge",
              "The circumferential cell edge length to aim for along the wall. The "
              "node count each wall edge gets is derived from it and from that "
              "segment's own arc length, and shown below.",
              model="ogrid_cell", group=GROUP, modes=_MB,
              opts=dict(lo=1e-12, hi=1e9)),
    FieldSpec("topo_ogrid_radial_count", "int", "Override Radial Nodes",
              "0 takes the derived count. The derivation is a default, not a cage — "
              "but it is worth reading first: it is the count at which a law "
              "starting from your BL_INITIAL_THICKNESS reaches the far field "
              "without ever growing faster than the 1:1 criterion allows.",
              model="ogrid_radial_count", group=GROUP, modes=_MB,
              opts=dict(lo=0, hi=20000)),
    FieldSpec("topo_ogrid_derived", "label", "Derivation",
              "What the parameters above imply, with the working shown: the ring's "
              "blocks and circumferential cells, the 1:1 growth ratio those imply, "
              "the wall first cell that ratio would give against the one your "
              "BL_INITIAL_THICKNESS asks for, and the radial node count that closes "
              "the gap between them.",
              model=None, group=GROUP, modes=_MB),
)

#: Which geometry row CAPTURES its binding into which segment row (#137). Declared
#: HERE rather than spelled in the panel, for the reason every other pairing in this
#: package is: a view holding it is a view a second binding family has to be edited
#: to add, and nothing would gate the pair. `tests/test_topology_param_specs.py`
#: check 9 requires both halves to be rows of this table, and check 10 requires each
#: segment row to be READ-ONLY.
BINDING_ROWS = (("topo_ogrid_body_geom", "topo_ogrid_body_segs"),
                ("topo_ogrid_far_geom", "topo_ogrid_far_segs"))

#: Rows that author the model's STATE rather than a family's parameter: which family
#: is selected, and whether it still generates the document (#139). Declared rather
#: than special-cased in the gate, which requires every OTHER row to be read by some
#: family — neither of these ever is, by construction: `family` SELECTS the function
#: that does the reading, and `detached` decides whether it is called at all. A third
#: entry here should be viewed with suspicion; a parameter that no family reads is
#: the control-that-does-nothing this table's own gate exists to catch, and calling
#: it "state" is the obvious way to smuggle one past.
TOPOLOGY_STATE_ROWS = ("topo_family", "topo_detached")

#: Rows that author no model field, declared rather than inferred: the derived-count
#: read-out displays a number the family function computed and writes nothing back.
#: Named here so the bidirectional gate can hold "every OTHER row is read by a
#: family" without a read-out counting as an unread parameter.
TOPOLOGY_READONLY = ("topo_hgrid_counts_derived", "topo_ogrid_derived")
