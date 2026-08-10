"""One direction for stage configuration: panel edit → model.

Finding N8's architectural half. Each stage's settings existed twice — as widgets on a
panel and as a model the controller holds (``global_mesh_config`` and friends, referenced
about a hundred times) — and the model was only refreshed when the stage actually *ran*.
In between it lagged the panel, and every workaround for that lag was a separate partial
copy: ``_sync_global_scalars_from_panel`` copied everything except a hand-kept exclusion
set, ``handle_mesh_config_changed`` copied a *different* three fields, the solver model
was not refreshed at all, and dirty detection sidestepped the models by snapshotting
panels. One quantity, four sources of truth, each right about a different moment.

This module makes it one:

    user edits a widget  ->  sync_panel_to_model()  ->  the model is current
                                                    ->  everything downstream reads
                                                        the model and cannot be stale

The reverse direction already had its single funnel in ``push_panel_config``
(model → panel, undo-suppressed). Together they are the pair N8 asked for.

**Preserved fields are the crux.** A panel does not author every field of its model: the
solver panel has no widgets for the length unit, and the mesh panel none for ``bc_geom``.
Copying a freshly-read config wholesale would reset those to dataclass defaults — for the
length unit that means silently destroying ``Linf`` and with it the Reynolds number. So
the sync copies only what the panel authors, and the sets below say exactly what that is.
They are constants here (this runs on every edit; parsing sources at runtime would be
absurd) and ``tests/test_panel_model_sync.py`` proves each one equals what the panel's
``get_config`` actually assigns, by AST. A model field added later without a widget fails
that gate instead of silently going stale or silently being wiped.
"""
from __future__ import annotations

from app.services.logging_setup import get_logger

_log = get_logger(__name__)

#: ``panel attribute on MainWindow`` -> ``model attribute on the controller``.
PANEL_MODELS = (
    ("mesh_config_panel", "global_mesh_config"),
    ("solver_config_panel", "global_solver_config"),
    ("stl3d_config_panel", "global_stl3d_config"),
)

#: Model fields each panel does NOT author, and so must never overwrite.
#: Verified against the panels' own sources by tests/test_panel_model_sync.py.
PRESERVED_FIELDS = {
    # bc_geom: the geometry wall patch, owned by the per-geometry/segment BC dialogs
    #   and group_bc resolution, not by a panel field.
    # missing_geom_files: populated by load_from_file as a load diagnostic.
    "mesh_config_panel": frozenset({"bc_geom", "missing_geom_files"}),

    # length_unit / length_unit_metres: declared on the MESH panel; the solver panel
    #   only shows the derived Linf. Wiping these would take Linf with them.
    # grid_type / grid_data_format / bc_file_use_table / reorient_mesh /
    #   slice_to_simplex / solve_gcl: fixed for this workflow, no widget exists.
    # work_dir: staged per run by solver_case, not authored by the user.
    "solver_config_panel": frozenset({
        "length_unit", "length_unit_metres",
        "grid_type", "grid_data_format", "bc_file_use_table",
        "reorient_mesh", "slice_to_simplex", "solve_gcl",
        "work_dir",
    }),

    # The IB panel authors every field of its model.
    "stl3d_config_panel": frozenset(),
}


