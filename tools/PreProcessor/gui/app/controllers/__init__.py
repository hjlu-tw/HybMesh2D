from app.controllers.session_ctrl import SessionControllerMixin
from app.controllers.session_io_ctrl import SessionIOControllerMixin
from app.controllers.segment_ctrl import SegmentControllerMixin
from app.controllers.segment_vertex_ctrl import SegmentVertexControllerMixin
from app.controllers.segment_autodetect_ctrl import SegmentAutoDetectControllerMixin
from app.controllers.segment_props_ctrl import SegmentPropsControllerMixin
from app.controllers.segment_distribution_ctrl import SegmentDistributionControllerMixin
from app.controllers.transform_ctrl import TransformControllerMixin
from app.controllers.curve_ctrl import CurveControllerMixin
from app.controllers.curve_edit_ctrl import CurveEditControllerMixin
from app.controllers.backend_ctrl import BackendControllerMixin
from app.controllers.mesh_gen_ctrl import MeshGenControllerMixin
from app.controllers.mesh_export_ctrl import MeshExportControllerMixin
from app.controllers.mesh_layers_ctrl import MeshLayersControllerMixin
from app.controllers.open_endpoint_ctrl import OpenEndpointControllerMixin
from app.controllers.solver_ctrl import SolverControllerMixin
from app.controllers.postprocess_ctrl import PostprocessControllerMixin
from app.controllers.stl3d_ctrl import Stl3dControllerMixin
from app.controllers.extrude_ctrl import ExtrudeControllerMixin
from app.controllers.pipeline_ctrl import PipelineControllerMixin

# Re-export aggregator: AppController composes these mixins. Listed in __all__
# so the re-exports are an explicit public API (and not flagged as unused).
__all__ = [
    "SessionControllerMixin", "SessionIOControllerMixin",
    "SegmentControllerMixin", "SegmentVertexControllerMixin",
    "SegmentAutoDetectControllerMixin",
    "SegmentPropsControllerMixin", "SegmentDistributionControllerMixin",
    "TransformControllerMixin", "CurveControllerMixin",
    "CurveEditControllerMixin", "BackendControllerMixin",
    "MeshGenControllerMixin", "MeshExportControllerMixin",
    "MeshLayersControllerMixin", "OpenEndpointControllerMixin",
    "SolverControllerMixin", "PostprocessControllerMixin",
    "Stl3dControllerMixin", "ExtrudeControllerMixin",
    "PipelineControllerMixin",
]
