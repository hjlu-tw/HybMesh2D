"""The H-grid family: parameters in, a block topology document out (issue #134).

A PURE FUNCTION and nothing else. It imports no Qt, no mesher and no canvas, takes
a :class:`~app.services.topology_model.TopologyModel` and returns the topology
document as a plain ``dict`` — so the whole family is exercisable from a headless
process, and the gate that checks its output can check the DOCUMENT rather than a
file a mesher wrote.

WHY A FUNCTION AND NOT A DATA-DRIVEN TEMPLATE FILE (#133's decision, restated where
the first reader will look for it): seeding exactly one count per equivalence class,
closing the corner ring counter-clockwise and deciding which lines are interior are
LOGIC, not fill-in-the-blanks. Expressing them as data means inventing a second
language whose interpreter is this module anyway. Users extend the library by adding
a function and a row in the registry.

WHAT THE DOCUMENT MUST SATISFY, and why each one is satisfied BY CONSTRUCTION here
rather than checked afterwards — the mesher refuses every one of them by name
(`.claude/rules/mesher-multiblock.md`), and a template that can produce a refusal has
handed the user back the JSON they came here to avoid:

* **The corner ring closes counter-clockwise**, each block declaring its four edges
  ``[south, east, north, west]`` with south/north running i-min -> i-max and
  west/east running j-min -> j-max. Built from one index expression below, so the
  four sides cannot disagree.
* **Every id is unique** across corners, edges and blocks. The three families of id
  carry different prefixes (``c_`` / ``h_`` / ``v_`` / ``b_``) and their remaining
  text is the grid index, which is unique within a family. Note ``h_``/``v_`` are
  both edges: it is the PAIR that must not collide, and a horizontal edge is indexed
  over ``i < nx`` while a vertical one is indexed over ``i <= nx``, so the prefix is
  what separates them rather than the index.
* **Exactly one count seed per equivalence class.** Opposite sides of a block carry
  equal counts and a shared edge is one edge named by two blocks, so on this grid the
  horizontal edges of column ``i`` are ONE class and the vertical edges of row ``j``
  are another: ``nx + ny`` classes for ``nx*ny`` blocks. Seeded on the bottom row and
  the left column respectively, which is one seed per class and never two.
* **Each interior line is declared once**, as one edge of kind ``interface`` named by
  both of its blocks. There is no second declaration to keep in step because the edge
  list is built once and the blocks reference it by id.
* **No unknown keys.** Every key emitted below is in the schema
  (``src/MultiBlock.cpp`` ``rejectUnknownKeys``); the dict is built here rather than
  merged from user input, so a stray parameter name cannot reach the document.
* **Nothing reaches nothing.** Every corner of a full grid lies on an edge and every
  edge lies in at least one block.

WHY THE BOTTOM-WALL OPTION IS A SPACING AND NOT A KIND. A boundary edge MUST be
``kind: "wall"`` — the mesher requires a wall to bound exactly one block side and an
interface/cut exactly two — so "is the bottom a wall" cannot be a choice of kind;
there is nothing for it to choose. What it does choose is whether the bottom row's
vertical edges CLUSTER toward y_min, which is the thing a flat plate or a duct floor
actually wants. That is ``spacing: {"wall_ends": "start"}``: the edge's start corner
is the one on y_min because these edges are declared upward.

AND IT DECLARES NO ``ds_start``, deliberately. Leaving the first-cell height out makes
the edge take the run's ``BL_INITIAL_THICKNESS``, which is #133's decision that a
template uses the existing boundary-layer parameter names rather than an alias: the
physical quantity is identical, and a second field for it would be a second place for
a user to set one number.

SPACING DOES NOT PROPAGATE — only COUNTS do. The shipped hand-written H-grid says so
in its own header, and it is why the clustering below is written onto EVERY vertical
edge of the bottom row rather than onto one of them and left to spread.
"""
from __future__ import annotations

from app.services.topology_preflight import Refusal


#: The template's own name for the family, as stored in the project file and as
#: looked up in the registry. A string rather than an enum because it is persisted.
FAMILY = "hgrid"


