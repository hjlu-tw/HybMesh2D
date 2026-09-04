"""The mesh GENERATION PATH, named once on the GUI side.

Two paths exist and a case picks one. The numbers and their meaning are the
mesher's — ``MeshMode`` in ``include/MeshMode.hpp`` — and this module is the GUI's
single spelling of them, so a panel, a field-spec table and the ``.dat`` writer
cannot each carry their own literal ``0``/``1``.

``tests/test_field_spec_tables.py`` check 14 compares these constants and the
per-field ``modes=`` declarations they appear in against that C++ header, in both
directions. Qt-free: this is a fact about a config, not about a widget.
"""
from __future__ import annotations

#: The existing path: boundary-layer quads + Gmsh far-field triangles. THE
#: DEFAULT, so a case that predates the multi-block path meshes exactly as before.
MESH_MODE_HYBRID = 0

#: Topology-driven multi-block structured. Uses Gmsh nowhere.
MESH_MODE_MULTIBLOCK = 1

#: Every mode, in the order the panel's combo offers them.
MESH_MODES: tuple[int, ...] = (MESH_MODE_HYBRID, MESH_MODE_MULTIBLOCK)

#: (value, label) pairs for the mode combo. Kept beside the constants because the
#: label is what tells a user which of the two numbers they are choosing.
MESH_MODE_CHOICES: list[tuple[int, str]] = [
    (MESH_MODE_HYBRID, "0: Hybrid (boundary layer + Gmsh far field)"),
    (MESH_MODE_MULTIBLOCK, "1: Multi-block structured (topology file)"),
]


def missing_mesh_input(mesh_config) -> str:
    """Why the mesh stage cannot run for ``mesh_config``, or ``""`` when it can.

    **The two paths read DIFFERENT inputs, and only the hybrid path's
    requirement was ever checked.** ``geom_files`` empty is fatal there — there is
    nothing to grow a boundary layer from — and it is NORMAL in multi-block,
    where a topology may declare every corner itself: two of this repo's five
    shipped topology cases (``config/multiblock_square.dat`` and
    ``multiblock_hgrid.dat``) name no ``GEOM_FILE`` at all and mesh fine from
    ``run.sh``, while the other three bind their edges to one. The headless runner
    applied the hybrid precondition to both and refused them (#56), so the CLI
    could mesh a case the pipeline could not.

    Stated as one function rather than as an ``if mode == 1`` at each call site
    because there are two hosts (the blocking runner and the GUI's mesh
    controller) and a third would be written the same way the first two were.

    Duck-typed on purpose: the caller has a ``MeshConfig``, but this module is
    Qt-free and about a CONFIG, not about the class.
    """
    if mesh_config is None:
        return "no mesh configuration"
    mode = int(getattr(mesh_config, "mesh_mode", MESH_MODE_HYBRID) or 0)
    if mode == MESH_MODE_MULTIBLOCK:
        if not str(getattr(mesh_config, "mesh_topology_file", "") or "").strip():
            return ("the multi-block path fills a DECLARED block topology and "
                    "MESH_TOPOLOGY_FILE names none")
        return ""
    if not getattr(mesh_config, "geom_files", None):
        return "mesh stage has no geometry input (geom_files empty)"
    return ""
