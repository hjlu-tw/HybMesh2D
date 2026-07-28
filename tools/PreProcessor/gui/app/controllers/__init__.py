from app.controllers.session_ctrl import SessionControllerMixin
from app.controllers.session_io_ctrl import SessionIOControllerMixin
from app.controllers.segment_ctrl import SegmentControllerMixin
from app.controllers.segment_canvas_ctrl import SegmentCanvasControllerMixin
from app.controllers.segment_vertex_ctrl import SegmentVertexControllerMixin
from app.controllers.segment_autodetect_ctrl import SegmentAutoDetectControllerMixin
from app.controllers.segment_props_ctrl import SegmentPropsControllerMixin
from app.controllers.segment_distribution_ctrl import SegmentDistributionControllerMixin
from app.controllers.transform_ctrl import TransformControllerMixin
from app.controllers.transform_apply_ctrl import TransformApplyControllerMixin
from app.controllers.curve_ctrl import CurveControllerMixin
from app.controllers.curve_join_ctrl import CurveJoinControllerMixin
from app.controllers.curve_draw_ctrl import CurveDrawControllerMixin
from app.controllers.curve_edit_ctrl import CurveEditControllerMixin
from app.controllers.file_edit_ctrl import FileEditControllerMixin
from app.controllers.pending_edit_ctrl import PendingEditControllerMixin
from app.controllers.backend_ctrl import BackendControllerMixin
from app.controllers.mesh_gen_ctrl import MeshGenControllerMixin
from app.controllers.mesh_export_ctrl import MeshExportControllerMixin
from app.controllers.mesh_layers_ctrl import MeshLayersControllerMixin
from app.controllers.open_endpoint_ctrl import OpenEndpointControllerMixin
from app.controllers.solver_ctrl import SolverControllerMixin
from app.controllers.solver_bc_ctrl import SolverBcControllerMixin
from app.controllers.solver_tools_ctrl import SolverToolsControllerMixin
from app.controllers.postprocess_ctrl import PostprocessControllerMixin
from app.controllers.stl3d_ctrl import Stl3dControllerMixin
from app.controllers.stl3d_fit_ctrl import Stl3dFitControllerMixin
from app.controllers.session_load_ctrl import SessionLoadControllerMixin
from app.controllers.session_tabs_ctrl import SessionTabsControllerMixin
from app.controllers.extrude_ctrl import ExtrudeControllerMixin
from app.controllers.pipeline_ctrl import PipelineControllerMixin
from app.controllers.signal_wiring_ctrl import SignalWiringMixin
from app.controllers.lifecycle_ctrl import LifecycleControllerMixin

# Re-export aggregator: AppController composes these mixins. Listed in __all__
# so the re-exports are an explicit public API (and not flagged as unused).
__all__ = [
    "SessionControllerMixin", "SessionIOControllerMixin",
    "SegmentControllerMixin", "SegmentCanvasControllerMixin",
    "SegmentVertexControllerMixin",
    "SegmentAutoDetectControllerMixin",
    "SegmentPropsControllerMixin", "SegmentDistributionControllerMixin",
    "TransformControllerMixin", "TransformApplyControllerMixin",
    "CurveControllerMixin", "CurveJoinControllerMixin",
    "CurveDrawControllerMixin",
    "CurveEditControllerMixin", "FileEditControllerMixin",
    "PendingEditControllerMixin", "BackendControllerMixin",
    "MeshGenControllerMixin", "MeshExportControllerMixin",
    "MeshLayersControllerMixin", "OpenEndpointControllerMixin",
    "SolverControllerMixin", "SolverBcControllerMixin",
    "SolverToolsControllerMixin", "PostprocessControllerMixin",
    "Stl3dControllerMixin", "Stl3dFitControllerMixin",
    "SessionLoadControllerMixin", "SessionTabsControllerMixin",
    "ExtrudeControllerMixin",
    "PipelineControllerMixin",
    "SignalWiringMixin", "LifecycleControllerMixin",
]
