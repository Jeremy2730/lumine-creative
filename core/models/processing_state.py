"""core/models/processing_state.py

Responsabilidad:
    - Guardar el estado de trabajo actual: imagen actual, ruta de
      origen, historial de operaciones aplicadas y estado de
      procesamiento.
    - Entregar una vista inmutable (ImageSnapshot) a las capas superiores.

No conoce:
    - GUI ni algoritmos de imagen.

Notas:
    - Pensado para Deshacer/Rehacer: bastaría con guardar aquí una pila de
      (imagen, operaciones) en vez de una sola.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from PIL import Image

from core.exceptions import NoImageLoadedError


class ProcessingStatus(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"


@dataclass(frozen=True)
class AppliedOperation:
    """Registro de una operación ya aplicada."""

    name: str
    label: str


@dataclass(frozen=True)
class ImageSnapshot:
    """Vista inmutable del estado, pensada para entregar a capas superiores."""

    image: Image.Image
    source_path: Path | None
    operations: tuple[AppliedOperation, ...]
    status: ProcessingStatus

    @property
    def size(self) -> tuple[int, int]:
        return self.image.size

    @property
    def dpi(self) -> float | None:
        """Resolución (PPI) de los metadatos de la imagen, si existe."""
        value = self.image.info.get("dpi")
        if not value:
            return None
        return float(value[0])


@dataclass
class ProcessingState:
    """Estado mutable del motor (uso interno del ``DesignEngine``)."""

    source_path: Path | None = None
    current: Image.Image | None = None
    operations: list[AppliedOperation] = field(default_factory=list)
    status: ProcessingStatus = ProcessingStatus.IDLE

    @property
    def has_image(self) -> bool:
        return self.current is not None

    def load(self, path: Path, image: Image.Image) -> None:
        """Inicia una sesión de trabajo con una imagen nueva."""
        self.source_path = path
        self.current = image
        self.operations = []
        self.status = ProcessingStatus.IDLE

    def commit(self, image: Image.Image, applied: tuple[AppliedOperation, ...]) -> None:
        """Acepta el resultado de un procesamiento exitoso."""
        self.current = image
        self.operations.extend(applied)

    def snapshot(self) -> ImageSnapshot:
        if self.current is None:
            raise NoImageLoadedError()
        return ImageSnapshot(
            image=self.current,
            source_path=self.source_path,
            operations=tuple(self.operations),
            status=self.status,
        )
