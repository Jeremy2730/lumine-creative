"""core/__init__.py

Responsabilidad:
    - Exponer DesignEngine, ImagePipeline, PipelineResult e ImageOperation:
      la API pública del motor de procesamiento.

No conoce:
    - GUI; nada en core/ importa CustomTkinter.
"""
from core.design_engine import DesignEngine
from core.image_pipeline import ImagePipeline, PipelineResult
from core.operation import ImageOperation

__all__ = ["DesignEngine", "ImagePipeline", "PipelineResult", "ImageOperation"]