def _cell_counts(span: float, blocks: int, cell: float) -> list[int]:
    """The derived NODE count for each of ``blocks`` equal divisions of ``span``.

    A node count, not an interval count: the mesher's ``count`` is "how many nodes
    on this edge, its two end corners included", so it is intervals + 1 and its floor
    is 2. Rounding to the nearest interval count (rather than ceiling) keeps the
    delivered cell size closest to the one asked for; the ``max(1, ...)`` is what
    stops a target larger than the block itself asking for zero intervals, which
    would be a count of 1 and a refusal.
    """
    if blocks <= 0 or cell <= 0.0:
        return []
    width = abs(float(span)) / float(blocks)
    intervals = max(1, int(round(width / float(cell))))
    return [intervals + 1] * int(blocks)


def _override(counts: list[int], text: str) -> list[int]:
    """``counts`` with any position the user overrode replaced.

    The override is a comma-separated list, one entry per division, and an entry that
    is blank or unparseable keeps the derived value for that position — so a half-typed
    override degrades to the derivation rather than to a refusal while the user is
    still typing it. A shorter list overrides a prefix; a longer one is truncated,
    because a position that does not exist has nothing to override.
    """
    if not text:
        return counts
    out = list(counts)
    for i, tok in enumerate(str(text).split(",")):
        if i >= len(out):
            break
        tok = tok.strip()
        if not tok:
            continue
        try:
            v = int(tok)
        except ValueError:
            continue
        if v >= 2:
            out[i] = v
    return out


def hgrid_counts(model) -> tuple[list[int], list[int]]:
    """``(x_counts, y_counts)`` — the node count of each column and each row.

    ONE OWNER for the derivation, called by the family function below AND by the
    panel that displays it. The ticket asks for the derived counts to be visible as
    the user types; a panel that computed its own would be free to display a number
    the generated mesh does not use, which is the drift a single owner exists to make
    impossible.
    """
    xs = _cell_counts(model.hgrid_x_max - model.hgrid_x_min,
                      model.hgrid_nx, model.hgrid_cell)
    ys = _cell_counts(model.hgrid_y_max - model.hgrid_y_min,
                      model.hgrid_ny, model.hgrid_cell)
    return (_override(xs, model.hgrid_counts_x),
            _override(ys, model.hgrid_counts_y))


def build(model, ctx=None) -> dict:
    """The H-grid topology document for ``model``, as a plain dict.

    ``ctx`` is the binding context every family function is handed (#137) and this
    one ignores: the H-grid declares only FREE corners — the shipped hand-written
    H-grid case has no geometry file at all — so there is nothing here to resolve
    against the user's CAD. Accepted rather than omitted so the registry has ONE
    call shape; a family whose signature differed would make ``fam.build`` a
    dispatch rather than a call.
    """
    nx, ny = int(model.hgrid_nx), int(model.hgrid_ny)
    x0, x1 = float(model.hgrid_x_min), float(model.hgrid_x_max)
    y0, y1 = float(model.hgrid_y_min), float(model.hgrid_y_max)
    xc, yc = hgrid_counts(model)

    # The grid lines. Computed from the fraction rather than by accumulating a step,
    # so the last line is EXACTLY x1 instead of x1 plus nx roundings.
    xs = [x0 + (x1 - x0) * i / nx for i in range(nx + 1)]
    ys = [y0 + (y1 - y0) * j / ny for j in range(ny + 1)]

    def cid(i, j): return f"c_{i}_{j}"
    def hid(i, j): return f"h_{i}_{j}"
    def vid(i, j): return f"v_{i}_{j}"

    corners = [{"id": cid(i, j), "kind": "free", "xy": [xs[i], ys[j]]}
               for j in range(ny + 1) for i in range(nx + 1)]

    edges = []
    # Horizontal edges, declared LEFT TO RIGHT so that a block's south and north
    # both run i-min -> i-max, which is the convention the mesher reads.
    for j in range(ny + 1):
        for i in range(nx):
            e = {"id": hid(i, j), "corners": [cid(i, j), cid(i + 1, j)],
                 # Interior iff there is a block on both sides of it.
                 "kind": "interface" if 0 < j < ny else "wall"}
            # One seed per column class, on the bottom row.
            if j == 0:
                e["count"] = xc[i]
            edges.append(e)
    # Vertical edges, declared UPWARD so that west and east both run j-min -> j-max
    # — and so that "start" names the bottom end for the wall clustering below.
    for j in range(ny):
        for i in range(nx + 1):
            e = {"id": vid(i, j), "corners": [cid(i, j), cid(i, j + 1)],
                 "kind": "interface" if 0 < i < nx else "wall"}
            # One seed per row class, on the left column.
            if i == 0:
                e["count"] = yc[j]
            # Spacing is each edge's OWN and does not propagate, so every edge of the
            # bottom row carries it, not just the seeded one.
            if j == 0 and model.hgrid_wall_bottom:
                e["spacing"] = {"wall_ends": "start"}
            edges.append(e)

    blocks = [{"id": f"b_{i}_{j}",
               # [south, east, north, west] — one expression, so the four sides of
               # every block are wound the same way by construction.
               "edges": [hid(i, j), vid(i + 1, j), hid(i, j + 1), vid(i, j)]}
              for j in range(ny) for i in range(nx)]

    return {"format_version": 1, "corners": corners,
            "edges": edges, "blocks": blocks}