class PanelSyncControllerMixin:
    """Keeps each stage's model equal to its panel, continuously."""

    def sync_panel_to_model(self, panel_attr: str, extra_preserve=()) -> bool:
        """Copy the panel's authored fields into its model. Returns True if any changed.

        ``extra_preserve`` is for a caller that is itself mid-mutation of some field and
        must win over the panel for that one — the geometry-list operations do this.
        It is deliberately a separate argument rather than being folded into
        PRESERVED_FIELDS: "the panel cannot author this" and "I am busy owning this right
        now" are different claims, and merging them once already made the exclusion list
        look like ownership when it was not.
        """
        model_attr = dict(PANEL_MODELS).get(panel_attr)
        if model_attr is None:
            return False
        model = getattr(self, model_attr, None)
        panel = getattr(self.main_window, panel_attr, None)
        if model is None or panel is None:
            return False

        # Population in progress: reading the panel now would sample a half-filled
        # form and write it into the model — corruption, not staleness.
        #
        # The PANEL's own flag is checked first and is the one that matters. Relying on
        # the caller having used push_panel_config would make a forgotten funnel
        # catastrophic, when previously it cost only a spurious undo step; `set_config`
        # knows it is populating and cannot forget. The controller-side suppression flag
        # is checked too, because it also covers the panel-level `mesh_config_changed`
        # route into this method.
        if getattr(panel, "_loading", False):
            return False
        if getattr(self, "_suppress_project_undo", False):
            return False

        try:
            live = panel.get_config()
        except (AttributeError, ValueError, TypeError, RuntimeError):
            # Reading a panel must never break the edit the user just made. Logged at
            # warning because a config that cannot be read means later stages will run
            # on stale values — a silent degradation of what the user asked for.
            _log.warning("could not read %s; its model stays stale", panel_attr,
                         exc_info=True)
            return False

        preserve = PRESERVED_FIELDS.get(panel_attr, frozenset()) | frozenset(
            extra_preserve)
        changed = False
        for key, val in vars(live).items():
            if key in preserve:
                continue
            if getattr(model, key, None) != val:
                changed = True
            setattr(model, key, val)

        # Let the model restore its own invariants. A sync can otherwise leave a
        # derived field disagreeing with a preserved one — the solver's Linf has a
        # widget while the length unit it is derived FROM does not — producing an
        # inconsistency the sync itself created.
        normalize = getattr(model, "normalize", None)
        if callable(normalize):
            normalize()
        return changed

    def sync_panels_to_models(self) -> None:
        """Refresh every stage model from its panel.

        Used before an action that reads several models at once (saving a workspace or
        a pipeline script), so what gets written is what is on screen.
        """
        for panel_attr, _model_attr in PANEL_MODELS:
            self.sync_panel_to_model(panel_attr)

    def push_models_to_panels(self) -> None:
        """Seed every stage panel from its model. Call once, at startup.

        A panel is built with whatever Qt leaves in an un-set widget — 0, or the
        range floor — not with its model's defaults, and until the user first
        entered that stage nothing populated it. That was harmless while the
        models were only refreshed when a stage ran; it stopped being harmless
        the moment the sync above made the panel authoritative, because the
        startup baseline reads every panel back into its model. An un-populated
        panel then *becomes* the defaults: BL layers 0 (no boundary layer grown
        at all), growth 1.001, Gmsh MeshAdapt, the outer BCs all inlet.

        So the pair needs a starting point, and it has to be model → panel:
        the dataclass defaults are the ones written down, reviewed and shared
        with Config.hpp.
        """
        # One suppression around the WHOLE loop, not one per push: each
        # push_panel_config ends by re-reading every panel (to re-baseline the undo
        # recorder), and mid-loop that would read the panels this loop has not
        # reached yet — seeding the Mesh panel would clobber the solver model with
        # the untouched solver panel. Nesting keeps that read for the outer exit,
        # by which point all three panels hold their models' values.
        with self.suppress_project_undo():
            for panel_attr, model_attr in PANEL_MODELS:
                panel = getattr(self.main_window, panel_attr, None)
                model = getattr(self, model_attr, None)
                if panel is not None and model is not None:
                    self.push_panel_config(panel, model)

    def on_panel_edited(self, panel_attr: str) -> None:
        """A stage panel was edited by the user.

        Order matters: the model is updated FIRST, then the undo snapshot is scheduled.
        A snapshot is meant to record the state after the edit, and anything the
        recorder or a listener reads from the model must already be current.
        """
        self.sync_panel_to_model(panel_attr)
        if hasattr(self, "schedule_project_snapshot"):
            self.schedule_project_snapshot()
