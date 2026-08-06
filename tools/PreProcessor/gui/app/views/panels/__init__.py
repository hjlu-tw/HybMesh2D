from app.views.panels.file_panel import FilePanel
from app.views.panels.geometry_panel import GeometryPanel
from app.views.panels.vertex_panel import VertexPanel
from app.views.panels.geom_stats_panel import GeomStatsPanel
from app.views.panels.edge_list_panel import EdgeListPanel
from app.views.panels.edge_props_panel import EdgePropsPanel
from app.views.panels.advanced_panel import AdvancedPanel
from app.views.panels.actions_panel import ActionsPanel

# Re-export aggregator for the sidebar panels (explicit public API).
__all__ = [
    "FilePanel", "GeometryPanel", "VertexPanel", "EdgeListPanel",
    "GeomStatsPanel",
    "EdgePropsPanel", "AdvancedPanel", "ActionsPanel",
]
