"""app/services/processing_service.py

Responsabilidad:
    - Coordinar el motor (DesignEngine) y el registro de herramientas
      (ToolRegistry) para los casos de uso: abrir, aplicar una herramienta,
      ejecutar un pipeline de varios pasos y guardar el resultado.

No conoce:
    - Algoritmos concretos de imagen (los crea el registro); GUI ni threads.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from app.services.tool_registry import ToolRegistry
from core.design_engine import DesignEngine
from core.image_pipeline import ImagePipeline
from core.models import ImageSnapshot
from core.operation import ImageOperation


class ProcessingService:
    """API de casos de uso: abrir, aplicar herramientas, ejecutar pipelines, guardar."""

    def __init__(self, engine: DesignEngine, registry: ToolRegistry, output_dir: Path) -> None:
        self._engine = engine
        self._registry = registry
        self._output_dir = Path(output_dir)

    @property
    def has_image(self) -> bool:
        return self._engine.has_image

    def snapshot(self) -> ImageSnapshot:
        return self._engine.snapshot()

    def open_image(self, path: Path) -> ImageSnapshot:
        return self._engine.open_image(path)

    def apply_tool(self, name: str, **params: object) -> ImageSnapshot:
        """Crea la herramienta registrada como ``name`` y la aplica (acumulativo)."""
        return self._engine.apply(self._registry.create(name, **params))

    def run_pipeline(
        self,
        steps: Sequence[tuple[str, dict[str, object]]],
        on_step: Callable[[ImageOperation], None] | None = None,
    ) -> ImageSnapshot:
        """Ejecuta varios pasos ``(nombre, parámetros)`` en orden."""
        pipeline = ImagePipeline(self._registry.create(name, **params) for name, params in steps)
        return self._engine.run_pipeline(pipeline, on_step=on_step)

    def save_result(self) -> Path:
        return self._engine.save(self._output_dir)