def preflight(model, ctx=None) -> tuple:
    """Why this family cannot fill the region it has been given, before anything
    runs (#165).

    THE H-GRID IS THE ONE FAMILY THAT BINDS TO NOTHING, so every refusal here is
    about the RECTANGLE the user declared and none of them names a curve. That is
    why :class:`~app.services.topology_preflight.Refusal` lets ``geom`` be empty
    rather than making every family invent one: an H-grid's "offending curve" is
    four numbers in the template rows, and the honest answer is to name the row.

    WHAT IT CHECKS, and each one was a CRASH or a developer-facing exit before:
    a grid of blocks needs at least one column and one row (``nx = 0`` divided by
    zero inside :func:`build`); a region needs FOUR distinct corners (``x_max ==
    x_min`` builds blocks of zero width, and ``x_max < x_min`` builds every one of
    them wound clockwise, which the mesher answers with ``HYBMESH_ERROR 8`` and a
    sentence about a block id); and a target cell size of zero derives no counts
    at all (:func:`_cell_counts` returns ``[]`` and :func:`build` raises
    ``IndexError``).

    ``ctx`` is accepted and ignored, as :func:`build` accepts and ignores it, so
    the registry keeps ONE call shape for every family's refusal too.
    """
    out = []
    nx, ny = int(model.hgrid_nx), int(model.hgrid_ny)
    if nx < 1 or ny < 1:
        out.append(Refusal(
            f"this region is divided into {nx} column(s) by {ny} row(s), and a "
            f"grid of blocks needs at least one of each.",
            fix="Set 'Blocks in X' and 'Blocks in Y' to 1 or more."))
    for axis, lo, hi, lo_row, hi_row in (
            ("left and right", float(model.hgrid_x_min),
             float(model.hgrid_x_max), "X Min", "X Max"),
            ("bottom and top", float(model.hgrid_y_min),
             float(model.hgrid_y_max), "Y Min", "Y Max")):
        if hi == lo:
            out.append(Refusal(
                f"the {axis} sides of the region are both at {lo:.6g}, so it is "
                f"a line and not a rectangle — it has two corners where a block "
                f"needs four.",
                fix=f"Move '{hi_row}' away from '{lo_row}'."))
        elif hi < lo:
            out.append(Refusal(
                f"'{hi_row}' ({hi:.6g}) is below '{lo_row}' ({lo:.6g}), so the "
                f"region is inside out and every cell in it would be too.",
                fix=f"Swap the two, or raise '{hi_row}' above '{lo_row}'."))
    if float(model.hgrid_cell) <= 0.0:
        out.append(Refusal(
            f"the target cell size is {float(model.hgrid_cell):.6g}, and a cell "
            f"has to be bigger than nothing.",
            fix="Set 'Target Cell Size' to the edge length you want."))
    return tuple(out)
