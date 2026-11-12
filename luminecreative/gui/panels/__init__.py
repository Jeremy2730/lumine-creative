"""gui/panels/__init__.py

Responsabilidad:
    - Exponer los paneles: ImagePanel, StatusPanel, ToolsPanel.
"""
from gui.panels.image_panel import ImagePanel
from gui.panels.status_panel import StatusPanel
from gui.panels.tools_panel import ToolsPanel

__all__ = ["ImagePanel", "StatusPanel", "ToolsPanel"]
