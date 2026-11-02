"""app/services/tool_registry.py

Responsabilidad:
    - Registrar herramientas (nombre -> fábrica de ImageOperation) para
      poder crearlas por nombre desde el servicio o la consola, sin que el
      motor conozca las clases concretas.

No conoce:
    - Los algoritmos de las herramientas; solo guarda cómo construirlas.
"""
from __future__ import annotations

from collections.abc import Callable

from core.exceptions import ProcessingError
from core.operation import ImageOperation

ToolFactory = Callable[..., ImageOperation]


class ToolRegistry:
    """Permite añadir herramientas sin tocar el servicio ni el motor."""

    def __init__(self) -> None:
        self._factories: dict[str, ToolFactory] = {}

    def register(self, name: str, factory: ToolFactory) -> None:
        self._factories[name] = factory

    def create(self, name: str, **params: object) -> ImageOperation:
        try:
            factory = self._factories[name]
        except KeyError:
            raise ProcessingError(
                user_message="❌ Herramienta no disponible.",
                detail=f"Herramienta no registrada: '{name}'",
            ) from None
        return factory(**params)

    def names(self) -> list[str]:
        return sorted(self._factories)
