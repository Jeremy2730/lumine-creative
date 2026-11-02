"""core/image_pipeline.py

Responsabilidad:
    - Encadenar una lista ordenada de ImageOperation y ejecutarlas sobre
      una imagen. Es atómico: si un paso falla, no se devuelve un
      resultado parcial.

No conoce:
    - Qué hace cada operación concreta ni de dónde viene la imagen.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from PIL import Image

from core.exceptions import DesignToolError, ProcessingError
from core.models import AppliedOperation
from core.operation import ImageOperation


@dataclass(frozen=True)
class PipelineResult:
    image: Image.Image
    applied: tuple[AppliedOperation, ...]


class ImagePipeline:
    """Ejecuta operaciones en orden. Agregar un paso = ``pipeline.add(op)``."""

    def __init__(self, operations: Iterable[ImageOperation] = ()) -> None:
        self._operations: list[ImageOperation] = list(operations)

    def add(self, operation: ImageOperation) -> "ImagePipeline":
        self._operations.append(operation)
        return self

    def __iter__(self) -> Iterator[ImageOperation]:
        return iter(self._operations)

    def __len__(self) -> int:
        return len(self._operations)

    def run(
        self,
        image: Image.Image,
        on_step: Callable[[ImageOperation], None] | None = None,
    ) -> PipelineResult:
        """Aplica todas las operaciones. Es atómico: si una falla, no hay resultado parcial."""
        applied: list[AppliedOperation] = []
        for operation in self._operations:
            if on_step is not None:
                on_step(operation)
            try:
                image = operation.apply(image)
            except DesignToolError:
                raise
            except Exception as exc:  # error técnico inesperado de una herramienta
                raise ProcessingError(
                    detail=f"Falló la operación '{operation.name}': {exc}"
                ) from exc
            applied.append(AppliedOperation(operation.name, operation.label))
        return PipelineResult(image=image, applied=tuple(applied))
