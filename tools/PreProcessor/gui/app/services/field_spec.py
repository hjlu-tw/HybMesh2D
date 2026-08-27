"""One declaration per config field: what it edits, how it is edited, what it means.

A stage-configuration panel used to be cut in half. One half BUILT widgets
(``self.fs_mach = _spin(4, 0.0, 100.0, "…")``); the other half read and wrote them
against a model (``cfg.fs_mach = self.fs_mach.value()`` /
``self.fs_mach.setValue(cfg.fs_mach)``). The interface between the halves was the
whole set of widgets, passed implicitly through ``self``, and nothing anywhere
declared what that set was — 176 widget attributes across five build mixins, named
back by hand in 246 read/write lines. The two halves agreed only because both spelled
the same name, and the failure modes were silent in both directions: a model field
with no widget went stale, a widget with no ``get_config`` line was a control that did
nothing.

A :class:`FieldSpec` is that missing declaration. The table is walked once to build,
once to read and once to write, so a field is mentioned once. This module holds the
record and the PURE questions asked of a table; the Qt half (which widget class a kind
maps to, and how to read/write it) is ``app/views/panels/field_widgets.py``.

**This module** is Qt-free, and gated as such by ``tests/test_qt_free_seam.py``'s
``services/`` sweep, so the record and the questions asked of a table can be used
anywhere. Be precise about what that does NOT buy: the TABLES live under
``views/panels/`` (they carry labels and tooltips, which is UI text), and importing
anything from that package runs its ``__init__``, which pulls in Qt. So
``config_ownership.preserved_fields()`` loads five PyQt6 modules the first time it is
called — measured, and measured to be UNCHANGED from before these tables existed, since
the deferred ``from app.views.panels.mesh_dialogs import _BL_OVERRIDE_KEYS`` it replaced
did the same. The deferral keeps ``config_ownership``'s IMPORT clean, which is what the
sweep checks and all its callers need (a Qt-side controller and two gate tests); it does
not make the answer reachable from a headless process, and nothing in the repo needs it
to be.

Three decisions worth knowing:

* **``model=None`` marks a spec that authors nothing.** The seed size/radius editors
  write per-geometry role data rather than a model field, and a derived read-out (the
  reference Reynolds number) writes nothing at all. Leaving them out of the table
  would be worse than it sounds — the unit-suffix list is derived from the table, so
  a physical length missing from it would silently lose its unit.
* **An irregular field carries its own irregularity.** Where a widget does not map
  onto its model field by kind alone (the STL3d encoding combo has three items and a
  bool field behind them), the ``read``/``write`` pair sits ON the spec, next to the
  field. The alternative — a ``kind="custom"`` escape hatch — puts the field straight
  back into an 85-line function, so there is deliberately no such kind.
* **An unknown kind is refused at construction.** A typo'd kind would otherwise build
  no widget and be discovered as a missing control; :meth:`FieldSpec.__post_init__`
  turns it into an import-time ``ValueError``.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

#: Widget kinds. Each names the widget class the builder makes, and therefore how the
#: field is read and written. Adding one is a change in two places by design: here (so
#: a typo cannot pass) and in ``field_widgets`` (so it has a widget).
#:
#: ``sci`` is not a styling choice — it is the physical-length rule (a fixed-notation
#: box silently clamps the 1e-7..1e-8 first-cell heights real CFD needs), which is why
#: the unit-suffix list is exactly this kind.
KINDS = frozenset({
    "sci",       # SciDoubleSpinBox — a PHYSICAL LENGTH (decade steps, no floor)
    "float",     # CleanDoubleSpinBox (opts: lo, hi, dec, step)
    "narrow",    # NarrowDoubleSpinBox — same, with a width cap for multi-spin rows
    "int",       # QSpinBox (opts: lo, hi)
    "text",      # QLineEdit (opts: fallback, placeholder, readonly)
    "gfloat",    # QLineEdit holding a float in %g — values a spin box cannot show
    "bool",      # QCheckBox (opts: text, as_int)
    "choice",    # QComboBox over (value, label) pairs (opts: choices, fallback)
    "path",      # QLineEdit + Browse button (opts: caption, filter, + text opts)
    "bcname",    # BCWidget — a boundary-patch name with its colour indicator
    "toggle",    # checkable make_button (the mesh panel's write-format switches)
    "label",     # QLabel read-out; authors nothing
})

#: Kinds whose widget holds a number the user can type or step.
NUMERIC_KINDS = frozenset({"sci", "float", "narrow", "int"})

#: Kinds that carry a length unit suffix. Only physical lengths do: a growth rate, an
#: angle or a layer count must never be labelled with one.
LENGTH_KINDS = frozenset({"sci"})


@dataclass(frozen=True)
class FieldSpec:
    """One editable field of one config panel.

    ``attr``   the panel attribute the widget is stored on (``self.<attr>``).
    ``kind``   one of :data:`KINDS`.
    ``label``  form-label text, without the trailing colon.
    ``tip``    tooltip / help text. Shown on the widget AND on the label's '?'.
    ``model``  the model field this edits. ``""`` means "same name as ``attr``";
               ``None`` means the field authors no model value.
    ``key``    the ``.dat`` / ``Config.hpp`` KEY, where the parameter has one.
    ``group``  which builder section owns the row. The gate refuses a group no
               builder walks, so a field cannot become unreachable-but-written.
    ``opts``   kind-specific: ranges, choices, fallbacks, layout hints.
    ``read`` / ``write``  the escape hatch for a field whose widget does not map
               onto its model field by kind alone. ``read(widget)`` returns the
               model value; ``write(widget, value)`` sets the widget.
    ``modes``  which generation MODES read this field, or ``None`` for a field
               every mode reads. Declared here rather than in a lookup table
               beside the panel, for the reason the KEY is: a second table is a
               second source of truth, and this one decides both what the panel
               shows and what the mesher warns about (``include/MeshMode.hpp``
               holds the mesher's half, and the two are compared in both
               directions by ``tests/test_field_spec_tables.py`` check 14).
    """

    attr: str
    kind: str
    label: str = ""
    tip: str = ""
    model: str | None = ""
    key: str = ""
    group: str = ""
    opts: Mapping[str, Any] = field(default_factory=dict)
    read: Callable[[Any], Any] | None = None
    write: Callable[[Any, Any], None] | None = None
    modes: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        if self.modes is not None:
            # A tuple, so the spec stays hashable/frozen; non-empty, because a
            # field no mode reads is a control that can never do anything, which
            # is exactly the silent failure this table exists to remove. `bool` is
            # excluded explicitly: it is an int subclass, so `modes=(True,)` would
            # otherwise pass and quietly mean mode 1.
            ok = (isinstance(self.modes, tuple) and self.modes
                  and all(type(m) is int for m in self.modes))
            if not ok:
                raise ValueError(
                    f"FieldSpec({self.attr!r}): modes must be a NON-EMPTY tuple of "
                    f"ints (the generation modes that read this field), got "
                    f"{self.modes!r}. Leave it None for a field every mode reads.")
        if self.kind not in KINDS:
            raise ValueError(
                f"FieldSpec({self.attr!r}): unknown kind {self.kind!r}. "
                f"Known kinds: {', '.join(sorted(KINDS))}. A kind with no builder "
                f"would produce no widget, i.e. a setting the user cannot reach "
                f"that is still written back to the model.")
        if not self.attr:
            raise ValueError("FieldSpec needs an attr (the panel attribute name)")
        if self.kind == "int":
            # An int field is a QSpinBox, whose setRange takes C++ ints. sip used to
            # accept a float there with a DeprecationWarning and now refuses it
            # outright, so `hi=1e6` — the natural way to write a large bound — builds
            # a panel on one machine and raises TypeError on another. Refuse it here,
            # where the kind itself is checked, rather than at widget-build time.
            for name in ("lo", "hi"):
                v = self.opts.get(name)
                if v is not None and not isinstance(v, int):
                    raise ValueError(
                        f"FieldSpec({self.attr!r}): kind 'int' needs an int {name}, "
                        f"got {v!r}. QSpinBox.setRange takes ints; a float bound "
                        f"raises TypeError on a newer sip.")

    @property
    def model_name(self) -> str | None:
        """The model field this spec authors, or None when it authors nothing."""
        if self.model is None:
            return None
        return self.model or self.attr

    @property
    def is_length(self) -> bool:
        """True for a physical length — the fields that carry a unit suffix."""
        return self.kind in LENGTH_KINDS


# ── pure questions asked of a table ─────────────────────────────────────────

def authored(*tables: Iterable[FieldSpec]) -> frozenset[str]:
    """Model fields the given tables author."""
    out = set()
    for table in tables:
        for spec in table:
            name = spec.model_name
            if name:
                out.add(name)
    return frozenset(out)


def duplicate_models(*tables: Iterable[FieldSpec]) -> tuple[str, ...]:
    """Model fields authored by more than one spec — the drift this exists to stop.

    Two specs for one field means two widgets writing it, and which one wins is
    decided by table order, i.e. by accident.
    """
    seen: dict[str, int] = {}
    for table in tables:
        for spec in table:
            name = spec.model_name
            if name:
                seen[name] = seen.get(name, 0) + 1
    return tuple(sorted(n for n, c in seen.items() if c > 1))


def duplicate_attrs(*tables: Iterable[FieldSpec]) -> tuple[str, ...]:
    """Panel attributes declared by more than one spec (one widget, two owners)."""
    seen: dict[str, int] = {}
    for table in tables:
        for spec in table:
            seen[spec.attr] = seen.get(spec.attr, 0) + 1
    return tuple(sorted(a for a, c in seen.items() if c > 1))


def by_attr(*tables: Iterable[FieldSpec]) -> dict[str, FieldSpec]:
    return {spec.attr: spec for table in tables for spec in table}


def by_key(*tables: Iterable[FieldSpec]) -> dict[str, FieldSpec]:
    """Specs indexed by their ``.dat`` KEY (only those that have one)."""
    return {spec.key: spec for table in tables for spec in table if spec.key}


def in_group(table: Iterable[FieldSpec], *groups: str) -> tuple[FieldSpec, ...]:
    """The table's specs belonging to ``groups``, in table order.

    Order is the table's, not the argument's: the table is the visual order of the
    form, so reading rows out of it keeps the panel looking the same.
    """
    want = set(groups)
    return tuple(s for s in table if s.group in want)


def group_names(table: Iterable[FieldSpec]) -> tuple[str, ...]:
    """Distinct group names, in first-appearance order."""
    out: list[str] = []
    for spec in table:
        if spec.group and spec.group not in out:
            out.append(spec.group)
    return tuple(out)


def reads_in_mode(spec: FieldSpec, mode: int) -> bool:
    """Does ``mode`` read this field? An undeclared spec is read by every mode."""
    return spec.modes is None or mode in spec.modes


def hidden_attrs(mode: int, *tables: Iterable[FieldSpec]) -> tuple[str, ...]:
    """Panel attributes ``mode`` does NOT read, in table order.

    What the panel hides. A subtraction over the declarations, not a list — the
    same shape as ``preserved`` and ``length_attrs``, and for the same reason.
    """
    return tuple(s.attr for table in tables for s in table
                 if not reads_in_mode(s, mode))


def length_attrs(*tables: Iterable[FieldSpec]) -> tuple[str, ...]:
    """Panel attributes holding a physical length, in table order.

    This is what the unit suffix is applied to. Derived from the kind rather than
    listed, so the list and the widgets cannot disagree.
    """
    return tuple(s.attr for table in tables for s in table if s.is_length)


def panel_variant(spec: FieldSpec) -> FieldSpec:
    """The spec as a PANEL's backing widget sees it, applying ``panel_choices``.

    A parameter can legitimately offer fewer values on the panel than in the dialog
    that edits it: ``BL_CONCAVE_METHOD``'s method 0 (Merge) is CLI-side and the GUI has
    never emitted it, so the panel's hidden backing combo offers method 5 alone while
    the dialog offers both. Resolving that HERE — by producing a second view of the one
    spec — keeps the read/write path free of a "which host am I?" flag, which would
    otherwise have to be threaded through four functions and got wrong exactly once.
    """
    narrowed = spec.opts.get("panel_choices")
    if not narrowed:
        return spec
    opts = {k: v for k, v in spec.opts.items() if k != "panel_choices"}
    opts["choices"] = list(narrowed)
    return dataclasses.replace(spec, opts=opts)


def panel_table(table: Iterable[FieldSpec]) -> tuple[FieldSpec, ...]:
    """:func:`panel_variant` over a whole table."""
    return tuple(panel_variant(s) for s in table)


def model_types(model_cls) -> dict[str, str]:
    """Each model field's DECLARED type, by name, as a plain string.

    Two callers ask this and they mean the same question: the ``.dat`` converter
    table (``models/mesh_config_keys``) and the BL dialog's coercion sets
    (``_BL_INT_ATTRS`` / ``_BL_BOOL_ATTRS``). It was written out twice, which is the
    duplication this module exists to remove — and the two copies were not even
    identical, since only one normalised a non-string annotation.

    ``from __future__ import annotations`` makes every annotation a string, so the
    normalisation is for a model module that does NOT use it, where a real class
    object arrives instead. Returning the name rather than the class keeps callers
    comparing against ``"int"`` / ``"bool"``, which is what both already did.
    """
    out: dict[str, str] = {}
    for f in dataclasses.fields(model_cls):
        t = f.type
        out[f.name] = t if isinstance(t, str) else getattr(t, "__name__", str(t))
    return out


def preserved(model_cls, tables: Sequence[Iterable[FieldSpec]],
              extra_authored: Iterable[str] = ()) -> frozenset[str]:
    """Model fields the panel does NOT author — the set a panel→model sync must keep.

    A subtraction, not a list: the model's own fields, minus what the tables author,
    minus what the panel authors outside a table. Hand-listing this is how the
    solver's ``length_unit`` came to be one edit away from being wiped (and ``Linf``,
    i.e. the Reynolds number, with it).
    """
    names = {f.name for f in dataclasses.fields(model_cls)}
    return frozenset(names - authored(*tables) - set(extra_authored))
