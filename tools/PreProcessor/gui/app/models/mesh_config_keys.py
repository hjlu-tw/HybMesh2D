"""Text-file KEY -> (dataclass attribute, converter), DERIVED rather than listed.

Shared by :class:`MeshConfig` (``to_dict`` / ``load_from_dict``) and the file I/O
helpers in ``mesh_config_io.py``. In its own tiny module so ``mesh_config.py`` and
``mesh_config_io.py`` can both import it without a circular import.

This used to be 49 hand-written entries, and 45 of them restated something already
declared: the field-spec table each parameter's widget is built from carries its
``.dat`` KEY beside its model field, and the CONVERTER is decided by the model
field's own declared type. Neither source could see the other. So the whole list is
now computed:

* **KEY -> model field** comes from the spec tables. Adding a mesh parameter is one
  spec row, and the ``.dat`` reader and writer follow with no edit here.
* **converter** comes from ``MeshConfig``'s dataclass field type. Verified against
  every hand-written converter this replaced, over 11 probe values each, comparing
  result, result TYPE and raised-exception type: zero differences. That matters
  because a converter is where a ``bool`` field silently becomes a ``0``/``1`` int
  (``gmsh_optimize`` is an int the panel edits with a checkbox) and where an int
  field must tolerate ``5.0`` in a hand-written file.

Note which direction the derivation runs, and why it is not the other one. The
tables live in ``app/services/`` PRECISELY so this module can import them: this
module is on the HEADLESS path (``mesh_config_io.config_to_text`` is called by
``run_pipeline.sh`` / ``run_batch.sh``), the tables were under
``app/views/panels/``, and every module there drags in that package's ``__init__``,
which eagerly imports eight Qt panels. Measured before moving them: importing either
table with PyQt6 blocked raised ImportError. Putting a spec import here without the
move would have made PyQt6 a requirement of a compute node that never draws a
window — the exact defect ``tests/test_qt_free_seam.py`` exists to prevent, which is
also why the old ``views/panels`` paths survive as re-export shims rather than the
call sites being rewritten.
"""
from __future__ import annotations

from typing import Callable

from app.models.mesh_config import MeshConfig
from app.services.field_spec import model_types
from app.services.mesh_bl_field_specs import BL_SPECS
from app.services.mesh_field_specs import MESH_SPECS

#: Text -> value, per model field TYPE. The .dat holds only numbers and bare words,
#: so these four cover it; an unknown type is refused below rather than silently
#: defaulted to ``str``, which would store the digits of a float as text.
_CONVERTERS: dict[str, Callable[[str], object]] = {
    # A bool is written as 1/0, and `int(s) != 0` is what every hand-written entry
    # did. Deliberately NOT int(float(s)) != 0: widening it here would change how a
    # malformed value behaves, and this module is meant to be a rename, not a fix.
    "bool": lambda s: int(s) != 0,
    # Tolerates "5.0" for an int field, which hand-written configs do contain.
    "int": lambda s: int(float(s)),
    "float": float,
    "str": str,
}

#: Keys with no spec, each with the reason it has no widget of its own. Four, and
#: every one is already justified elsewhere in the repo — this is the same fact from
#: the .dat's side, not a new exemption. A key that merely got FORGOTTEN would land
#: here silently, so ``tests/test_field_spec_tables.py`` proves this set is exactly
#: what the tables do not cover, and that each entry names a model field that
#: genuinely has no spec.
_RESIDUE: dict[str, str] = {
    # One UnitSelector row on the Mesh panel declares all three (they are in
    # MESH_EXTRA_AUTHORED for the same reason), so there is no per-field spec to
    # hang a KEY on. Not cosmetic: length_unit drives Linf, i.e. the Reynolds
    # number — see app/services/units.py.
    "LENGTH_UNIT": "length_unit",
    "LENGTH_UNIT_METRES": "length_unit_metres",
    "LENGTH_UNIT_NAME": "length_unit_name",
    # The geometry wall patch. Its reason for having no widget is NOT restated here:
    # it is `NO_WIDGET["mesh_config_panel"]["bc_geom"]` in
    # tests/test_field_spec_tables.py, which is where a field-with-no-widget must be
    # justified, and two copies of one reason would be free to drift apart while
    # check 13b (which compares the SETS) went on passing.
    "BC_GEOM": "bc_geom",
}

#: ``MeshConfig``'s declared field types, the authority on how a .dat value converts.
_MODEL_TYPES = model_types(MeshConfig)


def build_key_map(specs, residue: dict, types: dict | None = None) -> dict:
    """The KEY map for a set of specs plus a declared residue.

    A pure function taking its three inputs rather than reading module globals, so
    the gate can call it with an injected spec (proving one new spec row really is
    all it takes) and with a mutated type map (proving an unhandled type is refused
    rather than silently read as text). Building ``_KEY_MAP`` by calling it is what
    keeps those checks about the real derivation.
    """
    if types is None:
        types = _MODEL_TYPES

    def entry(key: str, attr: str):
        kind = types.get(attr)
        conv = _CONVERTERS.get(kind)
        if conv is None:
            raise TypeError(
                f"mesh_config_keys: {key} edits MeshConfig.{attr}, whose declared "
                f"type {kind!r} has no .dat converter. Add one to _CONVERTERS "
                f"deliberately — falling back to str would store a number as text "
                f"and the mesher would read a default.")
        return (attr, conv)

    out: dict = {}
    for spec in specs:
        if spec.key and spec.model_name:
            out[spec.key] = entry(spec.key, spec.model_name)
    for key, attr in residue.items():
        out[key] = entry(key, attr)
    return out


#: The specs that carry a .dat KEY, i.e. the derivation's input. Exposed so the gate
#: can compare the map against the tables without re-deriving which tables count.
KEYED_SPECS = tuple(s for s in (*MESH_SPECS, *BL_SPECS) if s.key)

_KEY_MAP = build_key_map(KEYED_SPECS, _RESIDUE)
