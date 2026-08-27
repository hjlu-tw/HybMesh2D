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
