"""core/operation.py

Responsabilidad:
    - Definir el contrato ImageOperation (imagen -> imagen) que cumple
      toda herramienta encadenable en un pipeline.

No conoce:
    - GUI; ninguna herramienta concreta debe depender de nada fuera de
      este contrato para que el motor las pueda usar sin conocerlas.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from PIL import Image

from core.progress import ProgressReporter


class ImageOperation(ABC):
    """Operación pura: imagen entrada -> imagen salida.

    Las herramientas concretas (carpeta ``tools/``) heredan de aquí. El motor
    depende de esta abstracción, nunca de una herramienta concreta.
    """

    #: Identificador estable (se usa en el historial y en el registro de herramientas).
    name: ClassVar[str]

    @property
    def label(self) -> str:
        """Texto corto para mostrar en el historial de procesos."""
        return self.name

    @abstractmethod
    def apply(self, image: Image.Image) -> Image.Image:
        """Devuelve una NUEVA imagen; no debe mutar la de entrada."""

    def apply_with_progress(self, image: Image.Image, reporter: ProgressReporter) -> Image.Image:
        """Como ``apply`` pero pudiendo informar de su avance por etapas.

        Opcional: por defecto delega en ``apply`` sin reportar nada (la interfaz
        mostrará entonces la barra indeterminada). Las herramientas con etapas
        reales lo sobrescriben.
        """
        return self.apply(image)
